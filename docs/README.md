# Brio-Esperanto Documentation Index

This index is the entry point for humans and agents into the Brio-Esperanto documentation tree. It mirrors the `docs/` layout and links the canonical doc in each area.

> **Status**: v2.8.1. For project-level context and operational directives, see [/CLAUDE.md](../CLAUDE.md). For the wiki-page inventory and authoring backlog, see [_inventories/brio-esperanto.md](_inventories/brio-esperanto.md).

---

## Folder map

| Folder | What lives here |
|--------|-----------------|
| [architecture/](architecture/) | Load-bearing architectural commitments — the fencing contract, transport-vs-rendering split, provider registry, end-to-end pipeline |
| [concepts/](concepts/) | Design concepts that shape the architecture — what makes the fence a contract; `no_think` mode; tier-based config split |
| [flows/](flows/) | Runtime flow walkthroughs — streaming completion, LangChain bridge |
| [operational/](operational/) | Operational discipline — release tagging |
| [embedding/](embedding/) | Embedding-specific reference (provider list, advanced features, getting-started guide) |
| [_inventories/](_inventories/) | Wiki page inventory + refresh/authoring log |
| [_OLD/](_OLD/) | Archived planning files; not citable as canonical sources |

Top-level files (mostly per-service-type reference docs and dated change announcements) are listed under [Canonical docs by topic](#canonical-docs-by-topic) below.

---

## Canonical docs by topic

### Architecture (the load-bearing reads)

The four architecture docs are the structural skeleton of the library. Read them in order if onboarding.

- [architecture/fencing-contract.md](architecture/fencing-contract.md) — Every non-streaming response is wrapped in `<out>...</out>`; brio_ext owns the fence; LLMs never see it. The most load-bearing client contract this library has.
- [architecture/adapter-driven-rendering.md](architecture/adapter-driven-rendering.md) — Why transport (HTTP) and rendering (chat templates) are split. Resolved the historic Qwen system-message bug; covers `TEMPLATE_PROVIDERS` vs. `PROMPT_PROVIDERS` dispatch.
- [architecture/provider-registry.md](architecture/provider-registry.md) — The `_provider_modules` static-dict + `importlib` lazy-load pattern. Why strings instead of imports, and how `BrioAIFactory` extends the registry via `deepcopy + override`.
- [architecture/chat-completion-pipeline.md](architecture/chat-completion-pipeline.md) — Capstone: the five-stage pipeline (registry lookup → wrap → render → call → fence) plus metrics side-stage. Cite this when reasoning about the whole flow; cite the per-stage docs when reasoning about one piece.

### Concepts

- [concepts/client-contract-fencing.md](concepts/client-contract-fencing.md) — The discipline of treating `<out>...</out>` as a versioned API contract with BrioDocs (sibling pattern to BrioRegistry's client-contract concept). What counts as breaking; why provider parity is structural.
- [concepts/no-think-mode.md](concepts/no-think-mode.md) — The `no_think` flag for reasoning-capable models (Qwen3/Qwen3.5, Gemma 4). Per-adapter ownership, why not factory-level; defaults across entry points; what it does and doesn't do.
- [concepts/tier-based-server-config.md](concepts/tier-based-server-config.md) — Tier defines *how* to run (context, GPU, threads); model defines *what* to run (GGUF file, chat format). Cross product is 3 × 7; productivity is a runtime concern, not a configuration one.

### Flows

- [flows/streaming-completion.md](flows/streaming-completion.md) — The streaming path. Documents the asymmetry with the non-streaming path: brio_ext doesn't add fences to streams; consumer-side filters extract them. `StreamingFenceFilter` + `StreamingThinkTagFilter` state machines, TTFT capture, why metrics are skipped.
- [flows/langchain-bridge.md](flows/langchain-bridge.md) — `to_langchain()` / `BrioBaseChatModel` / `create_langchain_wrapper`. The two implementation classes (recommended vs. legacy), three entry points, how `no_think` threads through, the four cases `_parse_fenced_content` handles.

### Operational

- [operational/release-tagging.md](operational/release-tagging.md) — The seven-step release flow (`/esperanto-release` slash command), major/minor/patch decision table with examples, the coordination beat with BrioDocs for major bumps, why `pyproject.toml` and `uv.lock` must stay in sync.

### Provider reference

Per-service-type reference docs covering the public API, configuration patterns, and provider-specific quirks.

- [llm.md](llm.md) — Language model providers (OpenAI, Anthropic, Google, Groq, Ollama, OpenRouter, xAI, Perplexity, Azure, Vertex, Mistral, DeepSeek, plus brio_ext's local llamacpp/hf_local). Common interface, streaming, structured output, LangChain integration.
- [embedding/](embedding/) — Embedding providers and features, organized into [getting started](embedding/guide.md), [providers](embedding/providers.md), [advanced features](embedding/advanced.md), and an [overview](embedding/README.md).
- [TRANSFORMERS_ADVANCED_FEATURES.md](TRANSFORMERS_ADVANCED_FEATURES.md) — Local-only embedding features (task-aware prefixes, late chunking, dimension control, quantization).
- [rerank.md](rerank.md) — Reranker providers (Jina, Voyage, Transformers).
- [speech_to_text.md](speech_to_text.md) — STT providers (OpenAI, Groq, ElevenLabs, openai-compatible).
- [text_to_speech.md](text_to_speech.md) — TTS providers (OpenAI, ElevenLabs, Google, Vertex, openai-compatible).

### BrioDocs integration & local model serving

- [brio_ext_integration.md](brio_ext_integration.md) — General integration guide for adopting `brio_ext` inside BrioDocs apps. Install, factory swap, local llama.cpp, remote providers, LangChain, testing checklist, env defaults, rollback.
- [brio_ext_integration_v2.md](brio_ext_integration_v2.md) — **Canonical for local-server operational use.** Tier-based launcher, seven supported models, four canonical test scenarios, current pass/fail status matrix.
- [llama_cpp_test_specification.md](llama_cpp_test_specification.md) — Detailed test spec: message structure, context-size cases, the historical Qwen system-message bug repro (now resolved). Operationally superseded by `brio_ext_integration_v2.md`; remains canonical for the spec details.

### Developer guide & change history

- [2025-12-20_Developer_Guide.md](2025-12-20_Developer_Guide.md) — Setup, project structure, registry architecture, adding a new provider/adapter, configuration cascading, common types reference, design principles, LangChain integration, quick-reference table.
- [2025-12-08 Performance Metrics Implementation.md](2025-12-08%20Performance%20Metrics%20Implementation.md) — TTFT and tokens/sec capture; the JSONL metrics logger; what's logged and where.
- [2025-12-10 Logging_migration_to_scalable_framework.md](2025-12-10%20Logging_migration_to_scalable_framework.md) — Platform-aware default paths for the metrics log (macOS / Windows / Linux; dev vs. prod).
- [2026-04-28_Gemma_4_Adapter_Breaking_Change.md](2026-04-28_Gemma_4_Adapter_Breaking_Change.md) — `GemmaAdapter` → `Gemma4Adapter` rename and matcher narrowing (PR #6 / BRIOPROD-360).

### Inventory & archive

- [_inventories/brio-esperanto.md](_inventories/brio-esperanto.md) — Wiki page inventory: 26 entries with source-status counts, refresh log, and authoring backlog.
- [_OLD/README.md](_OLD/README.md) — Per-file rationale for the four archived planning files (`NEXT_STEPS.md`, `Brio_Esperanto_implementation_Plan.md`, `Brio_Esperanto_git_setup_README.md`, `BRIODOCS_TIERS.md`).

---

## Quick links by role

**New developer** → [Developer Guide](2025-12-20_Developer_Guide.md) → [llm.md](llm.md) → [architecture/chat-completion-pipeline.md](architecture/chat-completion-pipeline.md)

**BrioDocs integrator** → [brio_ext_integration_v2.md](brio_ext_integration_v2.md) → [architecture/fencing-contract.md](architecture/fencing-contract.md) → [flows/langchain-bridge.md](flows/langchain-bridge.md)

**Adding a provider** → [Developer Guide § Adding a New Provider](2025-12-20_Developer_Guide.md) → [architecture/provider-registry.md](architecture/provider-registry.md) → [architecture/adapter-driven-rendering.md](architecture/adapter-driven-rendering.md)

**Adding an adapter (new model family)** → [architecture/adapter-driven-rendering.md](architecture/adapter-driven-rendering.md) → [Developer Guide § Adding a New Model/Adapter](2025-12-20_Developer_Guide.md) → existing adapters under [`src/brio_ext/adapters/`](../src/brio_ext/adapters/) for reference

**Release engineer** → [operational/release-tagging.md](operational/release-tagging.md) → [`/esperanto-release` slash command](../.claude/commands/esperanto-release.md) → [concepts/client-contract-fencing.md](concepts/client-contract-fencing.md) (for breaking-change discipline)

**Local-server operator** → [brio_ext_integration_v2.md § 9.1](brio_ext_integration_v2.md) → [`scripts/start_server_v2.sh`](../scripts/start_server_v2.sh) → [concepts/tier-based-server-config.md](concepts/tier-based-server-config.md)

**Wiki contributor / agent** → [_inventories/brio-esperanto.md](_inventories/brio-esperanto.md) (entry status, backlog, refresh/authoring log)

---

## Documentation conventions

- **Filename dates**: `YYYY-MM-DD_Topic_Name.md` for time-stamped docs (change announcements, dated implementation plans). Undated names for evergreen guides (e.g. `llm.md`, `Developer_Guide.md`, the `architecture/`/`concepts/`/`flows/` files).
- **Layered topics**:
  - **`architecture/`** — *what's structurally true and why.* Load-bearing.
  - **`concepts/`** — *the design idea behind the architecture.* Discipline, not mechanism.
  - **`flows/`** — *runtime walkthroughs.* What happens during a call.
  - **`operational/`** — *what humans do.* Release process, on-call, etc.
- **One canonical doc per topic**: when something is superseded, move the old version to [`_OLD/`](_OLD/) with a note in [`_OLD/README.md`](_OLD/README.md). For aspirational designs that were proposed but never built, use a `_Future/` subfolder (not yet present in this repo).
- **Source of truth for code-adjacent facts**: `CLAUDE.md` at repo root has the most current operational directives; this index points into deeper docs. Code comments are not canonical — if a fact lives only in a docstring, that's a missing-canonical-doc issue tracked in the [inventory backlog](_inventories/brio-esperanto.md).
- **Citation discipline**: wiki pages in `brio-swarms/shared/wiki/` cite docs from this tree; they don't duplicate. Stale docs in [`_OLD/`](_OLD/) and aspirational docs in `_Future/` are not citable as canonical.
- **Updating**: edit in place, keep entries scannable, update this index when adding a new top-level doc or moving something to/from archive. Update the [inventory](_inventories/brio-esperanto.md) when a doc's source-status changes (`current` ↔ `stale-needs-update` ↔ `missing`).

---

*Maintained by the Esperanto module agent. If a link 404s, check [`_OLD/`](_OLD/) — the file may have been archived.*
