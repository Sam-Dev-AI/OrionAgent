"""
Single Agent Chat -- Simple & Powerful

This script demonstrates a single agent with guards and tracing.
"""

import os
from orionagent import Agent, GeminiProvider

# ADD YOUR API KEY HERE
os.environ["GEMINI_API_KEY"] = "Your_API_Key"

def main():
    llm = GeminiProvider(model_name="gemini-2.5-flash", token_count=True)

    # Single agent set to be ultra-direct and brief
    agent = Agent(
        name="Orion",
        role="Direct Assistant",
        model=llm,
        memory="persistent", # Automatically manages simple persistent memory with vector fallback!
        use_default_tools=True,
        guards=["straight", "short"], # No emojis, no fluff, max 3 sentences!
        verbose=True,
    )

    print("\n🚀 OrionAI Single-Agent Chat (Direct & Brief)")
    print("----------------------------------------------")
    agent.chat("Hello. I am Orion. What is your request? (I will be very direct)")

if __name__ == "__main__":
    main()
