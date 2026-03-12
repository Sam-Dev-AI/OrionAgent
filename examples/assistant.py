import os
import psutil # Ensure psutil is installed for 'real powerful' tools
from orionagent import Agent, Manager, OpenAI, HitlConfig, tool, MemoryConfig

# 1. Configuration: OpenRouter with NVIDIA Nemotron
MODEL_ID = "nvidia/nemotron-3-super-120b-a12b:free"
API_KEY = "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"
BASE_URL = "https://openrouter.ai/api/v1"

# Initialize Model with Token Counting enabled
llm = OpenAI(
    model_name=MODEL_ID, 
    api_key=API_KEY, 
    base_url=BASE_URL, 
    token_count=True,
    temperature=0.4
)

# 2. Real Powerful Custom Tools
@tool
def get_system_health():
    """Returns a real-time 'Industrial' view of system CPU, Memory, and Disk health.
    Useful for system diagnostics and root-level monitoring.
    """
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    return f"STATUS: CPU: {cpu}% | RAM: {mem}% | DISK: {disk}%"

@tool
def deep_file_search(pattern: str, search_path: str = "."):
    """Performs a recursive deep search for files matching a pattern.
    Used for locating critical configuration or log files across the system.
    """
    matches = []
    for root, dirnames, filenames in os.walk(search_path):
        for filename in filenames:
            if pattern in filename:
                matches.append(os.path.join(root, filename))
    return f"FOUND {len(matches)} files: {matches[:10]}"

# 3. Dedicated Specialized Agents
# The Architect: Focuses on System Ops, Terminal, and Infrastructure
the_architect = Agent(
    name="TheArchitect",
    role="System Administrator & Infrastructure Engineer",
    description="Handles terminal execution, shell commands, and system diagnostics with root-level access.",
    model=llm,
    use_default_tools=True, # Built-in Shell/Terminal/Files
    tools=[get_system_health, deep_file_search],
    async_mode=True,
    verbose=True
)

# The Librarian: Focuses on Knowledge, RAG, and semantic context
the_librarian = Agent(
    name="TheLibrarian",
    role="Information Specialist & Knowledge Manager",
    description="Manages the Knowledge Base, ingests documents, and retrieves semantic matches.",
    model=llm,
    memory="session",
    async_mode=True
)

# Omni: The generalist 'Chief of Staff' who helps with everything
omni = Agent(
    name="Omni",
    role="Strategic General Assistant",
    description="A versatile assistant capable of handling creative tasks, scheduling, and general problem solving.",
    model=llm,
    memory="session",
    async_mode=True
)

# 4. Multi-Agent Manager: The Orchestrator
# Uses planning strategy to decompose tasks and high-permission HITL for safety.
manager = Manager(
    agents=[omni, the_architect, the_librarian],
    strategy="planning", # Autonomous task decomposition
    model=llm,
    memory="chroma", # Centralized Knowledge Base
    knowledge="assistant_master_knowledge",
    hitl=HitlConfig(
        permission_level="high", # High autonomy: asks only for critical risks
        ask_once=True,           # Review planning stage only
        plan_review=True
    ),
    debug=True # Industrial reasoning logs
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
    run_assistant()
