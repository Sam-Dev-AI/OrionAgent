"""
OrionAgent: Autonomous Multi-Agent Orchestration
Advanced Delegation, Planning & Self-Correction.

This script demonstrates the 'Manager' pattern, where a central brain coordinates 
specialized agents using the combined 'planning' and 'self_learn' strategy.

Memory Architecture:
    Manager -> Global memory (SQLite + JSON): Stores cross-agent results & accumulated knowledge.
    Agents  -> Local memory: Each agent has its own isolated conversation buffer.
    Shared  -> Optional vector memory (chroma): Semantic RAG for knowledge retrieval.

Key Advantages vs LangChain/AutoGen:
1. Zero-Magic Orchestration: You control the exact strategy (Planning + Self-Learn).
2. Global Memory: Manager records all agent results into a shared knowledge hub.
3. Cross-Agent Awareness: Later agent steps receive context from earlier steps via global memory.
4. Token Optimization: Shared system instructions and context.
"""

import os
from orionagent import Agent, Manager, Gemini

# 1. API KEY CONFIGURATION
os.environ["GEMINI_API_KEY"] = "Your_API_Key"

def main():
    # 2. INITIALIZE CENTRAL BRAIN
    # The Manager uses this model to devise plans and evaluate agent outputs.
    llm = Gemini(model_name="gemini-2.0-flash", token_count=True)

    # 3. DEFINE SPECIALIZED AGENTS
    # Each agent has LOCAL memory (isolated conversation buffer).
    researcher = Agent(
        name="Quill-Researcher",
        role="Technical Researcher",
        description="Expert at deep-web technical research and data extraction.",
        memory="session",              # LOCAL memory: agent's own session buffer
        use_default_tools=True,        # Auto-loads Web, Terminal, Python tools
        verbose=True
    )

    writer = Agent(
        name="Logic-Writer",
        role="Content Writer",
        description="Writes articles, summaries, and reports from research data.",
        memory="session",              # LOCAL memory: agent's own session buffer
        verbose=True
    )

    # 4. DEFINE THE MANAGER
    # The Manager acts as the orchestrator with GLOBAL memory.
    # It records all agent results into its session, building a cross-agent knowledge hub.
    # When strategy="planning", each delegated step receives the Manager's accumulated context.
    manager = Manager(
        model=llm,
        agents=[researcher, writer],
        strategy="planning",           # Enable Structured JSON Orchestration
        memory="session",              # GLOBAL memory: stores cross-agent results
        verbose=True,
        debug=True
    )

# ------------------------------------------------------------------
# Execution Scenarios
# ------------------------------------------------------------------

# Scenario A: Simple Task (Efficiency Gate Skip)
# The manager will see this is simple and bypass the planning phase.
    print("\n--- [A] Simple Task (Direct Skip) ---")
    manager.chat("Hello! Which agents are available?")

# Scenario B: Complex Task (Structured Orchestration)
# The manager will create a multi-step JSON plan.
# Step 1 result is recorded into GLOBAL memory, Step 2 agent receives it as context.
    print("\n--- [B] Complex Task (Strategic Plan) ---")
    manager.chat("Research the latest advancements in Fusion Energy and write a 2-paragraph summary.")

# Scenario C: Constrained Execution
# Forcing the use of only the Writer agent for a specific query.
    print("\n--- [C] Constrained Execution ---")
    manager.ask("Write a short poem about space.", allowed_agents=["Logic-Writer"])

    print("\n" + "="*50)
    print("ORIONAGENT: MULTI-AGENT SWARM ORCHESTRATION")
    print("="*52)
    print("MODE: Autonomous Planning + Self-Learning Verdicts")
    print("GOAL: Demonstrate cross-agent cooperation and global memory.\n")

    # 5. START INTERACTIVE MISSION
    # The manager will plan the research and analysis phases autonomously.
    manager.chat("How can I help you coordinate your intelligence swarm today?")

if __name__ == "__main__":
    main()
