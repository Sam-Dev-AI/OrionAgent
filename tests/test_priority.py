from orionagent import Agent, MemoryConfig, Gemini
from orionagent.memory.manager import MemoryPipeline
from unittest.mock import MagicMock

def test_priority_tiers():
    print("\n--- Testing Priority Tiers in OrionAgent ---")
    
    # 1. Test Default (should be medium)
    config = MemoryConfig()
    print(f"Default config priority: {config.priority}")
    assert config.priority == "medium"
    
    # 2. Test tiered logic in MemoryPipeline
    mock_llm = MagicMock()
    pipeline = MemoryPipeline(config)
    
    # Simulate a chunk of messages
    session = MagicMock()
    session.priority = "low"
    session.messages = [{"role": "user", "content": "hi"}] * 20
    
    # Test LOW
    pipeline._summarize_chunk(session, mock_llm)
    call_args = mock_llm.generate.call_args
    print(f"LOW Priority System Instruction: {call_args.kwargs['system_instruction']}")
    assert "minimalist" in call_args.kwargs['system_instruction'].lower()
    
    # Test MEDIUM
    session.priority = "medium"
    pipeline._summarize_chunk(session, mock_llm)
    call_args = mock_llm.generate.call_args
    print(f"MEDIUM Priority System Instruction: {call_args.kwargs['system_instruction']}")
    assert "structured" in call_args.kwargs['system_instruction'].lower()
    assert "expert" in call_args.kwargs['system_instruction'].lower()
    
    # Test HIGH
    session.priority = "high"
    pipeline._summarize_chunk(session, mock_llm)
    call_args = mock_llm.generate.call_args
    print(f"HIGH Priority System Instruction: {call_args.kwargs['system_instruction']}")
    assert "exhaustive" in call_args.kwargs['system_instruction'].lower()
    
    print("Priority Tier tests PASSED")

if __name__ == "__main__":
    test_priority_tiers()
