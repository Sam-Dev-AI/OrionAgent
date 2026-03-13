"""Direct strategy for Manager orchestration.

The default strategy. Extracts the current Manager behavior into a strategy
class: uses zero-cost keyword overlap routing to pick the best agent
and delegates the entire task in a single shot.
"""

from typing import Generator, List, Optional, Union, Any

from orionagent.agents.base_agent import Agent
from orionagent.agents.strategies.base import BaseStrategy
from orionagent.models.base_provider import ModelProvider


class DirectStrategy(BaseStrategy):
    """Delegates the entire task to the single best agent."""

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
    ) -> Union[str, Generator[str, None, None], Any]:

        prompt = f"{context}\n\n==== CURRENT TASK ====\n{task}" if context else task

        # If there's only one agent, skip keyword overhead entirely
        if len(agents) == 1:
            selected = agents[0]
        else:
            selected = self.select_agent(task, agents)
        
        if selected is None:
            # No agent matched keywords (e.g. "hi", "what is your name?")
            # Handled by the Manager level model
            if model:
                if hitl:
                    from orionagent.agents.hitl import HitlConfig
                    h_cfg = hitl if isinstance(hitl, HitlConfig) else HitlConfig()
                    self._approve_direct(task, "Manager (Internal)", h_cfg)
                if stream:
                    return self._stream_manager(model, prompt, system_instruction, temperature, tools)
                return model.generate(
                    prompt=prompt,
                    system_instruction=system_instruction,
                    temperature=temperature,
                    tools=tools
                )
            else:
                # No model and no agent match? Fallback to first agent as a safety
                selected = agents[0]

        if hitl:
            from orionagent.agents.hitl import HitlConfig
            h_cfg = hitl if isinstance(hitl, HitlConfig) else HitlConfig()
            if not self._approve_direct(task, selected.name, h_cfg):
                raise InterruptedError("Delegation rejected by user via HITL.")

        if stream:
            return self._stream_response(selected, prompt, model, record_trace=record_trace, priority=priority, temperature=temperature)
        
        result = selected.ask(
            task=prompt, 
            stream=False, 
            use_strategy=False, 
            record_memory=False, 
            record_trace=record_trace, 
            priority=priority, 
            temperature=temperature
        )
        return result

    def _approve_direct(self, task: str, agent_name: str, h_cfg: "HitlConfig") -> bool:
        """Interactive terminal approval for single delegation."""
        if h_cfg.permission_level == "high":
            return True
            
        if h_cfg.ask_once and h_cfg.is_session_authorized:
            return True
            
        from orionagent.agents.hitl import is_risky_action
        if h_cfg.permission_level == "medium":
            if not is_risky_action(task):
                return True

        print(f"\n\033[1m[ORION HITL] Delegation Approval Required\033[0m")
        print(f"Goal: {task}")
        print(f"Target Agent: {agent_name}")
        print("-" * 40)
        choice = input("Approve delegation? (y/n): ").strip().lower()
        if choice == 'y':
            print("\033[32m[APPROVED] Executing...\033[0m")
            if h_cfg.ask_once:
                h_cfg.authorize_session()
            return True
        else:
            print("\033[31m[ABORTED] Delegation rejected by user.\033[0m")
            return False

        print("\033[32m[APPROVED] Executing...\033[0m\n")


    @staticmethod
    def _stream_manager(
        model: ModelProvider, prompt: str, system_instruction: str, temperature: float, tools: list
    ) -> Generator[str, None, None]:
        yield from model.generate_stream(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=temperature,
            tools=tools
        )

    def _stream_response(
        self, agent: Agent, task: str, model: Any = None, record_trace: bool = True, priority: Optional[str] = None, temperature: float = None
    ) -> Generator[str, None, None]:
        yield from agent.ask(
            task=task, 
            stream=True, 
            use_strategy=False, 
            record_memory=False, 
            record_trace=record_trace, 
            priority=priority, 
            temperature=temperature
        )
