# Tier-Based Server Config

**Date:** 2026-04-27
**Status:** Active.
**Code:** `fixtures/briodocs_config.yaml` (the canonical tier definitions), `scripts/start_server_v2.sh` (the launcher that consumes them), `[[brio_ext_integration_v2]]` `docs/brio_ext_integration_v2.md` §9.1 (operational reference).

## What

Local llama.cpp setup is split into two orthogonal axes:

- **Tier** defines *how* to run the server: context window, GPU layers, threads, memory locking. Hardware-dependent.
- **Model** defines *what* to run: which GGUF file, which chat format. Independent of hardware.

The launcher takes one of each:

```bash
./scripts/start_server_v2.sh --tier 2 --model 1
# Tier 2 (4K context, GPU)  with Model 1 (Qwen 2.5 7B Instruct)
```

Three tiers × seven models = twenty-one valid combinations. The tier and model are picked separately because they answer different questions.

## Why the split

The earlier `start_server.sh` baked tier and model together — separate scripts per tier with hardcoded models. Adding a new model meant editing three scripts; running an existing model under a different tier meant editing whichever script was closest. The coupling encoded a false assumption: that model choice and hardware capability are linked. They aren't.

Hardware capability changes at deployment time:
- A developer on a 16GB MacBook Pro runs Tier 1 (8K context, GPU).
- The same code on an 8GB customer machine runs Tier 2 (4K context, GPU).
- A CI runner without a GPU runs Tier 3 (2K context, CPU-only).

Model choice changes at task time:
- "Use Qwen 2.5 7B" — the team's all-rounder default.
- "Use Phi-4 Reasoning for chain-of-thought tasks."
- "Try Llama 3.1 8B for that flow that's broken on Qwen."

The two questions are independent. Splitting them in the launcher means each axis can be selected without disturbing the other. A developer testing a new model under their Tier 1 environment uses `--tier 1 --model <new>`. A CI job validating the same model on minimal hardware uses `--tier 3 --model <new>`.

## The three tiers

Defined in `fixtures/briodocs_config.yaml`:

| Tier | Name | Context | GPU layers | Use case | Reranking candidates |
|---|---|---|---|---|---|
| 1 | High Performance | 8192 | -1 (all) | Development, research, max quality | 5 (with reranking) |
| 2 | Balanced | 4096 | -1 (all) | Production, most users | 3 |
| 3 | Fast | 2048 | 0 (CPU only) | Low-resource, quick testing | 1 (no reranking) |

All three use `use_mlock: true` and `n_threads: 8`. The two real differences are context window and GPU layer count.

The `candidate_count` field is consumed by BrioDocs at the application level — it's the number of completions BrioDocs requests for reranking. Esperanto and brio_ext don't see this; they handle individual requests. But the field lives in the same YAML so the BrioDocs app and the local server share one source of truth.

## The seven models

Defined in `start_server_v2.sh`:

| Model # | Name | Size | Chat format |
|---|---|---|---|
| 1 | Qwen 2.5 7B Instruct | ~4.4 GB | `chatml` |
| 2 | Qwen 2.5 3B Instruct | ~2.0 GB | `chatml` |
| 3 | Llama 3.1 8B Instruct | ~4.9 GB | `llama-3` |
| 4 | Llama 3.2 3B Instruct | ~2.0 GB | `llama-3` |
| 5 | Mistral 7B Instruct v0.3 | ~4.4 GB | `mistral-instruct` |
| 6 | Phi-4 Mini Instruct | ~2.7 GB | `chatml` |
| 7 | Phi-4 Reasoning | ~3 GB | `chatml` |

The chat format ties into the [`[[chat-adapter-system]]`](../_inventories/brio-esperanto.md) — when brio_ext runs a request against one of these, the model's chat format selects the adapter (or it's overridden by an explicit `chat_format` in the call config; see `[[adapter-driven-rendering]]`).

## What the cross product implies

Because tier and model are orthogonal, every (tier, model) pair is meant to work — but not every pair is *productive*:

- **Tier 1 + any model**: maximum quality. Best for development.
- **Tier 2 + 7B-class models**: production-equivalent.
- **Tier 3 + 7B-class models**: works but slow; reasoning tasks may exceed budget.
- **Tier 3 + Phi-4 Reasoning**: slow to the point of failure (reasoning needs more than 2K context). The integration doc explicitly warns against this combination.
- **Tier 3 + 3B-class models**: appropriate for CPU-only environments.

The launcher doesn't enforce productive pairings — it lets you run any combination so you can verify behavior at your tier of interest. Productivity is a runtime concern, not a configuration concern.

## How tier choice cascades into application behavior

Tier doesn't only configure the llama.cpp server. It also informs application-level decisions in BrioDocs:

- **`no_think` default**: at Tier 2/3, the token budget is too tight for a reasoning block plus an answer. BrioDocs sets `no_think=True` on reasoning-capable models when running at those tiers. See [`[[no-think-mode]]`](no-think-mode.md).
- **Candidate count**: 5 → 3 → 1 across Tiers 1/2/3, as above.
- **`max_tokens` budget**: the standard `model_parameters` block in the YAML sets `max_tokens: 512`. The application can override per-call (e.g., `1024` for the `reasoning` test scenario), but the default holds across tiers.
- **Stream vs. non-stream**: `stream: false` by default. Tier doesn't change this; the application chooses streaming based on the consumer surface (chat UI vs. batch processing).

Together: tier captures *server* behavior, application config captures *call-site* behavior, and the two are intentionally decoupled. The shared YAML keeps them aligned without coupling them.

## What "tier" does NOT mean

- **Not a quality ranking.** Tier 3 isn't "lower-quality output." It's lower-resource server settings. With a 7B model and a small prompt, Tier 3 produces the same quality as Tier 1; it just runs slower and truncates earlier.
- **Not a model class.** Tier doesn't bind to model size. You can run Phi-4 Mini (2.7GB) at Tier 1, or Qwen 2.5 7B (4.4GB) at Tier 3.
- **Not a provider.** Tier only describes the local llama.cpp server. Cloud providers (OpenAI, Anthropic) don't have tiers — their server-side configuration is theirs.
- **Not a temperature setting.** Sampling parameters (temperature, top_p, top_k) live in `model_parameters`, separate from tiers, and apply to all tiers equally.

## Why BrioDocs reads the same config

`fixtures/briodocs_config.yaml` is the source of truth for both ends:

- The **local server** (started by `scripts/start_server_v2.sh`) reads the tier's `server_config` to set llama.cpp flags.
- The **BrioDocs application** reads the tier's `candidate_count`, `use_case`, and the shared `model_parameters` to set up its request loop.

If these were two separate configs, drift would accumulate. The local server's max context might say 8K while the application's prompt budget assumes 4K, and you'd get silent truncation server-side. Sharing the YAML means changing a tier propagates to both consumers.

This shared-config approach is also why the v2 launcher exists. The earlier scripts encoded tier settings in shell variables — fine for the server side, useless to the BrioDocs app. v2's flow is "YAML is canonical; launcher reads it; app reads it; no encoding lives only in shell scripts."

## Adding a new tier or model

**New tier**: add a `tierN` block under `tiers:` in `briodocs_config.yaml` with `name`, `description`, `candidate_count`, `use_case`, and `server_config`. Add a case branch to `start_server_v2.sh`. The application picks it up by name.

**New model**: add a `case` branch in `start_server_v2.sh` mapping the model number to the `MODEL_FILE` and `CHAT_FORMAT`. Optionally add an entry to `chat_formats:` in the YAML so the application can look up the format string by model identifier. If the model uses a chat template not yet supported by an adapter, also add a new adapter (see [`[[chat-adapter-system]]`](../_inventories/brio-esperanto.md)).

The launcher CLI is the structural choice that makes both additions cheap. Without the orthogonal axes, adding a model would mean editing three tier-specific scripts; adding a tier would mean editing seven model-specific scripts. The split keeps the additions O(1) instead of O(n).

## Related

- `[[llamacpp-server-tiers]]` — the operational reference (canonical source: `docs/brio_ext_integration_v2.md`).
- `[[no-think-mode]]` — application behavior that depends on tier (Tier 2/3 → `no_think=True` default for reasoning models).
- `[[chat-adapter-system]]` — what the model's `chat_format` ties into.
- `[[adapter-driven-rendering]]` — why the chat format matters at request time.
- `[[hardware-tiers]]` (BrioDocs-owned, when authored) — the consumer-facing tier abstraction.
