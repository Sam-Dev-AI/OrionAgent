"""Self-learn strategy for Manager orchestration.

Wraps any base execution (keyword routing or planning) with a
lightweight learning layer:

  1. Execute the task with the best agent
  2. Quick LLM eval (~50 tokens) to check quality
  3. If good  -> store success pattern, return response
  4. If poor  -> re-delegate to a DIFFERENT agent with targeted feedback
  5. Skip eval entirely for known-good patterns (zero extra tokens)

Safeguards:
  - Hard loop cap via max_refinements (default 2, never infinite)
  - Never re-sends to the same agent twice for the same task
  - Mistake memory prevents known-bad routing on future calls
"""

from typing import Dict, Generator, List, Optional, Set, Tuple, Union, Any

from orionagent.agents.base_agent import Agent
from orionagent.agents.strategies.base import BaseStrategy
from orionagent.models.base_provider import ModelProvider


# Lightweight eval prompt -- ~50 tokens of instructions
_EVAL_PROMPT = """Rate quality 1-5. If < 3, give ONE line feedback.
Task: {task}
Response: {response}

Reply ONLY:
SCORE: <#>
FEEDBACK: <text>"""


class SelfLearnStrategy(BaseStrategy):
    """Learns from execution results to improve routing over time.

    Uses an in-memory ledger of successes/failures per (task-keyword, agent)
    pair so that repeated similar tasks skip evaluation entirely.

    Args:
        max_refinements: Hard cap on retry attempts (default 2).
    """

    def __init__(self, max_refinements: int = 2):
        self.max_refinements = max_refinements
        # Ledger: {keyword: {agent_name: {"successes": int, "failures": int}}}
        self._learnings: Dict[str, Dict[str, Dict[str, int]]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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
    ) -> Union[str, Generator[str, None, None]]:
        # Fast bypass for simple conversational tasks
        if not self.is_complex_task(task):
            from orionagent.agents.strategies.direct import DirectStrategy
            return DirectStrategy().execute(task, agents, model, system_instruction, context, temperature, tools, stream, async_mode, verbose, debug, record_trace=record_trace)

        if not model:
            # No model for eval -- fall back to single delegation
            from orionagent.agents.strategies.direct import DirectStrategy
            return DirectStrategy().execute(task, agents, model, system_instruction, context, temperature, tools, stream, async_mode, verbose, debug, record_trace=record_trace)

        # Check if we have a learned best agent for this task type
        learned_agent = self._get_learned_agent(task, agents)

        if learned_agent:
            # Known-good pattern -- skip eval, zero extra tokens
            
            if stream:
                return learned_agent.ask(task, stream=True, use_strategy=False, record_memory=False, temperature=temperature)
            return learned_agent.ask(task, stream=False, use_strategy=False, record_memory=False, temperature=temperature)

        # Cold path -- execute + evaluate + learn
        if stream:
            return self._stream_with_learning(task, agents, model, system_instruction, context, temperature=temperature)
        return self._execute_with_learning(task, agents, model, system_instruction, context, temperature=temperature)

    # ------------------------------------------------------------------
    # Learning logic (non-streaming)
    # ------------------------------------------------------------------

    def _execute_with_learning(
        self,
        task: str,
        agents: List[Agent],
        model: ModelProvider,
        system_instruction: Optional[str] = None,
        context: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        tried: Set[str] = set()
        selected = self.select_agent(task, agents)
        if selected is None:
            # Fallback for meta-questions: just use the first agent
            selected = agents[0]
            
        original_task = task
        parts = []

        for attempt in range(self.max_refinements + 1):
            tried.add(selected.name)
            
            response = selected.ask(task, stream=False, use_strategy=False, record_memory=False, record_trace=False, temperature=temperature)
            
            score, feedback = self._evaluate(original_task, response, model, system_instruction, context)

            if score >= 3:
                # Good result -- store success, return
                self._record(original_task, selected.name, success=True)
                parts.append(response)
                return "".join(parts)

            # Bad result -- store failure
            self._record(original_task, selected.name, success=False)

            # Find a different agent OR retry current if it's the only one
            next_agent = self._pick_untried(agents, tried)
            if next_agent is None:
                if attempt < self.max_refinements:
                    # Retry same agent with feedback if still have refinements
                    task = f"{task}\n\n[Improve] {feedback}"
                    continue
                else:
                    parts.append(response)
                    return "".join(parts)

            # Re-delegate with targeted feedback
            task = f"{task}\n\n[Improve] {feedback}"
            selected = next_agent

        # Max refinements hit -- return last response
        parts.append(response)
        return "".join(parts)

    # ------------------------------------------------------------------
    # Learning logic (streaming)
    # ------------------------------------------------------------------

    def _stream_with_learning(
        self,
        task: str,
        agents: List[Agent],
        model: ModelProvider,
        system_instruction: Optional[str] = None,
        context: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Generator[str, None, None]:
        tried: Set[str] = set()
        selected = self.select_agent(task, agents)
        if selected is None:
            # Fallback for meta-questions: just use the first agent
            selected = agents[0]
            
        original_task = task

        for attempt in range(self.max_refinements + 1):
            # Must collect full response for evaluation
            response = selected.ask(task, stream=False, use_strategy=False, record_memory=False, record_trace=False, temperature=temperature)

            score, feedback = self._evaluate(original_task, response, model, system_instruction, context)

            if score >= 3:
                self._record(original_task, selected.name, success=True)
                yield response
                return

            # Bad result -- store failure
            self._record(original_task, selected.name, success=False)

            next_agent = self._pick_untried(agents, tried)
            if next_agent is None:
                if attempt < self.max_refinements:
                    task = f"{original_task}\n\n[Improve] {feedback}"
                    continue
                else:
                    yield response
                    return

            task = f"{original_task}\n\n[Improve] {feedback}"
            selected = next_agent

        # Fallback -- yield last response
        yield response

    # ------------------------------------------------------------------
    # Evaluation (lightweight ~50 token prompt)
    # ------------------------------------------------------------------

    def _evaluate(
        self,
        task: str,
        response: str,
        model: ModelProvider,
        system_instruction: Optional[str] = None,
        context: Optional[str] = None,
    ) -> Tuple[int, str]:
        """Quick quality check. Returns (score, feedback)."""
        # Truncate response to save tokens in eval
        truncated = response[:500] if len(response) > 500 else response

        prompt_task = f"{context}\n\n==== PREVIOUS CONTEXT RUNNING UP TO CURRENT TASK ====\n{task}" if context else task
        prompt = _EVAL_PROMPT.format(task=prompt_task, response=truncated)
        
        si = system_instruction + "\n\nBe very brief. Respond in the exact format requested." if system_instruction else "Be very brief. Respond in the exact format requested."

        raw = model.generate(
            prompt=prompt,
            system_instruction=si,
            temperature=0.0,
            max_tokens=60,
        )

        return self._parse_eval(raw)

    @staticmethod
    def _parse_eval(raw: str) -> Tuple[int, str]:
        """Parse the eval response into (score, feedback)."""
        score = 3  # default to pass
        feedback = "none"

        for line in raw.strip().split("\n"):
            line = line.strip()
            if line.upper().startswith("SCORE:"):
                try:
                    score = int(line.split(":", 1)[1].strip())
                except (ValueError, IndexError):
                    score = 3
            elif line.upper().startswith("FEEDBACK:"):
                feedback = line.split(":", 1)[1].strip()

        return score, feedback

    # ------------------------------------------------------------------
    # Learning storage
    # ------------------------------------------------------------------

    def _extract_keywords(self, task: str) -> str:
        """Extract a simple task signature for learning lookup."""
        # Use first 3 meaningful words as a lightweight key
        words = [w.lower() for w in task.split() if len(w) > 3]
        return " ".join(words[:3]) if words else "general"

    def _record(self, task: str, agent_name: str, success: bool) -> None:
        """Store a success/failure learning."""
        key = self._extract_keywords(task)
        if key not in self._learnings:
            self._learnings[key] = {}
        if agent_name not in self._learnings[key]:
            self._learnings[key][agent_name] = {"successes": 0, "failures": 0}

        if success:
            self._learnings[key][agent_name]["successes"] += 1
        else:
            self._learnings[key][agent_name]["failures"] += 1

    def _get_learned_agent(
        self, task: str, agents: List[Agent]
    ) -> Optional[Agent]:
        """Find a proven-good agent for this task type, or None."""
        key = self._extract_keywords(task)
        if key not in self._learnings:
            return None

        agent_stats = self._learnings[key]
        best_name, best_score = None, -1

        for name, stats in agent_stats.items():
            # Score = successes - failures. Must have at least 1 success.
            net = stats["successes"] - stats["failures"]
            if stats["successes"] > 0 and net > best_score:
                best_score, best_name = net, name

        if best_name:
            for a in agents:
                if a.name == best_name:
                    return a
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _pick_untried(
        agents: List[Agent], tried: Set[str]
    ) -> Optional[Agent]:
        """Return the first agent not yet tried, or None."""
        for a in agents:
            if a.name not in tried:
                return a
        return None

    @staticmethod
    def _stream_with_header(
        agent: Agent, task: str, learned: bool = False, model: Any = None, temperature: float = None
    ) -> Generator[str, None, None]:
        yield from agent.ask(task, stream=True, use_strategy=False, record_memory=False, temperature=temperature)
