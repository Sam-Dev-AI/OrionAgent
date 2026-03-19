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
        from google.genai import types
        config = self._build_config(
            system_instruction, 
            temperature if temperature is not None else self.temperature, 
            max_tokens, 
            tools
        )

        history = [types.Content(role="user", parts=[types.Part(text=prompt)])]
        
        def get_text(content):
            if not content or not content.parts:
                return ""
            return "".join(p.text for p in content.parts if p.text)

        while True:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=history,
                config=config,
            )
            self._print_token_usage(response.usage_metadata)

            if not response.candidates or not response.candidates[0].content:
                return ""

            content = response.candidates[0].content
            history.append(content)

            has_function_call = any(part.function_call for part in content.parts)
            if not has_function_call:
                return get_text(content)

            # Process Tool Calls
            from orionagent.tools.tool_executor import ToolExecutor
            executor = ToolExecutor()
            
            tool_parts = []
            for part in content.parts:
                if part.function_call:
                    name = part.function_call.name
                    args = part.function_call.args
                    if self.verbose:
                        print(f"\033[94m[TOOL CALL: {name}({args})]\033[0m")
                    res = executor.execute(name, args, tools)
                    tool_parts.append(
                        types.Part(function_response=types.FunctionResponse(name=name, response={"result": res}))
                    )
            
            history.append(types.Content(role="user", parts=tool_parts))
            # Loop continues to get the next model response based on tool output

    def generate_stream(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Tool]] = None,
    ) -> Generator[str, None, None]:
        """Yield chunks from Gemini. Intercepts and executes tools automatically."""
        from google.genai import types
        config = self._build_config(
            system_instruction, 
            temperature if temperature is not None else self.temperature, 
            max_tokens, 
            tools
        )

        history = [types.Content(role="user", parts=[types.Part(text=prompt)])]

        while True:
            stream = self._client.models.generate_content_stream(
                model=self.model_name,
                contents=history,
                config=config,
            )

            current_content_parts = []
            has_tool_call = False
            
            last_usage = None
            for chunk in stream:
                if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                    last_usage = chunk.usage_metadata

                if not chunk.candidates or not chunk.candidates[0].content:
                    continue

                content = chunk.candidates[0].content
                for part in content.parts:
                    if part.text:
                        current_content_parts.append(part)
                        yield part.text
                    elif part.function_call:
                        has_tool_call = True
                        current_content_parts.append(part)
                        # Print to logs only if verbose
                        if self.verbose:
                            print(f"\n\033[94m[TOOL CALL: {part.function_call.name}]\033[0m")
            
            # Apply usage only once per stream turn
            if last_usage:
                self._print_token_usage(last_usage)

            # After stream finishes, check if we need to call tools
            full_content = types.Content(role="model", parts=current_content_parts)
            history.append(full_content)

            if not has_tool_call:
                break

            # Execute tools and add results to history
            from orionagent.tools.tool_executor import ToolExecutor
            executor = ToolExecutor()
            
            tool_parts = []
            for part in current_content_parts:
                if part.function_call:
                    name = part.function_call.name
                    args = part.function_call.args
                    res = executor.execute(name, args, tools)
                    tool_parts.append(
                        types.Part(function_response=types.FunctionResponse(name=name, response={"result": res}))
                    )
            
            history.append(types.Content(role="user", parts=tool_parts))
            # Loop restarts with history containing tool responses
