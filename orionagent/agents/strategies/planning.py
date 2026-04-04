"""Planning strategy for Manager orchestration.

The default strategy. Uses the Manager's LLM to decompose a task
into small steps, assigns each step to the best agent, and executes
them sequentially. Optimised for low token usage:
  - Planning prompt is minimal (~100 instruction tokens)
  - Each step prompt only contains what that agent needs
  - No context duplication between steps
"""

import json
from typing import Generator, List, Optional, Union, Any

from orionagent.agents.base_agent import Agent
from orionagent.agents.strategies.base import BaseStrategy
from orionagent.models.base_provider import ModelProvider
from orionagent.agents.hitl import is_risky_action


_PLANNING_PROMPT = """[INDUSTRIAL PLANNER]
1. Decompose task into efficient steps using available agents.
2. Respect USER CONSTRAINTS (allowed_agents, blocked_agents, force_agent).
3. Output ONLY strict JSON. No markdown, no filler.

Schema:
{{
  "plan": [
    {{
      "step_id": 1,
      "task": "step description",
      "agent": "agent_name",
      "reason": "why this agent?"
    }}
  ],
  "metadata": {{
    "confidence": 0.9
  }}
}}

Agents:
{agents}

Task: {task}"""


class PlanningStrategy(BaseStrategy):
    """Decomposes a task into steps, delegates each to the best agent.

    This is the default Manager strategy -- always plans before executing.
    """

    def execute(
        self,
        task: str,
        agents: List[Agent],
        model: Optional[ModelProvider],
        system_instruction: Optional[str] = None,
        context: Optional[str] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Any]] = None,
        stream: bool = True,
        async_mode: bool = True,
        record_trace: bool = True,
        hitl: bool = False,
        priority: Optional[str] = None,
        manager_context: Optional[str] = None,
        on_step_complete: Optional[Any] = None,

    ) -> Union[str, Generator[str, None, None]]:
        from orionagent.tracing import tracer
        
        if not model:
            # No model to plan with -- fall back to single delegation
            from orionagent.agents.strategies.direct import DirectStrategy
            return DirectStrategy().execute(task, agents, model, system_instruction, context, temperature, tools, stream, async_mode, record_trace=record_trace, hitl=hitl, priority=priority, manager_context=manager_context, on_step_complete=on_step_complete)

        # Efficiency Gate: Check if planning is actually needed
        if not self._requires_planning(task, agents, model, system_instruction, context, temperature):
            if model.verbose: print("\n[PLANNER] Skipping planning stage for simple task.")
            
            # RELAX INSTRUCTION: Remove strict JSON/No-Conversation rules for simple turns
            relaxed_instruction = self._relax_instruction(system_instruction)
            
            from orionagent.agents.strategies.direct import DirectStrategy
            return DirectStrategy().execute(task, agents, model, relaxed_instruction, context, temperature, tools, stream, async_mode, record_trace=record_trace, hitl=hitl, priority=priority, manager_context=manager_context, on_step_complete=on_step_complete)

        from orionagent.tracing import tracer
        trace_id = tracer.start_trace("plan", "Creating task plan", task, verbose=model.verbose, debug=model.debug)
        plan = self._create_plan(task, agents, model, system_instruction, context, temperature, tools=tools)
        tracer.end_trace(trace_id, f"Plan created: {len(plan)} steps")

        # HITL Approval Gate
        if hitl:
            from orionagent.agents.hitl import HitlConfig
            h_cfg = hitl if isinstance(hitl, HitlConfig) else HitlConfig()
            if not self._approve_plan(plan, task, h_cfg, model=model):
                raise InterruptedError("Plan rejected by user via HITL.")


        if stream:
            return self._stream_plan(plan, agents, task, model, async_mode, priority=priority, temperature=temperature, tools=tools, manager_context=manager_context, on_step_complete=on_step_complete, verbose=model.verbose)
        return self._execute_plan_full(plan, agents, task, model, async_mode, priority=priority, temperature=temperature, tools=tools, manager_context=manager_context, on_step_complete=on_step_complete, verbose=model.verbose)

    # ------------------------------------------------------------------
    # Plan creation
    # ------------------------------------------------------------------

    def _create_plan(
        self,
        task: str,
        agents: List[Agent],
        model: ModelProvider,
        system_instruction: Optional[str] = None,
        context: Optional[str] = None,
        temperature: Optional[float] = None,
        tools: Optional[List[Any]] = None,
    ) -> list:
        """Ask the LLM to produce a compact JSON plan."""
        from orionagent.tracing import tracer
        roster_parts = []
        for a in agents:
            tools_list = [t.name for t in a.tools] if hasattr(a, 'tools') else []
            roster_parts.append(f"- Agent {a.name} ({a.role}): {a.description}. Tools: {tools_list}")
        
        # Include Manager-level tools in the roster
        if tools:
            for t in tools:
                roster_parts.append(f"- Manager Tool {t.name}: {t.description}")
                
        roster = "\n".join(roster_parts)
        
        if context:
            prompt_task = (
                f"{context}\n\n"
                f"==== ACTIVE TASK ====\n"
                f"IMPORTANT: The context above is for reference ONLY. "
                f"Plan for the following request:\n\n"
                f"{task}"
            )
        else:
            prompt_task = task
        prompt = _PLANNING_PROMPT.format(agents=roster, task=prompt_task)
        
        si = system_instruction + "\n\nReply with valid JSON only. No markdown, no explanation." if system_instruction else "Reply with valid JSON only. No markdown, no explanation."

        raw = model.generate(
            prompt=prompt,
            system_instruction=si,
            temperature=temperature if temperature is not None else 0.0,
        )
        
        if model.debug:
            print(f"\n[ORCHESTRATOR RAW]: {raw}")
 
        # Parse -- strip markdown fences if the model wraps them
        raw_clean = raw.strip()
        if raw_clean.startswith("```"):
            raw_clean = raw_clean.split("\n", 1)[1]  # drop opening fence
            raw_clean = raw_clean.rsplit("```", 1)[0]  # drop closing fence
            raw_clean = raw_clean.strip()
 
        try:
            data = json.loads(raw_clean)
            if isinstance(data, dict) and "plan" in data:
                plan = data["plan"]
            elif isinstance(data, list):
                plan = data
            else:
                plan = [{"task": task, "agent": None}]
        except json.JSONDecodeError as e:
            if model.verbose: print(f"[PLANNER ERROR] Failed to parse JSON: {e}")
            return [{"task": task, "agent": None}]

        if not isinstance(plan, list) or not plan:
            return [{"task": task, "agent": None}]

        return plan

    def _requires_planning(
        self,
        task: str,
        agents: List[Agent],
        model: ModelProvider,
        system_instruction: Optional[str] = None,
        context: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> bool:
        """Quickly check if the task needs decomposition or can be handled as a single step."""
        # Fast local checking instead of token-heavy LLM call
        return self.is_complex_task(task)

    def _relax_instruction(self, instruction: Optional[str]) -> Optional[str]:
        """Strip planning-specific strictness for simple/conversational tasks."""
        if not instruction:
            return instruction
        
        # 1. Remove JSON output format section
        if "[OUTPUT FORMAT - STRICT JSON]" in instruction:
            instruction = instruction.split("[OUTPUT FORMAT - STRICT JSON]")[0]
            
        # 2. Relax strict 'no-answer' rules
        instruction = instruction.replace("* DO NOT generate code, search the web, or produce final user answers.", "")
        instruction = instruction.replace("* Do NOT include conversational text.", "")
        instruction = instruction.replace("* ONLY delegate and coordinate.", "* Coordinate agents and handle general context.")
        
        # 3. Add conversational capability
        instruction += (
            "\n\n[CONVERSATION RULE]\n"
            "* If the task is a greeting, identity question, or doesn't require agent delegation, "
            "respond directly as the Manager."
        )
        return instruction.strip()

    # ------------------------------------------------------------------
    # Plan execution
    # ------------------------------------------------------------------

    def _find_agent_or_tool(self, name: Optional[str], agents: List[Agent], manager_tools: Optional[List[Any]] = None) -> Union[Agent, Any]:
        """Find agent by name or return a tool if the name matches."""
        if name:
            for a in agents:
                if a.name.lower() == name.lower():
                    return a
            if manager_tools:
                for t in manager_tools:
                    if t.name.lower() == name.lower():
                        return t
        return agents[0]

    def _execute_plan_full(
        self, plan: list, agents: List[Agent], original_task: str, model: Any = None, async_mode: bool = True, priority: Optional[str] = None, temperature: Optional[float] = None, tools: Optional[List[Any]] = None, manager_context: Optional[str] = None, on_step_complete: Optional[Any] = None, verbose: bool = False
    ) -> str:
        """Execute all plan steps and return a synthesized final result."""
        results = []
        last_result = ""
        # Execute steps sequentially based on the new flat plan schema
        for step in plan:
            # Safeguard: Trim context
            if len(last_result) > 10000:
                last_result = last_result[:5000] + "\n... [context truncated] ...\n" + last_result[-5000:]
            
            # Robustness for either old or new step keys
            instruction = step.get("task", step.get("s", step.get("step", original_task)))
            target_name = step.get("agent", step.get("a", "Unknown"))
            # Pass agents and tools (from signature) to the lookup
            target = self._find_agent_or_tool(target_name, agents, tools)
            
            # Build prompt with global context + step context
            prompt_parts = []
            if manager_context:
                prompt_parts.append(f"### GLOBAL CONTEXT ###\n{manager_context}")
            if last_result:
                prompt_parts.append(f"### PREVIOUS STEP CONTEXT ###\n{last_result}")
            prompt_parts.append(f"### TASK ###\n{instruction}")
            prompt = "\n\n".join(prompt_parts)
            
            # Case 1: Target is an Agent
            if isinstance(target, Agent):
                last_result = target.ask(
                    task=prompt,
                    stream=False,
                    use_strategy=False,
                    record_memory=False,
                    record_trace=True,
                    priority=priority,
                    temperature=temperature
                )
            # Case 2: Target is a Manager Tool
            else:
                # Tools might expect specific args, but for simple planning we pass prompt as 'task' if it accepts it
                import inspect
                sig = inspect.signature(target.run)
                if 'task' in sig.parameters or any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()):
                    last_result = target.run(input_data={'task': prompt})
                else:
                    last_result = target.run(input_data={})
            # Record step result into Manager's global memory
            if on_step_complete:
                on_step_complete(target_name, instruction, last_result)
            
            results.append({"agent": target_name, "task": instruction, "output": last_result})

        # Final Aggregation / Synthesis Layer
        return self._synthesize_results(original_task, results, model, verbose=verbose)

    def _stream_plan(
        self, plan: list, agents: List[Agent], original_task: str, model: Any = None, async_mode: bool = True, priority: Optional[str] = None, temperature: Optional[float] = None, tools: Optional[List[Any]] = None, manager_context: Optional[str] = None, on_step_complete: Optional[Any] = None, verbose: bool = False
    ) -> Generator[str, None, None]:
        """Stream plan execution, yielding debug info and the final synthesized result."""
        results = []
        last_result = ""
        for i, step in enumerate(plan, 1):
            if len(last_result) > 10000:
                last_result = last_result[:5000] + "\n... [context truncated] ...\n" + last_result[-5000:]
                
            instruction = step.get("task", step.get("s", step.get("step", original_task)))
            target_name = step.get("agent", step.get("a", "Unknown"))
            # Pass agents and tools (from signature) to the lookup
            target = self._find_agent_or_tool(target_name, agents, tools)
            
            # Only show visual headers if verbose is enabled
            if verbose:
                yield f"\n\033[1m[STEP {i}] {target_name}: {instruction}\033[0m\n"
            
            # Build prompt with global context + step context
            prompt_parts = []
            if manager_context:
                prompt_parts.append(f"### GLOBAL CONTEXT ###\n{manager_context}")
            if last_result:
                prompt_parts.append(f"### PREVIOUS STEP CONTEXT ###\n{last_result}")
            prompt_parts.append(f"### TASK ###\n{instruction}")
            prompt = "\n\n".join(prompt_parts)
            
            step_res = ""
            if isinstance(target, Agent):
                for chunk in target.ask(
                    task=prompt, 
                    stream=True, 
                    use_strategy=False, 
                    record_memory=False, 
                    record_trace=True, 
                    priority=priority, 
                    temperature=temperature
                ):
                    step_res += chunk
                    if verbose:
                        yield chunk
            else:
                # Tool execution (Tools are synchronous for now)
                import inspect
                sig = inspect.signature(target.run)
                if 'task' in sig.parameters or any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()):
                    step_res = target.run(input_data={'task': prompt})
                else:
                    step_res = target.run(input_data={})
                if verbose:
                    yield step_res
            
            last_result = step_res
            # Record step result into Manager's global memory
            if on_step_complete:
                on_step_complete(target_name, instruction, step_res)
            
            results.append({"agent": target_name, "task": instruction, "output": step_res})
            if verbose:
                yield "\n"

        # Final Aggregation / Synthesis Layer (Streaming)
        if verbose:
            yield "\n\033[1m[FINAL SYNTHESIS]\033[0m\n"
        
        final_answer = self._synthesize_results(original_task, results, model, verbose=verbose)
        
        # Format as JSON if required by user feedback (standardizing)
        res_obj = {
            "final_answer": final_answer,
            "trace": results if verbose else []
        }
        
        # If output needs to be a clean string, just yield the answer. 
        # But user requested JSON format: { "final_answer": "..." }
        yield json.dumps(res_obj, indent=2)

    def _synthesize_results(self, original_task: str, results: List[dict], model: Any, verbose: bool = False) -> str:
        """Combine all agent outputs into one coherent final response."""
        if not model:
            return results[-1]["output"] if results else "No results."

        # Filter out empty or meta-only outputs
        data_text = "\n\n".join([f"Agent ({r['agent']}): {r['output'][:5000]}" for r in results])
        
        prompt = (
            f"You are a master synthesiser. Based on the following research/work results, "
            f"provide a clean, professional, and comprehensive final answer to the user's original task.\n\n"
            f"ORIGINAL TASK: {original_task}\n\n"
            f"AGENT RESULTS:\n{data_text}\n\n"
            f"### FINAL ANSWER ###"
        )
        
        system_instruction = (
            "You are a master synthesiser. Join all agent results into a single, cohesive, "
            "and clean final response. NO conversational filler. NO markers like 'Synthesised Result:'. "
            "Just the clean answer."
        )
        
        try:
            return model.generate(prompt=prompt, system_instruction=system_instruction)
        except Exception as e:
            if verbose: print(f"[SYNTHESIS ERROR] {e}")
            return results[-1]["output"] if results else "Error during synthesis."
                        
    def _approve_plan(self, plan: list, original_task: str, h_cfg: "HitlConfig", model: Optional[ModelProvider] = None) -> bool:
        """Interactive terminal approval for the generated plan."""
        if h_cfg.permission_level == "high":
            return True
        
        if h_cfg.ask_once and h_cfg.is_session_authorized:
            return True
        
        if h_cfg.permission_level == "medium":
            plan_str = str(plan)
            # Efficient: Pass the model for LLM-based risk check
            if not is_risky_action(plan_str, model=model if h_cfg.use_llm else None):
                return True

        print(f"\n\033[1m[ORION HITL] Task Approval Required\033[0m")
        print(f"Goal: {original_task}")
        print("-" * 40)
        
        if h_cfg.plan_review:
            for i, group in enumerate(plan, 1):
                print(f"Group {i}:")
                for step in group:
                    agent = step.get("a", step.get("agent", "Unknown"))
                    instr = step.get("s", step.get("step", ""))
                    print(f"  - [{agent}]: {instr}")
        else:
            print("Plan Review disabled. High-level goal approval only.")
        
        print("-" * 40)
        choice = input("Approve plan? (y/n): ").strip().lower()
        if choice == 'y':
            print("\033[32m[APPROVED] Executing...\033[0m")
            if h_cfg.ask_once:
                h_cfg.authorize_session()
            return True
        else:
            print("\033[31m[ABORTED] Plan rejected by user.\033[0m")
            return False

        print("\033[32m[APPROVED] Executing plan...\033[0m\n")
