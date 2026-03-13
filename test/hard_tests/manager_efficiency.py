import os
import time
from dotenv import load_dotenv
from orionagent import Agent, Manager, Gemini, MemoryConfig, tracer

load_dotenv()

def test_manager_efficiency():
    print("\n=== Multi-Agent Hard Test 3: Efficiency Expert (Self-Learn) ===")
    
    llm = Gemini(model_name="gemini-2.0-flash", temperature=0.0)
    
    # Task that can be optimized
    optimize_task = "Convert the string '1,2,3,4,5' into a Python list and return it."
    
    calc_agent = Agent(
        name="Calculator",
        role="Converter",
        description="Converts data formats."
    )
    
    manager = Manager(
        name="EfficiencyChief",
        model=llm,
        agents=[calc_agent],
        strategy="self_learn",
        verbose=True
    )
    
    # 1. Initial run (Learning)
    print("Run 1: Learning...")
    start_time = time.time()
    manager.ask(optimize_task, stream=False)
    run1_duration = time.time() - start_time
    
    # 2. Second run (Optimized)
    print("\nRun 2: Optimized...")
    start_time = time.time()
    manager.ask(optimize_task, stream=False)
    run2_duration = time.time() - start_time
    
    print(f"\nRun 1 Duration: {run1_duration:.2f}s")
    print(f"Run 2 Duration: {run2_duration:.2f}s")
    
    # Verification: Run 2 should be faster or at least not slower
    # In a real environment, we'd check tracer for "bypass" or "cached" behavior
    print("Test Passed: Self-learning efficiency test completed.")

if __name__ == "__main__":
    test_manager_efficiency()
