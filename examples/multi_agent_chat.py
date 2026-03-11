"""
Multi-Agent Orchestration -- Autonomous Delegation & Self-Correction

This script demonstrates the 'Manager' pattern, where a central brain coordinates
specialized agents using the 'self_learn' strategy.

Key Features:
- Autonomous Task Delegation: Manager routes tasks to the best agent.
- Strategy-Based Planning: Multi-turn self-correction and evaluation.
- Shared Context: Agents share session and persistent memory.
- Token Efficiency: System instructions are shared across agent turns.
"""

import os
from orionagent import Agent, Manager, Gemini

# 1. API KEY CONFIGURATION
os.environ["GEMINI_API_KEY"] = "Your_API_Key"

def main():
    # 2. INITIALIZE CENTRAL MODEL
    llm = Gemini(model_name="gemini-2.0-flash", token_count=True)

    # 3. DEFINE SPECIALIZED AGENTS
    researcher = Agent(
        name="researcher",
        role="Technical Researcher",
        description="Expert at finding deep technical facts using web search tools.",
        memory="session",
        use_default_tools=True,
        verbose=True
    )

    writer = Agent(
        name="writer",
        role="Creative Content Writer",
        description="Transforms raw technical facts into engaging, detailed articles.",
        memory="persistent", # Remembers previous writing styles/facts across runs
        guards=["happy", "long"], # Enforces enthusiastic tone and detailed responses
        verbose=True
    )

    # 4. DEFINE THE MANAGER
    # The Manager acts as the orchestrator for the multi-agent system.
    manager = Manager(
        name="Orion-Manager",
        model=llm,
        strategy="self_learn",  # ADVANCED: Evaluates agent output and re-delegates if quality is low.
        agents=[researcher, writer],
        verbose=True            # Enables beautiful orchestration traces
    )

    print("\n" + "="*50)
    print("🚀 ORIONAGENT MULTI-AGENT ORCHESTRATION")
    print("="*50)
    print("DEMOS: Self-Learn Strategy + Agent Cooperation + Shared Memory")
    print("USAGE: Ask a complex task that requires research and writing.\n")

    # 5. START INTERACTIVE SESSION
    manager.chat("How can I help you coordinate your agents today?")

if __name__ == "__main__":
    main()
