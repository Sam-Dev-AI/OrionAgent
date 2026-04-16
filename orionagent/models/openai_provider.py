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
        thinking: bool = False,
        show_thinking: bool = True,
    ):
        super().__init__(
            token_count=token_count,
            streaming=streaming,
            verbose=verbose,
            debug=debug,
            thinking=thinking,
            show_thinking=show_thinking
        )
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
            
        in_tokens = usage.prompt_tokens or 0
        out_tokens = usage.completion_tokens or 0
        tot_tokens = usage.total_tokens or 0
        
        self.session_input_tokens += in_tokens
        self.session_output_tokens += out_tokens
        self.session_total_tokens += tot_tokens
        
        if self.token_count:
            print(f"\033[35m[Tokens] In: {in_tokens} | Out: {out_tokens} | Total: {tot_tokens}\033[0m", flush=True)

    def _parse_rogue_tool_calls(self, content: str) -> List[dict]:
        """Intercept XML-style tool calls (e.g. from Nemotron) and format as standard tool calls."""
        if not content or "<tool_call>" not in content:
            return []
            
        import re
        # Format: <tool_call><function=name><parameter=key>val</parameter></function></tool_call>
        calls = []
        raw_calls = re.findall(r"<tool_call>(.*?)</tool_call>", content, re.DOTALL)
        
        for rc in raw_calls:
            func_match = re.search(r"<function=(.*?)>", rc)
            if not func_match: continue
            name = func_match.group(1).strip()
            
            # Extract parameters
            args = {}
            params = re.findall(r"<parameter=(.*?)>(.*?)</parameter>", rc, re.DOTALL)
            for k, v in params:
                args[k.strip()] = v.strip()
            
            calls.append({
                "id": f"rogue_{name[:10]}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)}
            })
        return calls

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

        # Handle o1/o3 temperature constraint
        is_reasoning_model = self.model_name.startswith("o1") or self.model_name.startswith("o3")
        temp = temperature if temperature is not None else self.temperature
        
        # o1 models do not support temperature
        if is_reasoning_model:
            temp = None

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

        if not response.choices:
            return ""

        message = response.choices[0].message
        res = message.content or ""

        # Thinking filtering
        if self.thinking and not self.show_thinking:
            import re
            # Strip <thought>...</thought> and <reasoning>...</reasoning>
            res = re.sub(r"<(thought|reasoning)>.*?</\1>", "", res, flags=re.DOTALL).strip()
        
        # INTERCEPT ROGUE TOOLS (Nemotron XML)
        rogue_calls = self._parse_rogue_tool_calls(res)
        
        if message.tool_calls or rogue_calls:
            from orionagent.tools.tool_executor import ToolExecutor
            executor = ToolExecutor()
            
            messages.append(message) # Add assistant message to history
            
            # Unify standard and rogue calls for execution
            all_calls = []
            if message.tool_calls:
                all_calls.extend(message.tool_calls)
            
            for rc in rogue_calls:
                # Mock tool_call object for the loop
                class MockCall:
                    def __init__(self, id, name, args):
                        self.id = id
                        self.function = type('obj', (object,), {'name': name, 'arguments': args})
                all_calls.append(MockCall(rc["id"], rc["function"]["name"], rc["function"]["arguments"]))

            for tool_call in all_calls:
                name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except:
                    args = tool_call.function.arguments

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

        # Handle o1/o3 temperature constraint
        is_reasoning_model = self.model_name.startswith("o1") or self.model_name.startswith("o3")
        temp = temperature if temperature is not None else self.temperature
        
        # o1 models do not support temperature
        if is_reasoning_model:
            temp = None

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
        full_content = []
        
        in_thought = False
        thought_tags = ["<thought>", "<reasoning>"]
        end_thought_tags = ["</thought>", "</reasoning>"]
        
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
                content = delta.content
                full_content.append(content)
                
                # Thinking filtering
                if self.thinking and not self.show_thinking:
                    content_lower = content.lower()
                    
                    if any(tag in content_lower for tag in thought_tags):
                        in_thought = True
                        continue
                    
                    if any(tag in content_lower for tag in end_thought_tags):
                        in_thought = False
                        continue
                    
                    if in_thought:
                        continue
                
                yield content

        # INTERCEPT ROGUE TOOLS in accumulated history? 
        # Actually in stream we yield chunks immediately. 
        # For Nemotron, we'd need to collect the whole stream if we suspect tool calls.
        # But our current stream loop yields immediately.
        # FIX: We only intercept rogue calls if THEY WERE IN THE OUTPUT.
        # But we already yielded them to the user.
        # That's fine, we can still execute them and yield the final result.

        # INTERCEPT ROGUE TOOLS in accumulated content
        rogue_calls = self._parse_rogue_tool_calls("".join(full_content))

        if full_tool_calls or rogue_calls:
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
            
            for rc in rogue_calls:
                tool_calls_payload.append(rc)
            
            messages.append({"role": "assistant", "content": "".join(full_content) or None, "tool_calls": tool_calls_payload})

            # Execute standard tool calls
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
            
            # Execute rogue tool calls
            for rc in rogue_calls:
                name = rc["function"]["name"]
                args = json.loads(rc["function"]["arguments"])
                res = executor.execute(name, args, tools)
                
                messages.append({
                    "tool_call_id": rc["id"],
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
                if not final_chunk.choices:
                    continue
                if final_chunk.choices[0].delta.content:
                    yield final_chunk.choices[0].delta.content
