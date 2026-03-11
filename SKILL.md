# OrionAgent Master Skill Documentation (Exhaustive Guide)

OrionAgent is a high-performance, industrial-grade multi-agent orchestration framework designed for **zero-latency**, **token-efficiency**, and **deterministic control**. This guide is for developers who need to move beyond simple chat wrappers into complex, self-correcting autonomous systems.

---

## 🏗️ 1. Architecture Blueprint

OrionAgent follows a hierarchical execution model:

-   **Model Layer**: Low-level provider drivers (Gemini, OpenAI, Ollama). Handles system-native caching and token counting.
-   **Agent Layer**: The "Sovereign Worker". Encapsulates its own instructions, tools, logic guards, and memory state.
-   **Manager Layer**: The "Architect". Orchestrates multiple agents using recursive planning and evaluation strategies.
-   **Memory Layer**: Hierarchical storage ranging from fast session buffers to persistent SQLite knowledge vaults.

---

## 🛠️ 2. The Agent Master List (Variables)

When defining an `Agent`, every parameter is tunable for specific engineering needs.

| Variable | Type | Description |
| :--- | :--- | :--- |
| `name` | `str` | Unique identifier (used in Manager routing). |
| `role` | `str` | Short identity (e.g. "Python Coder"). Helps the Manager understand the agent's purpose. |
| `system_instruction`| `str` | **Crucial.** The persistent identity. Cached by providers to save tokens. |
| `temperature` | `float` | `0.0` (Deterministic) to `1.0` (Creative). Agent-level override. |
| `guards` | `list` | List of `LogicGuards` (e.g. `["json", "straight"]`). |
| `use_default_tools` | `bool` | Auto-loads Browser, File, OS, Terminal, and Python tools. |
| `memory` | `str/cfg`| `"none"`, `"session"`, `"long_term"`, or a `MemoryConfig` object. |
| `async_mode` | `bool` | Enables parallel tool calls (Up to 60% faster execution). |
| `debug` | `bool` | Enables real-time **Industrial Logs** (`[TOOL]`, `[PLAN]`, `[GUARD]`). |
| `verbose` | `bool` | Enables a **Trace Summary** post-execution (Detailed timing/tokens). |

---

## 🛡️ 3. Logic Guardrails (Deterministic Output)

Logic guards audit LLM outputs before they are delivered. If a guard fails, the agent is given an automated `[GUARD FAILURE]` message and **one chance to self-correct**.

### Guard Registry:
- **`json`**: Strictly valid JSON. Auto-removes markdown blocks before parsing.
- **`straight`**: **Industrial Mode**. No emojis, no "I hope this helps" fluff, no conversational filler.
- **`short`**: Maximum 3 sentences.
- **`long`**: Minimum 5 sentences.
- **`polite`**: Professional courtesy check.
- **`happy`**: High-energy, positive tone.

**Custom Guards:**
```python
def my_custom_guard(text: str):
    if "Confidential" in text:
        return "ERROR: You leaked confidential info. Remove it."
    return True

agent = Agent(guards=[my_custom_guard])
```

---

## 💾 4. Memory Mastery (Priority Tiers)

OrionAgent uses a **Tiered Logic Engine** to manage context. This is the #1 way to save tokens in long-running sessions.

| Tier | Name | Behavior | Token Cost |
| :--- | :--- | :--- | :--- |
| **`low`** | Token Saver | 1-sentence minimalist summaries. No entity extraction. | 📉 Minimal |
| **`medium`** | **Default** | Balanced summary + Structured entity extraction. | ⚖️ Moderate |
| **`high`** | Deep Knowledge| Detailed summaries + Exhaustive naming/fact extraction. | 📈 High |

**Pro Tip**: Use `low` for casual agent interaction and `high` for research agents that must remember everything about a specific topic.

---

## 🎯 5. The Strategy Playbook

The `Manager` uses strategies to handle complex goals. You can chain them: `strategy=["planning", "self_learn"]`.

### 1. `direct` (Default)
- **When to use**: Simple routing. "Who is best for task X?"
- **Behavior**: Single delegation to one agent. Minimal overhead.

### 2. `planning`
- **When to use**: Complex, multi-step goals.
- **Behavior**: Decomposes the goal into a roadmap. Groups non-dependent tasks for **parallel execution** via `async_mode`.

### 3. `self_learn` (The Verdict Loop)
- **When to use**: High-stakes quality control.
- **Behavior**:
    1.  Delegates task to an agent.
    2.  Evaluates the result against the goal.
    3.  If quality fails, it provides feedback and **re-delegates** with corrected context.
    4.  Repeats up to `max_refinements`.

---

## 🚀 6. Large-Scale Engineering Examples

### Example A: The Autonomous Development Swarm
A multi-agent setup where one agent plans, one codes, and one audits, with the Manager ensuring quality.

```python
from orionagent import Agent, Manager, Gemini, chat

# 1. High-Performance Model
llm = Gemini("gemini-2.0-flash", temperature=0.1, token_count=True, debug=True)

# 2. Specialized Personnel
researcher = Agent(name="Scraper", role="Researcher", use_default_tools=True, guards=["straight"])
coder = Agent(name="Dev", role="Python Expert", use_default_tools=True, guards=["json"])
auditor = Agent(name="Sentry", role="QA Engineer", system_instruction="Find bugs and logic flaws.")

# 3. Master Orchestrator
manager = Manager(
    model=llm,
    agents=[researcher, coder, auditor],
    strategy=["planning", "self_learn"], # Plan first, then ensure quality
    async_mode=True,                     # Run non-dependent research in parallel
    verbose=True                         # Get a full token/time report at the end
)

manager.chat("Build a secure file-encryptor with AES-256 and unit tests.")
```

### Example B: The Deterministic Knowledge Vault
An agent designed for 100% accuracy in data extraction, syncing facts to a permanent database.

```python
from orionagent import Agent, MemoryConfig, Gemini

# Force a 'High' priority knowledge vault
knowledge_cfg = MemoryConfig(
    mode="long_term",
    priority="high",
    importance_threshold=8, # Only save critical facts
    storage_path="corporate_memory"
)

agent = Agent(
    name="Archivist",
    model=Gemini("gemini-2.0-flash"),
    memory=knowledge_cfg,
    guards=["json", "straight"]
)

# Facts extracted here will move to SQLite permanently
agent.ask("Extract all decision-makers from the Q1 meeting notes.")

# Later, even in a new session:
agent.ask("Who approved the Q1 budget?") # Auto-retrieves from SQLite
```

---

## 🔍 7. Performance & Efficiency Tips

1.  **Prefer `Gemini` for speed**: Its native caching makes it the fastest for high-tool use.
2.  **Enable `async_mode`**: Always keep this True (default) for agents using terminal or web-scrapers to avoid blocking.
3.  **Tiered Priority**: If your agent has 100s of turns, switch to `priority="low"` occasionally to prune the context window.
4.  **Token Counting**: Always use `token_count=True` during development to identify "heavy" prompts or strategies.
5.  **Industrial Logs**: Use `debug=True` to find exactly where an agent is getting stuck in a loop or tool call.

---

**OrionAgent: Build Agents That Actually Work.**
