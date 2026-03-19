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


_PLANNING_PROMPT = """[INDUSTRIAL PLANNER]
1. Decompose task into 1-4 efficient steps using available agents.
2. NEVER refuse a task. Always find a way to use tools to get closer to the goal.
3. If the task is broad (e.g. "leads"), first DISCOVER, then EXTRACT.

Agents:
{agents}

[FEW-SHOT EXAMPLES]
Task: "find hotels in NYC"
Output: [[{{"s":"Discover hotels in NYC","a":"TheResearcher"}}], [{{"s":"Extract contacts for found hotels","a":"TheScraper"}}]]

Task: "hotel leads in Mumbai without website"
Output: [[{{"s":"Search for hotels in Mumbai likely to lack websites","a":"TheResearcher"}}], [{{"s":"Scrape contact details for the discovered list","a":"TheScraper"}}]]

Output ONLY strict JSON: [[{{"s":"step_description","a":"agent_name"}},...], ...]
(Outer array is sequence, inner array is parallel group).
Dependent tasks MUST be in separate outer array blocks.

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
        priority: Optional[str] = None,

    ) -> Union[str, Generator[str, None, None]]:
        from orionagent.tracing import tracer
        
        if not model:
            # No model to plan with -- fall back to single delegation
            from orionagent.agents.strategies.direct import DirectStrategy
            return DirectStrategy().execute(task, agents, model, system_instruction, context, temperature, tools, stream, async_mode, verbose, debug, record_trace=record_trace, hitl=hitl, priority=priority)

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
            return self._stream_plan(plan, agents, task, model, async_mode, priority=priority, temperature=temperature)
        return self._execute_plan_full(plan, agents, task, model, async_mode, priority=priority, temperature=temperature)

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
            f"- {a.name} ({a.role}): {a.description}. Tools: {[t.name for t in a.tools]}" for a in agents
        )
        
        prompt_task = f"{context}\n\n==== CURRENT TASK ====\n{task}" if context else task
        prompt = _PLANNING_PROMPT.format(agents=roster, task=prompt_task)
        
        si = system_instruction + "\n\nReply with valid JSON only. No markdown, no explanation." if system_instruction else "Reply with valid JSON only. No markdown, no explanation."

        raw = model.generate(
            prompt=prompt,
            system_instruction=si,
            temperature=temperature if temperature is not None else 0.0,
        )
        
        if debug:
            print(f"\n[PLANNER RAW]: {raw}")
 
        # Parse -- strip markdown fences if the model wraps them
        raw_clean = raw.strip()
        if raw_clean.startswith("```"):
            raw_clean = raw_clean.split("\n", 1)[1]  # drop opening fence
            raw_clean = raw_clean.rsplit("```", 1)[0]  # drop closing fence
            raw_clean = raw_clean.strip()
 
        try:
            plan = json.loads(raw_clean)
        except json.JSONDecodeError as e:
            print(f"[PLANNER ERROR] Failed to parse JSON: {e}")
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
        self, plan: list, agents: List[Agent], original_task: str, model: Any = None, async_mode: bool = True, priority: Optional[str] = None, temperature: Optional[float] = None
    ) -> str:
        """Execute all plan steps and return ONLY the final result."""
        import concurrent.futures
        last_result = ""

        # plan is now List[List[Dict]] (groups of parallel steps)
        for group in plan:
            # Safeguard: Trim context if it gets too large to save tokens
            if len(last_result) > 10000:
                last_result = last_result[:5000] + "\n... [context truncated to save tokens] ...\n" + last_result[-5000:]
            
            if not isinstance(group, list):
                group = [group] # robustness for single-step legacy or malformed plans
                
            if len(group) == 1 or not async_mode:
                # Single step in group or async disabled, run sequentially
                for step in group:
                    instruction = step.get("s", step.get("step", original_task))
                    agent = self._find_agent(step.get("a", step.get("agent")), agents)
                    prompt = f"### DATA CONTEXT FROM PREVIOUS STEPS ###\n{last_result}\n\n### YOUR CURRENT TASK ###\n{instruction}\n\nINSTRUCTION: Process the data context above to fulfill your task. If data is missing, use your tools to find it. DO NOT ASK QUESTIONS." if last_result else instruction
                    last_result = agent.ask(
                        task=prompt, 
                        stream=False, 
                        use_strategy=False, 
                        record_memory=False, 
                        record_trace=True, 
                        priority=priority, 
                        temperature=temperature
                    )
            else:
                # Parallel group
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = []
                    for step in group:
                        instruction = step.get("s", step.get("step", original_task))
                        agent = self._find_agent(step.get("a", step.get("agent")), agents)
                        prompt = f"### DATA CONTEXT FROM PREVIOUS STEPS ###\n{last_result}\n\n### YOUR CURRENT TASK ###\n{instruction}\n\nINSTRUCTION: Process the data context above to fulfill your task. If data is missing, use your tools to find it. DO NOT ASK QUESTIONS." if last_result else instruction
                        futures.append(executor.submit(
                            agent.ask, 
                            task=prompt, 
                            stream=False, 
                            use_strategy=False, 
                            record_memory=False, 
                            record_trace=True, 
                            priority=priority, 
                            temperature=temperature
                        ))
                    
                    results = [f.result() for f in concurrent.futures.as_completed(futures)]
                    last_result = "\n".join(str(r) for r in results if r is not None)

        return last_result

    def _stream_plan(
        self, plan: list, agents: List[Agent], original_task: str, model: Any = None, async_mode: bool = True, priority: Optional[str] = None, temperature: Optional[float] = None
    ) -> Generator[str, None, None]:
        """Stream plan execution, yielding ONLY the final step's result."""
        import concurrent.futures
        last_result = ""
        
        for i, group in enumerate(plan, 1):
            # Safeguard: Trim context if it gets too large to save tokens
            if len(last_result) > 10000:
                last_result = last_result[:5000] + "\n... [context truncated to save tokens] ...\n" + last_result[-5000:]
                
            if not isinstance(group, list):
                group = [group]
                
            is_final_group = (i == len(plan))
            
            if len(group) == 1 or not async_mode:
                for step_idx, step in enumerate(group):
                    instruction = step.get("s", step.get("step", original_task))
                    agent_name = step.get("a", step.get("agent", "Unknown"))
                    agent = self._find_agent(agent_name, agents)
                    
                    yield f"\n\033[1m[STEP {i}] {agent_name}: {instruction}\033[0m\n"
                    
                    prompt = f"### DATA CONTEXT FROM PREVIOUS STEPS ###\n{last_result}\n\n### YOUR CURRENT TASK ###\n{instruction}\n\nINSTRUCTION: Process the data context above to fulfill your task. If data is missing, use your tools to find it. DO NOT ASK QUESTIONS." if last_result else instruction
                    
                    step_res = ""
                    for chunk in agent.ask(
                        task=prompt, 
                        stream=True, 
                        use_strategy=False, 
                        record_memory=False, 
                        record_trace=True, 
                        priority=priority, 
                        temperature=temperature
                    ):
                        step_res += chunk
                        yield chunk
                    
                    last_result = step_res
                    yield "\n"
            else:
                # Parallel group execution
                yield f"\n\033[1m[STEP {i}] Parallel Execution Group\033[0m\n"
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = []
                    for step in group:
                        instruction = step.get("s", step.get("step", original_task))
                        agent_name = step.get("a", step.get("agent", "Unknown"))
                        agent = self._find_agent(agent_name, agents)
                        prompt = f"Previous result: {last_result}\n\nTask: {instruction}" if last_result else instruction
                        futures.append(executor.submit(
                            agent.ask, 
                            task=prompt, 
                            stream=False, 
                            use_strategy=False, 
                            record_memory=False, 
                            record_trace=True, 
                            priority=priority, 
                            temperature=temperature
                        ))
                    
                    results = []
                    for future in concurrent.futures.as_completed(futures):
                        res = future.result()
                        results.append(res)
                        yield f"- {res}\n"
                    
                    last_result = "\n".join(results)
                        
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
