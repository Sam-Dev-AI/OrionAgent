"""Ollama provider for OrionAI.
"""

import os
import json
import requests
from typing import Any, Generator, Optional, List
from orionagent.models.base_provider import ModelProvider
from orionagent.tools.base_tool import Tool


class Ollama(ModelProvider):
    """LLM provider backed by a local Ollama server."""

    def __init__(
        self,
        model_name: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        temperature: Optional[float] = None,
        token_count: bool = False,
        streaming: bool = True,
        verbose: bool = False,
        debug: bool = False,
    ):
        super().__init__(token_count=token_count, streaming=streaming, verbose=verbose, debug=debug)
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        
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

    def _print_token_usage(self, response: dict) -> None:
        """Accumulate token counts from Ollama response."""
        self.session_input_tokens += (response.get("prompt_eval_count") or 0)
        self.session_output_tokens += (response.get("eval_count") or 0)
        self.session_total_tokens += (response.get("prompt_eval_count", 0) + response.get("eval_count", 0))

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Tool]] = None,
    ) -> str:
        """Send *prompt* to Ollama."""
        url = f"{self.base_url}/api/generate"
        
        options = {}
        temp = temperature if temperature is not None else self.temperature
        if temp is not None:
            options["temperature"] = temp
        if max_tokens:
            options["num_predict"] = max_tokens

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": options
        }
        if system_instruction:
            payload["system"] = system_instruction

        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        
        self._print_token_usage(data)
        return data["response"]

    def generate_stream(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Tool]] = None,
    ) -> Generator[str, None, None]:
        """Yield chunks from Ollama."""
        url = f"{self.base_url}/api/generate"
        
        options = {}
        temp = temperature if temperature is not None else self.temperature
        if temp is not None:
            options["temperature"] = temp
        if max_tokens:
            options["num_predict"] = max_tokens

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": True,
            "options": options
        }
        if system_instruction:
            payload["system"] = system_instruction

        response = requests.post(url, json=payload, stream=True)
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                if data.get("done"):
                    self._print_token_usage(data)
                yield data.get("response", "")
