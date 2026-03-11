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
    ) -> Union[str, Generator[str, None, None]]:
        # Fast bypass for simple conversational tasks
        if not self.is_complex_task(task):
            from orionagent.agents.strategies.direct import DirectStrategy
            return DirectStrategy().execute(task, agents, model, system_instruction, context, temperature, tools, stream)

        if not model:
            # No model to plan with -- fall back to single delegation
            from orionagent.agents.strategies.direct import DirectStrategy
            return DirectStrategy().execute(task, agents, model, system_instruction, context, temperature, tools, stream)

        plan = self._create_plan(task, agents, model, system_instruction, context, temperature)

        if stream:
            return self._stream_plan(plan, agents, task, model)
        return self._execute_plan_full(plan, agents, task, model)

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
    ) -> list:
        """Ask the LLM to produce a compact JSON plan."""
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
        self, plan: list, agents: List[Agent], original_task: str, model: Any = None
    ) -> str:
        """Execute all plan steps and return ONLY the final result."""
        import concurrent.futures
        last_result = ""

        # plan is now List[List[Dict]] (groups of parallel steps)
        for group in plan:
            if not isinstance(group, list):
                group = [group] # robustness for single-step legacy or malformed plans
                
            if len(group) == 1:
                # Single step in group, run sequentially
                step = group[0]
                instruction = step.get("s", step.get("step", original_task))
                agent = self._find_agent(step.get("a", step.get("agent")), agents)
                prompt = f"Previous result: {last_result}\n\nTask: {instruction}" if last_result else instruction
                last_result = agent.ask(prompt, stream=False, use_strategy=False, record_memory=False)
            else:
                # Parallel group
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = []
                    for step in group:
                        instruction = step.get("s", step.get("step", original_task))
                        agent = self._find_agent(step.get("a", step.get("agent")), agents)
                        prompt = f"Previous result: {last_result}\n\nTask: {instruction}" if last_result else instruction
                        futures.append(executor.submit(agent.ask, prompt, False, False, None, False)) # instruction, stream, use_strategy, session_id, record_memory
                    
                    results = [f.result() for f in concurrent.futures.as_completed(futures)]
                    last_result = "\n".join(results)

        return last_result

    def _stream_plan(
        self, plan: list, agents: List[Agent], original_task: str, model: Any = None
    ) -> Generator[str, None, None]:
        """Stream plan execution, yielding ONLY the final step's result."""
        import concurrent.futures
        last_result = ""
        
        for i, group in enumerate(plan, 1):
            if not isinstance(group, list):
                group = [group]
                
            is_final_group = (i == len(plan))
            
            if len(group) == 1:
                step = group[0]
                instruction = step.get("s", step.get("step", original_task))
                agent = self._find_agent(step.get("a", step.get("agent")), agents)
                prompt = f"Previous result: {last_result}\n\nTask: {instruction}" if last_result else instruction
                
                if is_final_group:
                    yield from agent.ask(prompt, stream=True, use_strategy=False, record_memory=False)
                else:
                    last_result = agent.ask(prompt, stream=False, use_strategy=False, record_memory=False)
            else:
                # Parallel group execution
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = []
                    for step in group:
                        instruction = step.get("s", step.get("step", original_task))
                        agent = self._find_agent(step.get("a", step.get("agent")), agents)
                        prompt = f"Previous result: {last_result}\n\nTask: {instruction}" if last_result else instruction
                        futures.append(executor.submit(agent.ask, prompt, False, False, None, False))
                    
                    results = [f.result() for f in concurrent.futures.as_completed(futures)]
                    last_result = "\n".join(results)
                    
                    if is_final_group:
                        yield last_result
