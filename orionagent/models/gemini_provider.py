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


class Gemini(ModelProvider):
    """LLM provider backed by Google Gemini."""

    def __init__(
        self,
        model_name: str = "gemini-2.0-flash",
        api_key: Optional[str] = None,
        temperature: Optional[float] = None,
        token_count: bool = False,
        streaming: bool = True,
        verbose: bool = False,
        debug: bool = False,
    ):
        super().__init__(token_count=token_count, streaming=streaming, verbose=verbose, debug=debug)
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model_name = model_name
        self.temperature = temperature
        
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
        config = self._build_config(
            system_instruction, 
            temperature if temperature is not None else self.temperature, 
            max_tokens, 
            tools
        )

        response = self._client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )

        # Accumulate tokens
        self._print_token_usage(response.usage_metadata)

        # Handle tool calls
        if response.candidates[0].content.parts[0].function_call:
            from orionagent.tools.tool_executor import ToolExecutor
            executor = ToolExecutor()
            
            tool_outputs = []
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    name = part.function_call.name
                    args = part.function_call.args
                    res = executor.execute(name, args, tools)
                    tool_outputs.append({
                        "call_id": None, # Gemini 0.1 doesn't use call_id in simple mode
                        "name": name,
                        "output": res
                    })

            # Send back to model
            from google.genai import types
            
            # Gemini expects the full history for tool results
            history = [
                types.Content(role="user", parts=[types.Part(text=prompt)]),
                response.candidates[0].content,
                types.Content(role="user", parts=[
                    types.Part(function_response=types.FunctionResponse(name=o["name"], response={"result": o["output"]})) for o in tool_outputs
                ])
            ]

            final_response = self._client.models.generate_content(
                model=self.model_name,
                contents=history,
                config=config,
            )
            self._print_token_usage(final_response.usage_metadata)
            return final_response.text

        return response.text

    def generate_stream(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Tool]] = None,
    ) -> Generator[str, None, None]:
        """Yield chunks from Gemini. Intercepts and executes tools automatically."""
        config = self._build_config(
            system_instruction, 
            temperature if temperature is not None else self.temperature, 
            max_tokens, 
            tools
        )

        stream = self._client.models.generate_content_stream(
            model=self.model_name,
            contents=prompt,
            config=config,
        )

        full_content = []
        for chunk in stream:
            # We must check for function calls in the first chunk or combined chunks
            # In Gemini, if it's a tool call, it's usually the whole chunk.
            if chunk.candidates[0].content.parts[0].function_call:
                # Tool call detected in stream.
                # Logic: collect all chunks, execute, then re-call generate
                # But typically Gemini tool calls are non-streaming in the functional part.
                # For simplicity, if we detect a tool call, we stop streaming and handle as full.
                # Gemini tool calls in stream usually contain the whole call in one candidate.
                
                from orionagent.tools.tool_executor import ToolExecutor
                executor = ToolExecutor()
                
                tool_outputs = []
                for part in chunk.candidates[0].content.parts:
                    if part.function_call:
                        res = executor.execute(part.function_call.name, part.function_call.args, tools)
                        tool_outputs.append({"name": part.function_call.name, "output": res})

                from google.genai import types
                history = [
                    types.Content(role="user", parts=[types.Part(text=prompt)]),
                    chunk.candidates[0].content,
                    types.Content(role="user", parts=[
                        types.Part(function_response=types.FunctionResponse(name=o["name"], response={"result": o["output"]})) for o in tool_outputs
                    ])
                ]

                final_stream = self._client.models.generate_content_stream(
                    model=self.model_name,
                    contents=history,
                    config=config,
                )
                for final_chunk in final_stream:
                    if final_chunk.text:
                        yield final_chunk.text
                return

            if chunk.text:
                yield chunk.text
