import os
from dotenv import load_dotenv
from orionagent import Agent, Gemini, python_sandbox, logic_guard, is_json

load_dotenv()

def test_sandbox_coder():
    print("\n=== Single Agent Hard Test 1: Sandbox Coder ===")
    
    # Custom guard to ensure scientific notation isn't used for large numbers if not needed
    def no_scientific_notation(response: str) -> bool:
        return "e+" not in response.lower()

    llm = Gemini(model_name="gemini-2.0-flash", temperature=0.0)
    
    coder = Agent(
        name="Algorist",
        role="Mathematical Programmer",
        description="Solves complex mathematical problems using efficient Python code.",
        system_instruction="You are a strict programmer. You MUST use the python_sandbox tool for all calculations. Output only valid JSON containing the 'result' and 'code' used.",
        model=llm,
        tools=[python_sandbox],
        guards=[is_json, no_scientific_notation],
        verbose=True
    )
    
    # Task: Find the 100th prime number and return it in JSON
    task = "Calculate the 100th prime number using the python_sandbox tool."
    
    print(f"Task: {task}")
    
    response = coder.ask(task, stream=False)
    print(f"\nResponse: {response}")
    
    # Verification
    assert "541" in response, "100th prime should be 541"
    print("Test Passed: 100th prime correctly identified and JSON format maintained.")

if __name__ == "__main__":
    test_sandbox_coder()
