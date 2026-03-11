from dataclasses import dataclass, field
from typing import Optional

@dataclass
class MemoryConfig:
    """Configuration for agent memory capabilities.
    
    Attributes:
        mode: Memory mode ("none", "session", "persistent", or "long_term").
        working_limit: How many recent facts/messages to keep in fast working memory.
        chunk_size: How many messages before triggering a chunk summarization.
        summary_tokens: Token limit for chunk summaries.
        importance_threshold: Minimum importance score (1-10) for long-term fact extraction.
        vector_top_k: How many relevant facts to retrieve from persistent memory.
        storage_path: Base directory for storing memory files. Defaults to "memory".
    """
    mode: str = "session"
    working_limit: int = 12
    chunk_size: int = 20
    summary_tokens: int = 120
    importance_threshold: int = 7
    vector_top_k: int = 5
    storage_path: str = "memory"
    extract_entities: bool = True
    min_priority: str = "normal"
    entity_categories: list = field(default_factory=lambda: ["Personal", "Preference", "Decision", "Professional"])

    def __post_init__(self):
        # Simplify mode names: long_term is a friendlier alias for persistent
        if self.mode == "long_term":
            self.mode = "persistent"

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
            min_priority=data.get("min_priority", "normal"),
            entity_categories=data.get("entity_categories", ["Personal", "Preference", "Decision", "Professional"])
        )
