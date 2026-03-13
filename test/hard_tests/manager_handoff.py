import os
from dotenv import load_dotenv
from orionagent import Agent, Manager, Gemini, web_browser, file_manager, MemoryConfig

load_dotenv()

def test_manager_handoff():
    print("\n=== Multi-Agent Hard Test 6: Expert Handoff ===")
    
    llm = Gemini(model_name="gemini-2.0-flash", temperature=0.2)
    
    # Specialist 1: Technical Researcher
    researcher = Agent(
        name="TechResearcher",
        role="Deep Search Specialist",
        description="Handles complex technical queries using web search.",
        tools=[web_browser]
    )
    
    # Specialist 2: Technical Writer
    writer = Agent(
        name="TechWriter",
        role="Technical Author",
        description="Creates structured technical documentation.",
        system_instruction="You are a documentarian. You MUST use the file_manager tool with action='write' to save all summaries you receive. Do not just repeat the data.",
        model=llm,
        tools=[file_manager],
        verbose=True
    )
    
    manager = Manager(
        name="ProjectLead",
        model=llm,
        agents=[researcher, writer],
        strategy="planning", # Use planning for multi-step coordination
        memory=MemoryConfig(mode="persistent"),
        verbose=True
    )
    
    # Task: Research and then write (requires handoff or sequences)
    task = "Research the architecture of Transformers and save a summary to 'transformer_arch.txt'."
    
    print(f"Task: {task}")
    
    response = manager.ask(task, stream=False)
    print(f"\nResponse: {response}")
    
    # Verification
    import time
    time.sleep(2)
    assert os.path.exists("transformer_arch.txt"), "Handoff to writer should have saved the file."
    print("Test Passed: Expert handoff and cross-agent coordination verified.")

if __name__ == "__main__":
    test_manager_handoff()
