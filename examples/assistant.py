import csv
import traceback
from typing import List, Dict
from orionagent import Agent, Manager, Gemini, HitlConfig, tool, MemoryConfig, web_browser

# 1. Configuration: Model Setup
MODEL_ID = "gemini-2.0-flash"
API_KEY = "YOUR_API_KEY"

# Initialize Gemini Model
llm = Gemini(
    model_name=MODEL_ID, 
    api_key=API_KEY, 
    token_count=True,
    temperature=0.4
)

@tool
def discover_businesses(query: str):
    """Searches the web for business information based on a query. 
    Use this to find names, websites, or contact pages.

    Args:
        query: The search query to find businesses.
    """
    # Robust enhancement: Ensure location context is preserved
    clean_query = query if "list" in query.lower() or "directory" in query.lower() else f"{query} list directory"
    results = web_browser(action="search", query_or_url=clean_query)
    return f"Web discovery for '{query}':\n{results}"

@tool
def get_contact_info(business_name: str, location: str):
    """Specific search for phone numbers and contact details of a business.

    Args:
        business_name: The name of the business to search for.
        location: The city or region of the business.
    """
    search_query = f"{business_name} {location} phone number contact official website"
    results = web_browser(action="search", query_or_url=search_query)
    return f"Contact extraction for {business_name} in {location}:\n{results}"

@tool
def save_leads_to_csv(leads: List[Dict], filename: str):
    """Saves a list of leads (dictionaries) to a CSV file.
    
    Args:
        leads: A list of dictionaries where each dict represents a lead (e.g., [{'name': 'Hotel A', 'phone': '123'}]).
        filename: The target filename (e.g., 'mumbai_leads.csv').
    """
    if not leads:
        return "Error: No leads provided to save."
    
    try:
        # Ensure filename ends with .csv
        if not filename.endswith(".csv"):
            filename += ".csv"
            
        keys = leads[0].keys()
        with open(filename, 'w', newline='', encoding='utf-8') as output_file:
            dict_writer = csv.DictWriter(output_file, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(leads)
        return f"Successfully saved {len(leads)} leads to {filename}"
    except Exception as e:
        return f"Failed to save CSV: {str(e)}"

# 3. Dedicated Specialized Agents
the_researcher = Agent(
    name="TheResearcher",
    role="Researcher",
    description="Finds business information and leads. Use 'discover_businesses'.",
    model=llm,
    system_instruction="""You are an industrial researcher. 
MANDATORY: You MUST use 'discover_businesses' for every lead discovery task.
DO NOT ASK for confirmation. DO NOT summarize only. 
Output the raw findings including names and estimated locations.""",
    use_default_tools=False,
    tools=[discover_businesses],
    async_mode=True,
    verbose=True
)

the_scraper = Agent(
    name="TheScraper",
    role="Scraper",
    description="Gets contact details for businesses. Use 'get_contact_info'.",
    model=llm,
    system_instruction="""You are an industrial scraper. 
MANDATORY: For every business name provided, you MUST call 'get_contact_info'.
DO NOT ASK for confirmation. Return phone numbers and official website links if found.
Process ALL businesses provided in your data context.""",
    use_default_tools=False,
    tools=[get_contact_info],
    async_mode=True,
    verbose=True
)

omni = Agent(
    name="Omni",
    role="Lead Manager",
    description="Aggregates results and saves them to files. Use 'save_leads_to_csv'.",
    model=llm,
    system_instruction="""You are the Lead Master. 
Your final task is to take all findings from previous steps, format them as a list of dictionaries, and call 'save_leads_to_csv'.
DO NOT ASK if you should save—EXECUTE it. The filename must be what the user requested or a descriptive one.""",
    memory="session",
    tools=[save_leads_to_csv],
    async_mode=True
)

# 4. Multi-Agent Manager: The Orchestrator
# Uses planning strategy to decompose tasks.
manager = Manager(
    model=llm,
    agents=[the_researcher, the_scraper, omni],
    strategy="planning", # Autonomous task decomposition
    system_instruction="""You are Orion, the Lead Master Orchestrator. 
Your mission is to coordinate a technical swarm to discover and verify high-quality business leads.

AGENT PROTOCOL:
- Delegate broad discovery (finding names/lists) to 'TheResearcher'.
- Delegate detailed extraction (phone numbers, addresses) to 'TheScraper'.
- Delegate final consolidation and file creation (CSV saving) to 'Omni'.

REASONING ENGINE:
- You are an INDUSTRIAL system. Never ask if you should do something—PLAN IT and EXECUTE IT.
- If a user asks for leads, your default path is: Discover -> Scrape -> Save -> Report.""",
    memory="chroma", # Centralized Knowledge Base
    knowledge="assistant_master_knowledge",
    hitl=HitlConfig(
        permission_level="high", # High autonomy: asks only for critical risks
        ask_once=True,           # Review planning stage only
        plan_review=True
    ),
    debug=True, # Industrial reasoning logs
    verbose=True # See agent steps
)

def run_assistant():
    print("=== ORIONAGENT OMNI-ASSISTANT ACTIVE ===")
    print(f"Model: {MODEL_ID} | Strategy: Planning | Performance: Async")
    
    while True:
        try:
            user_input = input("\n[USER]: ")
            if user_input.lower() in ["exit", "quit"]:
                break
                
            # Execute with full multi-agent orchestration
            response = manager.ask(user_input, stream=True)
            
            print("\n[OMNI]: ", end="")
            for chunk in response:
                print(chunk, end="", flush=True)
            print()
            
            # Print token savings from Clean Brain optimization
            llm.print_session_tokens()
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nERROR: {str(e)}")

if __name__ == "__main__":
    try:
        run_assistant()
    except Exception:
        traceback.print_exc()
