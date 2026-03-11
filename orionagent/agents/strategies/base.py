"""Base strategy interface for Manager orchestration.

Every strategy must implement `execute()` which receives the task,
agent list, and the manager's model, then returns a response.
"""

from typing import Generator, List, Optional, Union, Any

from orionagent.agents.base_agent import Agent
from orionagent.models.base_provider import ModelProvider


class BaseStrategy:
    """Abstract base class for all Manager strategies.

    Subclasses implement `execute()` to define how the Manager
    routes tasks to agents and assembles the final response.
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
    ) -> Union[str, Generator[str, None, None], "AgentHandoff"]:
        """Run the strategy on *task* using the given *agents*.

        Args:
            task:    The user's task or question.
            agents:  List of agents registered with the Manager.
            model:   The Manager-level model (for planning / eval calls).
            stream:  If True, yield chunks; if False, return full string.
        """
        raise NotImplementedError("Subclasses must implement execute().")

    # ------------------------------------------------------------------
    # Shared helpers available to all strategies
    # ------------------------------------------------------------------

    @staticmethod
    def select_agent(task: str, agents: List[Agent]) -> Agent:
        """Pick the best agent using whole-word overlap scoring.

        Filters common stop words to focus on meaningful intent and avoids 
        accidental delegation of meta-questions.
        """
        import re
        
        # 1. Focus on meaningful words only
        stop_words = {
            "a", "an", "the", "and", "or", "but", "is", "are", "was", "were", 
            "what", "how", "who", "where", "why", "when", "your", "my", "me", "do", "you",
            "to", "in", "on", "at", "for", "with", "about"
        }
        
        # Extract whole words from task
        task_words = set(re.findall(r'\b\w+\b', task.lower()))
        meaningful_task_words = task_words - stop_words
        
        if not meaningful_task_words:
            # If no meaningful words remain (meta-questions), return None
            return None

        best_agent, best_score = agents[0], 0
        for agent in agents:
            # Extract whole words from agent metadata
            agent_text = f"{agent.role} {agent.description}".lower()
            agent_words = set(re.findall(r'\b\w+\b', agent_text))
            
            # Score based on whole-word intersection
            score = len(meaningful_task_words.intersection(agent_words))
            
            if score > best_score:
                best_score, best_agent = score, agent
        
        # If no agent matched any meaningful words, return None to let caller handle it
        return best_agent if best_score > 0 else None

    @staticmethod
    def is_complex_task(task: str) -> bool:
        """Determines if a task is complex enough to require advanced strategies.
        
        Bypasses planning and self-learning for simple conversational turns.
        """
        words = len(task.split())
        if words > 25:
            return True
        
        # Check for sequencing or complexity indicators
        complex_keywords = [
            " and ", " then ", " after ", " first ", " finally ", 
            " research ", " compare ", " summary ", " outline ",
            " plan ", " steps "
        ]
        task_lower = task.lower()
        if any(kw in task_lower for kw in complex_keywords):
            return True
            
        return False
