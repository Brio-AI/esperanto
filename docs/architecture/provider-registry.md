# Provider Registry

**Date:** 2026-04-27
**Status:** Active.
**Code:** `AIFactory._provider_modules` + `_import_provider_class` (`src/esperanto/factory.py`), `BrioAIFactory._provider_modules` + `_LANGUAGE_OVERRIDES` + `register_with_factory` (`src/brio_ext/factory.py`).

## What

Esperanto registers 15+ AI providers via a single class-level dictionary, mapping `(service_type, provider_name)` to a *string* identifier of the form `"module.path:ClassName"`:

```python
class AIFactory:
    _provider_modules = {
        "language": {
            "openai":     "esperanto.providers.llm.openai:OpenAILanguageModel",
            "anthropic":  "esperanto.providers.llm.anthropic:AnthropicLanguageModel",
            "google":     "esperanto.providers.llm.google:GoogleLanguageModel",
            # ...13 LLM providers total
        },
        "embedding":     {...},
        "reranker":      {...},
        "speech_to_text":{...},
        "text_to_speech":{...},
    }
```

When `AIFactory.create_language("openai", "gpt-4")` runs, the factory:

1. Looks up `_provider_modules["language"]["openai"]` → gets the `"module:class"` string.
2. Splits on `:` → `("esperanto.providers.llm.openai", "OpenAILanguageModel")`.
3. Calls `importlib.import_module(...)` to load the module *at this moment*.
4. Calls `getattr(module, class_name)` to get the class.
5. Instantiates it with the supplied `model_name` and `config`.

Strings until step 3, code thereafter. The registry never imports a provider module unless a caller actually asks for it.

## Why strings instead of imports

The library declares many providers with heavy optional dependencies:

| Provider | Heavy dep |
|---|---|
| `transformers` (embedding, reranker) | `torch`, `transformers`, optionally `sentence-transformers`, `sklearn` |
| `vertex` (LLM, embedding, TTS) | `google-cloud-aiplatform` |
| `voyage` (embedding, reranker) | `voyageai` |
| `elevenlabs` (TTS, STT) | `elevenlabs` SDK |
| ... |

If `_provider_modules` held actual class references, importing `esperanto.factory` would trigger every provider import — including `torch`, which cold-starts in seconds and fails outright if not installed. A user who only wants `openai` would still pay for `vertex`'s import or, worse, see a hard `ImportError` for a provider they don't use.

Lazy string lookup defers each provider's import until that provider is requested. A caller who only uses OpenAI never imports `torch`. A caller who tries to use `transformers` without installing the extras gets a precise error message naming the missing package.

That precise error happens in `_import_provider_class`:

```python
try:
    module = importlib.import_module(module_name)
    return getattr(module, class_name)
except ImportError as e:
    missing_package = str(e).split("'")[1] if "'" in str(e) else None
    error_msg = f"Provider '{provider}' requires additional dependencies."
    if missing_package:
        error_msg += f" Missing package: {missing_package}."
    error_msg += f"\nInstall with: uv add {missing_package} or pip install {missing_package}"
    raise ImportError(error_msg) from e
```

This means the user sees `Provider 'transformers' requires additional dependencies. Missing package: torch. Install with: uv add torch ...` instead of a raw stack trace from somewhere inside `transformers`'s init.

## How `BrioAIFactory` extends the registry

`BrioAIFactory` (in `src/brio_ext/factory.py`) adds two providers (`llamacpp`, `hf_local`) that aren't part of upstream Esperanto. It does so by extending the class-level dict at class-creation time:

```python
_LANGUAGE_OVERRIDES = {
    "llamacpp": "brio_ext.providers.llamacpp_provider:LlamaCppLanguageModel",
    "hf_local": "brio_ext.providers.hf_local_provider:HuggingFaceLocalLanguageModel",
}

class BrioAIFactory(AIFactory):
    _provider_modules = deepcopy(AIFactory._provider_modules)
    _provider_modules["language"] = {
        **AIFactory._provider_modules["language"],
        **_LANGUAGE_OVERRIDES,
    }
```

Two things happen here:

1. **`deepcopy`** of the parent's `_provider_modules`. This gives `BrioAIFactory` a fully independent copy — mutating `BrioAIFactory._provider_modules["embedding"]` later won't leak into `AIFactory`.
2. **Explicit re-merge of `"language"`**. The new language sub-dict is built from `parent_language` + `_LANGUAGE_OVERRIDES`, with overrides winning on key collisions. (None currently collide; the structure is set up so they could.)

The deepcopy is technically belt-and-suspenders for the current code (nothing mutates the dict in place after class creation). But it makes the inheritance robust to anyone who, in the future, adds an in-place mutation — sub-class mutations can never leak upward into Esperanto-only consumers. That isolation is part of the same separation-of-concerns the library follows everywhere else (see [`[[adapter-driven-rendering]]`](adapter-driven-rendering.md) for the rendering equivalent).

The result: anywhere the parent class is used (`from esperanto.factory import AIFactory`), only the upstream providers are visible. Anywhere `BrioAIFactory` is used, both upstream providers AND `llamacpp`/`hf_local` are visible. No global mutation, no monkey-patching at runtime.

## `register_with_factory` — the legacy alternative

For code that already had its own `AIFactory` subclass before brio_ext existed, there's a runtime patch path:

```python
from esperanto.factory import AIFactory
from brio_ext.factory import register_with_factory

register_with_factory(AIFactory)
# AIFactory.create_language now applies brio_ext rendering and fencing,
# but the provider registry itself is untouched.
```

What `register_with_factory` actually does: monkey-patches `AIFactory.create_language` to wrap the result with brio_ext's adapter dispatch and fencing. **It does not extend the provider registry** — `llamacpp` and `hf_local` are still only available via `BrioAIFactory`.

This is intentional. New code should always use `BrioAIFactory` directly. `register_with_factory` exists only to support a couple of pre-brio_ext call sites that haven't migrated yet.

## When the registry is consulted

Once per `create_*` call:

```
BrioAIFactory.create_language("llamacpp", "qwen2.5-7b-instruct", config={...})
   → _import_provider_class("language", "llamacpp")
      → look up _provider_modules["language"]["llamacpp"]
      → importlib.import_module(...) (first call only — cached by Python's import system)
      → getattr(module, "LlamaCppLanguageModel")
   → LlamaCppLanguageModel(model_name=..., config={...})
   → _wrap_language_model(model, ..., chat_format=...)  # brio_ext adapter dispatch
   → return wrapped model
```

After the first call to a given `(service, provider)`, the underlying module is in `sys.modules` and subsequent lookups are essentially free. The registry-as-strings cost is paid exactly once per process per provider used.

## Adding a new provider

Three steps, no factory subclassing required:

1. **Create the class** in `src/esperanto/providers/{service_type}/{provider_name}.py`. Subclass the base class for that service type (`LanguageModel`, `EmbeddingModel`, etc.) and implement the required hooks. See [`docs/2025-12-20_Developer_Guide.md`](../2025-12-20_Developer_Guide.md) Adding a New Provider.
2. **Register the string** in `_provider_modules[service_type]` in `src/esperanto/factory.py`.
3. **Add tests** under `tests/providers/{service_type}/test_{provider}_provider.py`. Mock `httpx.Client` / `httpx.AsyncClient`; assert response normalization to standard shape.

That's it for cloud providers. Local-model providers that need adapter dispatch also belong to `BrioAIFactory._LANGUAGE_OVERRIDES` and the `PROMPT_PROVIDERS` set in [`adapter-driven-rendering.md`](adapter-driven-rendering.md).

## Adding a new service type

Less common, but possible. Service types are top-level keys in `_provider_modules` (`"language"`, `"embedding"`, `"reranker"`, `"speech_to_text"`, `"text_to_speech"`).

To add e.g. `"image_generation"`:

1. Add a base class in `src/esperanto/providers/image_generation/base.py` (analogous to `LanguageModel`).
2. Add `"image_generation": {...}` to `_provider_modules` in `src/esperanto/factory.py`.
3. Add a `create_image_generation` classmethod to `AIFactory` (and `BrioAIFactory`'s deepcopy will pick it up automatically).
4. Implement at least one provider for the new service type.

The dictionary structure makes service types as cheap to add as providers, but the factory method (`create_image_generation`) needs to be added explicitly — the dict alone isn't enough.

## What this design does NOT do

- **No plugin discovery.** Providers are not auto-loaded from entry points. Adding a provider requires a code change to `factory.py`. This is a deliberate trade-off: explicit registration means the canonical provider list is git-trackable in one place.
- **No runtime registration API.** There's no `AIFactory.register("newprovider", "...")` method. Mutating the class-level dict at runtime would create state ordering bugs depending on import order.
- **No version pinning per provider.** Provider deps live in `pyproject.toml` extras (`[transformers]`, `[google]`, etc.), not in the registry.
- **No fallback / failover.** If `openai` is unavailable, `_import_provider_class` raises. Consumers that want failover (e.g., "use Claude if GPT is down") implement that at the call-site level, not in the factory.

## Related

- `[[esperanto-core-library]]` — the upstream package whose registry this is.
- `[[brio-ext-extension-package]]` — the extension layer that uses `deepcopy` to extend the registry without touching upstream.
- `[[adapter-driven-rendering]]` — the *other* brio_ext extension point; together they keep the cloud and local code paths cleanly separated.
- `[[adding-a-new-provider]]` — the operational walkthrough for the three-step add.
