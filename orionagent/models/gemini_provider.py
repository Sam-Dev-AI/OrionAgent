"""Google Gemini provider for OrionAI.

system_instruction is passed via GenerateContentConfig -- Gemini keeps
it cached separately from the user prompt, so you only pay for those
tokens once per caching window instead of every single call.
"""

import os
import json
from typing import Any, Generator, Optional, List
from orionagent.models.base_provider import ModelProvider
from orionagent.tools.base_tool import Tool


class GeminiProvider(ModelProvider):
    """LLM provider backed by Google Gemini."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.0-flash",
        token_count: bool = False,
    ):
        super().__init__(token_count=token_count)
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model_name = model_name
        
        self.session_input_tokens = 0
        self.session_output_tokens = 0
        self.session_total_tokens = 0

        from google import genai
        self._client = genai.Client(api_key=self.api_key)


    # ------------------------------------------------------------------
    # Config builder
    # ------------------------------------------------------------------

    def _build_config(self, system_instruction, temperature, max_tokens, tools=None):
        """Return a GenerateContentConfig when any option is set."""
        if not any([system_instruction, temperature is not None, max_tokens is not None, tools]):
            return None
        from google.genai import types
        
        kwargs = {}
        if system_instruction:
            kwargs["system_instruction"] = system_instruction
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_output_tokens"] = max_tokens
        if tools:
            kwargs["tools"] = [{"function_declarations": [
                {"name": t.name, "description": t.description, "parameters": t.parameters} for t in tools
            ]}]
            
        return types.GenerateContentConfig(**kwargs)

    # ------------------------------------------------------------------
    # Standard generation
    # ------------------------------------------------------------------
    
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
        self.session_input_tokens += (usage.prompt_token_count or 0)
        self.session_output_tokens += (usage.candidates_token_count or 0)
        self.session_total_tokens += (usage.total_token_count or 0)

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Tool]] = None,
    ) -> str:
        """Send *prompt* to Gemini. Intercepts and executes tools automatically."""
        messages = prompt
        config = self._build_config(system_instruction, temperature, max_tokens, tools)
        
        while True:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=messages,
                config=config,
            )
            self._print_token_usage(response.usage_metadata)
            
            if response.function_calls:
                from google.genai import types
                
                # If first loop, convert string prompt into robust message format
                if isinstance(messages, str):
                    messages = [{"role": "user", "parts": [{"text": messages}]}]
                    
                messages.append(response.candidates[0].content) # Add model turn
                
                # Parallel tool execution
                from orionagent.tools.tool_executor import ToolExecutor
                executor = ToolExecutor()
                
                calls = []
                for fc in response.function_calls:
                    args_str = json.dumps(fc.args) if isinstance(fc.args, dict) else str(fc.args)
                    calls.append({"name": fc.name, "args": args_str})
                
                results = executor.execute_many(calls, tools)
                
                tool_results = []
                for res in results:
                    tool_results.append(
                        types.Part.from_function_response(
                            name=res["name"],
                            response={"result": res["result"]}
                        )
                    )
                messages.append({"role": "user", "parts": tool_results})
            else:
                return response.text

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
        """Stream response chunks from Gemini in real-time, handling tools automatically."""
        messages = prompt
        config = self._build_config(system_instruction, temperature, max_tokens, tools)
        
        while True:
            # If we have tools, we must be careful. Gemini's stream API 
            # will return function_calls in chunks if they are present.
            
            stream = self._client.models.generate_content_stream(
                model=self.model_name,
                contents=messages,
                config=config,
            )
            
            first_chunk = next(stream, None)
            if not first_chunk:
                return

            # Accumulate tool calls if present in the first part of the stream
            if first_chunk.function_calls:
                # If it's a tool call, we consume the rest of the stream 
                # (usually tool calls come in the first chunk or two)
                full_response = first_chunk
                for chunk in stream:
                    # In practice, Gemini tool calls are usually in one chunk, 
                    # but we should handle accumulation if needed.
                    pass 
                
                from google.genai import types
                if isinstance(messages, str):
                    messages = [{"role": "user", "parts": [{"text": messages}]}]
                
                messages.append(full_response.candidates[0].content)
                
                # Parallel tool execution
                from orionagent.tools.tool_executor import ToolExecutor
                executor = ToolExecutor()
                
                calls = []
                for fc in full_response.function_calls:
                    args_str = json.dumps(fc.args) if isinstance(fc.args, dict) else str(fc.args)
                    calls.append({"name": fc.name, "args": args_str})
                
                results = executor.execute_many(calls, tools)
                
                tool_results = []
                for res in results:
                    tool_results.append(
                        types.Part.from_function_response(
                            name=res["name"],
                            response={"result": res["result"]}
                        )
                    )
                messages.append({"role": "user", "parts": tool_results})
                # Loop continues to get the model's response to tool results
                continue
                
            else:
                # It's a text response, yield the first chunk and then the rest
                if first_chunk.text:
                    yield first_chunk.text
                
                final_usage = first_chunk.usage_metadata
                for chunk in stream:
                    if chunk.usage_metadata:
                        final_usage = chunk.usage_metadata
                    if chunk.text:
                        yield chunk.text
                
                self._print_token_usage(final_usage)
                return
