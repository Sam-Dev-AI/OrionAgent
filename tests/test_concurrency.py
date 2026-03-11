import sys
import os
import time
import unittest
from typing import Generator, List, Optional, Any

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from orionagent import Agent, Manager, Model, Tool
from orionagent.models.base_provider import ModelProvider

class MockProvider(ModelProvider):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.calls = 0

    def generate(self, prompt, **kwargs) -> str:
        self.calls += 1
        return f"Response to: {prompt}"

    def generate_stream(self, prompt, **kwargs) -> Generator[str, None, None]:
        self.calls += 1
        yield f"Stream response to: {prompt}"

class SleepTool(Tool):
    def __init__(self, duration=0.5):
        super().__init__(
            name="sleep_tool",
            description="Sleeps for a bit and returns OK",
            parameters={"type": "object", "properties": {}}
        )
        self.duration = duration
        self.call_count = 0

    def run(self, input_data) -> str:
        self.call_count += 1
        time.sleep(self.duration)
        return "OK"

class TestConcurrency(unittest.TestCase):
    def test_model_streaming_default(self):
        # Testing Model factory default
        model = Model(provider="openai", api_key="test")
        self.assertTrue(model.streaming)

    def test_agent_async_mode_default(self):
        agent = Agent(name="test")
        self.assertTrue(agent.async_mode)
        self.assertTrue(agent.tool_executor.async_mode)

    def test_manager_async_mode_default(self):
        manager = Manager()
        self.assertTrue(manager.async_mode)

    def test_parallel_tool_execution(self):
        tool = SleepTool(duration=1.0)
        agent = Agent(name="test", tools=[tool], async_mode=True)
        
        # We manually trigger execute_many to simulate parallel calls
        calls = [{"name": "sleep_tool", "args": {}}, {"name": "sleep_tool", "args": {}}]
        
        start = time.time()
        results = agent.tool_executor.execute_many(calls, agent.tools)
        end = time.time()
        
        duration = end - start
        self.assertEqual(len(results), 2)
        self.assertEqual(tool.call_count, 2)
        # Should be around 1s if parallel, 2s if sequential
        self.assertLess(duration, 1.5, f"Execution took too long: {duration}s")

    def test_sequential_tool_execution(self):
        tool = SleepTool(duration=1.0)
        agent = Agent(name="test", tools=[tool], async_mode=False)
        
        calls = [{"name": "sleep_tool", "args": {}}, {"name": "sleep_tool", "args": {}}]
        
        start = time.time()
        results = agent.tool_executor.execute_many(calls, agent.tools)
        end = time.time()
        
        duration = end - start
        self.assertEqual(len(results), 2)
        self.assertEqual(tool.call_count, 2)
        # Should be > 2s if sequential
        self.assertGreater(duration, 1.9, f"Execution was too fast: {duration}s")

if __name__ == "__main__":
    unittest.main()
