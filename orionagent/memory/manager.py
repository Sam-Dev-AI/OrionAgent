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
        
        # Ensure newline before assistant debug log if streaming just finished
        if is_debug and role == "assistant":
            print()

        display_content = content[:50] if content else ""
        tracer.log_event("memory", f"Storing {role} turn", display_content, verbose=is_verbose, debug=is_debug)

        session.messages.append({"role": role, "content": content})
        # Instant save for interactive consistency
        self.session_manager.save(session)
        
        # Layered Summarization Logic
        # 1. Maintain a very small Dialogue Layer (e.g. 6 messages)
        # 2. Move excess to Recent Detailed Summary
        if len(session.messages) > self.config.working_limit // 2:
            self._update_recent_summary(session, llm)
            
        # 3. Archive Recent Summary to Chunks when Chunks of work are done (every chunk_size turns roughly)
        # We use a simple counter or just check if recent_summary is getting complex
        if len(session.messages) + self._estimate_tokens(session.recent_summary) // 50 > self.config.chunk_size:
            self._summarize_chunk(session, llm)
            
    def _estimate_tokens(self, text: str) -> int:
        """Rough estimation of tokens (4 chars per token)."""
        if not text: return 0
        return len(text) // 4

    def _update_recent_summary(self, session: Session, llm: Any):
        """Move older messages into a detailed 'Recent Summary' layer."""
        if not llm or len(session.messages) < 4:
            return
            
        # Take the oldest half of messages to summarize into the 'Detailed' layer
        # This layer carries "few more details"
        to_summarize = session.messages[:-2] # Keep at least 2 for immediate context
        session.messages = session.messages[-2:]
        
        text = "\n".join([f"[{m['role']}] {m['content']}" for m in to_summarize])
        
        prompt = (
            f"Update the following detailed summary with these new dialogue turns.\n"
            f"Keep the summary DETAILED but concise (under {self.config.max_recent_summary_tokens} tokens).\n"
            f"Focus on specific actions, decisions, and key details.\n\n"
            f"CURRENT SUMMARY: {session.recent_summary}\n\n"
            f"NEW TURNS:\n{text}"
        )
        
        try:
            session.recent_summary = llm.generate(prompt=prompt, system_instruction="You are a detailed but concise secretary.")
            self.session_manager.save(session)
        except Exception:
            pass
            
    def _summarize_chunk(self, session: Session, llm: Any):
        """Archive the 'Recent Summary' into a concise 'Chunk Summary' and reset it."""
        if not llm:
            return
            
        # Instead of just messages, we summarize the RECENT SUMMARY which already has the details
        text_to_summarize = session.recent_summary
        if not text_to_summarize and session.messages:
             text_to_summarize = "\n".join([f"[{m['role']}] {m['content']}" for m in session.messages])
             session.messages = []
             
        if not text_to_summarize: return
        
        # Tiered Summarization Logic
        if session.priority == "low":
            # 1. LOW: Minimalist 1-sentence summary, no entities
            prompt = f"Provide a one-sentence summary of this conversation segment. Be extremely concise.\n\n{text_to_summarize}"
            system_instruction = "You are a minimalist summarizer."
        elif session.priority == "high":
            # 2. HIGH: Exhaustive detail + Structured Extraction
            categories = ", ".join(self.config.entity_categories)
            prompt = (
                f"Provide a DETAILED summary of the conversation and exhaustively extract every key entity and fact.\n"
                f"Output MUST be strict JSON:\n"
                f'{{"summary": "A detailed multi-paragraph summary", "entities": [ {{"name": "...", "category": "...", "value": "...", "importance": 1-10}} ]}}\n\n'
                f"Use categories: {categories}.\n\nCONVERSATION:\n{text_to_summarize}"
            )
            system_instruction = "You are an expert at exhaustive structured information extraction."
        else:
            # 3. MEDIUM (Default): Balanced summary + Structured Extraction
            categories = ", ".join(self.config.entity_categories)
            prompt = (
                f"Summarize the conversation segment and extract key entities/facts.\n"
                f"Output MUST be strict JSON:\n"
                f'{{"summary": "A concise summary", "entities": [ {{"name": "...", "category": "...", "value": "...", "importance": 1-10}} ]}}\n\n'
                f"Use categories: {categories}.\n\nCONVERSATION:\n{text_to_summarize}"
            )
            system_instruction = "You are an expert at extracting structured information."

        try:
            raw_response = llm.generate(prompt=prompt, system_instruction=system_instruction)
            
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
                session.chunk_summaries.append(raw_response[:self.config.max_chunk_tokens * 4])
                
            session.recent_summary = "" # Clear recent summary as it's now a chunk
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
            # Ensure global summary is within limits
            session.session_summary = session_summary[:self.config.max_global_summary_tokens * 4]
            session.chunk_summaries = [] # Clear the chunks
            self.session_manager.save(session)
        except Exception:
            pass

    def build_context(self, session: Session, current_task: str) -> str:
        """Assemble the context for the LLM based on mode and session state."""
        if self.config.mode == "none":
            return ""
            
        context_parts = []
        
        # Add a clear preamble to orient the LLM
        preamble = (
            "--- CONVERSATION HISTORY ---\n"
            "The following is a retrieved history of the current conversation. "
            "Use this ONLY as context. DO NOT respond to these historical messages directly. "
            "The active task is always identified as 'ACTIVE TASK' at the end of this prompt.\n"
        )
        context_parts.append(preamble)
        
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
                context_parts.append("[LONG_TERM_FACTS]")
                for f in facts:
                    context_parts.append(f"- {f['content']}")
                    
        # 2. Structured Entities/Facts (High priority)
        if self.config.extract_entities and session.entities:
            context_parts.append("\n[EXTRACTED_KNOWLEDGE]")
            for name, data in session.entities.items():
                cat = data.get("category", "General")
                val = data.get("value", "")
                context_parts.append(f"- [{cat}] {name}: {val}")

        # 3. Global Recap (Layer 4)
        if session.session_summary:
            context_parts.append("\n[SESSION_SUMMARY]")
            context_parts.append(session.session_summary[:self.config.max_global_summary_tokens * 4])
            
        # 4. Chunk Summaries (Layer 3)
        if session.chunk_summaries:
            context_parts.append("\n[HISTORICAL_CHUNKS]")
            for chunk in session.chunk_summaries[-3:]: # Only latest 3 chunks
                context_parts.append(f"- {chunk[:self.config.max_chunk_tokens * 4]}")
                
        # 5. Recent Detailed Summary (Layer 2)
        if session.recent_summary:
            context_parts.append("\n[LATEST_SUMMARY]")
            context_parts.append(session.recent_summary[:self.config.max_recent_summary_tokens * 4])
                
        # 6. Working Dialogue (Layer 1 - Raw)
        if session.messages:
            context_parts.append("\n[RECENT_DIALOGUE]")
            # Apply strict limit to raw dialogue with per-message truncation
            remaining_budget = self.config.max_dialogue_tokens
            
            # We iterate in reverse to keep the LATEST messages first
            dialogue_turns = []
            for msg in reversed(session.messages):
                if remaining_budget <= 0:
                    break
                    
                role_name = "USER" if msg["role"] == "user" else "ASSISTANT"
                content = msg["content"]
                content_tokens = self._estimate_tokens(content)
                
                if content_tokens > remaining_budget:
                    # Truncate this specific message to fit the rest of the budget
                    char_limit = remaining_budget * 4
                    content = content[:char_limit] + "... [TRUNCATED]"
                    content_tokens = remaining_budget
                
                dialogue_turns.insert(0, f"[{role_name}]: {content}")
                remaining_budget -= content_tokens
            
            context_parts.extend(dialogue_turns)
        
        context_parts.append("\n--- END OF HISTORY ---")
                
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
