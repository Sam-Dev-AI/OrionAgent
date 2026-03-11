import json
import os
import time
from typing import Any, Dict, List, Optional
import threading

from orionagent.memory.base import BaseMemory

class JSONStorage(BaseMemory):
    """A simple, file-based persistent storage engine.
    
    Ideal for Long-Term (Episodic/Semantic) Memory when you want 
    zero external dependencies but need facts to survive restarts.
    """

    def __init__(self, filepath: str = "orionagent_memory.json"):
        self.filepath = filepath
        self._lock = threading.Lock()
        self._ensure_file()

    def _ensure_file(self):
        """Creates the JSON file if it does not exist."""
        if not os.path.exists(self.filepath):
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump({}, f)

    def _read_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Reads all data from the JSON file."""
        with self._lock:
            try:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return {}

    def _write_data(self, data: Dict[str, List[Dict[str, Any]]]):
        """Writes data back to the JSON file safely."""
        with self._lock:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

    def add(self, content: str, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        data = self._read_data()
        
        if user_id not in data:
            data[user_id] = []
            
        memory_obj = {
            "id": self._generate_id(),
            "content": content,
            "user_id": user_id,
            "metadata": metadata or {},
            "created_at": time.time()
        }
        
        data[user_id].append(memory_obj)
        self._write_data(data)
        return [memory_obj]

    def search(self, query: str, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Basic keyword search across the JSON file."""
        data = self._read_data()
        if user_id not in data:
            return []
            
        user_memories = data[user_id]
        query_words = set(query.lower().split())
        
        # Score memories by how many query words they contain
        scored_memories = []
        for m in user_memories:
            content_lower = m["content"].lower()
            score = sum(1 for word in query_words if word in content_lower)
            if score > 0:
                scored_memories.append((score, m))
                
        # Sort by score (descending), then by recency (descending)
        scored_memories.sort(key=lambda x: (x[0], x[1]["created_at"]), reverse=True)
        
        # Extract just the memory dicts up to the limit
        return [m[1] for m in scored_memories[:limit]]

    def get_all(self, user_id: str) -> List[Dict[str, Any]]:
        data = self._read_data()
        return data.get(user_id, [])

    def delete(self, memory_id: str) -> bool:
        data = self._read_data()
        deleted = False
        
        for user_id, memories in data.items():
            original_len = len(memories)
            data[user_id] = [m for m in memories if m["id"] != memory_id]
            if len(data[user_id]) < original_len:
                deleted = True
                
        if deleted:
            self._write_data(data)
            
        return deleted
