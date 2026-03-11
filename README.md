# 🌌 OrionAI

<div align="center">

![OrionAI Banner](https://img.shields.io/badge/OrionAI-The%20Sovereign%20Multi--Agent%20Framework-blueviolet?style=for-the-badge)

**A minimalistic yet industrially robust multi-agent orchestration framework. Precision-engineered for memory persistence, logic validation, and autonomous self-correction.**

[![PyPI version](https://img.shields.io/badge/pypi-v0.4.0-blue.svg)](https://pypi.org/project/orionagent/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[Quick Start](#-quick-start) • [Architecture](#-architecture-blueprints) • [Features & Variables](#-features--core-variables) • [OrionAI vs Others](#-orionagent-vs-langchain--autogen) • [Agent Guide](#-the-agent-api)

</div>

---

## 🔥 Why OrionAI?

OrionAI is built for developers who need **absolute control** over agent behavior without the overhead of heavy abstractions. It combines the simplicity of a micro-framework with advanced features like **token-efficient system instructions**, **hierarchical summarization memory**, and **deterministic logic guards**.

### 🌟 Sovereign Features
- **🛡️ Deterministic Guards**: Enforce JSON schemas, tone, or length before a response leaves the agent.
- **🤖 Autonomous Orchestration**: Swap between structured `Planning` and recursive `Self-Learn` loops.
- **💾 Strategic Memory**: Hierarchical pipelines that distill conversations into long-term SQLite knowledge.
- **⚡ Token Optimization**: Persistent system instructions for Gemini/OpenAI save thousands of context tokens.
- **🔌 Multi-Provider Native**: First-class support for **Gemini 2.0**, **GPT-4o**, and **Local Ollama**.

---

## 🏗️ Architecture Blueprints

OrionAI's architecture is designed to be highly modular, separating the LLM intelligence engine from the orchestration, memory, and tooling layers.

```text
┌────────────────────────────────────────────────────────┐
│                 User Application / Goal                │
└───────────────────────────┬────────────────────────────┘
                            │ 1. Submits Task
┌───────────────────────────▼────────────────────────────┐
│ 👔 MANAGER LAYER (Orchestration)                       │
│                                                        │
│  [Strategy Engine]  ──────────▶  [Agent Dispatcher]    │
│  (Planning & Self-Learn)         (Routes sub-tasks)    │
└───────────────────────────┬────────────────────────────┘
                            │ 2. Delegates
┌───────────────────────────▼────────────────────────────┐
│ 🤖 AGENT CORE (Execution & Validation)                 │
│                                                        │
│  [Logic Guards]     ──────────▶  [Tool Registry]       │
│  (Enforces Format/Tone)          (Web/Terminal/Files)  │
└─────────────────┬──────────────────────┬───────────────┘
                  │ 3. Prompts Model     │ 4. Reads/Writes State
┌─────────────────▼────────┐  ┌──────────▼───────────────┐
│ 🧠 INTELLIGENCE TIER     │  │ 💾 STATE & MEMORY TIER   │
│                          │  │                          │
│  • Cloud: Gemini/GPT-4   │  │  • Session RAM (Short)   │
│  • Local: Ollama Native  │  │  • SQLite DB (Long-term) │
└──────────────────────────┘  └──────────────────────────┘
```

---

## 🥊 OrionAI vs LangChain & AutoGen

Why choose OrionAI over the established giants? OrionAI is built to eliminate the "black box" feeling of modern agent frameworks.

| Feature / Philosophy | 🌌 OrionAI | 🦜🔗 LangChain | 🤖 AutoGen |
| :--- | :--- | :--- | :--- |
| **Abstractions** | **Minimalist & Explicit.** You know exactly what is happening under the hood. No hidden prompted API calls. | **Heavy.** Deeply nested abstractions that can make debugging difficult. | **Complex.** Highly capable but involves a steeper learning curve for simple tasks. |
| **Output Control** | **Deterministic Logic Guards.** If an agent returns bad JSON or the wrong tone, it self-corrects internally before the user ever sees it. | Relies heavily on complex output parsers which can silently fail. | Focuses on multi-agent conversation rather than strict output shaping. |
| **Memory System** | **Built-in Hierarchical.** Seamlessly cascades from short-term context to long-term SQLite databases via automated summarization. | Requires manual wiring of memory classes (e.g., `ConversationBufferMemory`). | Basic persistent memory; advanced summarization needs custom implementation. |
| **Use Case** | Teams that want **production-ready reliability**, fast setup, and zero magic. | Connecting massive chains of various tools and data sources. | Complex multi-agent simulations and coding tasks. |

---

## 🚀 Quick Start

### 🔌 Complete Installation
OrionAI requires Python 3.8+. Optimized for asynchronous streaming and tool execution.

```bash
pip install orionagent
```

### 🏁 10-Second Example: Detailed Single Agent
```python
from orionagent import Agent, Model, default_tools

# 1. Choose your brain
llm = Model(provider="gemini", model="gemini-2.0-flash")

# 2. Configure your agent
researcher = Agent(
    name="Vanguard",
    role="Senior Research Analyst",
    system_instruction="Provide objective, source-backed data.",
    model=llm,
    guards=["straight", "short"], # Logic Guards force specific output formats
    use_default_tools=True        # Auto-load Terminal, Web, and Files tools
)

# 3. Ask and Stream
response = researcher.chat("Summarize the current state of Solid State Batteries.")
print(response)
```

---

## ⚙️ Features & Core Variables

When building with OrionAI, you will primarily interact with the `Agent`, `Manager`, and `Model` classes. Here are the core variables and features you should know:

### 👤 1. The Agent Class (`orionagent.Agent`)
The fundamental worker unit. It takes instructions, executes tools, and guarantees output quality.
* **`name`** *(str)*: A unique identifier for the agent (e.g., `"Coder"`). Crucial for multi-agent logging.
* **`role`** *(str)*: Defines the agent's persona (e.g., `"Python Software Engineer"`).
* **`model`** *(Model Option)*: The language model instance parsing the tasks.
* **`system_instruction`** *(str)*: Base rules the agent must always follow. Optimized continuously.
* **`guards`** *(List[str])* [Optional]: Enforces output schemas. Available built-ins: `"json"`, `"straight"`, `"short"`, `"long"`, `"polite"`, `"happy"`.
* **`use_default_tools`** *(bool)* [Optional]: Set to `True` to give the agent Web Browsing, File Manipulation, and Terminal access immediately. Default: `False`.
* **`tools`** *(List[Callable])* [Optional]: A list of custom Python functions decorated with `@tool`. You can easily bind your own backend APIs to the agent.
* **`memory`** *(str or MemoryConfig)* [Optional]: How the agent remembers. Options: `"none"`, `"session"`, `"long_term"`. Default: `"session"`.
* **`max_refinements`** *(int)* [Optional]: How many times the agent is allowed to self-correct upon hitting a Logic Guard failure. Default: `2`.
* **`verbose`** *(bool)* [Optional]: If `True`, the agent prints detailed execution logs including active tool calls, reasoning steps, and token counts constraints to the terminal. Default: `False`.

### 👔 2. The Manager Class (`orionagent.Manager`)
The orchestrator. It receives a high-level goal, devises a plan, and delegates tasks to `Agents`.
* **`model`** *(Model Option)*: The manager's personal LLM used strictly for planning and strategy.
* **`agents`** *(List[Agent])* [Optional]: The team of specialized agents the manager can dispatch tasks to.
* **`strategy`** *(str)* [Optional]: Dictates how the manager handles goals. 
  * `"planning"`: Creates a step-by-step checklist and executes it linearly.
  * `"self-learn"`: Dynamically iterates, evaluates agent outputs, and corrects course until the goal is fully achieved.
* **`system_instruction`** *(str)* [Optional]: Instructions solely for the Manager to dictate overall team management.

### 🧠 3. The Model Class (`orionagent.Model`)
A unified interface wrapper for different LLM providers.
* **`provider`** *(str)*: Defines the AI engine. Supported: `"gemini"`, `"openai"`, or `"ollama"`.
* **`model`** *(str)*: The specific model string (e.g., `"gemini-2.0-flash"`, `"gpt-4o"`, `"qwen2.5-coder"`).

---

## 🛰️ Advanced Capabilities

### Multi-Agent Handoffs
Agents can autonomously pass control to others. The Manager detects these handoffs and re-routes the task with all context history securely intact.

```python
from orionagent.tools import trigger_handoff

# Agent code triggering a handoff:
return trigger_handoff(
    target_agent="Coder", 
    task="Fix the bug in main.py",
    brief="Found a syntax error on line 42.",
    state_json='{"file": "main.py", "line": 42}'
)
```

### 🧠 Hierarchical Memory System
OrionAI features a deeply integrated, highly configurable memory pipeline to ensure your agents maintain context without overflowing their token limits.

#### How It Works:
1. **Short-Term Buffer (`"session"`)**: Retains the exact, raw back-and-forth turns of the current task in RAM.
2. **Summarization Pipeline**: When the session hits a predefined token limit, a background LLM process pauses to summarize the oldest messages.
3. **Long-Term Storage (`"long_term"`)**: Extracted facts, user preferences, and critical context are saved permanently into a local **SQLite Database** (`memory.db`) or a **JSON File**. 
4. **Vector Injection**: When a new task matches historical context, those facts are automatically injected into the system prompt.

#### Memory Configurations (`MemoryConfig`):
You can deeply customize this behavior rather than using the default string handles:

```python
from orionagent import Agent, Model
from orionagent.memory import MemoryConfig

advanced_memory = MemoryConfig(
    memory_type="long_term",
    storage_type="sqlite",       # 'sqlite' or 'json'
    max_turns=10,                # Starts summarization after 10 turns
    user_id="user_123",          # Isolate memory context per user
    storage_path="./agent_db/"   # Custom directory for the DB files
)

agent = Agent(name="Recall", role="Assistant", model=Model("openai", "gpt-4o"), memory=advanced_memory)
```

---

## 📂 Project Structure
```text
OrionAI/
├── orionagent/
│   ├── agents/          # Orchestration: BaseAgent, Manager, Strategies, Guards
│   ├── models/          # Providers: OpenAI (GPT), Gemini (Google), Ollama (Local)
│   ├── memory/          # State: Pipeline, SQLiteStorage, JSONStorage, Session
│   ├── tools/           # Execution: Web, Terminal, Files, Python Sandbox
│   └── tracing.py       # Observability: Performance & Token Tracing
├── examples/            # Ready-to-use boilerplate (Memory, Multi-Agent)
└── test/                # Comprehensive test suite (Pytest)
```

---

## 🛣️ Roadmap & Vision
OrionAI is actively evolving to balance capability with its minimalist philosophy.
- [ ] **Native Vector Embeddings**: Direct integration with ChromaDB/Qdrant for mass-scale semantic search.
- [ ] **Observability Dashboard**: A local web UI to visualize real-time handoffs, tool execution latency, and strategy flows.
- [ ] **Streaming JSON Validation**: Validating output formatting byte-by-byte as the LLM streams it.
- [ ] **Human-in-the-Loop (HITL)**: Built-in pause/resume states requiring human approval before critical tool executions natively.
- [ ] **Async Multi-Agent Clusters**: True parallel execution where multiple agents work on independent sub-tasks simultaneously before merging.

**Contributing:** We value every PR. See [CONTRIBUTING.md](CONTRIBUTING.md) for architectural guidelines.

## ⚖️ License & Contact
Released under the **MIT License**. Created by [Samir Lade](mailto:ladesamir10@gmail.com).

<div align="center">

**OrionAI: Build Agents That Actually Work.**

</div>
