# Gemma Adapter Restricted to Gemma 4 (Breaking Change)

**Date:** 2026-04-28
**Component:** `brio_ext/adapters/gemma_adapter.py`, `brio_ext/registry.py`
**Ticket:** BRIOPROD-360

## Summary

The Gemma prompt adapter has been rewritten to target the Gemma 4 chat
template (`<|turn>...<turn|>` framing) and renamed `GemmaAdapter` →
`Gemma4Adapter`. Its `can_handle` matcher and the registry's chat-format
key map have been narrowed to Gemma 4 only.

This is a **breaking change** for any caller relying on the previous
adapter being matched on Gemma 2 or Gemma 3 model identifiers.

## What changed

### Adapter matching

| Match path | Before | After |
|---|---|---|
| `can_handle("gemma-4-26b-a4b-it")` | ✅ matched | ✅ matched |
| `can_handle("gemma-2-9b")` | ✅ matched (rendered the wrong format) | ❌ no match |
| `can_handle("gemma-3-27b")` | ✅ matched (rendered the wrong format) | ❌ no match |
| `chat_format="gemma"` | resolved to `GemmaAdapter` | ❌ no match |
| `chat_format="gemma-4"` / `"gemma4"` | n/a | ✅ resolves to `Gemma4Adapter` |

When no adapter matches, `get_adapter()` returns `None` — silent
fallthrough at the call site, not an exception.

### Why Gemma 2/3 are out of scope

The previous `GemmaAdapter` emitted the Gemma 1/2/3 format
(`<start_of_turn>...<end_of_turn>`). Gemma 4 uses an entirely different
chat template with new turn markers, a thinking channel, and a
different stop sequence. Re-using one adapter class for both formats
would mean either:

- silently rendering the wrong format for one generation (the previous
  behaviour for Gemma 4 callers), or
- branching on model id inside a single adapter class — which obscures
  which template is actually being applied.

Splitting them by class is clearer and lets Gemma 5 land alongside
without collision.

BrioDocs does not currently deploy Gemma 2 or Gemma 3, so this PR
ships only the Gemma 4 adapter. If a Gemma 2/3 deployment is added
later, restore the legacy renderer as a separate
`Gemma123Adapter` (or similar) and register it before `Gemma4Adapter`
in `src/brio_ext/registry.py`.

## Migration

If any downstream code (BrioDocs configs, tests, scripts) still does
one of the following, update it:

| Old | New |
|---|---|
| `chat_format="gemma"` | `chat_format="gemma-4"` (only valid for Gemma 4 model IDs) |
| Direct import: `from brio_ext.adapters.gemma_adapter import GemmaAdapter` | `from brio_ext.adapters.gemma_adapter import Gemma4Adapter` |
| Model id like `gemma-2-9b` relying on automatic adapter resolution | Either pin the model to a Gemma 4 variant, or contribute a `Gemma2Adapter`/`Gemma3Adapter` |

No callers inside the Esperanto / `brio_ext` codebase used these
paths at the time of this change.

## Verification

- `uv run pytest src/brio_ext/tests/test_adapters_unit.py` — 43 tests
  pass, including 14 new Gemma 4 tests that render the bundled E4B
  chat template through Jinja2 and assert the adapter produces an
  identical prompt.
- The new `can_handle` test explicitly asserts that `gemma-2-9b` and
  `gemma-3-27b` do **not** match.
