"""Model factory for OrionAI.

Lets developers attach a model directly to an Agent without
configuring the Framework:

    from orionagent import Agent, Model

    agent = Agent(
        name="assistant",
        role="general AI assistant",
        model=Model(provider="gemini", model="gemini-2.0-flash", api_key="..."),
    )

Supported providers (and their keywords):
    provider="gemini"  -- Google Gemini  (requires GEMINI_API_KEY or api_key=)
    provider="openai"  -- OpenAI GPT     (requires OPENAI_API_KEY or api_key=)
    provider="ollama"  -- Local Ollama   (no key needed, base_url= to customise)
"""

from orionagent.models.base_provider import ModelProvider


class Model:
    """Simple factory that creates the right ModelProvider from keywords.

    Args:
        provider: Which LLM backend to use: "gemini", "openai", or "ollama".
        model:    Model name/version (e.g. "gemini-2.0-flash", "gpt-4o-mini").
        api_key:  API key (optional -- falls back to env var if not provided).
        base_url: Custom server URL (mainly for Ollama, default localhost:11434).
    """

    def __new__(
        cls,
        provider: str,
        model: str = None,
        api_key: str = None,
        base_url: str = None,
        temperature: float = None,
        streaming: bool = True,
        verbose: bool = False,
        debug: bool = False,
        thinking: bool = False,
        show_thinking: bool = True,
    ) -> ModelProvider:
        # Build kwargs, only passing values that were explicitly provided
        kwargs = {
            "streaming": streaming,
            "verbose": verbose,
            "debug": debug,
            "thinking": thinking,
            "show_thinking": show_thinking
        }
        if model is not None:
            kwargs["model_name"] = model
        if api_key is not None:
            kwargs["api_key"] = api_key
        if base_url is not None:
            kwargs["base_url"] = base_url
        if temperature is not None:
            kwargs["temperature"] = temperature

        from orionagent.models.provider_registry import get_provider
        return get_provider(provider, **kwargs)
