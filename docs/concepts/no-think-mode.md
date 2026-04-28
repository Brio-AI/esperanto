# `no_think` Mode

**Date:** 2026-04-27
**Status:** Active.
**Code:** `ChatAdapter.render(messages, no_think=False)` (`src/brio_ext/adapters/__init__.py`), per-adapter implementations (`qwen_adapter.py`, `gemma_adapter.py`, others), `BrioBaseChatModel.no_think` field (`src/brio_ext/langchain_wrapper.py`), pass-through in `chat_complete` closure (`src/brio_ext/factory.py`).

## What

`no_think` is an optional boolean flag that tells reasoning-capable models (Qwen3/Qwen3.5, Gemma 4) to skip their internal reasoning phase and produce an answer directly. The flag is plumbed end-to-end through brio_ext so that callers don't need to know which adapter is active or what the model's thinking-mode mechanism looks like.

Default is `False`. Set to `True` when the token budget can't accommodate a full reasoning block plus an answer.

## When to use it

Reasoning models split their output into two phases:

1. **Reasoning phase** — the model "thinks out loud" inside `<think>...</think>` tags or a thinking channel. Can be hundreds to thousands of tokens.
2. **Answer phase** — the actual response the consumer wants.

If `max_tokens` is large enough to fit both phases, no problem. If it isn't — common at Tier 2 (4K context, 512 default `max_tokens`) and almost always at Tier 3 — the model exhausts its budget mid-reasoning and never emits the answer. The consumer gets either:

- An empty string (everything was inside an unclosed `<think>`)
- Truncated reasoning content with no actual answer
- A warning logged by `_parse_fenced_content` about budget exhaustion

`no_think=True` sidesteps this by conditioning the model to skip reasoning entirely. The full token budget goes to the answer.

The trade-off: the model's quality on hard questions is generally lower without reasoning. Use `no_think=True` for short structured outputs, classification-style tasks, or anything where the cost of an empty/truncated response exceeds the cost of a less-reasoned answer.

## Why it lives on adapters, not the factory

Originally this flag lived on `BrioAIFactory`. Commit `e520800` moved it to per-adapter ownership. The reason: how you suppress reasoning is **completely different per model family**:

- **Qwen3/Qwen3.5**: prefill the assistant turn with an empty `<think></think>` block — the model treats reasoning as already complete and skips to the answer.
- **Gemma 4**: omit the `<|think|>` system marker that would normally steer the model toward extended reasoning.
- **Phi-4 / Llama 3 / Mistral**: no thinking mode at all; the parameter is meaningless.

A factory-level setting would have to centralize all of those mechanisms in a switch statement that's really an adapter concern. Putting it on adapters means each adapter owns exactly the logic for its own model family. New reasoning models added later get their own `no_think` semantics in their own adapter.

The abstract base class `ChatAdapter.render(messages, no_think=False)` documents the convention: every adapter accepts the parameter, but only the ones with reasoning modes do anything with it. Llama/Mistral/Phi adapters accept-and-ignore.

## How it threads through

```
caller passes no_think=True
        │
        ▼
BrioBaseChatModel(brio_model, no_think=True)         # LangChain entry
   OR  create_langchain_wrapper(model, no_think=True)
   OR  model.chat_complete(messages, no_think=True)  # direct call
        │
        ▼
brio_ext chat_complete closure (set up by _wrap_language_model)
        │
        │  passes no_think kwarg to render_for_model
        │
        ▼
render_for_model(model_id, messages, provider, chat_format, no_think=True)
        │
        │  resolves adapter, then:
        │
        ▼
adapter.render(messages, no_think=True)
        │
        │  Qwen: prefilled <think></think>
        │  Gemma4: omits <|think|> marker
        │  others: ignored
        │
        ▼
RenderedPrompt with model-specific prompt string
```

The factory's `chat_complete` closure has the parameter wired through:

```python
def chat_complete(self, messages, stream=None, no_think=False):
    rendered = render_for_model(model_id, messages, provider,
                                chat_format=chat_format, no_think=no_think)
    ...
```

Same for `achat_complete`.

## Per-adapter behavior

| Adapter | `no_think=True` behavior |
|---|---|
| `QwenAdapter` | Prefill assistant turn with `<|im_start|>assistant\n<think>\n\n</think>\n` — conditions Qwen3/Qwen3.5 to treat reasoning as already done. Works via raw `/v1/completions` because the model continues from where the prompt left off. |
| `Gemma4Adapter` | Omit the `<|think|>` system marker. Without it the model is not steered into the reasoning channel, even though Gemma 4 supports one. |
| `LlamaAdapter` | Accepts the kwarg, ignores the value. Llama 3.1/3.2 don't have a thinking phase. |
| `MistralAdapter` | Accepts the kwarg, ignores the value. |
| `PhiAdapter` | Accepts the kwarg, ignores the value. Phi-4 Reasoning *does* reason out loud (always), but doesn't expose a switch — the model's behavior isn't controllable from the prompt. If you need to suppress its reasoning, use Phi-4 Mini instead, or accept the budget cost. |

The adapters that ignore `no_think` still accept the parameter so the renderer's call signature is uniform. Without that uniformity, the renderer would need an adapter-capability check before every call.

## Default value across entry points

| Entry point | Default `no_think` |
|---|---|
| `model.to_langchain()` | `False` (lambda passes nothing; `BrioBaseChatModel.__init__` defaults to `False`) |
| `create_langchain_wrapper(model)` | `False` (function default) |
| `BrioBaseChatModel(brio_model=model)` | `False` (Pydantic field default) |
| `model.chat_complete(messages)` | `False` (closure default) |

To enable, pass `no_think=True` explicitly. There's no global env var or config switch — the choice is per-call (or per-wrapper-instance for the LangChain path).

## Common patterns

### Tier-aware default (recommended for Tier 2/3)

```python
from brio_ext.factory import BrioAIFactory, create_langchain_wrapper

# tier comes from briodocs_config.yaml or your tier selection logic
no_think = tier in ("tier2", "tier3")  # tight budgets

model = BrioAIFactory.create_language("llamacpp", "qwen3-7b-instruct", config={...})
lc_model = create_langchain_wrapper(model, no_think=no_think)
```

### Per-call override

```python
# Wrapper constructed without no_think (the default)
lc_model = create_langchain_wrapper(model)

# But underlying chat_complete still accepts the kwarg directly
response = model.chat_complete(messages, no_think=True)
```

The LangChain bridge fixes `no_think` at construction time. Direct `chat_complete` calls can override per request.

## What `no_think` does NOT do

- **It doesn't strip already-emitted `<think>` tags.** That's `_parse_fenced_content` / `StreamingThinkTagFilter` in [`[[langchain-bridge-flow]]`](../flows/langchain-bridge.md). `no_think` operates on the *prompt* to discourage emission; the filters operate on the *response* to remove anything that slipped through.
- **It doesn't apply to cloud providers.** `TEMPLATE_PROVIDERS` (OpenAI, Anthropic, Groq, Ollama) bypass adapters entirely — `no_think` is silently ignored because there's no adapter render step in their path. Cloud reasoning models with their own switches (e.g., OpenAI's `reasoning_effort`) need to be configured via the provider's own config dict.
- **It doesn't gate on whether the model actually supports thinking.** Calling `no_think=True` with `LlamaAdapter` doesn't error — it just has no effect.

## Related

- `[[chat-adapter-system]]` — the registry that holds the adapters whose `render()` reads this flag.
- `[[adapter-driven-rendering]]` — why per-format logic lives on adapters in the first place.
- `[[langchain-bridge-flow]]` — the constructor parameter and how the bridge passes it through.
- `[[tier-based-server-config]]` — the tier system that motivates `no_think=True` defaults at Tier 2/3 (when authored).
