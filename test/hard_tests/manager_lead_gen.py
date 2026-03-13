import os
from dotenv import load_dotenv
from orionagent import Agent, Manager, Gemini, web_browser, file_manager, MemoryConfig

load_dotenv()

def test_manager_lead_gen():
    print("\n=== Multi-Agent Hard Test 1: Lead Gen Pipeline ===")
    
    llm = Gemini(model_name="gemini-2.0-flash", temperature=0.1)
    
    finder = Agent(
        name="LeadFinder",
        role="Search Specialist",
        description="Searches for business listings and websites.",
        tools=[web_browser]
    )
    
    scraper = Agent(
        name="DetailScraper",
        role="Web Scraper",
        description="Extracts data from specific URLs.",
        tools=[web_browser]
    )
    
    writer = Agent(
        name="DataWriter",
        role="Data Manager",
        description="Saves search results to local files.",
        system_instruction="You are a data entry expert. You MUST use the file_manager tool with action='write' to save every metadata chunk you receive. Do not just reply with text.",
        model=llm,
        tools=[file_manager],
        verbose=True
    )
    
    manager = Manager(
        name="SalesDirector",
        model=llm,
        agents=[finder, scraper, writer],
        strategy=["planning", "self_learn"],
        memory=MemoryConfig(mode="persistent", priority="high"),
        verbose=True
    )
    
    # Task: Comprehensive lead generation
    task = "Find 2 wedding venues in Austin, TX, get their website content, and save the metadata to 'austin_leads.txt'."
    
    print(f"Task: {task}")
    
    response_chunks = []
    for chunk in manager.ask(task, stream=True):
        print(chunk, end="", flush=True)
        response_chunks.append(chunk)
    
    full_response = "".join(response_chunks)
    print(f"\nResponse: {full_response}")
    
    # Verification
    import time
    time.sleep(2)
    assert os.path.exists("austin_leads.txt"), "The leads file should have been created."
    print("Test Passed: Multi-agent lead gen pipeline executed and verified.")

if __name__ == "__main__":
    test_manager_lead_gen()
