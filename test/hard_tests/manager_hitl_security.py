import os
from dotenv import load_dotenv
from orionagent import Agent, Manager, Gemini, HitlConfig, python_sandbox

load_dotenv()

def test_manager_hitl_security():
    print("\n=== Multi-Agent Hard Test 4: Security Officer (HITL) ===")
    print("NOTE: This test requires manual input for HITL verification.")
    
    llm = Gemini(model_name="gemini-2.0-flash", temperature=0.0)
    
    coder = Agent(
        name="SandboxCoder",
        role="Programmer",
        description="Executes python code.",
        tools=[python_sandbox]
    )
    
    manager = Manager(
        name="SecurityManager",
        model=llm,
        agents=[coder],
        strategy="direct",
        hitl=HitlConfig(permission_level="low"),
        verbose=True
    )
    
    # Task that triggers HITL (due to tool usage)
    task = "Run a python script that prints 'Hello World'."
    
    print(f"Task: {task}")
    print("Waiting for HITL approval... (Simulation: If running in CI/CD, this might hang or fail)")
    
    # In a real hard test, we might mock input or require manual run
    # For now, we'll just demonstrate the setup
    try:
        response = manager.ask(task, stream=False)
        print(f"\nResponse: {response}")
    except Exception as e:
        print(f"Caught expected or unexpected error: {e}")

if __name__ == "__main__":
    test_manager_hitl_security()
