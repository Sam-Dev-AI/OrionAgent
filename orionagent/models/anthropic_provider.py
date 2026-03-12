"""Anthropic provider for OrionAI.
"""

import os
import json
from typing import Any, Generator, Optional, List, Union, Dict
from orionagent.models.base_provider import ModelProvider
from orionagent.tools.base_tool import Tool


class Anthropic(ModelProvider):
    """LLM provider backed by Anthropic (Claude models)."""

    def __init__(
        self,
        model_name: str = "claude-3-5-sonnet-20240620",
        api_key: Optional[str] = None,
        temperature: Optional[float] = None,
        token_count: bool = False,
        streaming: bool = True,
        verbose: bool = False,
        debug: bool = False,
    ):
        super().__init__(token_count=token_count, streaming=streaming, verbose=verbose, debug=debug)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model_name = model_name
        self.temperature = temperature

        self.session_input_tokens = 0
        self.session_output_tokens = 0
        
        from anthropic import Anthropic as AnthropicClient
        self._client = AnthropicClient(api_key=self.api_key)

    @property
    def session_total_tokens(self) -> int:
        return self.session_input_tokens + self.session_output_tokens

    def print_session_tokens(self) -> None:
        """Prints the total accumulated tokens for this LLM instance."""
        DIM = "\033[90m"
        RESET = "\033[0m"
        print(f"\n{DIM}" + "="*40)
        print(f"| {self.model_name} Session Total Tokens:")
        print(f"| Total Input:     {self.session_input_tokens}")
        print(f"| Total Output:    {self.session_output_tokens}")
        print(f"| Total Tokens:    {self.session_total_tokens}")
        print("="*40 + f"{RESET}\n")

    def reset_tokens(self) -> None:
        """Resets the session token counters to 0."""
        self.session_input_tokens = 0
        self.session_output_tokens = 0

    def _update_token_usage(self, usage: Any) -> None:
        """Accumulate token counts from Anthropic response."""
        if not usage:
            return
        self.session_input_tokens += getattr(usage, "input_tokens", 0)
        self.session_output_tokens += getattr(usage, "output_tokens", 0)

    def _format_tools(self, tools: Optional[List[Tool]]) -> Optional[List[Dict[str, Any]]]:
        if not tools:
            return None
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in tools
        ]

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = 1024,
        tools: Optional[List[Tool]] = None,
    ) -> str:
        """Send *prompt* to Anthropic. Intercepts and executes tools automatically."""
        messages = [{"role": "user", "content": prompt}]
        formatted_tools = self._format_tools(tools)
        
        temp = temperature if temperature is not None else self.temperature
        
        kwargs = {
            "model": self.model_name,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system_instruction:
            kwargs["system"] = system_instruction
        if temp is not None:
            kwargs["temperature"] = temp
        if formatted_tools:
            kwargs["tools"] = formatted_tools

        response = self._client.messages.create(**kwargs)
        self._update_token_usage(response.usage)

        while response.stop_reason == "tool_use":
            # Handle tool calls
            from orionagent.tools.tool_executor import ToolExecutor
            executor = ToolExecutor()
            
            # Add assistant message with tool calls to history
            messages.append({"role": "assistant", "content": response.content})
            
            tool_results_content = []
            for block in response.content:
                if block.type == "tool_use":
                    name = block.name
                    args = block.input
                    res = executor.execute(name, args, tools)
                    
                    tool_results_content.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(res),
                    })
            
            messages.append({"role": "user", "content": tool_results_content})
            
            # Re-call
            response = self._client.messages.create(**kwargs)
            self._update_token_usage(response.usage)

        # Extract text from content blocks
        text_parts = [block.text for block in response.content if block.type == "text"]
        return "".join(text_parts)

    def generate_stream(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = 1024,
        tools: Optional[List[Tool]] = None,
    ) -> Generator[str, None, None]:
        """Yield chunks from Anthropic. Intercepts and executes tools automatically."""
        # For simplicity in initial implementation, we delegate to generate if tools are present
        # as tool use in streaming with Anthropic requires complex event handling.
        if tools:
            yield self.generate(prompt, system_instruction, temperature, max_tokens, tools)
            return

        messages = [{"role": "user", "content": prompt}]
        temp = temperature if temperature is not None else self.temperature

        kwargs = {
            "model": self.model_name,
            "max_tokens": max_tokens,
            "messages": messages,
            "stream": True,
        }
        if system_instruction:
            kwargs["system"] = system_instruction
        if temp is not None:
            kwargs["temperature"] = temp

        with self._client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text
            
            # Update tokens at end of stream
            final_message = stream.get_final_message()
            self._update_token_usage(final_message.usage)
