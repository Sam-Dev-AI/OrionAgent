"""Manager -- user-facing multi-agent orchestrator for OrionAI.

Usage:

    from orionagent import Agent, Manager
    from orionagent.models import Gemini

    llm = Gemini(model_name="gemini-2.0-flash")

    # Agents defined INLINE inside Manager:
    # Manager with agents:
    manager = Manager(
        model=llm,
        agents=[
            Agent(name="researcher", role="research",
                  description="Search the web for real-time data.",
                  tools=[web_browser]),
            Agent(name="writer", role="writing",
                  description="Write articles, summaries, and reports."),
        ]
    )

    for chunk in manager.ask("Write a summary on AI agents"):
        print(chunk, end="", flush=True)
"""

from typing import Generator, List, Optional, Union, Any, Dict, Callable
from orionagent.agents.base_agent import Agent
from orionagent.models.base_provider import ModelProvider
from orionagent.agents.strategies import get_strategy
from orionagent.tools.manager_tools import AgentRegistryTool, MemorySummarizerTool, TaskStatusTool


class Manager:
    """Orchestrates multiple agents using a configurable strategy.

    Args:
        model:            Default model provider. Attached to any agent
                          that doesn't already have a model set. Also used
                          by strategies for planning / evaluation calls.
        strategy:         How to orchestrate agents. Accepts:
                          - None or "direct" (default) -- single delegation
                          - "planning" -- plan then delegate
                          - "self_learn" -- learn from execution results
                          - ["planning", "self_learn"] -- combined
        agents:           List of Agent instances to register. The Manager
                          auto-attaches its model and memory to each agent.
        temperature:      Temperature for the Manager's own LLM calls.
        system_instruction: Default instructions for the Manager's orchestrator model.
        memory:           Memory level for the Manager's orchestrator. Defaults to "session".
    """

    def __init__(
        self,
        name: str = "Manager",
        model: Optional[ModelProvider] = None,
        strategy: Optional[Union[str, List[str]]] = None,
        system_instruction: Optional[str] = None,
        memory: Union[str, Dict[str, Any], "MemoryConfig"] = "session",
        agents: Optional[List[Agent]] = None,
        user_id: str = "default_user",
        max_refinements: int = 2,
        temperature: Optional[float] = None,
        knowledge: Optional[str] = None,
        async_mode: bool = True,
        hitl: Union[bool, "HitlConfig"] = False,
    ):
        self.name = name
        self._agents: List[Agent] = []
        self._model = model
        self.system_instruction = system_instruction or (
            "[ROLE: TASK ORCHESTRATOR]\n\n"
            "You are a Manager Agent responsible for coordinating a multi-agent system.\n\n"
            "Your responsibilities:\n"
            "1. PLAN: Break down the user’s task into clear, minimal sub-tasks.\n"
            "2. DELEGATE: Assign each sub-task to the most appropriate agent.\n"
            "3. MONITOR: Track progress and ensure task completion.\n\n"
            "---\n\n"
            "[STRICT RULES]\n"
            "* NEVER execute tasks yourself.\n"
            "* DO NOT generate code, search the web, or produce final user answers.\n"
            "* ONLY delegate and coordinate.\n"
            "* Be concise, logical, and structured.\n"
            "* Do NOT include conversational text.\n\n"
            "---\n\n"
            "[DECISION RULES]\n"
            "* Select agents based on their capabilities.\n"
            "* Respect user constraints (allowed_agents, blocked_agents, force_agent).\n"
            "* Prefer minimal steps (avoid over-planning).\n"
            "* If task is unclear, request clarification via structured output.\n"
            "* If no suitable agent exists, return an error.\n\n"
            "---\n\n"
            "[CONTEXT USAGE]\n"
            "You may use:\n"
            "* Task input\n"
            "* Available agents list\n"
            "* Memory summaries\n"
            "* User constraints\n\n"
            "---\n\n"
            "[OUTPUT FORMAT - STRICT JSON]\n"
            "{\n"
            "  \"plan\": [\n"
            "    {\n"
            "      \"step_id\": 1,\n"
            "      \"task\": \"...\",\n"
            "      \"agent\": \"...\",\n"
            "      \"reason\": \"...\"\n"
            "    }\n"
            "  ],\n"
            "  \"metadata\": {\n"
            "    \"confidence\": 0.0,\n"
            "    \"notes\": \"optional\"\n"
            "  }\n"
            "}"
        )
        self.user_id = user_id
        self.temperature = temperature
        from orionagent.agents.hitl import HitlConfig
        self.async_mode = async_mode
        
        # HITL Configuration (Safety Lock)
        if isinstance(hitl, bool):
            # If hitl=True, default to 'medium' (Balanced Risk Check) and plan_review=True
            self.hitl = HitlConfig(
                permission_level="medium" if hitl else "high",
                use_llm=True,
                plan_review=True
            )
        else:
            self.hitl = hitl

        
        # --- Memory setup (Same as Agent) ---
        from orionagent.memory.config import MemoryConfig
        from orionagent.memory.session import SessionManager
        from orionagent.memory.manager import MemoryPipeline
        from orionagent.memory.storage.sqlite_storage import SQLiteStorage
        
        if isinstance(memory, MemoryConfig):
            self.memory_config = memory
        elif isinstance(memory, dict):
            self.memory_config = MemoryConfig.from_dict(memory)
        else:
            # Treats strings and defaults (session) the same
            self.memory_config = MemoryConfig(mode=memory)
            
        import os
        self._session_manager = SessionManager(base_dir=self.memory_config.storage_path)
        
        if self.memory_config.mode in ["persistent", "long_term", "chroma"]:
            db_file = os.path.join(self.memory_config.storage_path, "orionagent.db")
            use_vdb = (self.memory_config.mode == "chroma")
            self._persistent_db = SQLiteStorage(db_path=db_file, use_chroma=use_vdb)
        else:
            self._persistent_db = None

        self._memory_pipeline = MemoryPipeline(self.memory_config, self._persistent_db)
        
        # --- Knowledge / RAG setup (Same as Agent) ---
        from orionagent.knowledge.knowledge_base import KnowledgeBase
        from orionagent.tools.rag_tools import IngestTool, QueryKnowledgeTool
        
        if isinstance(knowledge, str):
            self.knowledge = KnowledgeBase(collection_name=knowledge)
        else:
            self.knowledge = knowledge

        self.tools = [
            AgentRegistryTool(self),
            MemorySummarizerTool(self),
            TaskStatusTool(self)
        ]

        if self.knowledge:
            self.tools.append(IngestTool(self.knowledge))
            self.tools.append(QueryKnowledgeTool(self.knowledge))
            
        self._strategy = get_strategy(
            strategy, max_refinements=max_refinements
        )

        # Register agents passed inline
        if agents:
            for agent in agents:
                self.add(agent)


    @property
    def agents(self) -> List[Agent]:
        """Returns the list of agents registered with this manager."""
        return self._agents

    # ------------------------------------------------------------------
    # Agent registration
    # ------------------------------------------------------------------

    def add(self, agent: Agent) -> "Manager":
        """Add an agent to this manager.

        Auto-attaches the Manager's model and memory to the agent
        if the agent doesn't already have them set.

        Returns self so calls can be chained:
            manager.add(researcher).add(writer)
        """
        if self._model and agent.model is None:
            agent.model = self._model
        
        self._agents.append(agent)
        return self

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    def ask(
        self,
        task: str,
        stream: bool = True,
        session_id: Optional[str] = None,
        priority: Optional[str] = None,
        record_memory: bool = True,
        record_trace: bool = True,
        temperature: Optional[float] = None,
        allowed_agents: Optional[List[str]] = None,
        blocked_agents: Optional[List[str]] = None,
        force_agent: Optional[str] = None,
    ) -> Union[str, Generator[str, None, None]]:
        """Orchestrate a task across multiple agents."""
        from orionagent.tracing import tracer
        from orionagent.agents.handoff import AgentHandoff
        
        trace_id = None
        if record_trace:
            trace_id = tracer.start_trace("manager_ask", self.name, task, verbose=self._model.verbose, debug=self._model.debug)

        if not self._agents and not self.tools:
            error = "Error: No agents or tools added to the manager."
            if record_trace:
                tracer.end_trace(trace_id, error)
            return (x for x in [error]) if stream else error

        # If no agents, create a proxy so the Manager can handle tasks via Strategy
        execution_agents = self._agents
        if not execution_agents:
            from orionagent.agents.base_agent import Agent
            manager_proxy = Agent(
                name=self.name,
                role="Manager",
                description="The primary orchestrator.",
                model=self._model,
                tools=self.tools,
                use_default_tools=False,
                system_instruction=self.system_instruction,
                memory="session",
            )
            execution_agents = [manager_proxy]

        # Filter agents based on constraints
        if allowed_agents:
            execution_agents = [a for a in execution_agents if a.name in allowed_agents]
        if blocked_agents:
            execution_agents = [a for a in execution_agents if a.name not in blocked_agents]
        
        if not execution_agents:
            raise ValueError("No agents available after applying allowed/blocked filters.")

        # Build constraint instructions for the prompt
        constraints = []
        if allowed_agents: constraints.append(f"ALLOWED_AGENTS: {allowed_agents}")
        if blocked_agents: constraints.append(f"BLOCKED_AGENTS: {blocked_agents}")
        if force_agent: constraints.append(f"FORCE_AGENT: {force_agent}")
        constraint_text = "\n".join(constraints) if constraints else "None"

        context = None
        manager_context = None
        sid = session_id or self._session_manager.auto(self.user_id, "Manager")
        session = self._session_manager.load(self.user_id, "Manager", sid)
        if not session:
            from orionagent.memory.session import Session
            session = Session(self.user_id, "Manager", sid)
        
        if priority:
            session.priority = priority

        if self.memory_config.mode != "none":
            self._memory_pipeline.process_turn(session, "user", task, self._model)
            context = self._memory_pipeline.build_context(session, current_task=task)
            # Build a separate global context for injection into agent prompts
            manager_context = self._build_global_context(session)

        # Enrich system instruction with agent roster
        roster_items = []
        for a in execution_agents:
            tools_list = ", ".join([t.name for t in a.tools]) if a.tools else "None"
            roster_items.append(f"- {a.name}: {a.role}. {a.description} (Tools: {tools_list})")
            
        agent_roster = "\n".join(roster_items)
        enriched_instruction = (
            f"{self.system_instruction}\n\n"
            f"You have access to the following agents:\n{agent_roster}\n\n"
            f"==== USER CONSTRAINTS ====\n{constraint_text}\n\n"
            f"If a task matches an agent's expertise, the system will delegate it. "
            f"If the task is about your identity or general greetings, "
            f"handle it directly."
        )

        # Define callback to record agent results into Manager's global memory
        def _on_step_complete(agent_name: str, step_task: str, result: str):
            """Record an agent's result into Manager's global memory session."""
            if self.memory_config.mode == "none":
                return
            # Truncate result for memory efficiency
            result_summary = result[:2000] if len(result) > 2000 else result
            memory_entry = f"[Agent: {agent_name}] Task: {step_task[:200]}\nResult: {result_summary}"
            self._memory_pipeline.process_turn(session, "assistant", memory_entry, self._model)
            if self._model.debug:
                print(f"\n[GLOBAL MEMORY] Recorded result from {agent_name} ({len(result)} chars)")

        result = self._strategy.execute(
            task=task,
            agents=execution_agents,
            model=self._model,
            system_instruction=enriched_instruction,
            context=context,
            temperature=temperature if temperature is not None else self.temperature,
            tools=self.tools,
            stream=stream,
            async_mode=self.async_mode,
            record_trace=False,
            hitl=self.hitl,
            priority=priority,
            manager_context=manager_context,
            on_step_complete=_on_step_complete,
        )

        
        # Handle Handoff objects (Direct Return)
        if isinstance(result, AgentHandoff):
            tracer.log_event("handoff_detected", result.target_agent, result.task, metadata={"source": result.source_agent})
            target = next((a for a in execution_agents if a.name == result.target_agent), None)
            if target:
                final_res = target.ask(result.to_prompt(), stream=stream, record_trace=False)
                if trace_id:
                    tracer.end_trace(trace_id, "[Handoff Executed]")
                return final_res
            else:
                err = f"Error: Handoff target agent '{result.target_agent}' not found."
                if trace_id:
                    tracer.end_trace(trace_id, err)
                return (x for x in [err]) if stream else err

        if stream:
            def _stream_and_log():
                full_response = []
                for chunk in result:
                    full_response.append(chunk)
                    yield chunk
                res_str = "".join(full_response)
                if self.memory_config.mode != "none":
                    self._memory_pipeline.process_turn(session, "assistant", res_str, self._model)
                if trace_id:
                    tracer.end_trace(trace_id, res_str)
                if self._model.verbose and record_trace:
                    tracer.print_summary()
            return _stream_and_log()
        else:
            if self.memory_config.mode != "none":
                self._memory_pipeline.process_turn(session, "assistant", result, self._model)
            if trace_id:
                tracer.end_trace(trace_id, result)
            if self._model.verbose and record_trace:
                tracer.print_summary()
            return result
    # ------------------------------------------------------------------
    # Global Memory Context Builder
    # ------------------------------------------------------------------

    def _build_global_context(self, session) -> str:
        """Build a condensed global memory context for injection into agent prompts.
        
        This creates the 'Global Memory' tier from the architecture diagram.
        Agents receive this as ### GLOBAL CONTEXT ### in their prompts,
        giving them awareness of cross-agent results and accumulated knowledge.
        """
        parts = []
        
        # 1. Key entities/facts (most compact, highest value)
        if session.entities:
            entity_items = []
            # Sort by importance and take top 8 for space efficiency
            sorted_entities = sorted(session.entities.items(), key=lambda x: x[1].get("importance", 0), reverse=True)[:8]
            for name, data in sorted_entities:
                cat = data.get("category", "General")
                val = data.get("value", "")
                entity_items.append(f"- [{cat}] {name}: {val}")
            if entity_items:
                parts.append("KNOWN FACTS:\n" + "\n".join(entity_items))
        
        # 2. Session summary (global recap)
        if session.session_summary:
            parts.append(f"SESSION RECAP:\n{session.session_summary[:500]}")
        
        # 3. Recent chunk summaries (last 2 only for token efficiency)
        if session.chunk_summaries:
            recent_chunks = session.chunk_summaries[-2:]
            chunks_text = "\n".join(f"- {c[:300]}" for c in recent_chunks)
            parts.append(f"RECENT HISTORY:\n{chunks_text}")
        
        # 4. Recent detailed summary
        if session.recent_summary:
            parts.append(f"LATEST CONTEXT:\n{session.recent_summary[:400]}")
        
        combined = "\n\n".join(parts) if parts else ""
        
        # Optimization: If context is still too large (> 3000 chars), condense further
        if len(combined) > 3000 and self._model:
            try:
                # One-shot condensation call to LLM
                condense_prompt = (
                    f"Condense the following conversation context into a single, high-density paragraph "
                    f"that preserves all key facts and decisions. Output ONLY the paragraph.\n\n"
                    f"CONTEXT:\n{combined}"
                )
                summary = self._model.generate(
                    prompt=condense_prompt,
                    system_instruction="You are an expert context compressor.",
                    temperature=0.0
                )
                return f"SESSION SUMMARY (Condensed):\n{summary.strip()}"
            except Exception:
                # Fallback to simple truncation
                return combined[:3000] + "... [TRUNCATED]"
        
        return combined

    def chat(self, greeting: str = None, session_id: Optional[str] = None, temperature: Optional[float] = None):
        """Starts an interactive chat session with the manager."""
        from orionagent.chat import chat
        return chat(self, greeting=greeting, session_id=session_id, temperature=temperature)
