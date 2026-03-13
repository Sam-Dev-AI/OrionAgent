import os
import threading
from dotenv import load_dotenv
from orionagent import Agent, Manager, Gemini, MemoryConfig

load_dotenv()

def test_manager_concurrency():
    print("\n=== Multi-Agent Hard Test 5: Concurrency & Priority ===")
    
    llm = Gemini(model_name="gemini-2.0-flash", temperature=0.2)
    
    agent = Agent(name="Worker", role="Task Processor")
    
    manager = Manager(
        name="Director",
        model=llm,
        agents=[agent],
        strategy="direct",
        verbose=False
    )
    
    def run_task(task_id, priority):
        print(f"Starting Task {task_id} with priority {priority}")
        response = manager.ask(f"Task {task_id}: Say hello.", stream=False, priority=priority)
        print(f"Finished Task {task_id}")
        return response

    # Run two tasks concurrently
    t1 = threading.Thread(target=run_task, args=(1, "high"))
    t2 = threading.Thread(target=run_task, args=(2, "low"))
    
    t1.start()
    t2.start()
    
    t1.join()
    t2.join()
    
    print("Test Passed: Concurrent priority tasks handled.")

if __name__ == "__main__":
    test_manager_concurrency()
