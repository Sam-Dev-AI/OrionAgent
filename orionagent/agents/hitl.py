from dataclasses import dataclass, field
from typing import Optional, List, Union

@dataclass
class HitlConfig:
    """Configuration for Human-in-the-Loop (HITL) safety layer.
    
    Attributes:
        permission_level: "low" (always ask), "medium" (ask for risky actions), "high" (never ask).
        ask_once: If True, approving once allows the entire subsequent plan or session turn.
        plan_review: If True, displays the full decomposition for review.
        _session_allowed: Internal tracker for persistence logic.
    """
    permission_level: str = "low" # "low", "medium", "high"
    ask_once: bool = False
    plan_review: bool = True
    _session_allowed: bool = field(default=False, init=False, repr=False)

    def authorize_session(self):
        self._session_allowed = True

    @property
    def is_session_authorized(self) -> bool:
        return self._session_allowed

def is_risky_action(text: str) -> bool:
    """Detect if a text contains potentially destructive or high-impact actions."""
    risky_keywords = [
        "delete", "rm ", "remove", "wipe", "format", "terminate",
        "write", "create", "update", "modify",
        "execute", "run", "terminal", "shell", "bash", "cmd",
        "send", "email", "post", "publish", "deploy"
    ]
    text_lower = text.lower()
    return any(kw in text_lower for kw in risky_keywords)
