"""Ollama provider for OrionAI.

Connects to a locally running Ollama server.
Install Ollama: https://ollama.com  |  Run: ollama pull llama3.2
"""

import json
import urllib.request
from typing import Generator, Optional, List
from orionagent.models.base_provider import ModelProvider
from orionagent.tools.base_tool import Tool


class Ollama(ModelProvider):
    """LLM provider backed by a local Ollama server."""

    def __init__(
        self,
        model_name: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        token_count: bool = False,
        streaming: bool = True,
        verbose: bool = False,
        debug: bool = False,
    ):
        super().__init__(token_count=token_count, streaming=streaming, verbose=verbose, debug=debug)
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        
        self.session_input_tokens = 0
        self.session_output_tokens = 0
        self.session_total_tokens = 0


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

    def _print_token_usage(self, response_json: dict) -> None:
        """Accumulate token counts silently. Use print_session_tokens() to display."""
        prompt_tokens = (response_json.get("prompt_eval_count") or 0)
        completion_tokens = (response_json.get("eval_count") or 0)
        
        self.session_input_tokens += prompt_tokens
        self.session_output_tokens += completion_tokens
        self.session_total_tokens += (prompt_tokens + completion_tokens)

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Tool]] = None,
    ) -> str:
        """Send *prompt* to Ollama. Intercepts and executes tools automatically."""
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        while True:
            payload = {
                "model": self.model_name,
                "messages": messages,
                "stream": False,
                "options": self._build_options(temperature, max_tokens),
            }
            if tools:
                payload["tools"] = [
                    {
                        "type": "function", 
                        "function": {"name": t.name, "description": t.description, "parameters": t.parameters}
                    } for t in tools
                ]

            req = urllib.request.Request(
                f"{self.base_url}/api/chat",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req) as resp:
                    data = json.loads(resp.read())
                    self._print_token_usage(data)
                    
                    message = data.get("message", {})
                    
                    if message.get("tool_calls"):
                        messages.append(message) # Keep model's tool call turn
                        
                        for tc in message["tool_calls"]:
                            func_call = tc["function"]
                            target = next((t for t in tools if t.name == func_call["name"]), None)
                            if target:
                                from orionagent.tracing import tracer
                                args_str = json.dumps(func_call["arguments"]) if isinstance(func_call["arguments"], dict) else str(func_call["arguments"])
                                tracer.log_event("tool", f"Executing {func_call['name']}", args_str, verbose=self.verbose, debug=self.debug)
                                try:
                                    res = target.run(args_str)
                                except Exception as e:
                                    res = f"Error: {e}"
                            else:
                                res = f"Unknown tool: {func_call['name']}"
                                
                            messages.append({
                                "role": "tool",
                                "content": str(res)
                            })
                    else:
                        content = message.get("content", "")
                        return content
            except Exception as e:
                return f"Error connecting to Ollama: {e}"

    def generate_stream(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Tool]] = None,
    ) -> Generator[str, None, None]:
        """Stream response chunks from Ollama in real-time, handling tools automatically."""
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        while True:
            payload = {
                "model": self.model_name,
                "messages": messages,
                "stream": True,
                "options": self._build_options(temperature, max_tokens),
            }
            if tools:
                payload["tools"] = [
                    {
                        "type": "function", 
                        "function": {"name": t.name, "description": t.description, "parameters": t.parameters}
                    } for t in tools
                ]

            req = urllib.request.Request(
                f"{self.base_url}/api/chat",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            
            tool_calls = []
            text_buffer = []
            
            try:
                with urllib.request.urlopen(req) as resp:
                    for line in resp:
                        if not line:
                            continue
                        chunk = json.loads(line)
                        msg = chunk.get("message", {})
                        
                        # Handle text
                        if msg.get("content"):
                            text = msg["content"]
                            text_buffer.append(text)
                            yield text
                            
                        # Handle tool calls (Ollama usually sends them at the end of the stream)
                        if msg.get("tool_calls"):
                            tool_calls.extend(msg["tool_calls"])
                            
                        if chunk.get("done"):
                            self._print_token_usage(chunk)
                            break
                
                if tool_calls:
                    messages.append({"role": "assistant", "tool_calls": tool_calls})
                    for tc in tool_calls:
                        func_call = tc["function"]
                        target = next((t for t in tools if t.name == func_call["name"]), None)
                        if target:
                            from orionagent.tracing import tracer
                            args_str = json.dumps(func_call["arguments"]) if isinstance(func_call["arguments"], dict) else str(func_call["arguments"])
                            tracer.log_event("tool", f"Executing {func_call['name']}", args_str, verbose=self.verbose, debug=self.debug)
                            try:
                                res = target.run(args_str)
                            except Exception as e:
                                res = f"Error: {e}"
                        else:
                            res = f"Unknown tool: {func_call['name']}"
                        
                        messages.append({
                            "role": "tool",
                            "content": str(res)
                        })
                    # Loop continues
                    continue
                else:
                    return

            except Exception as e:
                yield f"\nError connecting to Ollama: {e}"
                return

    @staticmethod
    def _build_options(temperature, max_tokens) -> dict:
        opts = {}
        if temperature is not None:
            opts["temperature"] = temperature
        if max_tokens is not None:
            opts["num_predict"] = max_tokens
        return opts
