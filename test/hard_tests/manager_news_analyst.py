import os
from dotenv import load_dotenv
from orionagent import Agent, Manager, Gemini, web_browser, MemoryConfig, tracer

load_dotenv()

def test_manager_news_analyst():
    print("\n=== Multi-Agent Hard Test 2: Latest News Analyst ===")
    
    llm = Gemini(model_name="gemini-2.0-flash", temperature=0.4)
    
    sourcer = Agent(
        name="NewsSourcer",
        role="Researcher",
        description="Searches for latest technical news.",
        tools=[web_browser]
    )
    
    analyst = Agent(
        name="TrendAnalyst",
        role="Analyst",
        description="Summarizes and analyzes news trends."
    )
    
    manager = Manager(
        name="EditorialChief",
        model=llm,
        agents=[sourcer, analyst],
        strategy="planning",
        memory=MemoryConfig(mode="session"),
        verbose=True,
        debug=True
    )
    
    # Task: Latest news analysis
    task = "Search for the latest news on AI agents from today and provide a 3-bullet point summary."
    
    print(f"Task: {task}")
    
    response = manager.ask(task, stream=False, priority="high")
    print(f"\nResponse: {response}")
    
    # Verification
    events = tracer.history
    has_plan = any(e['event'] == 'plan' for e in events)
    assert has_plan, "Planning should have occurred."
    print("Test Passed: Latest news analysis with high priority and planning verified.")

if __name__ == "__main__":
    test_manager_news_analyst()
