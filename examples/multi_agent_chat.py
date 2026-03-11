"""
OrionAI: Autonomous Multi-Agent Orchestration
Advanced Delegation, Planning & Self-Correction.

This script demonstrates the 'Manager' pattern, where a central brain coordinates 
specialized agents using the combined 'planning' and 'self_learn' strategy.

Key Advantages vs LangChain/AutoGen:
1. Zero-Magic Orchestration: You control the exact strategy (Planning + Self-Learn).
2. Logic Guards: Every agent output is evaluated for quality before moving to the next step.
3. Token Optimization: Shared system instructions and context.
4. Long-Term Memory: Shared knowledge via persistent SQLite storage.
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
    researcher = Agent(
        name="Quill-Researcher",
        role="Technical Researcher",
        description="Expert at deep-web technical research and data extraction.",
        memory="session",
        use_default_tools=True,    # Auto-loads Web, Terminal, Python tools
        guards=["straight"],        # Enforcement: No emojis/fluff in data
        verbose=True
    )

    analyst = Agent(
        name="Logic-Analyst",
        role="Business Strategy Consultant",
        description="Analyzes raw data to extract ROI, risks, and strategic trends.",
        memory="persistent",       # Retains business logic context across runs
        guards=["short", "straight"], # Enforcement: Brief, no emoji, professional tone
        verbose=True
    )

    # 4. DEFINE THE MANAGER
    # The Manager acts as the orchestrator. By combining 'planning' and 'self_learn',
    # it first breaks the goal into steps and then evaluates each step for quality.
    manager = Manager(
        name="Orion-Supreme",
        model=llm,
    # 🛡️ ADVANCED: Combined Strategy
        # 'planning'   -> Decomposes the task into a logical roadmap.
        # 'self_learn' -> Quality control. If an agent fails the 'verdict', Manager re-delegates.
        strategy=["planning", "self_learn"], 
        agents=[researcher, analyst],
        verbose=True            # Enables beautiful orchestration traces
    )

    print("\n" + "="*50)
    print("ORIONAI: MULTI-AGENT SWARM ORCHESTRATION")
    print("="*52)
    print("MODE: Autonomous Planning + Self-Learning Verdicts")
    print("GOAL: Demonstrate cross-agent cooperation and shared memory.\n")

    # 5. START INTERACTIVE MISSION
    # The manager will plan the research and analysis phases autonomously.
    manager.chat("How can I help you coordinate your intelligence swarm today?")

if __name__ == "__main__":
    main()
