"""
Multi Agent Chat -- Advanced Orchestration

This script demonstrates a Manager coordinating multiple agents.
"""

import os
from orionagent import Agent, Manager, GeminiProvider

# ADD YOUR API KEY HERE
os.environ["GEMINI_API_KEY"] = "Your_API_Key"

def main():
    llm = GeminiProvider(model_name="gemini-2.5-flash", token_count=True)

    # 1. Setup Agents
    researcher = Agent(
        name="researcher",
        role="Researcher",
        description="I find facts and real-time data using web search and system tools.",
        memory="session", # Automatically gets session memory
        use_default_tools=True,
        guards=["polite"],
        verbose=True
    )

    writer = Agent(
        name="writer",
        role="Writer",
        description="I write enthusiastic and detailed articles.",
        memory={
            "mode": "persistent",
            "chunk_size": 10,
            "vector_top_k": 3
        }, # Advanced memory configuration
        guards=["happy", "long"], # Must be cheerful and at least 5 sentences!
        verbose=True
    )

    # 2. Setup Manager with 'selflearn' strategy for autonomous correction
    manager = Manager(
        model=llm,
        strategy="self_learn",  # MOST ADVANCED: Manager evaluates and re-delegates if needed
        verbose=True,         # See the beautiful dimmed orchestration trace
        agents=[researcher, writer]
    )

    print("\n🚀 OrionAI Multi-Agent Advanced Chat")
    print("-------------------------------------")
    print("DEMOS: Planning Strategy + Auto-Handoff + Built-in Guards")
    manager.chat("How can I help you coordinate your agents today?")

if __name__ == "__main__":
    main()
