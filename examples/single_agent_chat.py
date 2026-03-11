"""
Single Agent Showcase -- Simple, Persistent & Secure

This script demonstrates a high-performance single agent utilizing:
- Native Model Integration (Gemini, OpenAI, etc.)
- Hierarchical Memory (Session-based + Vector-backed Persistence)
- Output Logic Guards (Tone and length control)
- Real-time Execution Tracing
- Built-in Toolsets (Web Search, File Management, etc.)
"""

import os
from orionagent import Agent, Gemini, tool

# 1. API KEY CONFIGURATION
# It is best practice to use environment variables.
os.environ["GEMINI_API_KEY"] = "Your_API_Key"

# 2. OPTIONAL: Define a custom tool
@tool
def get_weather(location: str):
    """Fetches the current weather for a given city."""
    return f"The weather in {location} is currently sunny and 25°C."

def main():
    # 3. INITIALIZE PROVIDER
    # We use Gemini here, but you can swap to OpenAI() or Ollama() easily.
    llm = Gemini(model_name="gemini-2.0-flash", token_count=True)

    # 4. DEFINE THE AGENT
    # This agent is configured to be ultra-efficient and direct.
    agent = Agent(
        name="Orion-Core",
        role="Productivity Specialist",
        system_instruction="You are a helpful assistant that answers questions accurately and concisely.",
        model=llm,
        memory="persistent",       # Automatically handles vector storage and retrieval
        use_default_tools=True,    # Injects Web Search, Terminal, Python, and File tools
        tools=[get_weather],       # Appends our custom weather tool
        guards=["straight", "short"], # Enforces no emojis and max 3 sentences
        verbose=True,              # Enables the beautiful dimmed execution trace
    )

    print("\n" + "="*50)
    print("🚀 ORIONAGENT SINGLE-AGENT DEMO")
    print("="*50)
    print("FEATURES: Persistence + Logic Guards + Multi-Tooling")
    print("COMMANDS: Type 'exit' to quit.\n")

    # 5. START INTERACTIVE CHAT
    # .chat() initiates a recursive, autonomous conversational loop.
    # Alternatively, use .ask() for single-turn programmatic calls.
    agent.chat("Hello! I am ready to assist. Type your request below:")

if __name__ == "__main__":
    main()
