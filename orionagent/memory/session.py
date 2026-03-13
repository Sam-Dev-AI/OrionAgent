import json
import os
import uuid
import time
from typing import Any, Dict, List, Optional
from orionagent.memory.config import MemoryConfig

class Session:
    """Represents a conversation session for a specific user and agent."""
    
    def __init__(self, user_id: str, agent_id: str, session_id: Optional[str] = None):
        self.user_id = user_id
        self.agent_id = agent_id
        self.session_id = session_id or str(uuid.uuid4())
        self.messages: List[Dict[str, str]] = []
        self.chunk_summaries: List[str] = []
        self.recent_summary: str = "" # Layer for "few more details" but short
        self.session_summary: str = ""
        self.entities: Dict[str, Dict[str, Any]] = {} # name -> {value, category, importance}
        self.priority: str = "normal"
        self.created_at = time.time()
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "messages": self.messages,
            "chunk_summaries": self.chunk_summaries,
            "recent_summary": self.recent_summary,
            "session_summary": self.session_summary,
            "entities": self.entities,
            "priority": self.priority,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        session = cls(
            user_id=data["user_id"],
            agent_id=data["agent_id"],
            session_id=data["session_id"]
        )
        session.messages = data.get("messages", [])
        session.chunk_summaries = data.get("chunk_summaries", [])
        session.recent_summary = data.get("recent_summary", "")
        session.session_summary = data.get("session_summary", "")
        session.entities = data.get("entities", {})
        session.priority = data.get("priority", "normal")
        session.created_at = data.get("created_at", time.time())
        session.updated_at = data.get("updated_at", time.time())
        return session
        
class SessionManager:
    """Manages loading and saving Session objects to disk."""
    
    def __init__(self, base_dir: str = "memory"):
        self.base_dir = os.path.join(base_dir, "sessions")
        
    def _get_path(self, user_id: str, agent_id: str, session_id: str) -> str:
        # User requested path: sessions/{user_id}/{agent_id}/{session_id}.json
        path = os.path.join(self.base_dir, user_id, agent_id)
        os.makedirs(path, exist_ok=True)
        return os.path.join(path, f"{session_id}.json")
        
    def load(self, user_id: str, agent_id: str, session_id: str) -> Optional[Session]:
        path = self._get_path(user_id, agent_id, session_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return Session.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None
            
    def save(self, session: Session):
        session.updated_at = time.time()
        path = self._get_path(session.user_id, session.agent_id, session.session_id)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(session.to_dict(), f, indent=2)

    def auto(self, user_id: str, agent_id: str) -> str:
        """Automatically create or return the latest session_id for a user/agent pair."""
        path = os.path.join(self.base_dir, user_id, agent_id)
        if not os.path.exists(path):
            return str(uuid.uuid4())
            
        files = [f for f in os.listdir(path) if f.endswith(".json")]
        if not files:
            return str(uuid.uuid4())
            
        # Get the most recently modified file
        latest_file = max(files, key=lambda x: os.path.getmtime(os.path.join(path, x)))
        return latest_file.replace(".json", "")
