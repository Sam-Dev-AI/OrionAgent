from orionagent import Agent, OpenAI, chat

# 1. High-Performance Model Configuration (LM Studio)
# qwen/qwen3.5-9b model is loaded at http://127.0.0.1:1234
# Ensure LM Studio is running and the model is loaded before executing.
llm = OpenAI(
    model_name="qwen/qwen3.5-9b",
    base_url="http://127.0.0.1:1234/v1",  # LM Studio uses /v1 for OpenAI compatibility
    api_key="lm-studio",                # Placeholder key for local usage
    temperature=0.7,
    token_count=True,     # Enable reasoning support (e.g. for DeepSeek-R1) # Set to False to hide <think> tags from the user
    debug=False
    
)

# 2. Simple Single Agent Setup
# - memory="session": Fast temporary conversation buffer
# - use_default_tools=True: Provides access to Browser, File, OS, Terminal, and Python tools
agent = Agent(
    name="Orion-LMStudio",
    role="General Assistant",
    model=llm,
    memory="session",
    use_default_tools=True
)

# 3. Interactive Chat Loop
# Launches a persistent terminal session with a "You: " prompt
if __name__ == "__main__":
    chat(
        agent, 
        greeting="🚀 Orion Agent Online (LM Studio). Connected to qwen/qwen3.5-9b.\nType 'exit' or 'quit' to end the session."
    )
