"""AgentHandoff for OrionAI.

Enables efficient "Stateless" handoffs between agents by passing a 
concise brief instead of the entire conversation history.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class AgentHandoff:
    """Encapsulates a handoff from one agent to another.

    Attributes:
        target_agent:   Name of the agent expected to receive the task.
        task:           The specific sub-task for the next agent.
        brief:          A concise context summary (replaces full history).
        state:           Optional structured data to pass along.
        source_agent:   Name of the agent initiating the handoff.
    """
    target_agent: str
    task: str
    brief: str
    state: Dict[str, Any] = field(default_factory=dict)
    source_agent: Optional[str] = None

    def __str__(self) -> str:
        return (
            f"==== HANDOFF FROM {self.source_agent or 'Unknown'} to {self.target_agent} ====\n"
            f"TASK: {self.task}\n"
            f"BRIEF: {self.brief}\n"
            f"STATE: {self.state}\n"
            f"==========================================================="
        )

    def to_prompt(self) -> str:
        """Converts the handoff into a sterile prompt for the next agent."""
        return (
            f"You are taking over a task from {self.source_agent or 'a colleague'}.\n\n"
            f"**CONTEXT BRIEF**:\n{self.brief}\n\n"
            f"**REQUIRED STATE**:\n{self.state if self.state else 'None'}\n\n"
            f"**YOUR SPECIFIC TASK**:\n{self.task}"
        )
