# OrionAI

<div align="center">

**A minimalistic yet industrially robust multi-agent orchestration framework. Precision-engineered for memory persistence, logic validation, and autonomous self-correction.**

[![PyPI version](https://img.shields.io/badge/pypi-v0.4.0-blue.svg)](https://pypi.org/project/orionagent/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[Quick Start](#quick-start) • [Architecture](#architecture-blueprints) • [Memory System](#memory-tier-deep-dive) • [Orchestration](#orchestration-strategies) • [OrionAI vs Others](#orionagent-vs-langchain--autogen)

</div>

---

## Why OrionAI?

OrionAI is designed to eliminate the "black box" complexity of modern agent frameworks. It provides a low-abstraction, high-control environment for building agents that are **token-efficient**, **persistent by default**, and **deterministic via logic guards**.

### Sovereign Features
- **Deterministic Guards**: Enforce JSON schemas, tone, or length before a response leaves the agent.
- **Autonomous Orchestration**: Multi-strategy engine supporting structured Planning and recursive Self-Learning.
- **Strategic Memory**: Hierarchical pipelines that distill conversations into long-term SQLite knowledge.
- **Token Optimization**: Native provider system instructions and shared context pruning.
- **Multi-Provider Native**: First-class support for Gemini 2.0, GPT-4o, and Local Ollama (Qwen2.5/Llama3).

---

## Architecture Blueprints

The framework is built on a decoupled architecture that separates intent (Manager) from execution (Agent) and state (Memory).

### System Data Flow
```text
[ USER GOAL ] 
      │
      ▼
┌───────────────────┐      ┌──────────────────────────┐
│ MANAGER           │◄────▶│ ORCHESTRATION STRATEGY   │ (Planning / Self-Learn)
│ (The Orchestrator)│      └──────────────────────────┘
└─────────┬─────────┘
          │ (Delegates Sub-Tasks)
          ▼
┌───────────────────┐      ┌──────────────────────────┐
│ AGENT             │◄────▶│ TOOL REGISTRY            │ (Web, Python, Terminal)
│ (The Worker)      │      └──────────────────────────┘
└─────────┬─────────┘
          │ (Validation Loop)
          ▼
┌───────────────────┐      ┌──────────────────────────┐
│ LOGIC GUARDS      │─────▶│ MEMORY TIER              │ (Session / SQLite)
│ (The Feedback)    │      └──────────────────────────┘
└───────────────────┘
```

---

## Quick Start

### 10-Second Example: Single Agent Power
For simple tasks, the Agent class provides everything you need with minimal boilerplate.

```python
from orionagent import Agent, Gemini, tool

@tool
def crypto_ticker(symbol: str):
    """Fetches real-time prices for crypto assets."""
    return f"Current {symbol} Price: $65,000 (Mock)"

# Configured with Persistence and Logic Guards
agent = Agent(
    name="Vanguard",
    role="Research Analyst",
    model=Gemini("gemini-2.0-flash"),
    memory="persistent",       # Saves state to SQLite automatically
    use_default_tools=True,    # Web Search, File, Terminal access
    tools=[crypto_ticker],
    guards=["straight", "short"] # Enforces professional tone and brevity
)

agent.chat("What is the current BTC price and summarize its impact?")
```

### Multi-Agent Showcase: Autonomous Delegation
The Manager coordinates specialized agents using advanced strategies.

```python
from orionagent import Agent, Manager, Gemini

# Specialized Workers
researcher = Agent(name="Researcher", role="Technical Scraper", use_default_tools=True)
writer = Agent(name="Writer", role="Content Strategist", guards=["happy", "long"])

# The central brain combining Planning and Self-Correction
manager = Manager(
    model=Gemini("gemini-2.0-flash"),
    agents=[researcher, writer],
    strategy=["planning", "self_learn"] # Plan first, then evaluate results
)

manager.chat("Research the latest 2024 AI trends and write a 500-word blog post.")
```

---

## Memory Tier Deep-Dive

OrionAI uses a hierarchical memory pipeline to maintain context without token-bloating.

### 1. Session Memory (Short-Term)
- **Mechanism**: Stores the raw, exact conversation history for the current session.
- **Storage**: RAM / JSON.
- **Use Case**: Immediate back-and-forth context.

### 2. Persistent Memory (Long-Term)
- **Mechanism**: Extracts key facts, user preferences, and results from previous sessions.
- **Storage**: SQLite Database (`orionagent.db`).
- **Optimization**: Uses LLM-based summarization to distill 10,000+ tokens of history into a 200-token "Knowledge Brief".
- **Isolation**: Supports `user_id` scoping to keep data separate for different end-users.

---

## Orchestration Strategies

The Manager uses the **Strategy Engine** to handle complex, multi-step goals.

### Planning Strategy
- **How it works**: Decomposes a high-level goal into a JSON task-map (steps).
- **Parallelism**: Steps that don't depend on each other are executed in parallel (multi-threaded).
- **Context Pass**: Result of Step A is automatically injected as context for Step B.

### Self-Learn Strategy (The Verdict)
- **Evaluation Loop**: After an agent completes a task, the Manager runs a 50-token quality check.
- **Self-Correction**: If the output is poor (Score < 3/5), the Manager re-delegates to a DIFFERENT agent with targeted feedback.
- **Zero-Token Bypass**: The framework remembers success patterns. For repeated tasks, it skips evaluation to save tokens.

---

## Token Efficiency & Performance

OrionAI is built for production environments where token costs and latency matter.

1. **Native System Instructions**: We use provider-specific system roles (Gemini Context Config, OpenAI System Role). Unlike other frameworks that re-send the system prompt every turn, OrionAI stores it once, saving 500-1000 tokens per interaction.
2. **Context Pruning**: Old messages are summarized or dropped before hits the LLM's context limit, preventing "context collapse".
3. **Lazy Model Loading**: Models are only initialized when the first task is received, reducing startup latency.

---

## OrionAI vs LangChain & AutoGen

| Feature | OrionAI | LangChain | AutoGen |
| :--- | :--- | :--- | :--- |
| **Philosophy** | Zero-Magic / Explicit | Abstraction-Heavy | Conversational Swarm |
| **Logic Validation** | Built-in Guards | Needs custom OutputParsers | Limited strict control |
| **Memory** | Native SQLite Auto-Brief | Manual Buffer wiring | Basic persistence |
| **Tokens** | Optimized System Prompts | Full history re-sending | High growth in swarms |

---

## Roadmap
- **Observability Dashboard**: Local Web UI for real-time trace visualization.
- **Human-in-the-Loop**: Pause points for human approval on dangerous tool calls.
- **Async Clusters**: True multi-process parallel execution for large-scale tasks.

---

## License & Contact
Released under the **MIT License**. Created by Samir Lade.

<div align="center">

**OrionAI: Build Agents That Actually Work.**

</div>
