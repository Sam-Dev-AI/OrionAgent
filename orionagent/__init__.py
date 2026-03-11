"""OrionAI: A minimalistic, multi-agent orchestration framework.

Usage -- single agent:

    from orionagent import Agent, Model

    agent = Agent(
        name="assistant",
        role="assistant",
        model=Model("gemini", "gemini-2.0-flash"),
    )

    for chunk in agent.ask("Explain AI agents"):
        print(chunk, end="", flush=True)

Usage -- multi-agent via Manager:

    from orionagent import Agent, Model, Manager

    manager = Manager(model=Model("gemini", "gemini-2.0-flash"))
    manager.add(Agent(name="researcher", role="research"))
    manager.add(Agent(name="writer",     role="writer"))

    for chunk in manager.ask("Research AI and write a summary"):
        print(chunk, end="", flush=True)
"""

__version__ = "0.1.0"

from orionagent.agents.base_agent import Agent
from orionagent.agents.manager import Manager
from orionagent.tools.base_tool import Tool
from orionagent.models.base_provider import ModelProvider
from orionagent.models.model import Model
from orionagent.models.provider_registry import get_provider, register_provider, list_providers
from orionagent.tools import (
    Tool, ToolExecutor, tool, file_manager, web_browser, system_tools, execute_python, execute_command, default_tools
)
from orionagent.memory import Session, MemoryConfig, JSONStorage, InMemoryStorage, SQLiteStorage
from orionagent import memory
from orionagent.tracing import tracer
from orionagent.agents.handoff import AgentHandoff
from orionagent.agents.guards import logic_guard, is_json, is_polite, contains_keywords, GUARD_REGISTRY
from orionagent.tools.handoff_tool import trigger_handoff
from orionagent.chat import chat

# Import specific providers
from orionagent.models.openai_provider import OpenAIProvider
from orionagent.models.gemini_provider import GeminiProvider
from orionagent.models.ollama_provider import OllamaProvider

__all__ = [
    # Core APIs
    "Agent",
    "Manager",
    "Tool",
    "tool",
    "file_manager",
    "web_browser",
    "system_tools",
    "execute_python",
    "execute_command",
    "Session",
    "MemoryConfig",
    "JSONStorage",
    "InMemoryStorage",
    "SQLiteStorage",
    "memory",
    # Model APIs
    "ModelProvider",
    "Model",
    "OpenAIProvider",
    "GeminiProvider",
    "OllamaProvider",
    # Provider utilities
    "get_provider",
    "register_provider",
    "list_providers",
    # Internals
    "ToolExecutor",
    "default_tools",
    "chat",
    "tracer",
]
