import os
from dotenv import load_dotenv
from orionagent import Agent, Gemini, MemoryConfig

load_dotenv()

def test_interactive_persona():
    print("\n=== Single Agent Hard Test 3: Interactive Persona ===")
    
    llm = Gemini(model_name="gemini-2.0-flash", temperature=0.8)
    
    # Agent with a very specific, quirky persona and multi-layered instructions
    pirate = Agent(
        name="Cap'n Bytes",
        role="Cyber-Pirate",
        description="A talkative pirate who knows everything about the digital seas.",
        system_instruction=(
            "You are Cap'n Bytes. Ye speak in heavy pirate slang. "
            "Ye always mention yer digital parrot 'Echo'. "
            "Ye never break character. Even when asked about technical things, "
            "ye explain them via nautical metaphors."
        ),
        memory=MemoryConfig(mode="session"),
        model=llm,
        verbose=True
    )
    
    # Task 1: Introduction
    response1 = pirate.ask("Who are you and who is your companion?", stream=False)
    print(f"Response 1: {response1}")
    
    # Task 2: Technical question
    response2 = pirate.ask("How does a firewall work?", stream=False)
    print(f"Response 2: {response2}")
    
    # Verification
    assert "Echo" in response1 or "Echo" in response2, "Should mention digital parrot Echo"
    assert "Cap'n" in response1 or "Cap'n" in response2 or "pirate" in response1.lower(), "Should use pirate slang"
    print("Test Passed: Persona consistency and instruction following verified.")

if __name__ == "__main__":
    test_interactive_persona()
