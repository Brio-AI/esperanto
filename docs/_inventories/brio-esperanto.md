# Brio Esperanto — Wiki Page Inventory

**Domain:** Brio-Esperanto (the unified AI-provider interface library; consumed by BrioDocs as a git submodule)
**Author:** esperanto module agent
**Date:** 2026-04-25
**Source interview:** _none on file — this inventory is drafted from `CLAUDE.md`, `docs/`, source, and `.claude/memory/`._

Esperanto is a Python library, not a service. Its core value proposition is **shape consistency** across 15+ AI providers — same `ChatCompletion`/`Message`/`Usage` types, same call surface, same `<out>...</out>` fencing contract — regardless of whether the underlying provider is OpenAI, Anthropic, llama.cpp, or a HuggingFace local model. The repo is split into two packages: `esperanto/` (provider implementations) and `brio_ext/` (BrioDocs-specific extension layer that adds adapter-based chat-template rendering, output fencing, metrics logging, and a LangChain bridge). The wiki shape reflects that — most fragility lives at the brio_ext layer, where Esperanto meets the BrioDocs application contract.

## Doc-layer reminder

Per repo convention, this inventory treats sources by layer:

- **`docs/`** — canonical reference for behavior; cited by wiki pages.
- **`CLAUDE.md`** — operational directives for the module agent. **Not** a canonical wiki source.
- **`.claude/memory/`** — synthesis snapshots. **Not** canonical sources.
- **Top-level planning files** (`NEXT_STEPS.md`, `Brio_Esperanto_implementation_Plan.md`, `BRIODOCS_TIERS.md`, `Brio_Esperanto_git_setup_README.md`) — historical or aspirational; should be moved to `docs/_OLD/` and `docs/_Future/` per Registry's example. **Not** canonical sources.

## Source status field

Every entry below has a `source_status` field with exactly one of three values.

| Status | Meaning | Count |
|---|---|---|
| `current` | Canonical source exists in `docs/` and reflects code today. Wiki page can be authored from it directly. | 16 |
| `stale-needs-update` | Canonical source exists in `docs/` but predates substantive changes. Refresh the source before citing. | 1 |
| `missing` | No canonical `docs/` source yet. A new doc must be authored before the wiki page can land. | 9 |

**Totals:** 26 entries (1 repo overview + 25 pages). 9 of 26 are blocked on a missing `docs/` source — the brio_ext-layer architectural commitments and operational discipline that are load-bearing for BrioDocs but live only as inline code comments and CLAUDE.md directives today. The foundational fencing pair (`[[fencing-contract]]` + `[[client-contract-fencing]]`) landed 2026-04-27; the remaining nine can be authored without further blockers.

**Refresh log:**
- 2026-04-27: `docs/2025-12-20_Developer_Guide.md` refreshed against version 2.8.1 — flipped `[[brio-esperanto]]` and `[[provider-normalization-pattern]]` to `current`.
- 2026-04-27: `docs/llm.md` refreshed against version 2.8.1 — added Vertex, brio_ext pointer, `response.timings`/`response.content` examples, and fixed the bogus `chunk.provider` reference in the streaming example. Flipped `[[multiprovider-llm-support]]` and (jointly with the dev guide refresh) `[[esperanto-core-library]]` to `current`.
- 2026-04-27: `docs/llama_cpp_test_specification.md` refreshed — status badges now show both Oct 2025 (historical) and current ✅ marks for Qwen/Mistral/Phi-4; "The Bug" / "Current Workaround (HACK)" sections marked as historical with explicit "REMOVED" callouts; header points readers to `brio_ext_integration_v2.md` for operational use. Flipped `[[chat-adapter-system]]` and `[[llamacpp-local-provider]]` to `current`.
- 2026-04-27: `docs/TRANSFORMERS_ADVANCED_FEATURES.md` refreshed — verified Recommended Models list and chunk-size table still match code; documented previously-missing `quantize`, `model_cache_dir`, and `device="auto"` auto-detection. Flipped `[[transformers-advanced-embedding]]` to `current`.
- 2026-04-27: `docs/brio_ext_integration.md` refreshed — replaced 215-line superseded §10 with a clean redirect to v2 and the test spec; added §2.1 documenting `register_with_factory`; corrected real factual bugs (`LLAMACPP_BASE_URL` env var name, default port `8080` with v2 launcher caveat, `BRIO_USE_BRIO_FACTORY` removed as fictional, `<out>` fence framing fixed). Flipped `[[brio-ext-extension-package]]` to `current`.

**Authoring log:**
- 2026-04-27: `docs/architecture/fencing-contract.md` authored. Documents the `<out>...</out>` contract, the six-step `_ensure_fence` algorithm, where it's enforced (non-streaming + streaming), edge cases, what the contract does NOT cover, and versioning implications. Preserves the BrioDocs↔brio_ext flow diagram fragment from the archived `NEXT_STEPS.md`. Flipped `[[fencing-contract]]` to `current`.
- 2026-04-27: `docs/concepts/client-contract-fencing.md` authored. Concept-level pair to `[[fencing-contract]]`: treats the fence as a versioned API contract rather than a format choice. Covers the silent-failure mode across the Esperanto ↔ BrioDocs boundary, what counts as breaking (illustrative table), the three implications of the discipline (tests assert directly, breaking changes need a coordination beat, provider parity is structural), and the sibling pattern in BrioRegistry. Flipped `[[client-contract-fencing]]` to `current`.

---

## Pages this domain needs

### Repo overview (lives in `repos/`)

#### `[[brio-esperanto]]`
- **Category:** repo overview
- **Source status:** `current`
- **Summary:** Python library providing a unified interface for 15+ AI providers (LLM, embedding, reranker, STT, TTS) plus a BrioDocs-specific extension layer (`brio_ext`) that adds chat-template adapters, `<out>` fencing, metrics, and LangChain compatibility. Consumed by BrioDocs as a git submodule, pinned by tag.
- **Canonical source:** `docs/2025-12-20_Developer_Guide.md`. Refreshed 2026-04-27 against version 2.8.1; now reflects the `start_server_v2.sh` tier-based launcher, the `no_think` parameter on `create_langchain_wrapper`, the streaming fence-extraction wiring, and the full `ChatCompletion`/`Timings` shape.
- **Related:** `[[esperanto-core-library]]`, `[[brio-ext-extension-package]]`, `[[briodocs-submodule-integration]]`

### Subsystems

#### `[[esperanto-core-library]]`
- **Category:** subsystem
- **Source status:** `current`
- **Summary:** The `esperanto` package — provider implementations for 13 LLMs (OpenAI, Anthropic, Google, Groq, Ollama, OpenRouter, xAI, Perplexity, Azure, Mistral, DeepSeek, Vertex, plus `openai-compatible` for self-hosted endpoints) plus embedding, reranker, STT, and TTS providers behind a single `AIFactory`.
- **Canonical source:** `docs/2025-12-20_Developer_Guide.md` (Project Structure + Registry Architecture sections) plus `docs/llm.md`. Both refreshed 2026-04-27 against v2.8.1; `llm.md` now lists Vertex, points BrioDocs developers at `BrioAIFactory`, and includes `response.timings` on the response example.
- **Related:** `[[provider-registry-pattern]]`, `[[provider-normalization-pattern]]`, `[[multiprovider-llm-support]]`, `[[http-only-architecture]]`

#### `[[brio-ext-extension-package]]`
- **Category:** subsystem
- **Source status:** `current`
- **Summary:** The `brio_ext` package — wraps `AIFactory` with `BrioAIFactory`, dispatches chat-template adapters, enforces `<out>...</out>` fencing on responses, logs JSONL metrics, and exposes a LangChain-compatible bridge. Adds two local providers (`llamacpp`, `hf_local`) on top of Esperanto's cloud-provider set.
- **Canonical source:** `docs/brio_ext_integration.md` (refreshed 2026-04-27) plus `docs/brio_ext_integration_v2.md`. §10 is now a clean redirect to v2 + the test spec. New §2.1 documents `register_with_factory`. Real factual corrections landed: `LLAMACPP_BASE_URL` (not `BRIO_LLAMACPP_BASE_URL`); default port `8080` with a port-mismatch caveat for the v2 launcher's `8765`; `BRIO_USE_BRIO_FACTORY` removed (it never existed in the codebase); the "stop tokens" framing of `<out>` fixed (it's a post-generation fence, not a stop sequence).
- **Related:** `[[chat-adapter-system]]`, `[[fencing-contract]]`, `[[langchain-bridge]]`, `[[metrics-logger]]`

#### `[[chat-adapter-system]]`
- **Category:** subsystem
- **Source status:** `current`
- **Summary:** Adapter registry (`src/brio_ext/registry.py`) with `QwenAdapter`, `LlamaAdapter`, `MistralAdapter`, `Gemma4Adapter`, `PhiAdapter` — each renders messages into the model's native chat-template format (ChatML, Llama, Mistral, Gemma 4) and declares its own stop tokens. Selection prefers `model_id` pattern matching, falls back to an explicit `chat_format` hint for custom-named models. As of 2026-04-28 (PR #6), `Gemma4Adapter` matches Gemma 4 only — Gemma 2/3 model ids no longer match (see `docs/2026-04-28_Gemma_4_Adapter_Breaking_Change.md`).
- **Canonical source:** `docs/llama_cpp_test_specification.md` (refreshed 2026-04-27) plus `docs/brio_ext_integration_v2.md` §9.6 (live status matrix). Test spec now correctly shows all five adapters validated; historical "🔴 FAILS / 🟡 NOT TESTED" badges are preserved with current ✅ marks alongside. The `model_id` → `chat_format` selection logic lives only in `registry.py` docstrings — that's a gap to be addressed by `[[adapter-driven-rendering]]` when authored, not a staleness in the source.
- **Related:** `[[fencing-contract]]`, `[[adapter-driven-rendering]]`, `[[llamacpp-local-provider]]`, `[[no-think-mode]]`

#### `[[llamacpp-local-provider]]`
- **Category:** subsystem
- **Source status:** `current`
- **Summary:** `LlamaCppLanguageModel` — talks to a local llama.cpp HTTP server (default `http://127.0.0.1:8765`), maps `max_tokens` to the server's `n_predict`, extracts built-in `timings` (prompt_per_second, predicted_per_second), and produces both message-mode and prompt-mode payloads to match the active adapter.
- **Canonical source:** `docs/llama_cpp_test_specification.md` (refreshed 2026-04-27 — status badges updated, "Current Workaround (HACK)" marked as removed, top header points readers to `brio_ext_integration_v2.md` for current operational use).
- **Related:** `[[chat-adapter-system]]`, `[[llamacpp-server-tiers]]`, `[[performance-metrics]]`

#### `[[metrics-logger]]`
- **Category:** subsystem
- **Source status:** `current`
- **Summary:** JSONL metrics logger (`brio_ext/metrics/logger.py`) that captures per-request `tier_id`, `model`, `total_time_ms`, `tokens_per_second`, prompt/completion tokens, and optional `ttft_ms` for streaming. Toggleable at runtime via `enable_metrics()`/`disable_metrics()` or at startup via `BRIO_METRICS_ENABLED`. Default path is platform-aware (`Library/Application Support/BrioDocs/` on macOS, `%APPDATA%/BrioDocs/` on Windows, `~/.config/briodocs/` on Linux).
- **Canonical source:** `docs/2025-12-08 Performance Metrics Implementation.md` plus `docs/2025-12-10 Logging_migration_to_scalable_framework.md`. Both align with current code.
- **Related:** `[[performance-metrics]]`, `[[chat-completion-pipeline]]`

### Flows

#### `[[chat-completion-pipeline]]`
- **Category:** flow
- **Source status:** `missing`
- **Summary:** End-to-end path of a `chat_complete` call through `BrioAIFactory` — `_wrap_language_model` injects an adapter, `render_for_model` produces either a `messages` payload (for chat-template providers like OpenAI/Anthropic) or a `prompt` payload (for prompt-mode providers like llamacpp/hf_local), the underlying provider executes, and `_ensure_fenced_completion` re-fences the response in `<out>...</out>` after stripping any model-emitted tags and trailing incomplete special tokens.
- **Canonical source:** Needs `docs/architecture/chat-completion-pipeline.md`. The flow exists across `brio_ext/factory.py`, `brio_ext/renderer.py`, and `brio_ext/adapters/*` but is never described as a single pipeline. The render-mode split (`TEMPLATE_PROVIDERS` vs. `PROMPT_PROVIDERS`) and the `_stop_config_guard` mechanism are particularly under-documented.
- **Related:** `[[adapter-driven-rendering]]`, `[[fencing-contract]]`, `[[chat-adapter-system]]`

#### `[[langchain-bridge-flow]]`
- **Category:** flow
- **Source status:** `missing`
- **Summary:** How `model.to_langchain()` (and the richer `BrioBaseChatModel` / `create_langchain_wrapper`) preserves the brio_ext rendering pipeline when consumed by LangChain/LangGraph — converting LangChain message types to brio_ext format, calling the wrapped `chat_complete`, then stripping `<out>` fences and `<think>` blocks before returning an `_AIMessage`.
- **Canonical source:** Needs `docs/flows/langchain-bridge.md`. Touched briefly in `docs/brio_ext_integration.md` §5 and the developer guide's LangChain Integration section, but the two-paths story (lightweight `to_langchain()` vs. full `BrioBaseChatModel`) and the `no_think` parameter wiring aren't explained.
- **Related:** `[[langchain-langgraph-integration]]`, `[[fencing-contract]]`, `[[no-think-mode]]`, `[[streaming-completion-flow]]`

#### `[[streaming-completion-flow]]`
- **Category:** flow
- **Source status:** `missing`
- **Summary:** Streaming path through brio_ext — uses `StreamingFenceFilter` and `StreamingThinkTagFilter` (in `esperanto.utils.streaming`) to apply `<out>`/`<output>` fence extraction and `<think>`-tag suppression chunk-by-chunk. Recently fixed (commit 1855de0) so the streaming path now matches the non-streaming `_ensure_fence` behavior.
- **Canonical source:** Needs `docs/flows/streaming-completion.md`. The fix was substantive (PR #2 / commit 7244b3e ported `_parse_fenced_content` into a shared module-level function) but only the commit messages document it. TTFT measurement during streaming and the "final-chunk usage/timings" handoff also live only in code.
- **Related:** `[[fencing-contract]]`, `[[langchain-bridge-flow]]`, `[[performance-metrics]]`

#### `[[adding-a-new-provider]]`
- **Category:** flow
- **Source status:** `current`
- **Summary:** Operational steps to extend the registry — create `{Provider}LanguageModel` in `src/esperanto/providers/{type}/`, register in `_provider_modules` in `factory.py`, write tests under `tests/providers/{type}/`, run `uv run pytest -v`. Same pattern applies to embedding/reranker/STT/TTS.
- **Canonical source:** `docs/2025-12-20_Developer_Guide.md` (Adding a New Provider section, lines ~200–400). The walkthrough is concrete and current; sample code matches the codebase pattern.
- **Related:** `[[provider-registry-pattern]]`, `[[provider-normalization-pattern]]`, `[[testing-discipline]]`

### Architecture

#### `[[provider-registry-pattern]]`
- **Category:** architecture
- **Source status:** `missing`
- **Summary:** Static dictionary + `importlib`-based dynamic loading — `_provider_modules["language"]["openai"] = "esperanto.providers.llm.openai:OpenAILanguageModel"`. Lets the library declare 15+ providers without import-time costs from optional dependencies (e.g., `transformers`, `torch`). `BrioAIFactory` extends the parent map by `deepcopy` + override (`_LANGUAGE_OVERRIDES` for `llamacpp`/`hf_local`).
- **Canonical source:** Needs `docs/architecture/provider-registry.md`. Described informally in the developer guide's Registry Architecture section, but the `deepcopy`-and-override extension pattern that brio_ext uses isn't explained anywhere.
- **Related:** `[[esperanto-core-library]]`, `[[brio-ext-extension-package]]`, `[[adding-a-new-provider]]`

#### `[[provider-normalization-pattern]]`
- **Category:** architecture
- **Source status:** `current`
- **Summary:** All providers must convert vendor-specific responses into the shared `ChatCompletion` / `Message` / `Choice` / `Usage` / `Timings` Pydantic models before returning. This is the library's core value proposition — consumers code against one shape regardless of provider.
- **Canonical source:** `docs/2025-12-20_Developer_Guide.md` (Common Types Reference and Design Principles sections, refreshed 2026-04-27 against `src/esperanto/common_types/response.py`). Now lists the full `ChatCompletion` shape (including `provider`, `timings`, `object`, the `content` shortcut) and a dedicated `Timings` class definition.
- **Related:** `[[provider-registry-pattern]]`, `[[multiprovider-llm-support]]`, `[[fencing-contract]]`

#### `[[adapter-driven-rendering]]`
- **Category:** architecture
- **Source status:** `missing`
- **Summary:** The architectural choice to split *transport* (provider HTTP plumbing) from *rendering* (chat-template format). Providers shouldn't know about ChatML vs. Llama vs. Mistral; adapters shouldn't know about HTTP. The renderer dispatches: `TEMPLATE_PROVIDERS` (cloud APIs that handle templating themselves) get message-mode passthrough; `PROMPT_PROVIDERS` (llamacpp, hf_local) get adapter-rendered raw prompts.
- **Canonical source:** Needs `docs/architecture/adapter-driven-rendering.md`. The `TEMPLATE_PROVIDERS`/`PROMPT_PROVIDERS` split lives only in `brio_ext/renderer.py` line 13–14 with no rationale documented. This was the architectural fix for the Qwen system-message bug and it deserves a first-class explanation.
- **Related:** `[[chat-adapter-system]]`, `[[chat-completion-pipeline]]`, `[[fencing-contract]]`

#### `[[fencing-contract]]`
- **Category:** architecture
- **Source status:** `current`
- **Summary:** Every chat completion returned through `BrioAIFactory` is wrapped in `<out>...</out>`. The contract: brio_ext owns fencing, LLMs never see `<out>` in their prompts (deliberately removed in adapter prompts and stop tokens). Consumers (BrioDocs) rely on the fences to extract clean content from raw model output, in both non-streaming and streaming mode.
- **Canonical source:** `docs/architecture/fencing-contract.md` (authored 2026-04-27). Documents the contract shape, where it's enforced (`_ensure_fence`, `StreamingFenceFilter`), the six-step `_ensure_fence` algorithm, edge cases (empty generation, truncation, LLM-emitted fences), what the contract does NOT cover, and versioning implications. Cites the diagram fragment preserved in `docs/_OLD/NEXT_STEPS.md`.
- **Related:** `[[client-contract-fencing]]`, `[[chat-adapter-system]]`, `[[streaming-completion-flow]]`, `[[langchain-bridge-flow]]`

#### `[[http-only-architecture]]`
- **Category:** architecture
- **Source status:** `stale-needs-update`
- **Summary:** Deliberate design choice: every provider uses `httpx` directly rather than vendor SDKs (no `openai`, no `anthropic`, no `google-generativeai`). Trades vendor-SDK ergonomics for control over normalization, predictable failure modes, and minimal dependency footprint (core install needs only `pydantic` + `httpx`).
- **Canonical source:** `docs/2025-12-20_Developer_Guide.md` (Design Principles section, line ~603). Mentioned but not justified — the rationale (control over response shape, avoiding provider-SDK breaking changes, smaller install surface) is in `CLAUDE.md` but not in canonical docs.
- **Related:** `[[provider-normalization-pattern]]`, `[[esperanto-core-library]]`

### Integrations

#### `[[briodocs-submodule-integration]]`
- **Category:** integration
- **Source status:** `missing`
- **Summary:** BrioDocs consumes Brio-Esperanto as a git submodule pinned by tag (e.g., `v2.8.0`). The release-tagging discipline (`pyproject.toml` version bump → tag → push) is what makes BrioDocs builds reproducible. BrioDocs treats `BrioAIFactory` as the import boundary; everything downstream of `chat_complete` is brio_ext's contract.
- **Canonical source:** Needs `docs/integrations/briodocs-submodule.md`. The developer guide mentions the submodule pattern in its "Integration with BrioDocs" section but doesn't document the version-tagging flow or the BrioDocs-side import surface. Co-authoring with the BrioDocs agent would produce the most useful page.
- **Related:** `[[fencing-contract]]`, `[[release-tagging-discipline]]`, `[[briodocs-llm-pipeline]]` (BrioDocs-owned)

#### `[[langchain-langgraph-integration]]`
- **Category:** integration
- **Source status:** `current`
- **Summary:** What `to_langchain()` exposes — a `BrioBaseChatModel` that LangGraph and LangChain chains can use directly. The wrapper preserves brio_ext's full rendering+fencing pipeline (unlike calling the underlying esperanto provider's `to_langchain()` directly, which bypasses brio_ext). Streaming and `no_think` mode are both supported.
- **Canonical source:** `docs/brio_ext_integration.md` §5 plus `docs/2025-12-20_Developer_Guide.md` (LangChain Integration section). Both reflect the current API.
- **Related:** `[[langchain-bridge-flow]]`, `[[fencing-contract]]`, `[[no-think-mode]]`

#### `[[llamacpp-server-tiers]]`
- **Category:** integration
- **Source status:** `current`
- **Summary:** Brio-Esperanto ships `scripts/start_server_v2.sh` and `fixtures/briodocs_config.yaml` defining three tiers (Tier 1: 8K ctx + GPU; Tier 2: 4K ctx + GPU; Tier 3: 2K ctx + CPU-only) decoupled from seven model selections. Tier defines *how* to run the server; model defines *what* to run. BrioDocs reads the same config to launch the local server with matching settings.
- **Canonical source:** `docs/brio_ext_integration_v2.md` (§9.1, §9.4). Current and reflects the v2 launcher.
- **Related:** `[[tier-based-server-config]]`, `[[llamacpp-local-provider]]`, `[[hardware-tiers]]` (BrioDocs-owned)

### Features

#### `[[multiprovider-llm-support]]`
- **Category:** feature
- **Source status:** `current`
- **Summary:** Single `AIFactory.create_language(provider, model_name)` call surface across 13 LLM providers — OpenAI, OpenAI-compatible, Anthropic, Google, Groq, Ollama, OpenRouter, xAI, Perplexity, Azure, Vertex, Mistral, DeepSeek; plus local `llamacpp`/`hf_local` via brio_ext's `BrioAIFactory`.
- **Canonical source:** `docs/llm.md` (refreshed 2026-04-27 against v2.8.1). Now lists Vertex, points BrioDocs developers at `BrioAIFactory`, includes `response.timings` and `response.content` shortcut on the response example, and corrects the streaming example (chunks have no `provider` field).
- **Related:** `[[provider-registry-pattern]]`, `[[provider-normalization-pattern]]`, `[[esperanto-core-library]]`

#### `[[transformers-advanced-embedding]]`
- **Category:** feature
- **Source status:** `current`
- **Summary:** Local-only embedding features in the `transformers` provider — task-aware prefixes (8 task types from `EmbeddingTaskType`), late chunking with semantic boundary detection, output-dimension control via PCA reduction or zero-padding expansion, model-aware chunk-size limits, optional 4-bit/8-bit quantization via `bitsandbytes`.
- **Canonical source:** `docs/TRANSFORMERS_ADVANCED_FEATURES.md` (refreshed 2026-04-27). Verified that the chunk-size table and Recommended Models list still match the live `_configure_model_specific_settings()` and `models` property; added documentation for the `quantize` and `model_cache_dir` parameters and the `device="auto"` cuda/mps/cpu detection logic, all of which had been missing.
- **Related:** `[[esperanto-core-library]]`, `[[provider-normalization-pattern]]`

#### `[[performance-metrics]]`
- **Category:** feature
- **Source status:** `current`
- **Summary:** Per-request capture of `tokens_per_second`, `prompt_tokens_per_second`, `total_time_ms`, and (streaming-only) `ttft_ms` — extracted from llama.cpp's built-in `timings` for local models, calculated from wall-clock for cloud providers. Surfaced both in the `ChatCompletion.timings` response field (consumers see live numbers) and in the JSONL log (offline analysis).
- **Canonical source:** `docs/2025-12-08 Performance Metrics Implementation.md`. Aligns with current code; all four phases marked complete.
- **Related:** `[[metrics-logger]]`, `[[llamacpp-local-provider]]`, `[[streaming-completion-flow]]`

### Concepts

#### `[[client-contract-fencing]]`
- **Category:** concept
- **Source status:** `current`
- **Summary:** The notion that the `<out>...</out>` envelope is not formatting — it is a production API contract with BrioDocs. Changing the fence shape (e.g., to `<output>`, or removing fencing for some provider, or letting LLMs emit fences themselves) would silently break every consumer that strips fences to get clean content. Sibling in spirit to BrioRegistry's `[[client-contract]]`.
- **Canonical source:** `docs/concepts/client-contract-fencing.md` (authored 2026-04-27). Treats the discipline as distinct from the mechanism (which lives in `[[fencing-contract]]`). Covers the silent-failure mode the contract protects against, what counts as breaking, the three implications (tests assert directly, breaking changes need a coordination beat, provider parity is structural), and the sibling pattern in BrioRegistry.
- **Related:** `[[fencing-contract]]`, `[[briodocs-submodule-integration]]`, `[[client-contract]]` (Registry-owned, parallel concept)

#### `[[no-think-mode]]`
- **Category:** concept
- **Source status:** `missing`
- **Summary:** Optional `/no_think` directive that brio_ext can prepend to the first user message for reasoning-capable models (Qwen3, Qwen3.5). Used when token budget can't accommodate a full reasoning block plus an answer (typical for Tier 2/3). Recently moved from factory ownership to per-adapter ownership (commit e520800) so each adapter can decide whether the directive applies.
- **Canonical source:** Needs `docs/concepts/no-think-mode.md`. The `no_think` parameter threads through `factory.py`, `langchain_wrapper.py`, `renderer.py`, and the adapters but is documented only by inline docstrings. The reason it lives on adapters now (and not the factory) is non-obvious without reading the commit.
- **Related:** `[[chat-adapter-system]]`, `[[langchain-bridge-flow]]`, `[[tier-based-server-config]]`

#### `[[tier-based-server-config]]`
- **Category:** concept
- **Source status:** `missing`
- **Summary:** Configuration split underlying `start_server_v2.sh`: tier defines *how* to run a local model (context window, GPU layers, threads, mlock), model defines *what* to run (which GGUF file, which chat format). The split lets BrioDocs select hardware-appropriate settings independently of model choice.
- **Canonical source:** Needs `docs/concepts/tier-based-server-config.md`. The split is named in `brio_ext_integration_v2.md` ("Tier defines HOW to run; Model defines WHAT to run") but only as a benefits bullet; not explained as a design concept.
- **Related:** `[[llamacpp-server-tiers]]`, `[[no-think-mode]]`, `[[hardware-tiers]]` (BrioDocs-owned)

### Operational

#### `[[release-tagging-discipline]]`
- **Category:** operational
- **Source status:** `missing`
- **Summary:** Cutting a release: bump `pyproject.toml` version → commit → `git tag vX.Y.Z` → push tag → BrioDocs submodule pointer can pin to the tag. The `/esperanto-release` slash command automates the version bump. Every tag is a frozen API surface that BrioDocs may pin against — breaking changes need a major bump and a coordination beat with the BrioDocs team.
- **Canonical source:** Needs `docs/operational/release-tagging.md`. The mechanism is described in the developer guide's "Versioning" subsection (one paragraph), but the *discipline* — what counts as breaking, when to coordinate, how the `/esperanto-release` skill fits — is not written down.
- **Related:** `[[briodocs-submodule-integration]]`, `[[fencing-contract]]`, `[[client-contract-fencing]]`

#### `[[testing-discipline]]`
- **Category:** operational
- **Source status:** `current`
- **Summary:** Two-tier testing: (1) unit tests under `tests/providers/{type}/test_{provider}_provider.py` mock `httpx.Client`/`httpx.AsyncClient` and assert response normalization; (2) integration smoke tests under `src/brio_ext/tests/integration/test_provider_smoke.py` hit live providers behind `BRIO_TEST_<PROVIDER>_MODEL` env-var gates and assert `<out>` fencing is intact end-to-end.
- **Canonical source:** `docs/2025-12-20_Developer_Guide.md` (Testing Guidelines section) plus `docs/brio_ext_integration.md` §8. Both align with current `tests/` layout.
- **Related:** `[[adding-a-new-provider]]`, `[[fencing-contract]]`

---

## Backlog: missing canonical docs

Nine wiki pages remain blocked on missing `docs/` sources. (`docs/architecture/fencing-contract.md` and `docs/concepts/client-contract-fencing.md` were authored 2026-04-27 and are no longer in the backlog.) Suggested authoring order — earlier docs serve as foundation for later ones:

1. ~~**`docs/architecture/fencing-contract.md`**~~ — ✅ authored 2026-04-27.
2. ~~**`docs/concepts/client-contract-fencing.md`**~~ — ✅ authored 2026-04-27.
3. **`docs/architecture/adapter-driven-rendering.md`** — the transport-vs-rendering split. The architectural fix that resolved the Qwen system-message bug; deserves a first-class explanation, not just a code comment.
4. **`docs/architecture/provider-registry.md`** — static-dict + dynamic-import pattern, including the `BrioAIFactory` `deepcopy`-and-override extension trick.
5. **`docs/architecture/chat-completion-pipeline.md`** — render → call → fence flow tying together the previous architecture docs.
6. **`docs/flows/streaming-completion.md`** — the streaming path including the recent fence-extraction fix and TTFT capture.
7. **`docs/flows/langchain-bridge.md`** — `to_langchain()` vs. full `BrioBaseChatModel` and how `no_think` threads through.
8. **`docs/concepts/no-think-mode.md`** — what `/no_think` does, why it now lives on adapters instead of the factory.
9. **`docs/concepts/tier-based-server-config.md`** — tier=HOW vs. model=WHAT split as a design concept.
10. **`docs/integrations/briodocs-submodule.md`** — co-authored with the BrioDocs agent. Submodule pinning, import surface, version-coordination protocol.
11. **`docs/operational/release-tagging.md`** — release discipline; what counts as breaking; how `/esperanto-release` fits.

## Stale-needs-update: existing canonical docs requiring freshness review

One `docs/` file is still authoritative in shape but predates substantive changes. (`docs/2025-12-20_Developer_Guide.md`, `docs/llm.md`, `docs/llama_cpp_test_specification.md`, `docs/TRANSFORMERS_ADVANCED_FEATURES.md`, and `docs/brio_ext_integration.md` were all refreshed 2026-04-27 and are no longer stale.)

| File | Vintage | What's drifted | Wiki entries depending on it |
|---|---|---|---|
| `docs/2025-12-20_Developer_Guide.md` (Design Principles depth) | refreshed 2026-04-27 but Design Principles still single-bullet | The "Pure HTTP" bullet states the design without justifying it. `[[http-only-architecture]]` needs the rationale (response-shape control, avoiding SDK breaking changes, smaller install surface) added either as an expanded subsection here or as a dedicated `docs/architecture/http-only-architecture.md`. | `[[http-only-architecture]]` |

## Stale documentation moved to `docs/_OLD/`

Top-level planning files that are not canonical references and should not be cited by wiki pages. All four were moved under `docs/_OLD/` (alongside the canonical `docs/` tree, so they're discoverable but clearly archived) with per-file rationale in [`docs/_OLD/README.md`](../_OLD/README.md):

- `NEXT_STEPS.md` — explicit "What's Next (Not Complete Yet)" plan from the `<out>`-removal-from-prompts work. Most items have shipped; the file no longer reflects current state. The "Architecture Summary" diagram at the bottom is the seed for the future `[[fencing-contract]]` page; preserve that fragment when writing the new doc.
- `Brio_Esperanto_implementation_Plan.md` — initial fork-and-integrate plan from when this repo was a `lfnovo/esperanto` fork. Branching strategy and `bridocs-vX.Y` tag scheme superseded by current `main` + semver practice.
- `Brio_Esperanto_git_setup_README.md` — one-time fork setup notes. Replaced by `docs/2025-12-20_Developer_Guide.md`.
- `BRIODOCS_TIERS.md` — older tier description that predates `fixtures/briodocs_config.yaml`. Canonical tier definition now lives in the YAML; `docs/brio_ext_integration_v2.md` §9.1 explains it.

## Aspirational documentation to move to `docs/_Future/`

None identified at this scan. The roadmap-style sections inside `brio_ext_integration.md` §11 ("Roadmap for automation") could be split out to `docs/_Future/test-automation-roadmap.md` if anyone tries to cite them as current.

## Pages I expect other agents to own (not in my inventory)

Used as `related:` targets without authoring the page myself. Listed here so cross-references resolve cleanly when the BrioDocs / Registry / MS-Addin / deployment inventories arrive.

- `[[briodocs-llm-pipeline]]` — likely BrioDocs-owned (subsystem). How the BrioDocs app assembles `system + content + insights + user` messages before handing them to `BrioAIFactory.create_language(...).chat_complete(...)`. The thing that calls Esperanto.
- `[[context-builder]]` — likely BrioDocs-owned (subsystem). Pre-truncation logic that runs upstream of brio_ext to keep context within the active tier's window. Esperanto trusts this happens; if it doesn't, llama.cpp truncates silently.
- `[[hardware-tiers]]` — likely BrioDocs-owned (concept). The user-facing "high performance / balanced / fast" tier abstraction. Esperanto's `[[llamacpp-server-tiers]]` is the implementation; `[[hardware-tiers]]` is the mental model.
- `[[client-contract]]` — Registry-owned (concept). Parallel concept: certain JSON files Registry serves are production APIs. Linked from `[[client-contract-fencing]]` because the *kind* of discipline is the same (treating an internal artifact as a versioned external interface).
- `[[release-publishing-flow]]` — Registry-owned (flow). The downstream consumer of any tagged Esperanto release that ends up bundled into a BrioDocs desktop build.
- `[[manifest-reality-reconciliation]]` — deployment-agent-owned (operational). Includes verifying that the BrioDocs binary published to Registry pins to a real Esperanto tag, not a missing one.
