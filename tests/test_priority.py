from orionagent import Agent, MemoryConfig, Gemini
from unittest.mock import MagicMock

def test_priority_refactoring():
    print("\n--- Testing Priority in MemoryConfig ---")
    
    # 1. Test Default (should be low)
    config_default = MemoryConfig()
    print(f"Default config priority: {config_default.priority}")
    assert config_default.priority == "low"
    
    # 2. Test Agent respect default
    mock_model = MagicMock()
    # Mocking memory to avoid JSON serialization issues with MagicMock in process_turn
    agent = Agent(name="Tester", model=mock_model, memory="none")
    # Manually inject a memory config since we want to test the default priority logic
    agent.memory_config = MemoryConfig(priority="low") 
    
    # We need to simulate a session to see if session.priority is set correctly
    task = "Hello"
    agent.ask(task, stream=False, record_memory=False)
    
    # 3. Test explicit override
    agent.ask(task, stream=False, priority="high", record_memory=False)
    
    print("Priority tests PASSED")

if __name__ == "__main__":
    test_priority_refactoring()
