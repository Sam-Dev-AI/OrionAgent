from typing import Any, Dict, List, Optional
import threading
import time

from orionagent.memory.base import BaseMemory

class InMemoryStorage(BaseMemory):
    """A blazing fast, entirely RAM-based storage engine.
    
    Ideal for Short-Term / Working Memory where low latency is critical
    and persistence between application restarts is not required.
    """

    def __init__(self):
        # Data structure: { "user_id": [ memory_dict_1, memory_dict_2, ... ] }
        self._store: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def add(self, content: str, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if user_id not in self._store:
                self._store[user_id] = []
                
            memory_obj = {
                "id": self._generate_id(),
                "content": content,
                "user_id": user_id,
                "metadata": metadata or {},
                "created_at": time.time()
            }
            
            self._store[user_id].append(memory_obj)
            return [memory_obj]

    def search(self, query: str, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        with self._lock:
            if user_id not in self._store:
                return []
                
            user_memories = self._store[user_id]
            
            # Simple case-insensitive exact keyword match
            query_lower = query.lower()
            results = [
                m for m in user_memories 
                if query_lower in m["content"].lower()
            ]
            
            # If no strict keyword matches, return the most recent memories as fallback context
            if not results:
                results = user_memories[-limit:]
                
            return results[:limit]

    def get_all(self, user_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._store.get(user_id, []))

    def delete(self, memory_id: str) -> bool:
        with self._lock:
            for user_id, memories in self._store.items():
                for i, memory in enumerate(memories):
                    if memory["id"] == memory_id:
                        del memories[i]
                        return True
            return False
