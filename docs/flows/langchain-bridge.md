# LangChain Bridge Flow

**Date:** 2026-04-27
**Status:** Active.
**Code:** `src/brio_ext/langchain_wrapper.py` (`BrioBaseChatModel`, legacy `BrioLangChainWrapper`, module-level `_parse_fenced_content`), `model.to_langchain()` attachment in `_wrap_language_model` (`src/brio_ext/factory.py`), `create_langchain_wrapper` factory helper (same file).

## What

Brio_ext exposes a LangChain/LangGraph-compatible bridge that wraps any model produced by `BrioAIFactory`. The bridge runs the [`[[chat-completion-pipeline]]`](../architecture/chat-completion-pipeline.md) (so adapter dispatch, fencing, and metrics all happen as usual), then strips the `<out>...</out>` fence and `<think>...</think>` blocks before returning a clean `AIMessage` to LangChain.

There are two implementation classes — `BrioBaseChatModel` (recommended) and the legacy `BrioLangChainWrapper`. Three entry points instantiate one of them. This document explains which to use when and how `no_think` threads through.

## Two implementation classes

| | `BrioBaseChatModel` (recommended) | `BrioLangChainWrapper` (legacy) |
|---|---|---|
| Base class | `BaseChatModel` (LangChain) | plain Python class |
| LangGraph callbacks | ✅ Yes (`on_chat_model_start`, `on_llm_new_token`, `on_llm_end`) | ❌ No |
| `stream_mode="messages"` | ✅ Supported via proper `_stream` / `_astream` | ❌ `stream()` raises `NotImplementedError` |
| Streaming behavior | True token-by-token via `StreamingFenceFilter` + `StreamingThinkTagFilter` | `astream()` yields the full response as a single chunk |
| Returns | `ChatResult` containing `AIMessage` | custom `_AIMessage` subclass |
| Fence parsing | Module-level `_parse_fenced_content` (shared) | Instance method (older copy) |
| Input string heuristic | None — caller passes structured messages | Treats strings starting with "you are a" / "# system" / etc. as system messages |
| Active development | Yes | Frozen — kept for back-compat |

**Use `BrioBaseChatModel` for new code.** `BrioLangChainWrapper` exists because some pre-LangGraph call sites haven't migrated. Don't add features to it.

## Three entry points

All three end up returning a `BrioBaseChatModel`:

```python
# 1. Lightweight default — attached to every wrapped model in _wrap_language_model
model = BrioAIFactory.create_language("llamacpp", "qwen2.5-7b-instruct", config={...})
lc_model = model.to_langchain()
# Equivalent to BrioBaseChatModel(brio_model=model)
# no_think defaults to False

# 2. With no_think — use create_langchain_wrapper
from brio_ext.factory import create_langchain_wrapper
lc_model = create_langchain_wrapper(model, no_think=True)

# 3. Direct construction — full constructor access
from brio_ext.langchain_wrapper import BrioBaseChatModel
lc_model = BrioBaseChatModel(brio_model=model, no_think=True)
```

`BrioLangChainWrapper` is constructed only via direct import — it's not exposed by either factory helper.

## What the bridge does on each call

### `invoke` / `ainvoke` (non-streaming)

```
LangChain caller passes List[BaseMessage] or str
        │
        ▼
BrioBaseChatModel._generate / _agenerate
        │
        │  _convert_messages: LangChain types → {role, content} dicts
        │   (HumanMessage → "user", SystemMessage → "system", AIMessage → "assistant")
        │
        ▼
brio_model.chat_complete(messages, stream=False, no_think=self.no_think)
        │
        │  Runs the full chat-completion pipeline (registry → wrap → render → call → fence)
        │  Result is a ChatCompletion with content="<out>\n{...}\n</out>"
        │
        ▼
_build_chat_result
        │
        │  _parse_fenced_content extracts inner content from the fence
        │  and strips <think>...</think> blocks
        │
        ▼
ChatResult(generations=[ChatGeneration(message=AIMessage(content=...))])
```

The caller sees a clean `AIMessage` — no `<out>` tags, no `<think>` blocks, no model-specific format markers.

### `_stream` / `_astream` (true token streaming)

```
LangChain caller invokes .stream() or .astream()
        │
        ▼
BrioBaseChatModel._stream / _astream
        │
        │  _convert_messages
        │
        ▼
brio_model.chat_complete(messages, stream=True, no_think=self.no_think)
        │
        │  Runs stages 1–4 of the pipeline; stage 5 (fencing) is skipped for streams
        │  Returns an iterator/async iterator of ChatCompletionChunk
        │
        ▼
fence_filter = StreamingFenceFilter()
think_filter = StreamingThinkTagFilter()

for chunk in stream_response:
    token = chunk.choices[0].delta.content
    defenced = fence_filter.process(token)         # strip <out>...</out> if present
    filtered = think_filter.process(defenced)      # suppress <think>...</think>
    yield ChatGenerationChunk(message=AIMessageChunk(content=filtered))

# Drain both filters
remaining = think_filter.process(fence_filter.flush())
remaining += think_filter.flush()
if remaining:
    yield ChatGenerationChunk(message=AIMessageChunk(content=remaining))
```

The fence-strip is consumer-side because brio_ext doesn't add fences to streams — see [`[[streaming-completion-flow]]`](streaming-completion.md) for the asymmetry. The bridge composes the two filters in order: fence first (the fence may surround the think tags), think second.

The `run_manager.on_llm_new_token` callback fires for each filtered chunk, giving LangGraph's streaming callbacks the per-token resolution they expect. This is why `BrioBaseChatModel` extends `BaseChatModel` rather than just being a plain Python class — the callback wiring is the whole point.

## How `no_think` threads through

`no_think` is a Qwen3/Qwen3.5-specific flag that prepends `/no_think` to the first user message, disabling the model's reasoning channel. Used on Tier 2/3 where the token budget can't fit a full reasoning block plus an answer. Models without thinking mode ignore the directive.

```
caller passes no_think=True via create_langchain_wrapper or BrioBaseChatModel(...)
        │
        ▼
BrioBaseChatModel._generate / _astream
        │
        │  Passes no_think=self.no_think through to chat_complete
        │
        ▼
brio_model.chat_complete(messages, stream=..., no_think=True)
        │
        │  brio_ext's chat_complete closure calls render_for_model(..., no_think=True)
        │
        ▼
adapter.render(messages, no_think=True)
        │
        │  QwenAdapter prepends "/no_think " to the first user message's content
        │  Other adapters honor the parameter signature but typically ignore the value
```

The default path `model.to_langchain()` does NOT accept `no_think` — it always produces `no_think=False`. To get `no_think=True` you must use `create_langchain_wrapper(model, no_think=True)` or `BrioBaseChatModel(brio_model=model, no_think=True)` directly. `[[no-think-mode]]` (when authored) will cover the parameter's semantics in detail.

## `_parse_fenced_content`: the shared helper

Lives at module scope in `src/brio_ext/langchain_wrapper.py` (line 481). Used by `BrioBaseChatModel._build_chat_result`. The legacy `BrioLangChainWrapper` has its own instance-method copy with the same logic.

The helper handles four cases for fence + think interaction:

1. **Normal case.** Content has `<out>...</out>` (or `<output>...</output>`). Extract inner content. Remove complete `<think>...</think>` blocks. Strip stray closing tags (`</think>`, `</assistant>`, `<|im_end|>`, `<|end|>`) that some models emit without openers. Return cleaned content.
2. **Unclosed `<think>`.** Model hit `max_tokens` mid-reasoning, so `</think>` was never emitted. Strip from `<think>` to end-of-string — never leak internal reasoning to the user.
3. **All-think output.** Reasoning fit entirely in `<think>` tags, with no answer outside. (Common when budget is too tight.) Try to find a JSON object inside the thinking content; return it if found, otherwise return the raw thinking content as a fallback. Logs a warning.
4. **Empty after cleaning, but `<think>` was present unclosed.** Return empty string with a warning, rather than leaking partial reasoning.

These cases exist because reasoning models (Qwen3/Qwen3.5, Phi-4 Reasoning) can fail in surprising ways under tight token budgets, and the bridge is the place where "what does the consumer actually see" gets decided.

## Streaming with `BrioLangChainWrapper` (legacy)

`BrioLangChainWrapper.stream()` raises `NotImplementedError`. `astream()` does exist but yields the full response as a single chunk after running `ainvoke()` synchronously — no token-by-token streaming. For real streaming, use `BrioBaseChatModel`.

This is a deliberate non-implementation: the legacy wrapper predates LangGraph callback support, and adding real streaming to it would mean duplicating the filter-composition logic that already lives in `BrioBaseChatModel._stream`.

## What this flow does NOT cover

- **Tool / function calls.** `bind_tools()` on `BrioBaseChatModel` and `BrioLangChainWrapper` are stubs (`return self`). Tool/function-call semantics across providers aren't normalized at the bridge.
- **Structured output / JSON mode.** Provider-side feature; the bridge passes through whatever the underlying provider produced.
- **`bind` for parameter overrides.** Stub on `BrioLangChainWrapper`. Use `BrioAIFactory.create_language` with the desired config rather than late binding.
- **Direct system-prompt-via-string heuristic.** Only `BrioLangChainWrapper.invoke` does the "starts with 'you are a' → system message" inference. `BrioBaseChatModel` expects callers to pass structured messages.

## Related

- `[[chat-completion-pipeline]]` — the pipeline `chat_complete` runs through inside the bridge.
- `[[fencing-contract]]` — what `<out>...</out>` is, and why the bridge strips it.
- `[[streaming-completion-flow]]` — why fence stripping happens consumer-side for streams; documents the two filters.
- `[[chat-adapter-system]]` — where `no_think` actually takes effect.
- `[[no-think-mode]]` — the parameter's semantics in detail (when authored).
