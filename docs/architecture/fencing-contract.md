# Fencing Contract

**Date:** 2026-04-27
**Status:** Active. Load-bearing client contract with BrioDocs.
**Code:** `_ensure_fence` (`src/brio_ext/factory.py:250-278`), `_strip_trailing_incomplete_tokens` (`factory.py:281-299`), `StreamingFenceFilter` / `StreamingThinkTagFilter` (`src/esperanto/utils/streaming.py`).

## What

Every chat completion returned through `BrioAIFactory` — non-streaming or streaming, cloud provider or local llama.cpp server — has its content wrapped in `<out>...</out>` fences:

```
<out>
{generated content}
</out>
```

This is the **fencing contract**: brio_ext owns the fence; the LLM never sees `<out>` in its prompt or stop-token list; consumers (BrioDocs) rely on the fence to extract clean content from raw model output.

```
BrioDocs Application
  ↓ (assembles system + content + insights + user)
  ↓
brio_ext (BrioAIFactory)
  ↓ (renders to LLM format — ChatML, [INST], etc.)
  ↓ (NO <out> tags in prompt!)
  ↓
LLM (cloud API or llama.cpp)
  ↓ (generates natural content)
  ↓
brio_ext
  ↓ (wraps in <out>...</out>)
  ↓
BrioDocs Application
  ↓ (strips fences, uses content)
```

The key insight: **LLMs don't know about `<out>` tags. They just generate content. brio_ext handles all the formatting.** This split is preserved in [`docs/_OLD/NEXT_STEPS.md`](../_OLD/NEXT_STEPS.md) as the rationale for the original `<out>`-removal-from-prompts work.

## Why

Chat-completion APIs return whatever the model generated, which can include format artifacts the consumer doesn't want:

- ChatML special tokens (`<|im_start|>`, `<|im_end|>`)
- `[INST]` / `[/INST]` tags from Llama-style templates
- Reasoning models' `<think>...</think>` blocks
- Trailing incomplete special tokens when the model hits `max_tokens` mid-token (e.g., `[/`, `<|`, `<<`)
- LLM-emitted `<out>` tags when the model imitated previous turns in the prompt

Brio_ext fences the *useful* content in `<out>...</out>` after stripping these artifacts. Consumers can split on the fence to extract clean text without parsing model-specific markers.

The fence is **always present**, even for empty generations (`<out>\n</out>`) — so consumers can always assume the structure exists.

## Who owns the fence

**Brio_ext owns the fence. The LLM is never instructed to produce it.**

The library deliberately:

- **Does not include `<out>` in adapter prompts.** Each chat-template adapter (`QwenAdapter`, `LlamaAdapter`, `MistralAdapter`, `Gemma4Adapter`, `PhiAdapter`) renders the model's native template without any `<out>` reference.
- **Does not include `<out>` in stop tokens.** `DEFAULT_STOP` in `src/brio_ext/renderer.py` is empty; adapters declare their own model-specific stops (e.g., `<|im_end|>` for ChatML), never `<out>` or `</out>`.

This was a deliberate change. The earlier design did inject `<out>` into prompts and stop-token lists, but LLMs proved unreliable at producing it: missing closing tags, extra whitespace, nested fences, occasional refusals. Doing the fencing on the brio_ext side makes the contract deterministic regardless of how the model behaves.

## Where it's enforced

### Non-streaming responses

`_ensure_fenced_completion` in `src/brio_ext/factory.py` runs after every non-streaming `chat_complete` call. It iterates over `result.choices`, runs each message's `content` through `_ensure_fence`, and returns a copy of the `ChatCompletion` with re-fenced content.

`_ensure_fence` (`factory.py:250-278`) does six things in order:

1. Strip whitespace.
2. If empty, return `<out>\n</out>` (the empty-completion form).
3. Run the matching adapter's `clean_response()` to remove model-specific format markers.
4. Strip trailing incomplete special tokens via `_strip_trailing_incomplete_tokens` (handles the `max_tokens`-truncation case).
5. Strip any LLM-emitted `<out>`/`<output>` open and close tags.
6. Re-fence the cleaned content as `<out>\n{stripped}\n</out>`.

Step 5 is the "LLM imitated us" case. If the prompt includes prior assistant turns that were fenced (e.g., a multi-turn conversation persisted across requests), the model may produce its own `<out>` tags. The library strips those and re-emits canonical fences — guaranteeing exactly one fence, never duplicated, never malformed.

### Streaming responses

Before commit `1855de0`, the streaming path did not apply the fence. Consumers calling `chat_complete(messages, stream=True)` (or `astream` via the LangChain wrapper) saw raw chunks without `<out>...</out>` framing, breaking the contract for any consumer that switched to streaming.

The fix: `StreamingFenceFilter` (in `src/esperanto/utils/streaming.py`) now wraps the chunk stream and emits `<out>` before the first content chunk and `</out>` after the last. The shared module-level `_parse_fenced_content` helper (commit `7244b3e`) ensures both paths use identical extraction logic.

`StreamingThinkTagFilter` runs alongside it for reasoning models that wrap all output in `<think>...</think>` — the filter passes through the post-think content while preserving the fence at the outer layer.

## What consumers can rely on

Given a `ChatCompletion` returned from any `BrioAIFactory.create_language(...).chat_complete(...)` call:

```python
content = response.choices[0].message.content
# Always one of:
#   "<out>\n{actual content}\n</out>"
#   "<out>\n</out>"            # empty generation
```

Consumers can extract the inner content with a single regex:

```python
import re

match = re.match(r"<out>\n?(.*?)\n?</out>", content, re.DOTALL)
inner = match.group(1) if match else content
```

The same shape holds for streaming — the very first non-empty chunk includes the opening `<out>\n`, the last chunk includes the closing `\n</out>`, and chunks in between carry whatever the model emitted between them.

The LangChain wrapper (`BrioBaseChatModel`) does the inner-content extraction automatically and returns the unfenced text in `_AIMessage.content`. Consumers that don't want to do their own extraction should use `model.to_langchain()` or `create_langchain_wrapper(model)`.

## Edge cases

| Case | Behavior |
|---|---|
| Empty generation | Returns `<out>\n</out>`. Always parseable; never a bare empty string. |
| Truncation mid-token (`max_tokens` cuts off `[/INST` mid-emit) | `_strip_trailing_incomplete_tokens` removes garbage like `[/`, `<|`, `<<`, `[/S`, `<|e` before the closing fence is added. Regex at `factory.py:296`. |
| LLM-emitted `<out>` or `<output>` tags | Stripped before re-fencing. Result is single-fenced regardless. |
| Adapter-specific format markers | Each adapter's `clean_response()` strips its own markers (`[/INST]`, `<|im_end|>`, etc.) before the fence is applied. |
| Model emits nested fences | Outer-most strip in step 5 catches the outermost pair; inner pairs survive as literal text. (Rare in practice; if it becomes a problem, harden step 5 to loop until idempotent.) |

## What the contract does NOT cover

- **Streaming chunks individually.** `<out>` only appears in the first chunk and `</out>` in the last. Mid-stream chunks have neither — consumers must accumulate the chunks or use the LangChain wrapper.
- **Tool calls / function calls.** `tool_calls` and `function_call` on `Message` are passed through unchanged. The fence wraps the `content` field only.
- **Errors.** If the underlying provider raises, brio_ext re-raises. There is no "error fence" form.
- **Raw `esperanto.AIFactory` calls.** This contract is brio_ext-specific. Code that imports `from esperanto.factory import AIFactory` directly (bypassing brio_ext) gets unfenced output. BrioDocs should always go through `BrioAIFactory`.

## Versioning implications

The fence shape (`<out>` open tag, `</out>` close tag, exact `\n` whitespace inside) is a versioned interface. Changes are breaking changes:

- Renaming the fence (e.g., to `<output>...</output>`) → major version bump + BrioDocs coordination beat.
- Removing the leading/trailing newlines → breaks any consumer that splits on `\n`.
- Making the fence optional for some provider → silently fails for any consumer that assumes it's always present.

The contract is what makes drop-in provider swaps safe for BrioDocs. Anything that weakens "always exactly one `<out>...</out>` fence" weakens that guarantee.

See `[[client-contract-fencing]]` for the discipline this implies and `[[release-tagging-discipline]]` for how breaking changes are coordinated with the BrioDocs submodule consumer.

## Related

- `[[client-contract-fencing]]` — Concept-level framing of why the fence is a contract, not a format choice.
- `[[chat-completion-pipeline]]` — Where `_ensure_fence` sits in the request flow.
- `[[streaming-completion-flow]]` — How `StreamingFenceFilter` preserves the contract for streaming.
- `[[chat-adapter-system]]` — The adapters whose `clean_response()` runs inside `_ensure_fence`.
- `[[langchain-bridge-flow]]` — The wrapper that extracts inner content for LangChain consumers.
