from dataclasses import dataclass, field
from typing import Optional

@dataclass
class MemoryConfig:
    """Configuration for agent memory capabilities.
    
    Attributes:
        mode: Memory level:
            - "none": No memory at all.
            - "session": Fast temporary conversation buffer (Medium).
            - "long_term": Session + Persistent SQLite facts (High).
            - "chroma": Session + SQLite + Chroma Vector Knowledge (Ultimate).
        working_limit: How many recent facts/messages to keep in fast working memory.

        chunk_size: How many messages before triggering a chunk summarization.
        summary_tokens: Token limit for chunk summaries.
        importance_threshold: Minimum importance score (1-10) for long-term fact extraction.
        vector_top_k: How many relevant facts to retrieve from persistent memory.
        storage_path: Base directory for storing memory files. Defaults to "memory".
    """
    mode: str = "session" # none, session, persistent, long_term, chroma
    working_limit: int = 12
    chunk_size: int = 20
    summary_tokens: int = 500 # chunk summary limit
    
    # Layered Limits (New)
    max_dialogue_tokens: int = 500
    max_recent_summary_tokens: int = 300
    max_chunk_tokens: int = 500
    max_global_summary_tokens: int = 1000
    
    importance_threshold: int = 7
    vector_top_k: int = 5
    storage_path: str = "memory"
    extract_entities: bool = True
    priority: str = "medium"
    entity_categories: list = field(default_factory=lambda: ["Personal", "Preference", "Decision", "Professional"])

    def __post_init__(self):
        # Simplify mode names: long_term is a friendlier alias for persistent
        if self.mode == "long_term":
            self.mode = "persistent"
        
        # Ensure chroma storage uses a subfolder
        if self.mode == "chroma" and self.storage_path == "memory":
            self.storage_path = "memory/chroma_db"

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryConfig":
        """Load configuration from a dictionary."""
        return cls(
            mode=data.get("mode", "session"),
            working_limit=data.get("working_limit", 12),
            chunk_size=data.get("chunk_size", 20),
            summary_tokens=data.get("summary_tokens", 120),
            importance_threshold=data.get("importance_threshold", 7),
            vector_top_k=data.get("vector_top_k", 5),
            storage_path=data.get("storage_path", "memory"),
            extract_entities=data.get("extract_entities", True),
            priority=data.get("priority", "medium"),
            entity_categories=data.get("entity_categories", ["Personal", "Preference", "Decision", "Professional"])
        )

