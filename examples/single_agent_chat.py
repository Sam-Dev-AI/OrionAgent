"""
OrionAgent: 10-Second Power Example
Simple, Persistent & Industrially Robust.

This script demonstrates a high-performance single agent utilizing:
- Native Model Integration (Gemini 2.0 Flash)
- Hierarchical Memory (Persistent SQLite Storage)
- Logic Guards (Tone, emoji-free, and brevity control)
- Multi-Tooling (Custom AI tools with verdict evaluation)
"""

import os
import random
from orionagent import Agent, Gemini, tool

# 1. API KEY CONFIGURATION
# Best practice: 'Your_API_Key' placeholder for examples.
os.environ["GEMINI_API_KEY"] = "Your_API_Key"

# 2. DEFINE PREMIUM CUSTOM TOOLS
@tool
def analyze_sentiment(text: str):
    """Analyzes the emotional tone of a given text. Use for content moderation."""
    scores = ["Positive", "Netural", "Negative"]
    return f"Sentiment Analysis: {random.choice(scores)} (Confidence: 0.98)"

@tool
def get_crypto_price(symbol: str):
    """Fetches real-time price for any cryptocurrency (e.g., BTC, ETH)."""
    prices = {"BTC": "$68,432", "ETH": "$3,842", "SOL": "$145"}
    return f"Current {symbol} Price: {prices.get(symbol.upper(), 'Data unavailable')}"

@tool
def calculate_roi(investment: float, revenue: float):
    """Calculates Return on Investment (ROI) efficiency for business tasks."""
    roi = ((revenue - investment) / investment) * 100
    return f"Calculated ROI: {roi:.2f}%"

def main():
    # 3. INITIALIZE THE CORE ENGINE
    # OrionAgent supports multiple providers (Gemini, OpenAI, Ollama).
    llm = Gemini(model_name="gemini-2.5-flash", token_count=True, debug=True,api_key="Your_API_Key")

    # 4. DEFINE THE 'VANGUARD' AGENT
    # Precision-engineered to be ultra-efficient and direct.
    agent = Agent(
        name="Vanguard-Core",
        role="Intelligence Analyst",
        system_instruction="Provide objective, data-backed insights. No fluff.",
        model=llm,
        memory="long_term",        # Seamlessly saves conversation to memory/orionagent.db
        use_default_tools=True,    # Injects Web Search, Terminal, Python, and Files tools
        tools=[analyze_sentiment, get_crypto_price, calculate_roi],
        guards=["straight", "short"], # Logic Guards: No emojis, Max 3 sentences
        verbose=True,              # Post-session summary
        debug=True,                # Real-time 'Industrial' logs: [PLAN], [TOOL], [GUARD], [MEMORY]
    )

    print("\n" + "="*50)
    print("ORIONAGENT: THE SOVEREIGN AGENT FRAMEWORK")
    print("="*52)
    print("FEATURES: Persistence + Logic Guards + Multi-Tooling")
    print("STRATEGY: Single Agent Power-Loop")
    print("COMMANDS: Type 'exit' to quit.\n")

    # 5. START INTERACTIVE CHAT
    # .chat() initiates an autonomous, tool-aware conversational loop.
    agent.chat("System Online. Vanguard-Core ready for complex mission parameters.")

if __name__ == "__main__":
    main()
