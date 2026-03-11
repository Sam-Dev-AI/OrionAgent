from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

class MemoryTier(Enum):
    """Defines the operational tier of a memory store."""
    SHORT_TERM = "short_term"  # Working memory (exact chats, temporary)
    LONG_TERM = "long_term"    # Persistent episodic/semantic memory (facts)
    SUMMARY = "summary"        # Compressed short-term history

class BaseMemory(ABC):
    """Abstract base class for all memory storage backends."""

    @abstractmethod
    def add(self, content: str, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Adds a new memory to the store.
        
        Args:
            content: The text content to store.
            user_id: Identifier for the user/session owning this memory.
            metadata: Optional dictionary of additional context (e.g., timestamp, tier).
            
        Returns:
            A list containing the created memory object (as a dict).
        """
        pass

    @abstractmethod
    def search(self, query: str, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Searches for relevant memories.
        
        Args:
            query: The search string.
            user_id: Identifier for the user/session.
            limit: Maximum number of results to return.
            
        Returns:
            A list of dictionary objects representing matched memories.
        """
        pass

    @abstractmethod
    def get_all(self, user_id: str) -> List[Dict[str, Any]]:
        """Retrieves all memories for a specific user.
        
        Args:
            user_id: Identifier for the user/session.
            
        Returns:
            A list of all memory dictionary objects for the user.
        """
        pass

    @abstractmethod
    def delete(self, memory_id: str) -> bool:
        """Deletes a specific memory by ID.
        
        Args:
            memory_id: The unique identifier of the memory to delete.
            
        Returns:
            True if deletion was successful, False otherwise.
        """
        pass

    def _generate_id(self) -> str:
        """Helper to generate a unique memory ID."""
        return str(uuid.uuid4())
