# Release Tagging Discipline

**Date:** 2026-04-27
**Status:** Active.
**Code:** `pyproject.toml` (version field), `.claude/commands/esperanto-release.md` (the `/esperanto-release` slash command), GitHub Actions workflow (auto-publishes tagged releases to PyPI).

## What

Brio-Esperanto follows semver and ships every release as a git tag. BrioDocs consumes this repo as a git submodule and pins to specific tags — that's what makes BrioDocs builds reproducible. The discipline this implies: **every tag is a frozen API surface**. Breaking changes require coordination with the BrioDocs team before BrioDocs bumps its submodule pointer.

This is the operational counterpart to [`[[client-contract-fencing]]`](../concepts/client-contract-fencing.md) — that doc names the fence as a contract; this doc covers the version-management discipline that makes the contract enforceable.

## The release flow

The `/esperanto-release` slash command (`.claude/commands/esperanto-release.md`) automates the mechanical steps:

1. **Bump version in `pyproject.toml`.** Major / minor / patch per semver.
2. **`uv sync --all-extras`.** Updates `uv.lock` to match the new version state across all extras (`dev`, `transformers`, etc.).
3. **Commit both files.** `pyproject.toml` and `uv.lock` go in the same commit so the lockfile stays in sync with the version.
4. **Push to `main`.** Merge directly; release commits don't need their own PR.
5. **Tag.** `git tag vX.Y.Z` matching the new version.
6. **Push the tag.** `git push origin vX.Y.Z`.
7. **Create a GitHub release.** Via `gh release create`. Triggers a GitHub Actions workflow that publishes to PyPI.

Manual flow (when not using the slash command) is the same seven steps. The slash command exists because forgetting `uv.lock` in step 3 — the most common mistake — causes a downstream lockfile mismatch when consumers `uv sync`.

## What counts as a major / minor / patch

| Change type | Bump | Examples |
|---|---|---|
| **Breaking** — anything BrioDocs's existing code can fail against | Major (`X.Y.Z` → `(X+1).0.0`) | Renaming the `<out>` fence shape; removing a provider; changing `ChatCompletion` field types; removing the `no_think` parameter; reordering positional args on `chat_complete`. |
| **Additive** — new capability without changing existing surface | Minor (`X.Y.Z` → `X.(Y+1).0`) | Adding a new provider; adding a new adapter; adding a new optional kwarg with a safe default; adding a new field to a response model that consumers don't have to read. |
| **Bug fix** — behavior corrected, no contract change | Patch (`X.Y.Z` → `X.Y.(Z+1)`) | Fixing the streaming fence-extraction (commit 1855de0 in 2.8.0); correcting an env-var name in docs without changing the actual var; fixing a provider's response normalization to better match the standard shape. |

The hard cases are usually around what counts as additive. Two heuristics:

- **If a BrioDocs build pinned to the *previous* tag would still work after the change, it's not breaking.** New methods, new optional kwargs, new providers — fine. Renamed methods, removed kwargs, changed defaults — breaking.
- **If a consumer's existing extraction code can fail, it's breaking.** This is mostly the `[[fencing-contract]]` and the `ChatCompletion` shape. Changes there require a major bump even when they look additive.

When in doubt, prefer the higher bump. Going from 2.7.1 → 3.0.0 is cheap if the change is actually additive (consumers ignore the major bump). Going from 2.7.1 → 2.8.0 when the change is breaking is expensive (consumers ship broken builds).

## Coordination beat with BrioDocs

Major version bumps trigger a coordination beat. The flow is:

1. **Cut the major-version tag in Esperanto.** `git tag v3.0.0`.
2. **Notify the BrioDocs team.** Slack, GitHub issue, whatever the team uses for cross-repo coordination. Message includes (a) what changed, (b) what BrioDocs needs to update, (c) a link to the changelog or commit list.
3. **BrioDocs updates extraction code.** In a PR that *also* bumps the submodule pointer to the new tag.
4. **BrioDocs's CI re-runs.** End-to-end smokes verify the new contract holds.
5. **Only then does the BrioDocs PR merge.** Submodule bumps and contract updates ship together — never a submodule bump alone, never a contract update without the submodule pointing at a version that supports it.

The `<out>...</out>` fence is the most common source of major bumps in practice — and the only case where forgetting the coordination beat causes silent runtime breakage rather than a build failure. See [`[[client-contract-fencing]]`](../concepts/client-contract-fencing.md) for why "silent" is the load-bearing word.

Minor and patch bumps don't need the beat. BrioDocs can update the submodule pointer at any time after the new tag is pushed.

## What lives at each version

The version is stamped in two places that must stay in sync:

- `pyproject.toml` — the canonical version. Read by `uv build`, `pip install`, and PyPI.
- `uv.lock` — derived. Updated by `uv sync --all-extras`.

The `/esperanto-release` slash command updates both. Editing `pyproject.toml` by hand without re-running `uv sync` produces an inconsistent state — a fresh `uv sync` on a downstream machine will fail or update the lockfile in a way that doesn't match what was tagged. Always run `uv sync --all-extras` after a manual version bump.

The `version` field is *not* derived from git tags. It's a hand-edited field in `pyproject.toml`. The git tag is added *after* the version is bumped and committed. They have to match — both are inputs to PyPI publish, and a mismatch causes the GitHub Action to publish under the wrong name.

## What `/esperanto-release` automates

The slash command bundles the seven-step manual flow above into one invocation. Specifically:

- Forces `uv sync --all-extras` so the lockfile is always updated.
- Reminds you to commit `uv.lock` along with `pyproject.toml` (the most common mistake).
- Doesn't decide the bump for you — you supply the new version explicitly. The skill won't auto-pick major/minor/patch because that decision needs the table above, not heuristics.

The slash command is an aid, not a guarantee. It can't enforce the coordination beat for major bumps, and it can't tell whether your change is breaking. Both still require human judgment.

## What this doc does NOT cover

- **PyPI publishing internals.** The GitHub Actions workflow auto-publishes on tag push. Configuration of the workflow itself lives in `.github/workflows/`, not here.
- **BrioDocs-side submodule update flow.** That's owned by the BrioDocs agent and lives in `[[briodocs-submodule-integration]]` (BrioDocs side, when authored).
- **Pre-release tags.** `v3.0.0-rc1` and similar aren't currently used. If they get adopted, this doc needs an addendum on candidate-tag conventions.
- **Yanking releases.** PyPI `yank` is available but not currently documented as a flow; if a tagged release ever ships with a regression that requires a yank, document the procedure here.

## Related

- `[[client-contract-fencing]]` — the discipline this enables.
- `[[fencing-contract]]` — the most common source of major bumps.
- `[[briodocs-submodule-integration]]` — the consumer-side flow that this discipline coordinates with.
- `[[provider-registry-pattern]]` — provider additions are minor bumps; provider removals are major.
- `[[brio-esperanto]]` — the repo this discipline applies to.
