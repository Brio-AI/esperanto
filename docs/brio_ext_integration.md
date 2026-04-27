# Brio Ext Integration Guide

**Last refreshed:** 2026-04-27 against esperanto v2.8.1.

This guide explains how to adopt the `brio_ext` package from the Brio-Esperanto fork inside BrioDocs applications (Word add-in, Open Notebook, automation scripts).

## 1. Install the Brio fork

Install from `main` (brio_ext is now merged):

```bash
pip install -e ".[dev]"
```

If BrioDocs treats Esperanto as a submodule, update the pointer to the latest `main` commit and run `pip install -e .` inside the Brio-Esperanto checkout.

## 2. Swap factory imports

Replace existing imports that pull `AIFactory` from Esperanto with the Brio wrapper:

```python
try:
    from brio_ext.factory import BrioAIFactory as AIFactory
except ImportError:
    from esperanto import AIFactory  # fallback when brio_ext is missing
```

`BrioAIFactory` is API-compatible with `esperanto.AIFactory`. Existing code that calls `AIFactory.create_language`, `create_embedding`, etc., continues to work.

### Legacy: `register_with_factory`

If you have an existing `AIFactory` subclass (e.g., from a downstream extension that itself subclasses `esperanto.AIFactory`), you can patch it in place rather than swapping the import:

```python
from esperanto.factory import AIFactory
from brio_ext.factory import register_with_factory

register_with_factory(AIFactory)
# AIFactory.create_language now applies brio_ext rendering and fencing
```

This is a monkey-patch path kept for backward compatibility with code that was already using `AIFactory` before brio_ext existed. New code should prefer `BrioAIFactory` directly.

## 3. Local llama.cpp models

For `provider="llamacpp"` (local GGUF models):

```python
model = AIFactory.create_language(
    provider="llamacpp",
    model_name="qwen2.5-7b-instruct",
    config={
        "base_url": os.getenv("LLAMACPP_BASE_URL", "http://127.0.0.1:8765"),
        "temperature": 0.25,
        "top_p": 0.8,
    },
)
```

- The renderer applies the correct chat template via the matching adapter (`QwenAdapter`, `LlamaAdapter`, `MistralAdapter`, `GemmaAdapter`, `PhiAdapter`).
- The response is wrapped in `<out>...</out>` after generation by `_ensure_fenced_completion`. The LLM never sees `<out>` in its prompt or stop-token list — that contract is enforced entirely on the brio_ext side. See the `<out>` fencing notes in `CLAUDE.md` and (when authored) the `[[fencing-contract]]` wiki page.
- **Port mismatch caveat:** the bare `LlamaCppLanguageModel` defaults to `http://localhost:8080`, but `scripts/start_server_v2.sh` binds `127.0.0.1:8765`. If you use the v2 launcher, set `LLAMACPP_BASE_URL=http://127.0.0.1:8765` or pass `base_url` in `config`.
- Legacy fallback (OpenAI-compatible path) is still available by importing `esperanto.AIFactory` directly.

### Custom Model Names with `chat_format`

If you're using custom model names that don't match standard patterns (e.g., "phi-4-mini-reasoning"), explicitly specify the `chat_format` in the config:

```python
model = AIFactory.create_language(
    provider="llamacpp",
    model_name="phi-4-mini-reasoning",  # Custom name from model_defaults.json
    config={
        "base_url": "http://127.0.0.1:8765",
        "chat_format": "chatml",  # Hint: use ChatML format for Phi-4
        "temperature": 0.5,
    },
)
```

**Supported `chat_format` values:**
- `"chatml"` or `"chat-ml"` – ChatML format (Qwen, Phi-4)
- `"llama"`, `"llama3"`, or `"llama-3"` – Llama format
- `"mistral"` or `"mistral-instruct"` – Mistral format
- `"gemma"` – Gemma format

**Why this matters:** When integrating with BrioDocs model database, you can store `chat_format` alongside model configs and pass it through to brio_ext. This enables custom model names that don't follow standard patterns to still use the correct chat template.

## 4. Remote providers

Cloud providers (OpenAI, Anthropic, Grok, Ollama, etc.) continue to use the standard chat-completions payload — they handle their own chat templating, so brio_ext passes messages through unchanged (`TEMPLATE_PROVIDERS` in `brio_ext/renderer.py`). Adapter-rendered raw prompts are only used for `PROMPT_PROVIDERS` (`llamacpp`, `hf_local`).

Regardless of provider, brio_ext fences the final response in `<out>...</out>` after generation. BrioDocs payloads remain unchanged.

## 5. LangChain / LangGraph integration

Models created via `BrioAIFactory` have a built-in `.to_langchain()` method:

```python
model = AIFactory.create_language("llamacpp", "qwen2.5-7b-instruct", config={...})
lc_model = model.to_langchain()
result = lc_model.invoke("What is 2+2?")
print(result.content)  # Clean text, no <out> tags or <think> content
```

For finer control — including `no_think` mode and streaming — use `create_langchain_wrapper`:

```python
from brio_ext.factory import create_langchain_wrapper

lc_model = create_langchain_wrapper(model, no_think=True)

async for chunk in lc_model.astream(messages):
    print(chunk.content, end="", flush=True)
```

The wrapper handles:
- Stripping `<out>...</out>` fencing (both non-streaming and streaming, via `StreamingFenceFilter`)
- Extracting content from `<think>` tags via `StreamingThinkTagFilter` (for reasoning models that wrap all output in think tags)
- Converting LangChain message types (HumanMessage, SystemMessage, etc.) to brio_ext format
- Optionally prepending `/no_think` to the first user message — set `no_think=True` for Qwen3/Qwen3.5 on Tier 2/3 where the token budget cannot accommodate a full reasoning block plus an answer

No need for custom wrappers or monkey-patching in consumer applications.

## 6. Testing checklist

Before merging updates in BrioDocs:

1. Install the editable Brio-Esperanto fork (`pip install -e .`).
2. Run `pytest src/brio_ext/tests -q` inside the Brio-Esperanto repo.
3. In the BrioDocs repo, run targeted smoke tests:
   - Local llama.cpp model (ensure `<out>` fences, no explanations).
   - Ollama or cloud provider path (should honour the same contract).
4. Monitor for the `brio_ext not installed` warning. If it appears, double-check that the editable install succeeded.

## 7. Environment defaults

| Variable | Purpose | Default |
|----------|---------|---------|
| `LLAMACPP_BASE_URL` | llama.cpp HTTP server endpoint at runtime | `http://localhost:8080` |
| `BRIO_METRICS_ENABLED` | Enable JSONL metrics logging at startup (`1`/`true`/`yes`) | unset ⇒ disabled |
| `BRIODOCS_METRICS_PATH` | Override default metrics log path | platform default (see `docs/2025-12-10 Logging_migration_to_scalable_framework.md`) |
| `BRIODOCS_ENV` | `dev` to use `logs-dev/`, anything else uses `logs/` | unset ⇒ prod path |
| `BRIO_DEBUG` | Verbose renderer output (prompt, adapter selection, mode) | unset ⇒ quiet |

To wire a phased rollout, wrap the import with a try/except and guard factory usage with your own application-level flag — there is no built-in feature-flag env var.

## 8. Provider smoke tests (optional)

For quick end-to-end checks run the live-provider smokes in `src/brio_ext/tests/integration/test_provider_smoke.py`. They are skipped unless you supply environment variables:

```bash
BRIO_TEST_OPENAI_MODEL=gpt-4o-mini \
BRIO_TEST_ANTHROPIC_MODEL=claude-3-5-sonnet-20241022 \
BRIO_TEST_GROQ_MODEL=groq/llama3-8b-8192-tool-use-preview \
pytest src/brio_ext/tests/integration/test_provider_smoke.py -q -m integration

# llama.cpp server (optional)
BRIO_TEST_LLAMACPP_MODEL=qwen2.5-7b-instruct \
BRIO_TEST_LLAMACPP_BASE_URL=http://127.0.0.1:8765 \
pytest src/brio_ext/tests/integration/test_provider_smoke.py -q -m integration
```

For each provider, set `BRIO_TEST_<PROVIDER>_MODEL` (e.g. `BRIO_TEST_GROK_MODEL`,
`BRIO_TEST_MISTRAL_MODEL`). Optional overrides include:

- `BRIO_TEST_<PROVIDER>_PROVIDER` to point at compatible endpoints.
- `BRIO_TEST_<PROVIDER>_BASE_URL` for gateways that require explicit URLs.
- `BRIO_TEST_<PROVIDER>_CONFIG` (JSON) for provider-specific fields such as Azure deployment names or Vertex project IDs.
- `BRIO_TEST_<PROVIDER>_MAX_TOKENS`, `BRIO_TEST_<PROVIDER>_TEMPERATURE`, etc.

Each smoke test asserts:
- Responses are fenced in `<out>…</out>`
- The body between fences is non-empty
- Stop reason is `stop`/`length`

Use these whenever you change adapters, provider shims, or stop-token handling.

## 9. Rollback

If issues arise, revert to the previous behaviour by:

1. Switching the import back to `from esperanto import AIFactory`.
2. Removing any `llamacpp` provider usage (fall back to `openai-compatible`).
3. Keeping the existing llama.cpp server running—the fallback path still leverages it via the OpenAI-compatible API.

## 10. llama.cpp test matrix & scenarios

**Superseded.** The full tier-based architecture, server configuration, test scenarios, and troubleshooting guide live in **[brio_ext_integration_v2.md](./brio_ext_integration_v2.md)**. The detailed test specification (message structures, context-size cases, the historical Qwen system-message bug repro) lives in **[llama_cpp_test_specification.md](./llama_cpp_test_specification.md)**.

For day-to-day operational use:

```bash
# Start server with tier-based launcher
./scripts/start_server_v2.sh --tier 2 --model 1

# Run tests (positional arguments)
python scripts/test_with_llm.py pirate 1
python scripts/test_with_llm.py reasoning 1
```

The earlier inline test matrix and tier-startup commands that lived in this section have been removed — they duplicated content in the two docs above and had drifted from current state. If a missing detail surfaces, add it to the canonical doc rather than re-populating this section.

## 11. Roadmap for automation

1. Expand `test_provider_smoke.py` to load JSON fixtures representing the scenarios above.
2. Record golden outputs for the “inventor” and “pirate” tests per model.
3. Integrate into CI once credential handling is solved (or run manually before releases).

## 12. Support

For questions or regressions, coordinate with the Brio-Esperanto maintainers on `main`. The original fork integration plan (`docs/_OLD/Brio_Esperanto_implementation_Plan.md`) is archived for historical context — outstanding work now lives in PRs and the wiki page inventory at `docs/_inventories/brio-esperanto.md`.
