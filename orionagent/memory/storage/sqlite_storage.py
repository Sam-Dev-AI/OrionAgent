import json
import sqlite3
from typing import Any, Dict, List, Optional
from pathlib import Path
import os
import uuid

# SQLite fallback text similarity
from difflib import SequenceMatcher

def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

class SQLiteStorage:
    """SQLite-based storage layer for persistent memory with vector fallback.
    
    If chromadb is installed, uses it for semantic retrieval.
    Otherwise falls back to SequenceMatcher similarity.
    """
    def __init__(self, db_path: str = "memory/orionagent.db"):
        self.db_path = db_path
        base_dir = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(base_dir, exist_ok=True)
        self._init_db()
        
        self.use_chroma = False
        self.chroma_collection = None
        
        try:
            import chromadb
            from chromadb.config import Settings
            chroma_path = os.path.join(base_dir, "chroma_db")
            chroma_client = chromadb.PersistentClient(path=chroma_path)
            self.chroma_collection = chroma_client.get_or_create_collection(name="orion_memory")
            self.use_chroma = True
        except ImportError:
            pass
            
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS memory (
                    id TEXT PRIMARY KEY,
                    user_id TEXT,
                    agent_id TEXT,
                    text TEXT,
                    importance INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            ''')
            
    def add(self, content: str, user_id: str, agent_id: str, importance: int = 5, metadata: Optional[Dict[str, Any]] = None):
        """Add a persistent memory fact."""
        memory_id = str(uuid.uuid4())
        meta_str = json.dumps(metadata or {})
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'INSERT INTO memory (id, user_id, agent_id, text, importance, metadata) VALUES (?, ?, ?, ?, ?, ?)',
                (memory_id, user_id, agent_id, content, importance, meta_str)
            )
            
        if self.use_chroma and self.chroma_collection is not None:
            self.chroma_collection.add(
                documents=[content],
                metadatas=[{"user_id": user_id, "agent_id": agent_id, "importance": importance, **(metadata or {})}],
                ids=[memory_id]
            )
            
    def search(self, query: str, user_id: str, agent_id: str, limit: int = 5, min_importance: int = 1) -> List[Dict[str, Any]]:
        """Search persistent memory using Chroma if available, otherwise SequenceMatcher."""
        if self.use_chroma and self.chroma_collection is not None:
            results = self.chroma_collection.query(
                query_texts=[query],
                n_results=limit,
                where={"$and": [{"user_id": user_id}, {"agent_id": agent_id}, {"importance": {"$gte": min_importance}}]}
            )
            
            if not results["documents"] or not results["documents"][0]:
                return []
                
            memories = []
            for i in range(len(results["documents"][0])):
                memories.append({
                    "id": results["ids"][0][i],
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {}
                })
            return memories
            
        # Fallback to SequenceMatcher over SQLite data
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                'SELECT id, text, importance, metadata FROM memory WHERE user_id = ? AND agent_id = ? AND importance >= ?',
                (user_id, agent_id, min_importance)
            ).fetchall()
            
        scored_rows = []
        for row in rows:
            score = similarity(query, row['text'])
            if score > 0.1: # simple threshold
                scored_rows.append((score, row))
                
        scored_rows.sort(key=lambda x: x[0], reverse=True)
        top_rows = [x[1] for x in scored_rows[:limit]]
        
        memories = []
        for r in top_rows:
            memories.append({
                "id": r['id'],
                "content": r['text'],
                "metadata": json.loads(r['metadata']) if r['metadata'] else {}
            })
            
        return memories
        
    def clear(self, user_id: str, agent_id: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM memory WHERE user_id = ? AND agent_id = ?', (user_id, agent_id))
            
        if self.use_chroma and self.chroma_collection is not None:
            self.chroma_collection.delete(where={"$and": [{"user_id": user_id}, {"agent_id": agent_id}]})
