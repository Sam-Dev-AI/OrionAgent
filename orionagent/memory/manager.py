from typing import Any, Dict, List, Optional
from orionagent.memory.config import MemoryConfig
from orionagent.memory.session import Session, SessionManager
from orionagent.memory.storage.sqlite_storage import SQLiteStorage

class MemoryPipeline:
    """Handles the hierarchical memory lifecycle for an active session."""
    
    def __init__(self, config: MemoryConfig, persistent_db: Optional[SQLiteStorage] = None):
        self.config = config
        self.session_manager = SessionManager(base_dir=config.storage_path)
        self.persistent_db = persistent_db
        
    def process_turn(self, session: Session, role: str, content: str, llm: Any = None):
        """Process a single turn, adding it to the session and triggering summarization if needed."""
        if self.config.mode == "none":
            return
            
        from orionagent.tracing import tracer
        # If the LLM has verbose or debug enabled, we log
        is_verbose = getattr(llm, "verbose", False)
        is_debug = getattr(llm, "debug", False)
        tracer.log_event("memory", f"Storing {role} turn", content[:50], verbose=is_verbose, debug=is_debug)

        session.messages.append({"role": role, "content": content})
        self.session_manager.save(session)
        
        # Trigger summarization when we hit the chunk limit
        if len(session.messages) >= self.config.chunk_size:
            self._summarize_chunk(session, llm)
            
    def _summarize_chunk(self, session: Session, llm: Any):
        """Compress the oldest messages into a chunk summary with structured entity extraction."""
        if not llm:
            return
            
        messages_to_summarize = session.messages[:self.config.chunk_size]
        text_to_summarize = "\n".join([f"[{m['role']}] {m['content']}" for m in messages_to_summarize])
        
        # Token efficiency: if priority is low, just do a tiny summary
        if session.priority == "low":
            prompt = f"Provide a one-sentence summary of this conversation segment. Be extremely concise.\n\n{text_to_summarize}"
            try:
                summary = llm.generate(prompt=prompt, system_instruction="You are a minimalist summarizer.")
                session.chunk_summaries.append(summary)
                session.messages = session.messages[self.config.chunk_size:]
                self.session_manager.save(session)
                return
            except Exception:
                return

        # Normal/High priority: Structured JSON extraction
        categories = ", ".join(self.config.entity_categories)
        prompt = (
            f"Summarize the following conversation segment and extract key entities/facts.\n"
            f"Output MUST be strict JSON in this format:\n"
            f'{{"summary": "A concise summary", "entities": [ {{"name": "...", "category": "...", "value": "...", "importance": 1-10}} ]}}\n\n'
            f"Use categories: {categories}.\n\n"
            f"CONVERSATION:\n{text_to_summarize}"
        )
        
        try:
            raw_response = llm.generate(prompt=prompt, system_instruction="You are an expert at extracting structured information and summarizing conversations into JSON format.")
            
            import json
            import re
            
            # Extract JSON from potential markdown blocks
            json_match = re.search(r"\{.*\}", raw_response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                summary = data.get("summary", "")
                new_entities = data.get("entities", [])
                
                session.chunk_summaries.append(summary)
                self._merge_entities(session, new_entities)
            else:
                # Fallback if no JSON found
                session.chunk_summaries.append(raw_response[:200])
                
            session.messages = session.messages[self.config.chunk_size:]
            self.session_manager.save(session)
            
            if len(session.chunk_summaries) > 5:
                self._summarize_session(session, llm)
                
        except Exception:
            pass

    def _merge_entities(self, session: Session, new_entities: List[Dict[str, Any]]):
        """Merge newly extracted entities into the session bucket and sync to SQLite if high priority."""
        for entity in new_entities:
            name = entity.get("name")
            importance = entity.get("importance", 0)
            if not name: continue
            
            # Update Session Bucket (JSON)
            if name in session.entities:
                if importance >= session.entities[name].get("importance", 0):
                    session.entities[name] = entity
            else:
                session.entities[name] = entity

            # Sync to Lifetime Memory (SQLite) if importance is high enough
            if self.persistent_db and importance >= self.config.importance_threshold:
                content = f"[{entity.get('category', 'Fact')}] {name}: {entity.get('value', '')}"
                self.persistent_db.add(
                    content=content,
                    user_id=session.user_id,
                    agent_id=session.agent_id,
                    importance=importance,
                    metadata={"source_session": session.session_id}
                )

    def _summarize_session(self, session: Session, llm: Any):
        """Compress all chunk summaries into a single session summary."""
        chunks_text = "\n".join(session.chunk_summaries)
        
        prompt = (
            f"Combine these chronological summaries into one cohesive session summary "
            f"in under {self.config.summary_tokens} tokens.\n\n"
            f"{chunks_text}"
        )
        
        try:
            session_summary = llm.generate(prompt=prompt, system_instruction="You are an expert conversation summarizer.")
            session.session_summary = session_summary
            session.chunk_summaries = [] # Clear the chunks
            self.session_manager.save(session)
        except Exception:
            pass

    def build_context(self, session: Session, current_task: str) -> str:
        """Assemble the context for the LLM based on mode and session state."""
        if self.config.mode == "none":
            return ""
            
        context_parts = []
        
        # 1. Retrieve from Long-Term Memory (Persistent)
        if self.config.mode == "persistent" and self.persistent_db:
            facts = self.persistent_db.search(
                query=current_task,
                user_id=session.user_id,
                agent_id=session.agent_id,
                limit=self.config.vector_top_k,
                min_importance=self.config.importance_threshold
            )
            if facts:
                context_parts.append("==== LONG-TERM MEMORY ====")
                for f in facts:
                    context_parts.append(f"- {f['content']}")
                    
        # 2. Structured Entities/Facts (High priority)
        if self.config.extract_entities and session.entities:
            context_parts.append("\n==== KNOWN FACTS & ENTITIES ====")
            for name, data in session.entities.items():
                cat = data.get("category", "General")
                val = data.get("value", "")
                context_parts.append(f"- [{cat}] {name}: {val}")

        # 3. Session Summary
        if session.session_summary:
            context_parts.append("\n==== SESSION SUMMARY ====")
            context_parts.append(session.session_summary)
            
        # 4. Chunk Summaries (Recent conversation history)
        if session.chunk_summaries:
            context_parts.append("\n==== RECENT CONVERSATION SUMMARY ====")
            for chunk in session.chunk_summaries:
                context_parts.append(chunk)
                
        # 5. Working Memory (Recent Messages - Raw)
        recent_messages = session.messages[-self.config.working_limit:]
        if recent_messages:
            context_parts.append("\n==== WORKING MEMORY ====")
            for msg in recent_messages:
                context_parts.append(f"[{msg['role'].upper()}] {msg['content']}")
                
        return "\n".join(context_parts)

class AgentMemoryProxy:
    """A proxy object returned by `agent.memory` to expose easy CRUD operations."""
    
    def __init__(self, agent: Any):
        self.agent = agent
        
    def _get_persistent_db(self):
        if hasattr(self.agent, "_persistent_db"):
            return self.agent._persistent_db
        return None
        
    def add(self, text: str, importance: int = 5, metadata: Optional[Dict[str, Any]] = None):
        """Save a persistent fact."""
        db = self._get_persistent_db()
        if not db:
            raise ValueError("Agent memory mode must be 'persistent' to add facts.")
        db.add(content=text, user_id=self.agent.user_id, agent_id=self.agent.name, importance=importance, metadata=metadata)
        
    def view(self, limit: int = 10):
        """View persistent facts for this user and agent."""
        db = self._get_persistent_db()
        if not db:
            return []
        
        # For viewing purposes we just send a wildcard query or rely on SQLite fallback to fetch latest
        # We will use an empty string for SequenceMatcher fallback which returns low score, so we use min_importance 0
        return db.search(query="", user_id=self.agent.user_id, agent_id=self.agent.name, limit=limit, min_importance=0)
        
    def clear(self):
        """Clear all persistent memory for this user and agent."""
        db = self._get_persistent_db()
        if db:
            db.clear(user_id=self.agent.user_id, agent_id=self.agent.name)
