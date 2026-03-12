"""OpenAI provider for OrionAI.
"""

import os
import json
from typing import Any, Generator, Optional, List
from orionagent.models.base_provider import ModelProvider
from orionagent.tools.base_tool import Tool


class OpenAI(ModelProvider):
    """LLM provider backed by OpenAI (GPT models)."""

    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        temperature: Optional[float] = None,
        token_count: bool = False,
        streaming: bool = True,
        verbose: bool = False,
        debug: bool = False,
        base_url: Optional[str] = None,
    ):
        super().__init__(token_count=token_count, streaming=streaming, verbose=verbose, debug=debug)
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model_name = model_name
        self.temperature = temperature
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL", None)

        self.session_input_tokens = 0
        self.session_output_tokens = 0
        self.session_total_tokens = 0

        from openai import OpenAI
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)


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

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Tool]] = None,
    ) -> str:
        """Send *prompt* to OpenAI. Intercepts and executes tools automatically."""
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        formatted_tools = None
        if tools:
            formatted_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]

        temp = temperature if temperature is not None else self.temperature
        
        kwargs = {
            "model": self.model_name,
            "messages": messages,
        }
        if temp is not None:
            kwargs["temperature"] = temp
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if formatted_tools:
            kwargs["tools"] = formatted_tools

        response = self._client.chat.completions.create(**kwargs)

        # Accumulate tokens
        if hasattr(response, "usage"):
            self._print_token_usage(response.usage)

        message = response.choices[0].message
        if message.tool_calls:
            from orionagent.tools.tool_executor import ToolExecutor
            executor = ToolExecutor()
            
            messages.append(message) # Add assistant tool call message to history
            
            for tool_call in message.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                res = executor.execute(name, args, tools)
                
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": name,
                    "content": res,
                })

            # Final call with tool results
            final_response = self._client.chat.completions.create(
                model=self.model_name,
                messages=messages,
            )
            if hasattr(final_response, "usage"):
                self._print_token_usage(final_response.usage)
            return final_response.choices[0].message.content

        return message.content

    def generate_stream(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Tool]] = None,
    ) -> Generator[str, None, None]:
        """Yield chunks from OpenAI. Intercepts and executes tools automatically."""
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        formatted_tools = None
        if tools:
            formatted_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]

        temp = temperature if temperature is not None else self.temperature

        kwargs = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True}
        }
        if temp is not None:
            kwargs["temperature"] = temp
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if formatted_tools:
            kwargs["tools"] = formatted_tools

        stream = self._client.chat.completions.create(**kwargs)

        full_tool_calls = {} # tool_call_id -> {name, args, type}
        
        for chunk in stream:
            # Capture usage if present (usually in the last chunk with stream_options)
            if hasattr(chunk, "usage") and chunk.usage:
                self._print_token_usage(chunk.usage)

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    if tc.id:
                        full_tool_calls[tc.index] = {
                            "id": tc.id,
                            "name": tc.function.name,
                            "args": tc.function.arguments or ""
                        }
                    else:
                        full_tool_calls[tc.index]["args"] += (tc.function.arguments or "")
            
            if delta.content:
                yield delta.content

        if full_tool_calls:
            # End of stream, but we have tool calls to execute
            from orionagent.tools.tool_executor import ToolExecutor
            executor = ToolExecutor()
            
            # Prepare assistant message for history
            tool_calls_payload = []
            for idx in sorted(full_tool_calls.keys()):
                tc = full_tool_calls[idx]
                tool_calls_payload.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": tc["args"]}
                })
            
            messages.append({"role": "assistant", "tool_calls": tool_calls_payload})

            for idx in sorted(full_tool_calls.keys()):
                tc = full_tool_calls[idx]
                name = tc["name"]
                args = json.loads(tc["args"])
                res = executor.execute(name, args, tools)
                
                messages.append({
                    "tool_call_id": tc["id"],
                    "role": "tool",
                    "name": name,
                    "content": res,
                })

            # Re-call generate_stream for final response
            final_stream = self._client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                stream=True
            )
            for final_chunk in final_stream:
                if final_chunk.choices[0].delta.content:
                    yield final_chunk.choices[0].delta.content
