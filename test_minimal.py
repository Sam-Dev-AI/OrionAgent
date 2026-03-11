from orionagent import Agent

# Test memory mapping
agent_mem = Agent(memory="session")
print(f"Memory mode: {agent_mem.memory_config.mode}")

# Test model mapping
agent_mod = Agent(model="gemini")
print(f"Model provider: {agent_mod.model.__class__.__name__}")
print("Test completed.")
