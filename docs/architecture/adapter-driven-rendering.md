# Adapter-Driven Rendering

**Date:** 2026-04-27
**Status:** Active. The architectural fix for the historic Qwen system-message bug.
**Code:** `src/brio_ext/renderer.py` (`TEMPLATE_PROVIDERS` / `PROMPT_PROVIDERS` split, `render_for_model`), `src/brio_ext/adapters/*` (per-format adapters), `src/brio_ext/registry.py` (selection).

## What

The library cleanly splits two responsibilities that look related but should not be coupled:

- **Transport** — how to talk to a provider over HTTP (auth, retries, request/response shape, streaming protocol). Lives in `src/esperanto/providers/llm/*` and `src/brio_ext/providers/*`.
- **Rendering** — how to turn a list of `{role, content}` messages into the prompt string a particular *model family* expects (ChatML for Qwen/Phi, `[INST]` for Llama, `<s>[INST]` for Mistral, etc.). Lives in `src/brio_ext/adapters/*`.

A *provider* (the OpenAI HTTP client, the llamacpp HTTP client) doesn't know what ChatML is. An *adapter* doesn't know what an Authorization header is. The renderer dispatches between them.

## Why the split exists

The motivating bug: **Qwen 2.5 7B Instruct, served via llama.cpp's `/v1/chat/completions` endpoint, ignored system messages.** When BrioDocs sent a 22K-character system prompt with patent inventor names plus a user question "Who are the inventors?", the model returned "I don't have information about which specific patent you're referring to." GPT-4o-mini given the same prompt returned the correct answer.

The full repro and resolution narrative live in [`docs/llama_cpp_test_specification.md`](../llama_cpp_test_specification.md). The *architectural* fix — and the one this doc describes — is the split that prevents that class of bug from recurring.

The earlier design only had providers. Each provider used the corresponding `/v1/chat/completions`-style endpoint. For Qwen specifically, llama.cpp's chat-completion endpoint applied a chat template that did not preserve system messages correctly. There was nowhere in the library to *override* that templating without forking the provider.

The fix moves the templating decision out of the provider entirely. For local models, brio_ext renders the chat template itself (`<|im_start|>system\n...\n<|im_end|>\n<|im_start|>user\n...`) and sends the result to llama.cpp's *raw* `/v1/completions` endpoint, which doesn't apply any template of its own. The system message reaches the model exactly as we wrote it.

For cloud models, this isn't necessary — OpenAI, Anthropic, Groq etc. handle their own templating reliably. Their providers continue to use the chat-completions endpoint with messages passed through unchanged.

## Two render modes

The renderer produces one of two payload shapes:

| Mode | Output | Provider receives | Endpoint |
|---|---|---|---|
| `messages` | `{"messages": [...], "stop": [...]}` | List of `{role, content}` dicts unchanged | Provider's chat endpoint (`/v1/chat/completions`) |
| `prompt` | `{"prompt": "...", "stop": [...]}` | Pre-rendered raw prompt string | Provider's completion endpoint (`/v1/completions`) |

The mode is determined by the provider, not the adapter. An adapter knows how to render *both* modes if needed — but the renderer only calls `adapter.render()` for prompt-mode providers. For message-mode providers, it passes the messages through.

## Dispatch logic

`render_for_model` (in `src/brio_ext/renderer.py`) uses two sets to decide:

```python
TEMPLATE_PROVIDERS = {"openai", "anthropic", "grok", "ollama"}
PROMPT_PROVIDERS = {"llamacpp", "hf_local"}
```

Three branches:

1. **Adapter found AND provider in `PROMPT_PROVIDERS`** → call `adapter.render(messages)` and return `{"prompt": ..., "stop": ...}`. Used for local llama.cpp and HuggingFace Transformers backends.
2. **Provider in `TEMPLATE_PROVIDERS` (or no adapter found)** → return `{"messages": messages, "stop": []}`. The cloud provider's chat endpoint handles templating.
3. **Adapter found but provider in neither set** → fallback: still call `adapter.render(messages)` and return prompt-mode. Defensive default for unknown provider strings; gives the explicit-control path priority.

Set `BRIO_DEBUG=1` to see which branch fired and what payload was sent.

## What providers know

Providers (`OpenAILanguageModel`, `LlamaCppLanguageModel`, etc.) are responsible for:

- HTTP plumbing — building the request, sending it, handling errors, retrying.
- Authentication — API key headers, Bearer tokens, OAuth where applicable.
- Endpoint selection — `/v1/chat/completions` vs. `/v1/completions` vs. anything provider-specific.
- Response normalization — converting vendor-specific JSON into Esperanto's standard `ChatCompletion` / `Message` / `Usage` / `Timings` shape.
- Streaming protocol — SSE parsing, chunk emission.

Providers do **not** know:
- What chat template a particular model uses.
- That the response will be re-fenced in `<out>...</out>` later.
- What `<|im_start|>` or `[INST]` mean.

This means a new provider can be added without touching adapters, and a new model family can be supported (via a new adapter) without touching providers.

## What adapters know

Adapters (`QwenAdapter`, `LlamaAdapter`, `MistralAdapter`, `Gemma4Adapter`, `PhiAdapter`) are responsible for:

- The model family's chat-template syntax — special tokens, role markers, turn boundaries.
- Which model identifiers belong to this family (`can_handle(model_id)`).
- The model-specific stop tokens that should terminate generation (`<|im_end|>` for ChatML, etc.).
- Optional flags like `no_think` that prepend a directive to the first user message.
- A `clean_response()` helper that strips the family's format markers from generated text before fencing.

Adapters do **not** know:
- What HTTP endpoint will be called.
- What provider will run the prompt.
- How `<out>...</out>` fencing is applied (that happens after generation, in `_ensure_fence`).

The adapter API surface is `can_handle`, `render`, `clean_response` — and that's it.

## Selection

When `BrioAIFactory.create_language(provider, model_name, config)` runs, the renderer needs an adapter. `get_adapter()` in `src/brio_ext/registry.py` resolves it in this order:

1. **Pattern match on `model_id`** — iterate `ADAPTERS`; the first adapter whose `can_handle(model_id)` returns `True` wins. Pattern matching takes priority over the format hint so a `phi-4-mini` model with `chat_format="chatml"` still uses `PhiAdapter`, not the more general `QwenAdapter`.
2. **Format-string fallback** — if no adapter pattern-matched and the caller passed `config={"chat_format": "..."}`, map the format string to an adapter (`"chatml"` → `QwenAdapter`, `"llama"` → `LlamaAdapter`, etc.).
3. **No match** — return `None`. The renderer then falls back to message-mode passthrough (silently — not an exception). Use the format-string hint when integrating with custom-named models from BrioDocs's model database.

## Adding a new provider

To add `newprovider` to the cloud-provider set:

1. Implement `NewProviderLanguageModel` in `src/esperanto/providers/llm/newprovider.py` — see [`docs/2025-12-20_Developer_Guide.md`](../2025-12-20_Developer_Guide.md) Adding a New Provider.
2. Register it in `_provider_modules["language"]` in `src/esperanto/factory.py` (and optionally `_LANGUAGE_OVERRIDES` in `src/brio_ext/factory.py` for prompt-mode local providers).
3. Add `"newprovider"` to `TEMPLATE_PROVIDERS` in `src/brio_ext/renderer.py` if it handles its own chat templating, or `PROMPT_PROVIDERS` if it expects pre-rendered prompts and should run through an adapter.

Skipping step 3 means the renderer falls into the "no match" branch and message-mode passthrough — which is correct for most new cloud providers, but if you specifically want adapter-rendered prompts, you must opt in.

## Adding a new adapter

To add support for a new model family (e.g., a new chat-template format):

1. Implement `NewFamilyAdapter` in `src/brio_ext/adapters/newfamily_adapter.py` with `can_handle`, `render`, and `clean_response`.
2. Add the instance to `ADAPTERS` in `src/brio_ext/registry.py`.
3. If callers should be able to specify `chat_format="newfamily"` explicitly, extend `_get_adapter_by_format` in the same file.

The adapter will be picked up automatically by any provider in `PROMPT_PROVIDERS`. No changes to providers or the renderer are needed.

## Why this is "an architecture," not just code organization

The split is enforced by two structural choices:

1. **Adapters live in `brio_ext`, not `esperanto`.** Core esperanto providers (which can be used standalone, without brio_ext) never see adapters. This means cloud-only consumers of `esperanto.AIFactory` get exactly the upstream behavior with no magic, and adapter logic can evolve without touching upstream-relevant code.
2. **The renderer is the only place that knows about both.** Providers don't import adapters; adapters don't import providers. `render_for_model` is the single dispatch point. Adding a feature that crosses the boundary (e.g., per-provider stop-token handling) goes through the renderer or fails to compile.

This makes "is this thing a transport concern or a rendering concern?" a structural question instead of a code-review question.

## Related

- `[[chat-adapter-system]]` — the adapter registry and selection mechanics in detail.
- `[[chat-completion-pipeline]]` — where this dispatch sits in the full request flow (render → call → fence).
- `[[fencing-contract]]` — the post-generation step that wraps the response; complements rendering by handling the consumer-facing shape.
- `[[no-think-mode]]` — an adapter-level flag that demonstrates why these belong on adapters, not providers.
- `[[llamacpp-local-provider]]` — the prompt-mode provider that motivated the split.
