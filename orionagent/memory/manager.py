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
        """Compress the oldest messages into a chunk summary, and possibly update the session summary."""
        if not llm:
            return
            
        messages_to_summarize = session.messages[:self.config.chunk_size]
        text_to_summarize = "\n".join([f"[{m['role']}] {m['content']}" for m in messages_to_summarize])
        
        prompt = (
            f"Summarize the following conversation in under {self.config.summary_tokens} tokens. "
            "Keep facts, names, and key decisions.\n\n"
            f"{text_to_summarize}"
        )
        
        try:
            summary = llm.generate(prompt=prompt, system_instruction="You are an expert conversation summarizer.")
            session.chunk_summaries.append(summary)
            
            # Remove the summarized messages, keeping the rest
            session.messages = session.messages[self.config.chunk_size:]
            self.session_manager.save(session)
            
            # If we have too many chunks, summarize the session
            if len(session.chunk_summaries) > 5:
                self._summarize_session(session, llm)
                
        except Exception as e:
            # If summarization fails, don't crash the pipeline
            pass
            
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
            
        from orionagent.tracing import tracer
        # We don't easily have 'verbose' here without passing it, 
        # but build_context is usually called inside Agent.ask where trace is active.
        # For now, let's keep it quiet unless we add 'verbose' to build_context.
        
        context_parts = []
        
        # 1. Retrieve from Long-Term Memory
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
                    
        # 2. Session Summary
        if session.session_summary:
            context_parts.append("\n==== SESSION SUMMARY ====")
            context_parts.append(session.session_summary)
            
        # 3. Chunk Summaries
        if session.chunk_summaries:
            context_parts.append("\n==== RECENT CONVERSATION SUMMARY ====")
            for chunk in session.chunk_summaries:
                context_parts.append(chunk)
                
        # 4. Working Memory (Recent Messages)
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
