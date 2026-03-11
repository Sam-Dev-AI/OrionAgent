"""Provider registry for OrionAI.

Lets the framework load model providers by name so developers
can write `model_provider="gemini"` instead of importing and
instantiating provider classes manually.

Register a custom provider:
    from orionagent import register_provider
    register_provider("my_llm", MyProvider)
"""

from typing import Dict, Optional, Type
from orionagent.models.base_provider import ModelProvider

_PROVIDERS: Dict[str, Type[ModelProvider]] = {}


def _register_builtins() -> None:
    """Lazily register the providers that ship with OrionAI."""
    try:
        from orionagent.models.gemini_provider import GeminiProvider
        _PROVIDERS["gemini"] = GeminiProvider
    except Exception:
        pass

    try:
        from orionagent.models.openai_provider import OpenAIProvider
        _PROVIDERS["openai"] = OpenAIProvider
    except Exception:
        pass

    try:
        from orionagent.models.ollama_provider import OllamaProvider
        _PROVIDERS["ollama"] = OllamaProvider
    except Exception:
        pass


def register_provider(name: str, cls: Type[ModelProvider]) -> None:
    """Register a custom provider class under *name*."""
    _PROVIDERS[name] = cls


def get_provider(name: str, **kwargs) -> ModelProvider:
    """Instantiate and return a provider by its registered name.

    Extra keyword arguments are forwarded to the provider constructor
    (e.g. ``api_key``, ``model_name``, ``base_url``).

    Raises:
        ValueError: If the provider name is not registered.
    """
    if not _PROVIDERS:
        _register_builtins()

    cls = _PROVIDERS.get(name)
    if cls is None:
        available = ", ".join(_PROVIDERS.keys()) or "(none)"
        raise ValueError(
            f"Unknown provider '{name}'. Available: {available}"
        )
    return cls(**kwargs)


def list_providers() -> list:
    """Return a list of all registered provider names."""
    if not _PROVIDERS:
        _register_builtins()
    return list(_PROVIDERS.keys())
