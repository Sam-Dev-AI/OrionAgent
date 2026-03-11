"""Strategy module for Manager orchestration.

Provides the `get_strategy()` factory that maps user-friendly
keyword strings to concrete strategy instances.

Usage:
    strategy = get_strategy("planning")
    strategy = get_strategy("self_learn", max_refinements=3)
    strategy = get_strategy(["planning", "self_learn"])
"""

from typing import List, Union

from orionagent.agents.strategies.base import BaseStrategy
from orionagent.agents.strategies.direct import DirectStrategy
from orionagent.agents.strategies.planning import PlanningStrategy
from orionagent.agents.strategies.self_learn import SelfLearnStrategy


_STRATEGY_MAP = {
    "direct": DirectStrategy,
    "planning": PlanningStrategy,
    "self_learn": SelfLearnStrategy,
}


def get_strategy(
    strategy: Union[str, List[str], None] = None,
    **kwargs,
) -> BaseStrategy:
    """Create a strategy instance from a keyword or list of keywords.

    Args:
        strategy: Strategy name(s). Accepts:
                  - None or "direct"    -> DirectStrategy (default)
                  - "planning"          -> PlanningStrategy
                  - "self_learn"        -> SelfLearnStrategy
                  - ["planning", "self_learn"] -> Combined strategy
        **kwargs: Extra config passed to strategies (e.g. max_refinements).

    Returns:
        A BaseStrategy instance.

    Raises:
        ValueError: If an unknown strategy name is given.
    """
    if strategy is None:
        return DirectStrategy()

    # Normalise to a list
    if isinstance(strategy, str):
        names = [s.strip() for s in strategy.split(",")]
    else:
        names = list(strategy)

    # Validate all names
    for name in names:
        if name not in _STRATEGY_MAP:
            valid = ", ".join(sorted(_STRATEGY_MAP.keys()))
            raise ValueError(
                f"Unknown strategy '{name}'. Valid strategies: {valid}"
            )

    # Single strategy
    if len(names) == 1:
        cls = _STRATEGY_MAP[names[0]]
        return cls(**{k: v for k, v in kwargs.items() if _accepts(cls, k)})

    # Combined: planning + self_learn -> PlanningWithLearnStrategy
    if set(names) == {"planning", "self_learn"}:
        return _CombinedPlanLearnStrategy(**kwargs)

    # For any other combo, use the last one listed
    cls = _STRATEGY_MAP[names[-1]]
    return cls(**{k: v for k, v in kwargs.items() if _accepts(cls, k)})


def _accepts(cls, param: str) -> bool:
    """Check if a class __init__ accepts a given parameter."""
    import inspect
    sig = inspect.signature(cls.__init__)
    return param in sig.parameters


class _CombinedPlanLearnStrategy(BaseStrategy):
    """Combines PlanningStrategy + SelfLearnStrategy.

    Plans the task into steps (PlanningStrategy), then wraps each
    step execution with the SelfLearn evaluation and learning layer.
    """

    def __init__(self, max_refinements: int = 2, **kwargs):
        self._planner = PlanningStrategy()
        self._learner = SelfLearnStrategy(max_refinements=max_refinements)

    def execute(self, task, agents, model, system_instruction=None, context=None, temperature=None, tools=None, stream=True, async_mode=True, verbose=False, debug=False, record_trace=True):
        # Fast bypass for simple conversational tasks
        if not self.is_complex_task(task):
            from orionagent.agents.strategies.direct import DirectStrategy
            return DirectStrategy().execute(task, agents, model, system_instruction, context, temperature, tools, stream, async_mode, verbose, debug, record_trace=record_trace)

        if not model:
            return self._planner.execute(task, agents, model, system_instruction, context, temperature, tools, stream, async_mode, verbose, debug, record_trace=record_trace)

        # Step 1: Create a plan using the planning strategy
        plan = self._planner._create_plan(task, agents, model, system_instruction, context, temperature, verbose=verbose, debug=debug)

        if stream:
            return self._stream_combined(plan, agents, model, task, system_instruction, verbose=verbose, debug=debug, record_trace=record_trace)
        return self._execute_combined(plan, agents, model, task, system_instruction, verbose=verbose, debug=debug, record_trace=record_trace)

    def _execute_combined(self, plan, agents, model, original_task, system_instruction=None, verbose=False, debug=False, record_trace=True):
        """Execute plan groups and return ONLY the final result."""
        import concurrent.futures
        last_result = ""
        
        # plan is List[List[Dict]]
        for group in plan:
            if not isinstance(group, list):
                group = [group]
                
            if len(group) == 1:
                step = group[0]
                instruction = step.get("s", step.get("step", original_task))
                # Execute single step with learning
                last_result = self._learner.execute(
                    instruction, agents, model, system_instruction=system_instruction, context=last_result, stream=False, record_trace=False
                )
            else:
                # Parallel group execution with learning on each step
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = []
                    for step in group:
                        instruction = step.get("s", step.get("step", original_task))
                        futures.append(executor.submit(
                            self._learner.execute, 
                            instruction, agents, model, system_instruction, last_result, None, None, False, True, verbose, debug, False
                        ))
                    
                    results = [f.result() for f in concurrent.futures.as_completed(futures)]
                    last_result = "\n".join(results)

        return last_result

    def _stream_combined(self, plan, agents, model, original_task, system_instruction=None, verbose=False, debug=False, record_trace=True):
        """Stream plan groups, yielding ONLY the final group's result."""
        import concurrent.futures
        last_result = ""

        for i, group in enumerate(plan, 1):
            if not isinstance(group, list):
                group = [group]
                
            is_final_group = (i == len(plan))
            
            if len(group) == 1:
                step = group[0]
                instruction = step.get("s", step.get("step", original_task))
                
                if is_final_group:
                    # Final step: stream with learning
                    yield from self._learner.execute(
                        instruction, agents, model, system_instruction=system_instruction, context=last_result, stream=True, record_trace=False
                    )
                else:
                    # Intermediate: run silently with learning
                    last_result = self._learner.execute(
                        instruction, agents, model, system_instruction=system_instruction, context=last_result, stream=False, record_trace=False
                    )
            else:
                # Parallel group execution
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    futures = []
                    for step in group:
                        instruction = step.get("s", step.get("step", original_task))
                        futures.append(executor.submit(
                            self._learner.execute, 
                            instruction, agents, model, system_instruction, last_result, None, None, False, True, verbose, debug, False
                        ))
                    
                    results = [f.result() for f in concurrent.futures.as_completed(futures)]
                    last_result = "\n".join(results)
                    
                    if is_final_group:
                        yield last_result


__all__ = [
    "BaseStrategy",
    "DirectStrategy",
    "PlanningStrategy",
    "SelfLearnStrategy",
    "get_strategy",
]
