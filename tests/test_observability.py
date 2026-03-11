import sys
import os
import io
import unittest
from unittest.mock import patch
from typing import Generator

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from orionagent import Agent, Manager, Tool
from orionagent.models.base_provider import ModelProvider

class MockPlanningProvider(ModelProvider):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.verbose = kwargs.get("verbose", False)

    def generate(self, prompt, **kwargs) -> str:
        # If it's a planning prompt, return a simple plan
        if "JSON array of groups" in prompt:
            return '[[{"s": "test step", "a": "test_agent"}]]'
        return "Mock response"

    def generate_stream(self, prompt, **kwargs) -> Generator[str, None, None]:
        yield "Streaming mock response"

class TestObservability(unittest.TestCase):
    def test_log_propagation_and_output(self):
        """Verify that verbose=True on model propagates and triggers logs."""
        model = MockPlanningProvider(verbose=True)
        agent = Agent(name="test_agent", model=model, guards=["short"])
        manager = Manager(agents=[agent], model=model, strategy="planning")
        
        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        # Mock provider returns a tool call for the agent
        with patch.object(agent.model, 'generate', return_value='[[{"s": "test tool", "a": "test_agent"}]]'):
            # We need another mock for the tool execution phase
            with patch.object(agent.model, 'generate_stream', return_value=iter(["Tool response"])):
                manager.ask("Please use a tool.", stream=False)
            
            output = captured_output.getvalue()
            
            # Check for expected gray tags
            self.assertIn("[MANAGER_ASK]", output)
            self.assertIn("[MEMORY]", output)
            self.assertIn("[PLAN]", output)
            self.assertIn("[AGENT_ASK]", output)
            # self.assertIn("[TOOL]", output) # Should appear when tool is executed
        
        sys.stdout = sys.__stdout__

if __name__ == "__main__":
    unittest.main()
