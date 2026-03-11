"""Base model provider for OrionAI.

Defines the standard interface that all LLM providers must implement.
"""

import sys
from typing import Generator, Optional, List, Any
from orionagent.tools.base_tool import Tool

class ModelProvider:
    """Abstract base for model providers."""

    def __init__(self, token_count: bool = False, streaming: bool = True, verbose: bool = False, debug: bool = False):
        self.token_count = token_count
        self.streaming = streaming
        self.verbose = verbose
        self.debug = debug


    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Tool]] = None,
    ) -> str:
        """Generate a complete response from the model.

        Args:
            prompt:             The user task/question.
            system_instruction: Pre-prompt instructions for the model.
                                Sent via provider-native mechanism (not
                                baked into prompt) to save tokens.
            temperature:        Controls randomness (0.0 = deterministic).
            max_tokens:         Maximum tokens in the response.
            tools:              List of Tool objects the model can invoke.
        """
        # Tracing tool execution
        from orionagent.tracing import tracer
        # Note: The following lines assume 'tool_calls' and 'tool_executor' are defined
        # within the generate method's implementation, which is not shown in the base class.
        # This code is inserted as requested, but might require further context for a complete implementation.
        # For a base class, this might be a placeholder for subclasses to implement.
        # trace_id = tracer.start_trace("tool_execution", f"Executing {len(tool_calls)} tools", tool_calls, verbose=self.verbose)
        
        # results = tool_executor.execute_many(tool_calls, tools)
        # tracer.end_trace(trace_id, results)
        raise NotImplementedError("Subclasses must implement generate().")

    def generate_stream(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Tool]] = None,
    ) -> Generator[str, None, None]:
        """Yield response chunks as they arrive from the model."""
        yield self.generate(prompt, system_instruction, temperature, max_tokens, tools)
