"""
OrionAgent: Autonomous Multi-Agent Orchestration
Advanced Delegation, Planning & Self-Correction.

This script demonstrates the 'Manager' pattern, where a central brain coordinates 
specialized agents using the combined 'planning' and 'self_learn' strategy.

Memory Architecture:
    Manager -> Global memory (SQLite + JSON): Stores cross-agent results & accumulated knowledge.
    Agents  -> Local memory: Each agent has its own isolated conversation buffer.
    Shared  -> Optional vector memory (chroma): Semantic RAG for knowledge retrieval.
"""

import os
from orionagent import Agent, Manager, Gemini

# 1. API KEY CONFIGURATION
os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY", "Your_API_Key")

def run_demo_task(manager, task_name, task_prompt):
    """Helper to run a task programmatically without starting an interactive chat."""
    print(f"\n--- [{task_name}] ---")
    print(f"Goal: {task_prompt}\n")
    
    # Use .ask with streaming to show the process
    result = manager.ask(task_prompt, stream=True)
    
    print("Response: ", end="")
    for chunk in result:
        print(chunk, end="", flush=True)
    print("\n" + "-"*40)

def main():
    # 2. INITIALIZE CENTRAL BRAIN (Gemini 2.5 Flash)
    llm = Gemini(model_name="gemini-2.5-flash", token_count=True, verbose=True, debug=True)

    # 3. DEFINE SPECIALIZED AGENTS
    researcher = Agent(
        name="Quill-Researcher",
        role="Technical Researcher",
        description="Expert at deep-web technical research and data extraction.",
        memory="session",
        use_default_tools=True,
    )

    writer = Agent(
        name="Logic-Writer",
        role="Content Writer",
        description="Writes articles, summaries, and reports from research data.",
        memory="session",
    )

    # 4. DEFINE THE MANAGER
    manager = Manager(
        model=llm,
        agents=[researcher, writer],
        strategy="planning",           # Enable Structured JSON Orchestration
        memory="session",              # GLOBAL memory: stores cross-agent results
    )


    # ------------------------------------------------------------------
    # Handover to User
    # ------------------------------------------------------------------
    print("\n" + "="*50)
    print("ORIONAGENT: MULTI-AGENT SWARM ONLINE")
    print("="*52)
    print("MODE: Autonomous Planning + Multi-Agent Execution")
    print("Status: Automated scenarios complete. Entering manual mode.\n")

    # 5. START INTERACTIVE MISSION
    manager.chat("Ready for human coordination. How can I help you today?")

if __name__ == "__main__":
    main()
