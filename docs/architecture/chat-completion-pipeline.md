# Chat Completion Pipeline

**Date:** 2026-04-27
**Status:** Active. End-to-end view of a `chat_complete` call through `BrioAIFactory`.
**Code:** `BrioAIFactory.create_language` + `_wrap_language_model` + `_ensure_fenced_completion` + `_stop_config_guard` (`src/brio_ext/factory.py`), `render_for_model` (`src/brio_ext/renderer.py`), `_import_provider_class` (`src/esperanto/factory.py`).

## What

A single `chat_complete` call passes through five distinct stages: **registry lookup** (provider class), **wrap** (adapter dispatch attached to the model), **render** (messages or prompt payload), **call** (provider HTTP), **fence** (response wrapped in `<out>...</out>`), with metrics logging on the side.

This document is the capstone for the architecture set: it names each stage, shows the call sequence end-to-end, and points to the doc that owns each piece in detail. Use this when you need to reason about the *whole* request flow; use the per-stage docs when you need depth on one piece.

## The pipeline

```
BrioAIFactory.create_language(provider, model_name, config)         ┐
   ├─ AIFactory._import_provider_class("language", provider)        │  one-time
   ├─ provider_class(model_name, config)                            │  setup
   └─ _wrap_language_model(model, model_name, provider, chat_format)│  per model
        ├─ get_adapter(model_id, chat_format)                       │
        └─ replace .chat_complete / .achat_complete on the instance ┘

# Returned model — the caller now holds a wrapped instance.

model.chat_complete(messages, stream=None, no_think=False)          ┐
  ├─ render_for_model(model_id, messages, provider, chat_format,    │
  │                   no_think)                                     │
  │       └─ either {"messages": [...], "stop": [...]} (chat mode)  │
  │              or  {"prompt": "...", "stop": [...]}  (prompt mode)│  per request
  ├─ _stop_config_guard(self, stops)                                │
  │       ├─ original_chat(rendered["messages"], stream=...)        │
  │       │     OR self.prompt_complete(rendered["prompt"], ...)    │
  │       └─ provider issues HTTP, returns ChatCompletion           │
  ├─ _ensure_fenced_completion(result, adapter)                     │
  └─ _log_completion_metrics(...)         (non-streaming only)      ┘
```

## Stage 1: Registry lookup

`AIFactory._import_provider_class("language", provider)` is called once per `create_language`. It looks up the `(service_type, provider)` key in `_provider_modules`, gets a `"module:class"` string, lazily imports the module, and returns the class. See [`[[provider-registry-pattern]]`](provider-registry.md) for the full pattern, including why string-based lookup matters (lazy imports of optional heavy deps), how `BrioAIFactory` extends the registry (`deepcopy` + override for `llamacpp`/`hf_local`), and what `register_with_factory` does and doesn't do.

The class is instantiated immediately with `model_name=...` and `config=config or {}`. After this stage, you have a bare provider model — the kind you'd get from upstream `esperanto.AIFactory`.

## Stage 2: Wrap (adapter attached, methods replaced)

`_wrap_language_model` does the brio_ext-specific wiring on top of the bare provider model:

1. **Idempotency check.** If `model._brio_wrapped` is already True (because `_wrap_language_model` ran on this instance before), return immediately. Wrapping twice would chain the rendering+fencing — which would corrupt the `<out>` contract.
2. **Save originals.** `original_chat = model.chat_complete`, `original_achat = model.achat_complete`. The closures defined next will call these inside their own logic.
3. **Resolve the adapter.** `adapter = get_adapter(model_id, chat_format=chat_format)`. The adapter is captured in the closure — it's used at *response time* to clean format markers before fencing. (The same adapter is also looked up again inside `render_for_model` for the prompt-rendering call. Two lookups, one cached resolution per call site; cheap.)
4. **Replace methods.** New `chat_complete` and `achat_complete` closures are bound to the instance via `types.MethodType`. The closures hold `original_chat`, `adapter`, `model_id`, `provider`, `chat_format`, and `_LANGUAGE_OVERRIDES`-style metadata.
5. **Mark wrapped + attach `to_langchain`.** `_brio_wrapped = True`, plus `to_langchain = lambda: BrioBaseChatModel(brio_model=model)`.

After this stage, the caller holds a model whose `.chat_complete` is brio_ext's closure, not the provider's bare implementation.

## Stage 3: Render

When the caller invokes `model.chat_complete(messages, ...)`, the closure calls `render_for_model(model_id, messages, provider, chat_format=chat_format, no_think=no_think)`.

The renderer returns either:

- `{"messages": [...], "stop": [...]}` — chat mode, used for cloud providers (`TEMPLATE_PROVIDERS`).
- `{"prompt": "...", "stop": [...]}` — prompt mode, used for local providers (`PROMPT_PROVIDERS`).

The two modes route to different provider methods in stage 4. See [`[[adapter-driven-rendering]]`](adapter-driven-rendering.md) for the dispatch logic, the `TEMPLATE_PROVIDERS` / `PROMPT_PROVIDERS` sets, and the model_id → chat_format → no-match resolution chain.

The `no_think` flag, when True, prepends `/no_think` to the first user message inside the adapter's `render()`. Used for Qwen3/Qwen3.5 on Tier 2/3 where the token budget can't fit a full reasoning block plus an answer. (Will be covered in detail by `[[no-think-mode]]` once authored.)

## Stage 4: Call (with stop-token guard)

The closure issues the HTTP call to the provider, but first wraps it in `_stop_config_guard`:

```python
with _stop_config_guard(self, stops):
    if "messages" in rendered:
        result = original_chat(rendered["messages"], stream=stream)
    else:
        result = self.prompt_complete(rendered["prompt"], stop=stops, stream=stream)
```

`_stop_config_guard` is a tiny context manager that:
1. Saves the current value of `self._config["stop"]` (or marks it as "missing").
2. Sets `self._config["stop"] = stops` (the adapter's model-specific stops, e.g., `["<|im_end|>"]` for ChatML).
3. On exit, restores the previous value, or removes the key if it wasn't there to begin with.

Why a context manager? The provider's `chat_complete` reads `self._config` to build the request payload. Setting `_config["stop"]` permanently would bleed across calls. Setting it via a request parameter would require modifying every provider's signature. The guard is the smallest invasive change: it scopes the override to one HTTP call, then unwinds.

For prompt-mode providers (`llamacpp`, `hf_local`), the closure calls `self.prompt_complete(prompt, stop=stops, stream=...)` instead — a prompt-mode method on the local provider that hits `/v1/completions` directly. If neither method is callable on the provider, the closure raises `RuntimeError`, since something is mis-configured.

The async path (`achat_complete`) mirrors the sync version with `await` and falls back to the sync `prompt_complete` if no async variant exists on the provider — degrading gracefully rather than failing.

## Stage 5: Fence

Whatever the provider returns (a `ChatCompletion` for non-streaming, a generator/async-iterator for streaming) goes through `_ensure_fenced_completion(result, adapter)` before returning to the caller.

For non-streaming: every choice's `message.content` is run through `_ensure_fence`, which strips adapter-specific format markers, strips trailing incomplete special tokens (handling `max_tokens` truncation mid-token), strips any LLM-emitted `<out>` tags, and re-fences in canonical `<out>\n{content}\n</out>`.

For streaming: a separate path wraps the chunk stream with `StreamingFenceFilter` (and `StreamingThinkTagFilter` for reasoning models). The first non-empty chunk emits `<out>\n`, intermediate chunks pass through, and the final emits `\n</out>`.

See [`[[fencing-contract]]`](fencing-contract.md) for the six-step `_ensure_fence` algorithm, edge cases, and the streaming-path details.

## Side stage: Metrics logging

For non-streaming responses, after fencing:

```python
if isinstance(fenced, ChatCompletion):
    _log_completion_metrics(fenced, model_id, provider, tier_id, tier_label, context_size, request_time_ms)
```

`_log_completion_metrics` is a no-op unless `_metrics_enabled` is True (set via the `BRIO_METRICS_ENABLED` env var or the `enable_metrics()` runtime call). When active, it appends a JSONL record with timings, usage, and tier metadata. See [`[[performance-metrics]]`](../2025-12-08%20Performance%20Metrics%20Implementation.md) for the data model and the platform-aware path resolution.

Streaming responses do not log automatically. TTFT can be captured by the consumer if needed (record `time.perf_counter()` before the loop and at the first chunk).

## What this pipeline does NOT cover

- **Tool calls.** `tool_calls` and `function_call` on `Message` are passed through unchanged at the fence stage. The pipeline doesn't translate tool schemas across providers; that's the caller's responsibility (or a future enhancement).
- **Provider-specific extensions.** Things like Perplexity's `search_domain_filter` or Azure's deployment-name routing live entirely in their providers; the pipeline doesn't see them.
- **Retries.** No retry layer — the underlying `httpx` clients can raise; the wrapper re-raises. Consumers that need retry implement it at the call site.
- **Caching.** No response caching. Each call goes to the provider.

## Why this is "a pipeline" and not just "a function"

Each stage has a specific responsibility, owns its own doc, and can be tested in isolation:

| Stage | Owner doc |
|---|---|
| Registry lookup | [`[[provider-registry-pattern]]`](provider-registry.md) |
| Wrap (adapter dispatch) | [`[[chat-adapter-system]]`](../_inventories/brio-esperanto.md) |
| Render | [`[[adapter-driven-rendering]]`](adapter-driven-rendering.md) |
| Call (provider HTTP) | provider-specific docs (`docs/llm.md`, `docs/llama_cpp_test_specification.md`) |
| Fence | [`[[fencing-contract]]`](fencing-contract.md) |
| Metrics | [`docs/2025-12-08 Performance Metrics Implementation.md`](../2025-12-08%20Performance%20Metrics%20Implementation.md) |

The pipeline is the *composition*. Each stage stays single-purpose, the boundaries are explicit, and a change in one stage does not require touching another unless the contract between them changes.

## Related

- `[[provider-registry-pattern]]` — stage 1.
- `[[adapter-driven-rendering]]` — stage 3.
- `[[fencing-contract]]` — stage 5.
- `[[streaming-completion-flow]]` — variant of stages 4–5 for streaming.
- `[[langchain-bridge-flow]]` — what runs *after* this pipeline when the caller used `to_langchain()`.
- `[[chat-adapter-system]]` — the adapter resolution that's used in stages 2 and 3.
- `[[performance-metrics]]` — the side-stage logger.
