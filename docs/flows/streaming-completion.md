# Streaming Completion Flow

**Date:** 2026-04-27
**Status:** Active.
**Code:** `BrioAIFactory._wrap_language_model.chat_complete` (sync) / `achat_complete` (async) (`src/brio_ext/factory.py`), `_ensure_fenced_completion` short-circuit on non-`ChatCompletion` (same file), `StreamingFenceFilter` and `StreamingThinkTagFilter` (`src/esperanto/utils/streaming.py`), `_StreamingResponseWrapper` and `_AsyncStreamingResponseWrapper` (`src/brio_ext/providers/llamacpp_provider.py`).

## What

Streaming is the same five-stage pipeline as non-streaming ([`[[chat-completion-pipeline]]`](../architecture/chat-completion-pipeline.md)) for stages 1–4, but **diverges at stage 5 (fencing)**. Where the non-streaming path runs `_ensure_fenced_completion` to wrap the response in `<out>...</out>`, the streaming path passes the chunk iterator through unchanged. The fence-handling responsibility moves from the producer (brio_ext) to the consumer (typically the LangChain wrapper).

This asymmetry is deliberate. It's also a meaningful caveat to the [`[[fencing-contract]]`](../architecture/fencing-contract.md) — the contract that "every response is wrapped in `<out>...</out>`" applies to non-streaming returns. Streaming consumers see raw chunks unless they go through the LangChain wrapper or apply the fence filters themselves.

## The asymmetry

| | Non-streaming | Streaming |
|---|---|---|
| brio_ext wraps response in `<out>...</out>` | Yes (`_ensure_fence`) | No (passes through) |
| brio_ext logs metrics | Yes (`_log_completion_metrics`) | No (skipped) |
| Consumer-side filters needed | No (already fenced) | Yes (if fence-stripping wanted) |
| TTFT capture | N/A (single response) | Yes, at provider wrapper |

## Why it works this way

`_ensure_fenced_completion` is type-checked — it only operates on `ChatCompletion`:

```python
def _ensure_fenced_completion(result, adapter=None):
    if not isinstance(result, ChatCompletion):
        return result  # ← streams pass through unchanged
    ...
```

Streaming returns a generator (sync) or async iterator (async). Wrapping every chunk in `<out>...</out>` would require a chunk-stream wrapper; brio_ext deliberately doesn't add one. Two reasons:

1. **The semantics aren't well-defined.** If the LLM emits 50 chunks, do we put `<out>` on chunk 1 and `</out>` on chunk 50? What if chunk 1 is empty? What about retries that re-start the stream? A non-streaming response is a single object with a clear before/after; a stream is a sequence of arrivals.
2. **The consumer often wants the inverse.** Most stream consumers (LangChain wrapper, anything rendering tokens to a UI) want the *content*, not the fence. They'd strip the fence anyway. Pushing fence-handling to the consumer side avoids a wrap-then-strip round-trip.

So brio_ext provides filters consumers can compose, instead of deciding for them.

## The two streaming filters

Both live in `src/esperanto/utils/streaming.py`. Both are state-machine token processors with a `process(token) → str` API and a `flush() → str` finalizer.

### `StreamingFenceFilter`

Extracts content from `<out>...</out>` or `<output>...</output>` if the LLM emitted them. If no opening fence is seen within the first 30 characters (`MAX_SEARCH_CHARS`), the filter switches to passthrough mode — the stream is delivered unchanged.

State machine:

| State | Behavior |
|---|---|
| `searching` (initial) | Buffer up to `MAX_SEARCH_CHARS`. Look for an opening `<out>` or `<output>`. If found: switch to `fenced`. If buffer ceases to be a valid prefix of either tag, or exceeds `MAX_SEARCH_CHARS`: switch to passthrough (flush the buffer, no fence detected). |
| `fenced` | Extract inner content. Maintain a tail buffer of length `max(len(close_tag))` so a close tag split across two chunks (e.g., `</o` + `ut>`) is still detected. |
| `done` | Close tag seen. Discard everything after — including the close tag itself. |
| `passthrough` (no fence detected) | Yield every token unchanged. |

The tail buffer is the subtle part. When the model emits `</out>`, it can arrive split: chunk N ends with `</o`, chunk N+1 starts with `ut>`. The filter holds the last `len("</output>") = 9` characters of inner content in the buffer until either (a) the close tag is found (yield everything before it, discard the rest) or (b) more content arrives (slide the window forward, yield what fell off the front).

### `StreamingThinkTagFilter`

Suppresses content inside `<think>...</think>` (or any other named tags passed to the constructor — `["think", "reasoning"]` works for models that use either name). State machine:

| State | Behavior |
|---|---|
| Outside think | Pass tokens through. When a `<` is seen, start buffering to check if it's `<think>`. |
| Inside think | Buffer tokens; suppress them. When `</think>` is matched, exit. |
| Tag-prefix buffering | Hold characters that *might* be the start of a tag. If they form a complete tag, transition. If they cease to match any tag prefix, flush the buffer to output (we mistook normal `<` for a tag start). |

The latency is bounded: at most a few characters of buffering when `<` is encountered. Outside of those moments, tokens flow through immediately.

## Composing the filters

The LangChain wrapper applies them in this order: **fence first, then think.** This matters because the fence may surround the think tags, not the other way around. Stripping the fence first gives clean inner content; stripping think tags then suppresses any `<think>` blocks within that content.

Reference composition (from `src/brio_ext/langchain_wrapper.py`):

```python
fence_filter = StreamingFenceFilter()
think_filter = StreamingThinkTagFilter()

for chunk in stream_response:
    for token in chunk_to_tokens(chunk):
        defenced = fence_filter.process(token)
        filtered = think_filter.process(defenced) if defenced else ""
        if filtered:
            yield filtered

# Drain both filters at end of stream
remaining = think_filter.process(fence_filter.flush())
remaining += think_filter.flush()
if remaining:
    yield remaining
```

The drain at the end handles the buffered tail of each filter — content that was held back waiting for a possible tag completion.

## TTFT measurement

For local llamacpp streaming, `_StreamingResponseWrapper` (sync) and `_AsyncStreamingResponseWrapper` (async) wrap the underlying provider stream and capture wall-clock time to first chunk:

```python
class _StreamingResponseWrapper:
    def __init__(self, stream, start_time):
        self._stream = stream
        self._start_time = start_time
        self._ttft_ms: Optional[float] = None
        self._first_chunk = True

    def __iter__(self):
        for chunk in self._stream:
            if self._first_chunk:
                self._ttft_ms = (time.perf_counter() - self._start_time) * 1000
                self._first_chunk = False
            yield chunk

    @property
    def ttft_ms(self) -> Optional[float]:
        return self._ttft_ms
```

`start_time` is captured at the top of `chat_complete` *before* the HTTP request is sent. Time to first chunk is therefore wall-clock from request initiation to the first arriving chunk — which includes network round-trip, server queue time, and prompt-processing latency. After the stream is fully consumed, `wrapper.ttft_ms` is populated and can be read by the consumer.

Cloud providers don't currently wrap their streaming responses — TTFT is not captured for them. A consumer that wants TTFT for a cloud streaming call records `time.perf_counter()` before the loop and at the first chunk themselves.

## Metrics logging is skipped for streams

`_log_completion_metrics` is gated on `isinstance(fenced, ChatCompletion)` — same condition as `_ensure_fenced_completion`. Streams don't trigger it. This is partly principled (a stream's "total time" isn't well-defined until the consumer drains it) and partly practical (the logger is a sync write that would block stream emission).

If you want streaming metrics, capture them at the consumer site after the stream completes:

```python
import time
start = time.perf_counter()
chunks = []
async for chunk in lc_model.astream(messages):
    chunks.append(chunk)
total_ms = (time.perf_counter() - start) * 1000
# Optionally feed back into MetricsLogger.log() manually
```

The `BrioBaseChatModel` LangChain wrapper does NOT do this automatically.

## End-to-end flow

```
caller: lc_model.astream(messages)
        │
        ▼
BrioBaseChatModel._astream
        │
        │  (converts LangChain messages → {role, content} dicts)
        │
        ▼
brio_model.achat_complete(messages, stream=True, no_think=...)
        │
        │  (renderer dispatches to messages-mode or prompt-mode;
        │   provider issues HTTP with stream=True;
        │   _ensure_fenced_completion sees a stream and passes through)
        │
        ▼
async stream of ChatCompletionChunk objects
        │
        │  (BrioBaseChatModel iterates chunks, extracts deltas,
        │   pipes them through fence_filter then think_filter)
        │
        ▼
yields filtered text tokens to the caller
```

## What this flow does NOT cover

- **Tool calls in streams.** Tool/function-call delta handling is provider-specific and not normalized here.
- **Mid-stream errors.** If the provider raises mid-stream, the exception propagates. The filters' `flush()` is not guaranteed to be called in error paths — consumer should use try/finally if they need partial-content recovery.
- **Backpressure / cancellation.** No explicit cancellation API. Closing the iterator stops consumption; the underlying HTTP connection closes via `httpx`'s context management.

## Related

- `[[fencing-contract]]` — the non-streaming side of the asymmetry. The contract holds at the non-streaming `chat_complete()` boundary; streaming consumers must apply filters or use the LangChain wrapper.
- `[[chat-completion-pipeline]]` — stages 1–4 are identical to streaming; stage 5 is what diverges.
- `[[langchain-bridge-flow]]` — the consumer of these filters in production. Where `StreamingFenceFilter` + `StreamingThinkTagFilter` get composed.
- `[[performance-metrics]]` — what's captured for non-streaming and why streaming is different.
