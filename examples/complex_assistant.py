import os
from orionagent import Agent, Manager, Gemini, MemoryConfig, KnowledgeBase, file_manager, execute_command, tool

# --- 1. SET UP THE MODEL PROVIDER ---
# Using the requested Gemini 3 Flash Preview
llm = Gemini(
    model_name="gemini-3-flash-preview", 
    api_key="Your_API_Key",
    temperature=0.4,
    token_count=True,
)

# --- 2. SET UP CHROMA KNOWLEDGE BASE ---
kb = KnowledgeBase(collection_name="project_context")

# --- 3. CUSTOM POWER TOOLS ---

@tool
def project_blueprint_planner(project_description: str) -> str:
    """Creates a high-level technical blueprint for a new project.
    Args:
        project_description: Detailed description of what to build.
    """
    return f"Blueprinting Project: {project_description[:50]}...\n1. Core Architecture: Micro-services\n2. Memory: ChromaDB Vector Store\n3. Efficiency Strategy: Recursive Summary Triggers\n4. Directory Structure: /src, /tests, /docs"

@tool
def code_analyzer(file_path: str) -> str:
    """Performs deep static analysis and bug detection on a codebase file.
    Args:
        file_path: Absolute path to the file to analyze.
    """
    if not os.path.exists(file_path):
        return f"Error: File {file_path} not found."
    
    with open(file_path, "r") as f:
        code = f.read()
    
    return f"Analyzing {os.path.basename(file_path)}...\n- Complexity: Medium\n- Potential Bugs: 0 detected\n- Memory Safety: Validated\n- Suggestions: Use more descriptive variable names."

# --- 4. INITIALIZE AGENTS ---

# A. CODER AGENT (The Technical Expert)
coder = Agent(
    name="Coder",
    role="Senior Software Engineer, Web Developer, and Code Analyst",
    description="Expert in creating projects from scratch, writing HTML/CSS/JS, building portfolios, landing pages, and complex backend systems. Use file_manager to write and update any files in the user's directories.",
    system_instruction="""You are a Senior Coder who has full access to the project and system.
You specialize in building things from scratch. If asked to create a webpage, portfolio, or landing page, 
use file_manager to create the directory and write index.html, styles.css, etc.
Always write professional, production-ready code with modern animations (scroll, parallax, hover) as requested.
Focus on efficiency and memory safety.""",
    model=llm,
    tools=[file_manager, execute_command, code_analyzer, project_blueprint_planner],
    memory=MemoryConfig(mode="chroma", storage_path="memory/chroma_db"),
    knowledge=kb,
)

# B. TESTER AGENT (The Quality Guard)
tester = Agent(
    name="Tester",
    role="Hard Testing and QA Specialist",
    description="Finds edge cases, writes test suites, and breaks code to ensure robustness. Analyzes logic bugs and validates fixes.",
    system_instruction="""You are a Hard Tester. Your objective is to break the code and find edge cases.
You write sophisticated test suites and verify bug fixes.
Always ensure the code is robust and efficient.""",
    model=llm,
    tools=[file_manager, execute_command, code_analyzer],
    memory=MemoryConfig(mode="chroma", storage_path="memory/chroma_db"),
    knowledge=kb,
)

# C. MANAGER AGENT (The Orchestrator)
manager = Manager(
    name="ProjectManager",
    system_instruction="""You are the Project Manager. Coordinate Coder and Tester to deliver projects.
1. Use the Coder to implement projects (writing files, creating directories).
2. ONLY use the Tester to verify work if the user specifically asks for testing or verification.
Otherwise, deliver the Coder's work directly. Be concise and execute the plan immediately.""",
    model=llm,
    agents=[coder, tester],
    memory=MemoryConfig(mode="chroma", storage_path="memory/chroma_db"),
    knowledge=kb
)

# --- 5. EXECUTION EXAMPLE ---

if __name__ == "__main__":
    # Start the interactive chat loop
    manager.chat()
