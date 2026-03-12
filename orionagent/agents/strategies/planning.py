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


_PLANNING_PROMPT = """You are a task planner. Break the task into 1-4 steps.
Available agents:
{agents}

Reply ONLY with a JSON array of groups. Each group is an array of steps that can run in PARALLEL.
Format: [[{{"s": "instruction", "a": "agent_name"}}, ...], [...]]
IMPORTANT: If an agent has output constraints (e.g. 'straight' or 'short'), ensure the instruction 's' explicitly mentions these constraints to ensure compliance.

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
        verbose: bool = False,
        debug: bool = False,
        record_trace: bool = True,
        hitl: bool = False,

    ) -> Union[str, Generator[str, None, None]]:
        from orionagent.tracing import tracer
        # Fast bypass for simple conversational tasks
        if not self.is_complex_task(task):
            tracer.log_event("plan", "Bypassing planner", "Simple task detected", verbose=verbose, debug=debug)
            from orionagent.agents.strategies.direct import DirectStrategy
            return DirectStrategy().execute(task, agents, model, system_instruction, context, temperature, tools, stream, async_mode, verbose, debug, record_trace=record_trace, hitl=hitl)

        if not model:
            # No model to plan with -- fall back to single delegation
            from orionagent.agents.strategies.direct import DirectStrategy
            return DirectStrategy().execute(task, agents, model, system_instruction, context, temperature, tools, stream, async_mode, verbose, debug, record_trace=record_trace, hitl=hitl)

        from orionagent.tracing import tracer
        trace_id = tracer.start_trace("plan", "Creating task plan", task, verbose=verbose, debug=debug)
        plan = self._create_plan(task, agents, model, system_instruction, context, temperature, verbose=verbose, debug=debug)
        tracer.end_trace(trace_id, f"Plan created: {len(plan)} steps")

        # HITL Approval Gate
        if hitl:
            from orionagent.agents.hitl import HitlConfig
            h_cfg = hitl if isinstance(hitl, HitlConfig) else HitlConfig()
            if not self._approve_plan(plan, task, h_cfg):
                raise InterruptedError("Plan rejected by user via HITL.")


        if stream:
            return self._stream_plan(plan, agents, task, model, async_mode, temperature=temperature)
        return self._execute_plan_full(plan, agents, task, model, async_mode, temperature=temperature)

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
        verbose: bool = False,
        debug: bool = False,
    ) -> list:
        """Ask the LLM to produce a compact JSON plan."""
        from orionagent.tracing import tracer
        tracer.log_event("plan", "Decomposing task into steps", task[:50], verbose=verbose, debug=debug)
        roster = "\n".join(
            f"- {a.name} ({a.role}): {a.description}" for a in agents
        )
        
        prompt_task = f"{context}\n\n==== CURRENT TASK ====\n{task}" if context else task
        prompt = _PLANNING_PROMPT.format(agents=roster, task=prompt_task)
        
        si = system_instruction + "\n\nReply with valid JSON only. No markdown, no explanation." if system_instruction else "Reply with valid JSON only. No markdown, no explanation."

        raw = model.generate(
            prompt=prompt,
            system_instruction=si,
            temperature=temperature if temperature is not None else 0.0,
        )

        # Parse -- strip markdown fences if the model wraps them
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]  # drop opening fence
            raw = raw.rsplit("```", 1)[0]  # drop closing fence
            raw = raw.strip()

        try:
            plan = json.loads(raw)
        except json.JSONDecodeError:
            # If parsing fails, fall back to single-agent routing
            return [{"step": task, "agent": None}]

        if not isinstance(plan, list) or not plan:
            return [{"step": task, "agent": None}]

        return plan

    # ------------------------------------------------------------------
    # Plan execution
    # ------------------------------------------------------------------

    def _find_agent(self, name: Optional[str], agents: List[Agent]) -> Agent:
        """Find agent by name, fall back to first agent."""
        if name:
            for a in agents:
                if a.name.lower() == name.lower():
                    return a
        return agents[0]

    def _execute_plan_full(
        self, plan: list, agents: List[Agent], original_task: str, model: Any = None, async_mode: bool = True, temperature: Optional[float] = None
    ) -> str:
        """Execute all plan steps and return ONLY the final result."""
        import concurrent.futures
        last_result = ""

        # plan is now List[List[Dict]] (groups of parallel steps)
        for group in plan:
            if not isinstance(group, list):
                group = [group] # robustness for single-step legacy or malformed plans
                
            if len(group) == 1 or not async_mode:
                # Single step in group or async disabled, run sequentially
                for step in group:
                    instruction = step.get("s", step.get("step", original_task))
                    agent = self._find_agent(step.get("a", step.get("agent")), agents)
                    prompt = f"Previous result: {last_result}\n\nTask: {instruction}" if last_result else instruction
                    last_result = agent.ask(prompt, stream=False, use_strategy=False, record_memory=False, record_trace=False, temperature=temperature)
            else:
                # Parallel group
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = []
                    for step in group:
                        instruction = step.get("s", step.get("step", original_task))
                        agent = self._find_agent(step.get("a", step.get("agent")), agents)
                        prompt = f"Previous result: {last_result}\n\nTask: {instruction}" if last_result else instruction
                        futures.append(executor.submit(agent.ask, prompt, False, False, None, False, False, None, temperature)) # task, stream, use_strategy, session_id, record_memory, record_trace, priority, temperature
                    
                    results = [f.result() for f in concurrent.futures.as_completed(futures)]
                    last_result = "\n".join(results)

        return last_result

    def _stream_plan(
        self, plan: list, agents: List[Agent], original_task: str, model: Any = None, async_mode: bool = True, temperature: Optional[float] = None
    ) -> Generator[str, None, None]:
        """Stream plan execution, yielding ONLY the final step's result."""
        import concurrent.futures
        last_result = ""
        
        for i, group in enumerate(plan, 1):
            if not isinstance(group, list):
                group = [group]
                
            is_final_group = (i == len(plan))
            
            if len(group) == 1 or not async_mode:
                for step_idx, step in enumerate(group):
                    instruction = step.get("s", step.get("step", original_task))
                    agent = self._find_agent(step.get("a", step.get("agent")), agents)
                    prompt = f"Previous result: {last_result}\n\nTask: {instruction}" if last_result else instruction
                    
                    is_final_step = is_final_group and (step_idx == len(group) - 1)
                    
                    if is_final_step:
                        yield from agent.ask(prompt, stream=True, use_strategy=False, record_memory=False, record_trace=False, temperature=temperature)
                    else:
                        last_result = agent.ask(prompt, stream=False, use_strategy=False, record_memory=False, record_trace=False, temperature=temperature)
            else:
                # Parallel group execution
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = []
                    for step in group:
                        instruction = step.get("s", step.get("step", original_task))
                        agent = self._find_agent(step.get("a", step.get("agent")), agents)
                        prompt = f"Previous result: {last_result}\n\nTask: {instruction}" if last_result else instruction
                        futures.append(executor.submit(agent.ask, prompt, False, False, None, False, False, None, temperature))
                    
                    results = [f.result() for f in concurrent.futures.as_completed(futures)]
                    last_result = "\n".join(results)
                    
                    if is_final_group:
                        yield last_result
                        
    def _approve_plan(self, plan: list, original_task: str, h_cfg: "HitlConfig") -> bool:
        """Interactive terminal approval for the generated plan."""
        if h_cfg.permission_level == "high":
            return True
        
        if h_cfg.ask_once and h_cfg.is_session_authorized:
            return True
        
        from orionagent.agents.hitl import is_risky_action
        if h_cfg.permission_level == "medium":
            plan_str = str(plan)
            if not is_risky_action(plan_str):
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
