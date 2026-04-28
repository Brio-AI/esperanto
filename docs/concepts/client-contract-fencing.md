# Client Contract: `<out>` Fencing

**Date:** 2026-04-27
**Status:** Active.
**Pairs with:** [`docs/architecture/fencing-contract.md`](../architecture/fencing-contract.md) — the mechanism. This doc covers the discipline.

## Claim

The `<out>...</out>` envelope around every chat completion returned by `BrioAIFactory` is **not a formatting convention**. It is a versioned production API contract with BrioDocs.

That distinction matters because formatting choices can change with a refactor. API contracts can't.

## Why the distinction matters

The `<out>` fence sits at a layer boundary:

```
Brio-Esperanto (this library)  ───────►  BrioDocs (consumer)
       producer of the fence              extractor of the fence
```

BrioDocs reads the fence to find the content boundary in raw model output. It strips `<out>\n` from the start and `\n</out>` from the end and uses what's left. That extraction logic is hard-coded against the exact shape of the fence.

If anyone in this repo silently changes the fence — different tag name, different whitespace, made optional under some condition — every BrioDocs build that pulls a newer Esperanto submodule pointer will produce broken content with no error. The model still ran, the response still arrived, the JSON still parsed. The text the user sees in their document is just garbage with `<out>` tags scattered through it, or empty, or truncated.

This failure mode is silent because the producer and consumer are two repos owned by the same team. There's no schema check, no version negotiation, no integration test that catches it across the boundary. The contract is the only thing protecting against drift.

## What counts as a breaking change

Anything that changes what BrioDocs's existing extraction code expects to find:

| Change | Breaking? | Why |
|---|---|---|
| Rename to `<output>...</output>` | Yes | Extractor regex won't match. |
| Remove the leading `\n` after `<out>` | Yes | Anything splitting on `\n` to strip the fence loses content. |
| Make the fence conditional (e.g., omit for cloud providers) | Yes | Any consumer that always strips will see dangling text. |
| Allow the LLM to emit fences instead of brio_ext fencing | Yes | Reintroduces the unreliability the `<out>` removal-from-prompts work fixed. |
| Add a second tag inside (e.g., `<out>\n<meta>...</meta>\n{content}\n</out>`) | Yes | Existing extractors capture the meta block as content. |
| Change `_strip_trailing_incomplete_tokens` to leave more cruft | Possibly | Depends on whether BrioDocs sees the cruft as content. |
| Add a *new* response field outside the fence | No | Field is additive. Existing extractors ignore it. |
| Refactor the `_ensure_fence` implementation while preserving output shape | No | Black-box equivalence holds. |

The first five are major-version bumps. The last two are minor or patch.

## What the discipline implies

Three things follow from treating `<out>` as a contract:

### 1. Tests assert the contract directly

`src/brio_ext/tests/integration/test_provider_smoke.py` already asserts that responses are fenced in `<out>...</out>`, the body between fences is non-empty, and the stop reason is sensible. Those assertions are not testing implementation details — they're testing that the contract holds for every provider, end-to-end. The test must stay even when adapters or providers churn underneath.

### 2. Breaking changes need a coordination beat with BrioDocs

A breaking change can't ship as "just merge the PR." The flow is:

1. Cut a major-version Esperanto tag (e.g., `v3.0.0`).
2. The BrioDocs team chooses when to bump the submodule pointer.
3. BrioDocs's extraction logic is updated in the same PR that bumps the pointer.
4. BrioDocs's release process re-runs end-to-end smokes against the new contract.

If steps 3 and 4 are skipped, BrioDocs ships a broken build the moment its CI builds against the new pointer. See [`[[release-tagging-discipline]]`](../operational/release-tagging.md) for the tagging mechanics.

### 3. Provider parity is a contract requirement, not a nicety

Every provider (OpenAI, Anthropic, llamacpp, etc.) must produce the same fence shape. "OpenAI returns un-fenced because we trust its formatting more" is a contract violation, not an optimization. The whole point of brio_ext is that BrioDocs gets one shape regardless of where the response came from.

This is why [`[[adapter-driven-rendering]]`](../architecture/adapter-driven-rendering.md) is structured the way it is: adapters and providers vary; the fence does not.

## Sibling concept

BrioRegistry has the same kind of contract for `briodocs_models.json` and `releases.json` — they look like data files, but they're production APIs that the desktop app consumes live. See `[[client-contract]]` (Registry-owned) for the parallel framing.

The pattern in both cases: an artifact that *looks* internal (a JSON file in a repo, a string envelope in a Python library) is actually a versioned interface across a team boundary. Treating it as internal-only causes silent breakage. Treating it as a contract — with explicit versioning, coordination, and tests — keeps the boundary safe.

## What this doc does NOT do

- It doesn't describe the fence's mechanics. See [`[[fencing-contract]]`](../architecture/fencing-contract.md) for the `_ensure_fence` algorithm, edge cases, and streaming behavior.
- It doesn't enumerate every breaking change scenario. The table above is illustrative, not exhaustive — judgment call lives with the maintainer.
- It doesn't describe BrioDocs's extraction code. That lives in BrioDocs's repo and is owned by the BrioDocs agent.

## Related

- `[[fencing-contract]]` — the mechanism and code-level shape this doc treats as a contract.
- `[[release-tagging-discipline]]` — how breaking changes get coordinated with the BrioDocs submodule consumer.
- `[[briodocs-submodule-integration]]` — the consumer side of the boundary.
- `[[client-contract]]` (BrioRegistry-owned) — sibling concept for JSON-as-API.
- `[[adapter-driven-rendering]]` — why provider parity is structurally enforced, not just culturally expected.
