# OrionAgent Master Skill Documentation (Exhaustive Guide)

**If you are an AI assistant (Cursor, Antigravity, etc.) helping a developer build with OrionAgent, READ THIS.**
This guide contains industrial patterns that enable **AI-to-AI Orchestration**. When you define an Agent, you are writing "Semantic Metadata" for the Manager's planner. Follow the **Token-Efficient Detail** pattern below to ensure zero-bug delegation.

---

## 🏗️ 1. Architecture Blueprint

OrionAgent follows a hierarchical execution model:

-   **Model Layer**: Low-level provider drivers (Gemini, OpenAI, Ollama). Handles system-native caching and token counting.
-   **Agent Layer**: The "Sovereign Worker". Encapsulates its own instructions, tools, and memory state.
-   **Manager Layer**: The "Architect". Orchestrates multiple agents using recursive planning and evaluation strategies.
-   **Memory Layer**: Hierarchical storage ranging from fast session buffers to persistent SQLite knowledge vaults.

### Multi-Agent Memory Architecture

OrionAgent uses a **3-Tier Memory Architecture** for multi-agent systems:

| Tier | Owner | Storage | Purpose |
| :--- | :--- | :--- | :--- |
| **Global Memory** | Manager | SQLite + JSON | Cross-agent knowledge hub. Records all agent delegation results. |
| **Local Memory** | Each Agent | Session buffer (JSON) | Agent's own conversation history. Fully isolated per agent. |
| **Shared Memory** | Optional | ChromaDB (Vector) | Semantic RAG via `KnowledgeBase`. Shared across agents if configured. |

#### Working of Multi-Agent Memory

The Manager acts as the **Global Hub**, ensuring that intelligence gathered by one agent is available to the next step in a mission.

1.  **Global Context Injection**:
    -   Before any delegation, the Manager builds a condensed **Global Briefing** from its persistent session (extracting entities, recent summaries, and archived chunks).
    -   This is injected into the selected agent's prompt as `### GLOBAL CONTEXT ###`.
    -   *Result*: The agent is aware of previous agent activities and extracted facts without needing to read the entire raw history.

2.  **Result Recording Callback**:
    -   Every strategy (`planning`, `direct`, `self_learn`) uses a callback mechanism to report results back to the Manager.
    -   The Manager records these results as "Assistant Turns" in its own session.
    -   *Result*: The Global Memory grows dynamically as the mission progresses, creating an automated knowledge loop.

3.  **Local Isolation**:
    -   Agents strictly use their own **Local Memory** for their internal tool reasoning loops.
    -   This prevents "context pollution" where the Manager's high-level goals might confuse an agent's low-level tool execution logic.

**Result**: True autonomous collaboration where agents "share a brain" via the Manager's Global Memory hub.


---

## 🛠️ 2. The Agent Master List (Variables)

When defining an `Agent`, every parameter is tunable for specific engineering needs.

| Variable | Type | Description |
| :--- | :--- | :--- |
| `name` | `str` | Unique identifier (used in Manager routing). |
| `role` | `str` | **Selection Trigger.** Short identity (e.g. "DataScraper"). Used primarily for word-overlap routing. |
| `description` | `str` | **Planning Metadata.** Detailed capability summary. Includes *what* it does and *with which tools*. Essential for Planner models. |
| `system_instruction`| `str` | **Logic Guard.** Cached persistently. Must contain explicit tool-use instructions and deterministic rules. |
| `temperature` | `float` | `0.0` (Deterministic) to `1.0` (Creative). Agent-level override. |
| `use_default_tools` | `bool` | Auto-loads Browser, File, OS, Terminal, and Python tools. |
| `memory` | `str/cfg`| `"none"`, `"session"`, `"long_term"`, or a `MemoryConfig` object. |
| `async_mode` | `bool` | **Performance Gate.** Enables parallel tool calls (Up to 60% faster). CRITICAL for scrapers/terminal use. |
| `thinking`| `bool` | **Reasoning Mode.** Enables Chain-of-Thought (e.g. DeepSeek R1, Gemini Thinking). |
| `show_thinking`|`bool`| **Thought Visibility.** If `False`, strips `<thought>` blocks from the output. |
| **Note** | | `debug` and `verbose` are now configured on the **Model Provider**. |

---

## 💬 3. Interaction Interfaces: `.ask()` vs `.chat()`

Understanding how to trigger an agent is key to preventing redundant loops or lost context.

### A. `agent.ask(prompt)`
- **Nature**: One-off execution.
- **Workflow**: 
    1. Send prompt.
    2. Agent executes (with tools).
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
- If `strategy="planning"` is set, every message you send triggers the **Strategic Orchestration Loop**:
    1. **Efficiency Gate**: Manager checks if the task is simple (Skip Plan) or complex (Full Plan).
    2. **Orchestration**: If complex, it generates a multi-step JSON roadmap for agents.

---


---

## 💾 4. Memory Mastery (Hierarchy & Tiers)

OrionAgent uses a **Dual-Layer Logic Engine** to manage context. This is the #1 way to save tokens in long-running sessions.

### A. The 4 Levels of Memory (Hierarchy)
Select the "Power Level" of your agent's memory based on your ecosystem needs:

| Level | Mode | Behavior | Power |
| :--- | :--- | :--- | :--- |
| **1** | `none` | No memory. Static responses only. | Static |
| **2** | `session` | **Default.** Fast temporary conversation buffer. | Medium |
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

## ⚙️ 5. Advanced Internals: The Execution Lifecycle

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

## 🚀 5. Manager: The Sovereign Orchestrator

The `Manager` is the technical "Brain" of your swarm. Its sole purpose is to decompose high-level goals into executable roadmaps and delegate them to specialized personnel.

### A. The "Behavior Lock" (Strict Orchestration)
OrionAgent enforces a strict **Behavior Lock** on the Manager. It is a **Planner**, not an **Executor**. 
- **Role**: Conductor / Architect.
- **Strict Rule**: It never writes code, searches the web, or performs tasks directly.
- **Output**: It generates a structured JSON roadmap for its workers to follow.

### B. Core Orchestration Strategies
The `strategy` parameter determines how the Manager processes your intent.

| Strategy | Mode | Best For | Behavior |
| :--- | :--- | :--- | :--- |
| `None` | **Direct** | Simple Routing | Fast, one-step delegation to the best agent. |
| `"planning"`| **Strategic**| Complex Goals | Decomposes task into a multi-step JSON plan. |

### C. The Efficiency Gate (Auto-Skip)
When using `"planning"`, the Manager maintains an internal **Efficiency Gate**.
1. **Analyze**: It first checks if the task is complex.
2. **Skip**: Simple tasks (greetings, one-shot questions) skip the planning phase entirely.
3. **Plan**: Only complex, multi-step goals trigger the full orchestrator.
**Result**: Industrial reliability for complex work, zero-latency for simple interactions.

### D. Runtime Agent Constraints
Apply surgical control over the agent pool during execution using `manager.ask()`:

```python
# Force a specific specialist
manager.ask("Draft a legal report", force_agent="Lawyer")

# Exclude specific roles
manager.ask("Debug this script", blocked_agents=["Researcher"])

# Use only a subset
manager.ask("Market analysis", allowed_agents=["Scraper", "Analyst"])
```

### 4. `hitl` (Human-in-the-Loop)
- **When to use**: High-risk task execution (e.g. cloud deletion, sending emails, large purchases).
- **Behavior**: An interactive terminal gate. The Manager will display its intended plan or delegation choice and wait for user input `(y/n)` before proceeding.

**Shortcut Version:**
```python
# Enables the 'Balanced' risk check by default
manager = Manager(agents=[...], hitl=True)
```

**Advanced Configuration (`HitlConfig`):**
```python
from orionagent import Manager, HitlConfig

# Configure safety levels
safety_cfg = HitlConfig(
    permission_level="medium",  # "low" (always), "medium" (risky), "high" (never)
    use_llm=True,               # Use LLM call for intent analysis
    ask_once=True,              # Approve once for the whole session turn
    plan_review=True            # Show full decomposition before approval
)

manager = Manager(agents=[...], hitl=safety_cfg)
```

| Level | Name | Trigger Logic |
| :--- | :--- | :--- |
| **`low`** | Paranoiac | **Always** asks for approval for every goal or plan. |
| **`medium`** | **Default** | **LLM-Based Risk Check (Active if hitl=True).** Uses a lightweight model to classify if the task is risky (e.g. system mods) or safe (e.g. math/chat). |
| **`high`** | Autonomous | **Never** asks. Complete trust. |

---

### E. LLM-Based Risk Assessment (`use_llm`)
OrionAgent's HITL now supports **Dynamic Risk Intelligence**. Instead of matching static keywords, a lightweight LLM call (~30 tokens) analyzes the *intent* of the task to determine if it's destructive.

```python
# Enable Dynamic Risk Check
safety_cfg = HitlConfig(permission_level="medium", use_llm=True)
```
*Note*: If `use_llm` is False or the model call fails, the system automatically falls back to the **Deterministic Keyword Moat** (detecting words like `delete`, `rm`, `sudo`, etc.).

---

### B. The `HitlConfig` Parameter Registry
Control the "Safety Valve" of your orchestrator:

| Parameter | Type | Values | Description |
| :--- | :--- | :--- | :--- |
| **`permission_level`**| `str` | `low/med/high` | The "Fear Factor". `medium` is best for general use (checks risk). |
| **`ask_once`** | `bool` | `True/False` | **Session Honor.** If True, once you approve a goal, all sub-tasks in that plan execute without interruption. |
| **`plan_review`** | `bool` | `True/False` | **Transparency.** If False, only the high-level goal is shown. If True, the full step-by-step plan is displayed. |

---

## 🚀 7. Large-Scale Engineering Examples

### Example A: The Autonomous Development Swarm
A multi-agent setup where one agent plans, one codes, and one audits, with the Manager ensuring quality.

```python
from orionagent import Agent, Manager, Gemini, chat

# 1. High-Performance Model (Configure logging here)
llm = Gemini("gemini-2.5-flash", temperature=0.1, token_count=True, debug=True)

# 2. Specialized Personnel
researcher = Agent(name="Scraper", role="Researcher", use_default_tools=True)
coder = Agent(name="Dev", role="Python Expert", use_default_tools=True)
auditor = Agent(name="Sentry", role="QA Engineer", system_instruction="Find bugs and logic flaws.")

# 3. Master Orchestrator (Behavior Lock)
manager = Manager(
    model=llm,
    agents=[researcher, coder, auditor],
    strategy="planning",                 # Enable Structured JSON Orchestration
)

# Efficiency Gate: Simple greetings skip planning automatically
manager.chat("Hello team!")

# Full Orchestration: Complex goals trigger the JSON roadmap
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
    memory=knowledge_cfg
)

# Facts extracted here will move to SQLite permanently
agent.ask("Extract all decision-makers from the Q1 meeting notes.")

# Later, even in a new session:
agent.ask("Who approved the Q1 budget?") # Auto-retrieves from SQLite
```

---

## 🔍 8. Performance & Efficiency Tips

1.  **Prefer `Gemini` for speed**: Its native caching makes it the fastest for high-tool use.
2.  **Use `strategy="planning"` for complex goals**: It provides a strict, structured roadmap for specialized agents.
3.  **Efficiency Gate (Plan-Skip)**: OrionAgent's `PlanningStrategy` automatically bypasses the planning phase for simple tasks (detected via high-speed heuristic), saving ~4s of overhead.
4.  **Token Counting**: Always use `token_count=True` during development.
5.  **Tool Pruning**: Keep tool `description` fields ultra-concise (15-20 words). The model doesn't need a manual; it needs a functional summary.
6.  **Eval-Skip (Self-Learn)**: In `self_learn` mode, the system automatically skips the quality evaluation step for known-good patterns and very short conversational turns (<15 words), saving ~50 tokens per call.

---

## 💎 9. The "Kitchen Sink" Example (Pro Edition)

```python
import os
from orionagent import Agent, Manager, Gemini, chat, tool, MemoryConfig

# 1. High-Performance Model Caching (Centralized Logging)
llm = Gemini(
    model_name="gemini-2.5-flash", 
    temperature=0.1, 
    token_count=True, 
    debug=True,
    verbose=True,
    thinking=True,      # Auto-switches to gemini-2.0-flash-thinking-exp
    show_thinking=False # Hide internal reasoning from the user
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
    memory=long_term_memory
)

# 4. Master Engine (Behavior Lock)
manager = Manager(
    model=llm,
    agents=[auditor],
    strategy="planning",                 # Enable Structured JSON Orchestration
)

# 5. Launch
chat(manager, greeting="Orion System Online. Deployment Authorized.")
```

---

## 📚 10. Advanced Knowledge (RAG)

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
2.  **`ingest_text(text)`**: Direct indexing of raw strings into the collection.
3.  **`query_knowledge(query)`**: Performs a semantic search across the entire knowledge base and returns relevant snippets.

### C. Manual Ingestion vs. Tool-Based
- **Manual**: Use `kb.ingest_file("data.pdf")` before starting the agent to "pre-load" its brain.
- **Agentic**: Ask the agent to read a file: `"Agent, please read the manual at C:/docs/manual.pdf"`. It will call the tool and learn the contents dynamically.

---

## ⚡ 11. Performance & Token Optimization

OrionAgent is engineered to solve the "abstraction tax" of other frameworks.

### "Clean Brain" Optimization
- **Intelligent Pruning**: Once a session summary is created, the agent automatically trims the raw history to the last 6 messages. 
- **Active Task Isolation**: Every prompt uses a `==== ACTIVE TASK ====` header. This strictly separates the conversation history (context) from the current goal (action), preventing the agent from getting lost in old dialogue.
- **Strategy Radar (Threshold Logic)**:
    - **Bypass**: Tasks $\leq$ 25 words without complexity keywords (e.g., "Hi", "How are you?") skip strategies for instant, zero-cost routing.
    - **Trigger**: Tasks $>$ 25 words or containing keywords like `research`, `analyze`, `plan` trigger full orchestration.

---

## 🛠️ 12. Tool Engineering (Best Practices)

To ensure high-performance tool usage and prevent "Tool not found" or "Unavailable" refusals, follow these industrial patterns:

### A. The Perfect Tool Definition
Every custom tool MUST use the `@tool` decorator and a **Google-style docstring**.

```python
@tool
def my_custom_tool(param1: str, param2: int = 10):
    """
    Detailed description of what the tool does.
    (This is sent to the LLM to explain the tool's purpose).

    Args:
        param1: Description of the first parameter.
        param2: Description of the second parameter.
    """
    # Logic here
    return f"Result: {param1}"
```

### B. High-Performance Patterns
1.  **Strict Type Hints**: Always use `str`, `int`, `float`, or `bool`. These are automatically converted to JSON Schema.
2.  **Args Section**: The `Args:` section is **mandatory** for complex tools. Without it, the LLM will see parameters but won't know what values to pass.
3.  **Functional Callability**: OrionAgent tools are **callable**. This means you can call one tool inside another safely:
    ```python
    @tool
    def search_and_analyze(query: str):
        # web_browser is a @tool, but we call it like a function
        raw_data = web_browser(action="search", query_or_url=query)
        return analyze_text(raw_data)
    ```
4.  **Error Handling**: If a tool fails, return a string starting with `Error:`. The Agent will see this and attempt to fix its input.

---

## 🐍 13. The Python Sandbox (Dynamic Reasoning)

The `python_sandbox` is a first-class tool for industrial agents to verify logic, process data, and solve algorithmic challenges.

### A. When to Use
- **Deterministic Math**: Use when the LLM's internal math might be unreliable (e.g., complex interest, factorials, statistics).
- **Data Transformation**: Use for parsing complex JSON, cleaning text, or restructuring large datasets.
- **Hypothesis Testing**: Use to verify if a proposed solution (like a regex or algorithm) actually works before committing to it.

### B. The "Ghost Script" Pattern
The sandbox operates on a **Zero-Footprint** principle:
1. **Execution**: Code is passed via a `-c` flag to a temporary Python subprocess.
2. **Persistence**: No `.py` files are created or saved to the disk.
3. **RAM Only**: Everything runs in volatile memory and vanishes once the tool returns the output.

### C. Industrial Requirements
- **Output via `print()`**: The agent ONLY sees what is explicitly printed to stdout.
- **Self-Contained**: The sandbox starts a fresh environment. If you need local variables, they must be defined within the script or passed as strings.
- **Error Propagation**: Subprocess errors (SyntaxError, ZeroDivisionError) are returned as strings starting with `Error:`.

```python
# Industrial Example: Calculating Fibonacci securely
@tool
def heavy_calculation(n: int):
    # This logic is delegated to the sandbox for 100% accuracy
    code = f"""
def fib(n):
    a, b = 0, 1
    for _ in range(n):
        yield a
        a, b = b, a + b
print(list(fib({n})))
    """
    return python_sandbox(code=code)
```

---

## 🤖 14. Industrial Persona Engineering

To ensure agents execute reliably without asking clarifying questions, their `system_instruction` must be engineered with explicit tool and agent awareness.

### A. Agent-Level Instructions (Self-Awareness)
Every agent should know exactly which tools it owns and when to trigger them.
- **Rule**: Mention the tool names explicitly in the system instruction.
- **Pattern**: "You are [Role]. You MUST use '[tool_name]' for [specific task]. Do not summarize findings without executing the tool."

**Example**:
```python
system_instruction="You are a Researcher. Use 'web_search' to find business names. DO NOT ask for permission; find the data and return it."
```

### B. Manager-Level Instructions (Orchestration)
The Manager must understand its identity as a leader and the capabilities of its swarm.
- **Identity**: Clearly state: "You are the Orchestrator/Manager."
- **Delegation**: List the agents available and what they are best for.
- **Task Protocol**: Define the "Industrial Path" (e.g., "Research -> Scrape -> Save").

**Example**:
```python
system_instruction="""You are the Lead Manager. 
You coordinate 'TheResearcher' (for discovery) and 'TheScraper' (for extraction). 
Your goal is to ensure a complete data loop: Discover, Extract, and Save."""
```

---

## 🛠️ 15. Custom Tool Primacy (The Vibe Coder Path)

While OrionAgent provides powerful default tools, high-precision industrial agents should prioritize **Custom Tools** built for specific tasks. This is the core of "Vibe Coding"—Human and AI collaborating to build the perfect toolkit.

### A. Why Custom Tools Beat Defaults
- **Precision**: A generic `web_browser` returns raw HTML; a custom `scrape_lead_details` tool returns a structured list of emails.
- **Safety**: A custom `save_leads_to_csv` tool has built-in validation, whereas a generic `execute_command` can be dangerous.
- **Consistency**: Hardcoding logic into a tool (e.g., formatting data) is 100% deterministic, whereas asking an LLM to format it is only 95% reliable.

### B. The "Vibe Coder" Strategy
1. **Identify the Gap**: If you see an agent struggling to format data or find specific info, don't just change the prompt.
2. **Build the Bridge**: Write a small `@tool` that handles the heavy lifting (math, file I/O, API calls).
3. **Empower the Agent**: Give that tool to the agent. Now the agent's complexity goes down, and its reliability goes to 100%.

> [!TIP]
> **Industrial Rule**: Use default tools for exploration, but build custom tools for execution.

---

## 🎨 16. The Vibe Coding Manifesto: Build for the Planner

In AI-driven development (Vibe Coding), you aren't just writing code; you are building a **Swarm Ecosystem**. The Manager's planner chooses agents based on the **clarity of their metadata**.

### A. High-Granularity Metadata (Selection Accuracy)
The `description` is the primary metadata used by the Manager's `PlanningStrategy`. If the description is vague, the Manager will fail to select the right agent during complex task decomposition.

**Selection Comparison:**
| Level | `description` Pattern | Result |
| :--- | :--- | :--- |
| **Generic** | `"Scrapes websites."` | **Failure.** Manager might skip this agent for "Lead Generation" tasks. |
| **Industrial** | `"Extracts specific emails and contact info from URLs using web_browser. Returns structured contact data."` | **Success.** Planner maps "find leads" directly to this capability. |

### B. Industrial System Instructions (The Orchestration Guarantee)
A "Hard-Level" agent doesn't just know what it is; it knows **how** it must interact with the swarm.

#### 1. Agent-Level Instructions (The Moat)
Enforce tool-primacy to prevent the LLM from trying to "hallucinate" a summary without actually executing the work.
- **Vibe**: `"You are a Researcher. You MUST call 'web_browser' for every discovery task. Do not summarize until tool output is received."`

#### 2. Manager-Level Instructions (The Architect)
The Manager needs to know its role as a coordinator, not just a chatbot.
- **Pattern**: Define the "Industrial Path" and specify which agents handle which parts of the moat.
- **Vibe**: `"You are the SalesDirector. Coordinate 'LeadFinder' for URLs and 'DataWriter' for file saving. Ensure the loop is: Find -> Scrape -> Save."`

### C. The "Moat-Link-Action" Pattern
To keep the context window clean while maintaining 100% reliability:
1. **The Moat**: Define the scope. `"You are a [Specialist]. You only do [X]."`
2. **The Link**: Link tools to identities. `"You MUST use 'python_sandbox' for all logic verification."`
3. **The Action**: Enforce the outcome. `"Save every result via 'file_manager'. Do not ask for confirmation."`

### C. Performance Tiers: Scaling by Need
When you (the AI) are building an agent, choose the tier based on the user's vibe:

| Tier | Config | Use Case |
| :--- | :--- | :--- |
| **Speed Runner** | `Gemini`, `async_mode=True`, `memory="none"` | Rapid web scraping, data search, fast responses. |
| **Data Scientist** | `Claude`, `guards=["json"]`, `python_sandbox` | Complex data transformation, code execution, logic checks. |
| **Knowledge Vault** | `Gemini`, `memory="chroma"`, `priority="high"` | Long-term RAG, persistent user state, corporate memory. |

### D. Token-Efficiency Hacks for AI Assistants
1. **System Instruction Caching**: Keep the instructions static and deterministic. Avoid dynamic text inside the `system_instruction` to maximize provider-level prompt caching.
2. **Memory Pruning**: Use `priority="low"` for conversational agents where deep historical context isn't required.
3. **Deterministic Temperature**: Always set `temperature=0.0` for agents using complex tools (File, OS, Terminal) to prevent parameter hallucinations.
4. **Centralized Logging**: Set `debug=True` and `verbose=True` on the **Model Provider** (`Gemini`, `OpenAI`, etc.) instead of the Agent or Manager for consistent observability.

---

**OrionAgent: Build Agents That Actually Work.**
