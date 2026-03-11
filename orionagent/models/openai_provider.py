"""OpenAI provider for OrionAI.

system_instruction is sent as the "system" role message -- the
standard OpenAI mechanism which keeps it separate from user messages.
"""

import os
import json
from typing import Any, Generator, Optional, List
from orionagent.models.base_provider import ModelProvider
from orionagent.tools.base_tool import Tool

class OpenAIProvider(ModelProvider):
    """LLM provider backed by OpenAI (GPT models)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gpt-4o-mini",
        token_count: bool = False,
    ):
        super().__init__(token_count=token_count)
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model_name = model_name

        self.session_input_tokens = 0
        self.session_output_tokens = 0
        self.session_total_tokens = 0

        from openai import OpenAI
        self._client = OpenAI(api_key=self.api_key)


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
        self.session_total_tokens = 0

    def _print_token_usage(self, usage: Any) -> None:
        """Accumulate token counts silently. Use print_session_tokens() to display."""
        if not usage:
            return
        self.session_input_tokens += (usage.prompt_tokens or 0)
        self.session_output_tokens += (usage.completion_tokens or 0)
        self.session_total_tokens += (usage.total_tokens or 0)

    # ------------------------------------------------------------------
    # Standard generation
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Tool]] = None,
    ) -> str:
        """Send *prompt* to OpenAI. Intercepts and executes tools automatically."""
        messages = self._build_messages(prompt, system_instruction)
        
        while True:
            kwargs = self._build_kwargs(temperature, max_tokens)
            if tools:
                kwargs["tools"] = [
                    {
                        "type": "function", 
                        "function": {"name": t.name, "description": t.description, "parameters": t.parameters}
                    } for t in tools
                ]
                kwargs["tool_choice"] = "auto"
                
            response = self._client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                **kwargs,
            )
            self._print_token_usage(response.usage)
            choice = response.choices[0]
            
            if choice.message.tool_calls:
                messages.append(choice.message) # Keep assistant's tool call records
                for tc in choice.message.tool_calls:
                    target = next((t for t in tools if t.name == tc.function.name), None)
                    if target:
                        try:
                            # Pass raw JSON string directly to tool.run()
                            res = target.run(tc.function.arguments)
                        except Exception as e:
                            res = f"Error: {e}"
                    else:
                        res = f"Unknown tool: {tc.function.name}"
                        
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.function.name,
                        "content": str(res)
                    })
                # Loop repeats with tool outputs appended to messages!
            else:
                return choice.message.content

    # ------------------------------------------------------------------
    # Streaming generation
    # ------------------------------------------------------------------

    def generate_stream(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Tool]] = None,
    ) -> Generator[str, None, None]:
        """Stream response chunks from OpenAI in real-time, handling tools automatically."""
        messages = self._build_messages(prompt, system_instruction)
        
        while True:
            stream_kwargs = self._build_kwargs(temperature, max_tokens)
            stream_kwargs["stream_options"] = {"include_usage": True}
            if tools:
                stream_kwargs["tools"] = [
                    {
                        "type": "function", 
                        "function": {"name": t.name, "description": t.description, "parameters": t.parameters}
                    } for t in tools
                ]
                stream_kwargs["tool_choice"] = "auto"

            stream = self._client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                stream=True,
                **stream_kwargs,
            )
            
            # We need to detect if it's a tool call or text. 
            # OpenAI sometimes sends tool_calls in chunks.
            
            full_tool_calls_raw = {} # id -> {name, arguments}
            text_started = False
            final_usage = None
            
            for chunk in stream:
                if chunk.usage:
                    final_usage = chunk.usage
                
                if not chunk.choices:
                    continue
                
                delta = chunk.choices[0].delta
                
                # Check for tool calls
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        if tc.id:
                            full_tool_calls_raw[tc.index] = {
                                "id": tc.id,
                                "name": tc.function.name,
                                "arguments": tc.function.arguments or ""
                            }
                        else:
                            full_tool_calls_raw[tc.index]["arguments"] += tc.function.arguments or ""
                
                # Check for text
                if delta.content:
                    text_started = True
                    yield delta.content
            
            if full_tool_calls_raw:
                # Handle tool calls
                # Reconstruct choice.message for internal state
                # (OpenAI client usually wants the full message object)
                # But for simplicity, we'll build a messages update
                
                # First, add the assistant's message with tool calls
                tool_calls_list = []
                for index in sorted(full_tool_calls_raw.keys()):
                    tc = full_tool_calls_raw[index]
                    tool_calls_list.append({
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]}
                    })
                
                messages.append({"role": "assistant", "tool_calls": tool_calls_list})
                
                for tc_data in tool_calls_list:
                    tc_id = tc_data["id"]
                    tc_func = tc_data["function"]
                    target = next((t for t in tools if t.name == tc_func["name"]), None)
                    if target:
                        try:
                            res = target.run(tc_func["arguments"])
                        except Exception as e:
                            res = f"Error: {e}"
                    else:
                        res = f"Unknown tool: {tc_func['name']}"
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": tc_func["name"],
                        "content": str(res)
                    })
                # Loop continues
                continue
            
            self._print_token_usage(final_usage)
            return

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_messages(prompt: str, system_instruction: Optional[str]) -> list:
        """Build the messages list with an optional system role message."""
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        return messages

    @staticmethod
    def _build_kwargs(temperature, max_tokens) -> dict:
        kwargs = {}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        return kwargs
