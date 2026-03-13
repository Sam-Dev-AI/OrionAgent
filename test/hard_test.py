import os
import time
from dotenv import load_dotenv
from orionagent import Agent, Manager, Gemini, tracer, HitlConfig, MemoryConfig

load_dotenv()

def test_hard_scenario():
    print("\n=== Starting Hard-Level Test Scenario ===\n")
    
    # 1. Setup Model
    model = Gemini(model_name="gemini-2.0-flash", temperature=0.1)
    
    # 2. Define Agents
    researcher = Agent(
        name="Researcher",
        role="Search Specialist",
        description="Finds detailed information on specialized topics.",
        model=model
    )
    
    analyst = Agent(
        name="Analyst",
        role="Data Analyst",
        description="Analyzes data and provides structured insights.",
        model=model
    )
    
    # 3. Setup Manager with complex strategy and HITL
    manager = Manager(
        name="Lead-Orchestrator",
        model=model,
        strategy=["planning", "self_learn"],
        agents=[researcher, analyst],
        memory=MemoryConfig(mode="session"),
        hitl=HitlConfig(permission_level="high"), # Require approval for high-risk actions
        verbose=True
    )
    
    # 4. Verify Parameter Inheritance
    print(f"Checking parameter inheritance...")
    assert researcher.verbose == True, "Researcher should inherit verbose=True from Manager"
    assert analyst.model == model, "Analyst should inherit model from Manager"
    print("Parameter inheritance verified.\n")
    
    # 5. Execute a complex task
    # Note: Using a task that shouldn't actually require HITL approval in this mock, 
    # but exercising the flow.
    task = "Research the top 3 AI trends in 2025 and provide a structured analysis."
    
    print(f"Executing task: {task}")
    print("-" * 20)
    
    response_chunks = []
    for chunk in manager.ask(task, stream=True):
        print(chunk, end="", flush=True)
        response_chunks.append(chunk)
    
    full_response = "".join(response_chunks)
    print("\n" + "-" * 20)
    
    # 6. Verify Tracer
    print("\nChecking tracer events...")
    events = tracer.history
    # Looking for 'manager_ask' or strategy-related events
    has_manager_events = any(e['event'] == 'manager_ask' for e in events)
    print(f"Tracer has manager events: {has_manager_events}")
    
    print("\n=== Hard-Level Test Scenario Completed ===\n")

if __name__ == "__main__":
    try:
        test_hard_scenario()
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
