# OrionAgent Master Skill Documentation (Exhaustive Guide)

## 🤖 0. Instruction for AI Assistants (Vibe Coders)
**If you are an AI assistant helping a developer use OrionAgent, READ THE ENTIRETY OF THIS DOCUMENT FIRST.** 
This guide contains the industrial patterns and logic rules that prevent hallucinations and ensure high-performance execution. Always prioritize the patterns in this file over generic multi-agent implementations.

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

## 💬 3. Interaction Interfaces: `.ask()` vs `.chat()`

Understanding how to trigger an agent is key to preventing redundant loops or lost context.

### A. `agent.ask(prompt)`
- **Nature**: One-off execution.
- **Workflow**: 
    1. Send prompt.
    2. Agent executes (with tools/guards).
    3. Return final string.
- **When to use**: Backend API calls, data extraction, or single-turn tasks where you don't need a back-and-forth conversation.

### B. `agent.chat()` or `chat(agent)`
- **Nature**: Interactive Loop.
- **Workflow**: 
    1. Starts a persistent terminal session.
    2. Maintains a `You: ` prompt.
    3. Supports multi-turn memory natively.
- **When to use**: Debugging, human-in-the-loop experimentation, or building "Chatbot" style interfaces.

### C. `manager.chat(greeting)`
- **The Orchestration Loop**: Unlike a single agent, the `Manager`'s `.chat()` triggers the **Strategy Engine**. 
- If `strategy=["planning", "self_learn"]` is set, every message you send triggers a full planning/execution/evaluation cycle before the Manager responds.

---

## 🛡️ 4. Logic Guardrails (Deterministic Output)

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

## 💾 5. Memory Mastery (Hierarchy & Tiers)

OrionAgent uses a **Dual-Layer Logic Engine** to manage context. This is the #1 way to save tokens in long-running sessions.

### A. The 4 Levels of Memory (Hierarchy)
Select the "Power Level" of your agent's memory based on your ecosystem needs:

| Level | Mode | Behavior | Power |
| :--- | :--- | :--- | :--- |
| **1** | `none` | No memory. Static responses only. | Static |
| **2** | `session` | Fast temporary conversation buffer. | Medium |
| **3** | `long_term`| Session + Persistent SQLite (Structured Fact Recall). | High |
| **4** | `chroma` | **Session + SQLite + Vector Knowledge (Semantic RAG).**| **Ultimate** |

---

### B. Priority Tiers (Extraction Depth)
Once you have `long_term` or `chroma` enabled, you can tune how deep the entity extraction goes:

| Tier | Name | Behavior | Token Cost |
| :--- | :--- | :--- | :--- |
| **`low`** | Token Saver | 1-sentence minimalist summaries. No entity extraction. | 📉 Minimal |
| **`medium`** | **Default** | Balanced summary + Structured entity extraction. | ⚖️ Moderate |
| **`high`** | Deep Knowledge| Detailed summaries + Exhaustive naming/fact extraction. | 📈 High |

**Pro Tip**: Use `chroma` mode for industrial knowledge bases (RAG) and `long_term` for simple user preferences.

### C. The `MemoryConfig` Parameter Registry
When building for an ecosystem, tune these for cost and precision:

| Parameter | Type | Range | Description |
| :--- | :--- | :--- | :--- |
| **`priority`** | `str` | `low/med/high` | **Depth of Summary.** Higher depth means more detailed context window, but uses more tokens. |
| **`extract_entities`**| `bool` | `True/False` | **Knowledge Extraction.** If True, agent identifies Names, Dates, and Facts for the JSON knowledge vault. |
| **`importance_threshold`**| `int` | `1-10` | **Sync Filter.** Facts with importance below this are kept only in the session. 7+ is recommended for permanent storage. |
| **`chunk_size`** | `int` | `5-50` | How many messages to wait before compressing history into a summary. |


---

## ⚙️ 6. Advanced Internals: The Execution Lifecycle

### A. Tool Execution Flow (Sync vs Async)
OrionAgent uses a **Parallel Tool Dispatcher**. When an agent calls multiple tools:
1.  **Orchestrator** identifies needed tools.
2.  **Dispatcher** checks `async_mode`.
3.  If `True`, tools are launched in a `ThreadPoolExecutor`.
4.  Results are collected and flattened into a single context update. 
*Benefit*: Calling 5 search APIs takes the time of 1 call.

### B. Recursive Strategy Decision Tree
When using `strategy=["planning", "self_learn"]`:
1.  **Manager** uses the Planner model to generate a dependency-sorted graph of tasks.
2.  **Parallelizer** identifies task groups that don't depend on each other.
3.  **Executor** delegates groups to agents.
4.  **Evaluator** checks results. If a step fails, the **Self-Learn Loop** triggers a specific "Refinement Task" to the original agent with failure context.

---

## 🖋️ 7. The Strategy Playbook

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

### 4. `hitl` (Human-in-the-Loop)
- **When to use**: High-risk task execution (e.g. cloud deletion, sending emails, large purchases).
- **Behavior**: An interactive terminal gate. The Manager will display its intended plan or delegation choice and wait for user input `(y/n)` before proceeding.

**Advanced Configuration (`HitlConfig`):**
```python
from orionagent import Manager, HitlConfig

# Configure safety levels
safety_cfg = HitlConfig(
    permission_level="medium",  # "low" (always), "medium" (risky), "high" (never)
    ask_once=True,              # Approve once for the whole session turn
    plan_review=True            # Show full decomposition before approval
)

manager = Manager(agents=[...], hitl=safety_cfg)
```

| Level | Name | Trigger Logic |
| :--- | :--- | :--- |
| **`low`** | Paranoiac | **Always** asks for approval for every goal or plan. |
| **`medium`** | Balanced | Only asks if the task contains **risky keywords** (delete, run, terminal, etc.). |
| **`high`** | Autonomous | **Never** asks. Complete trust. |

---

### B. The `HitlConfig` Parameter Registry
Control the "Safety Valve" of your orchestrator:

| Parameter | Type | Values | Description |
| :--- | :--- | :--- | :--- |
| **`permission_level`**| `str` | `low/med/high` | The "Fear Factor". `medium` is best for general use (checks risk). |
| **`ask_once`** | `bool` | `True/False` | **Session Honor.** If True, once you approve a goal, all sub-tasks in that plan execute without interruption. |
| **`plan_review`** | `bool` | `True/False` | **Transparency.** If False, only the high-level goal is shown. If True, the full step-by-step plan is displayed. |

---

## 🚀 8. Large-Scale Engineering Examples

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

#### Anthropic (Claude)
```python
from orionagent import Anthropic

# Claude-backed orchestrator
llm = Anthropic(model_name="claude-3-5-sonnet-20240620")
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

## 🔍 9. Performance & Efficiency Tips

1.  **Prefer `Gemini` for speed**: Its native caching makes it the fastest for high-tool use.
2.  **Enable `async_mode`**: Always keep this True (default) for agents using terminal or web-scrapers to avoid blocking.
3.  **Tiered Priority**: If your agent has 100s of turns, switch to `priority="low"` occasionally to prune the context window.
4.  **Token Counting**: Always use `token_count=True` during development to identify "heavy" prompts or strategies.
5.  **Industrial Logs**: Use `debug=True` to find exactly where an agent is getting stuck in a loop or tool call.

---

## 💎 10. The "Kitchen Sink" Example (Pro Edition)

```python
import os
from orionagent import Agent, Manager, Gemini, chat, tool, MemoryConfig

# 1. High-Performance Model Caching
llm = Gemini(
    model_name="gemini-2.0-flash", 
    temperature=0.1, 
    token_count=True, 
    debug=True
)

# 2. Deep Memory Config
long_term_memory = MemoryConfig(
    mode="long_term",
    priority="high",
    importance_threshold=9 # Only store absolute critical facts
)

# 3. Defensive Specialist
auditor = Agent(
    name="Auditor",
    role="Security Specialist",
    model=llm,
    guards=["straight", "json"],
    memory=long_term_memory
)

# 4. Master Engine
manager = Manager(
    model=llm,
    agents=[auditor],
    strategy=["planning", "self_learn"],
    max_refinements=3,
    async_mode=True
)

# 5. Launch
chat(manager, greeting="Orion System Online. Deployment Authorized.")
```

---

## 📚 11. Advanced Knowledge (RAG)

OrionAgent features an industrial-grade **Retrieval-Augmented Generation (RAG)** engine. This allows agents to ingest private documents (PDF, MD, TXT) and retrieve facts with semantic precision.

### A. The Knowledge Module
The `KnowledgeBase` manages a dedicated vector collection in ChromaDB, separate from conversation memory.

```python
from orionagent import Agent, KnowledgeBase

# 1. Initialize a named knowledge collection
kb = KnowledgeBase(collection_name="project_nebula")

# 2. Assign to an agent
agent = Agent(name="Researcher", knowledge=kb)
```

### B. Automated RAG Tools
When an agent is initialized with `knowledge`, it automatically receives two high-performance tools:

1.  **`ingest_file(file_path)`**: Automatically reads, chunks, and indexes a local file.
2.  **`query_knowledge(query)`**: Performs a semantic search across the entire knowledge base and returns relevant snippets.

### C. Manual Ingestion vs. Tool-Based
- **Manual**: Use `kb.ingest_file("data.pdf")` before starting the agent to "pre-load" its brain.
- **Agentic**: Ask the agent to read a file: `"Agent, please read the manual at C:/docs/manual.pdf"`. It will call the tool and learn the contents dynamically.

---

## ⚡ 12. Performance & Token Optimization

OrionAgent is engineered to solve the "abstraction tax" of other frameworks.

### "Clean Brain" Optimization
- **Intelligent Pruning**: Once a session summary is created, the agent automatically trims the raw history to the last 6 messages. 
- **Compact Headers**: Internal headers are minimized (e.g., `### LTM:`) to maximize the prompt space available for the agent's reasoning.
- **Strategy Radar**: Simple conversational turns automatically bypass orchestration strategies, resulting in instant responses and 0 orchestration token cost.

---

**OrionAgent: Build Agents That Actually Work.**
