# _OLD — historical / superseded documentation

Files here are kept for historical reference only. **Do not cite as authoritative sources.** Wiki pages and current `docs/` content do not reference these files.

If you find yourself wanting to update something in here, the answer is almost always "write a new doc in `docs/` instead."

| File | Why archived |
|---|---|
| `NEXT_STEPS.md` | Plan from the `<out>`-removal-from-prompts work. Most items have shipped (component-based test system, numbered server selection, adapters with no-`<out>` prompts/stops). The trailing "Architecture Summary" diagram is the seed for the future `[[fencing-contract]]` wiki page; preserve that fragment when authoring the new doc, but the rest is historical. |
| `Brio_Esperanto_implementation_Plan.md` | Initial fork-and-integrate plan from when this repo was being set up as a fork of `lfnovo/esperanto`. Branching strategy, sync cadence, and `bridocs-vX.Y` tag scheme described here have been superseded by current practice (`main` branch, semver tags `vX.Y.Z`). |
| `Brio_Esperanto_git_setup_README.md` | One-time setup notes ("BrioDocs Extension Notes") describing local dev environment for the fork. Useful only for the original integration; current dev setup is documented in `docs/2025-12-20_Developer_Guide.md`. |
| `BRIODOCS_TIERS.md` | Older tier description with `temperature: 0.7` and the original five-models-per-tier framing. Current canonical tier definitions live in `fixtures/briodocs_config.yaml` (which uses `temperature: 0.5` and the seven-model `start_server_v2.sh` matrix); see `docs/brio_ext_integration_v2.md` §9.1. |
