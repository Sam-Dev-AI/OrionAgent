"""Manager -- user-facing multi-agent orchestrator for OrionAI.

Usage:

    from orionagent import Agent, Manager
    from orionagent.models import Gemini

    llm = Gemini(model_name="gemini-2.0-flash")

    # Agents defined INLINE inside Manager:
    manager = Manager(
        model=llm,
        strategy=["planning", "self_learn"],
        manager_instruction="You are Orion, an AI orchestrator.",
        memory=memory,
        temperature=0.7,
        agents=[
            Agent(name="researcher", role="research",
                  description="Search the web for real-time data.",
                  tools=[web_browser]),
            Agent(name="writer", role="writing",
                  description="Write articles, summaries, and reports."),
        ]
    )

    # Or add agents later (backward compatible):
    manager.add(Agent(name="coder", role="coding"))

    for chunk in manager.ask("Write a summary on AI agents"):
        print(chunk, end="", flush=True)
"""

from typing import Generator, List, Optional, Union, Any, Dict
from orionagent.agents.base_agent import Agent
from orionagent.models.base_provider import ModelProvider
from orionagent.agents.strategies import get_strategy


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
        tools:            Tools available to the Manager natively. Defaults
                          to [web_browser] if not provided.
        max_refinements:  For self_learn: max retry attempts (default 2).
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
        tools: Optional[List[Any]] = None,
        knowledge: Optional[str] = None,
        verbose: bool = False,
        async_mode: bool = True,
        debug: bool = False,
        hitl: Union[bool, "HitlConfig"] = False,
    ):
        self.name = name
        self._agents: List[Agent] = []
        self._model = model
        self.system_instruction = system_instruction or "You are Orion, a highly efficient AI orchestrator. Route tasks to the best agents and ensure high-quality results."
        self.user_id = user_id
        self.temperature = temperature
        # Inherit verbose and debug from model if not explicitly set
        self.verbose = verbose or (getattr(self._model, "verbose", False) if self._model else False)
        self.debug = debug or (getattr(self._model, "debug", False) if self._model else False)
        from orionagent.agents.hitl import HitlConfig
        self.async_mode = async_mode
        
        # HITL Configuration
        if isinstance(hitl, bool):
            self.hitl = HitlConfig(permission_level="low" if hitl else "high")
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

        self.tools = list(tools) if tools else []
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
        
        if self.verbose:
            agent.verbose = True
        if self.debug:
            agent.debug = True
            
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
        record_memory: bool = True,
        record_trace: bool = True,
        temperature: Optional[float] = None,
    ) -> Union[str, Generator[str, None, None]]:
        """Orchestrate a task across multiple agents."""
        from orionagent.tracing import tracer
        from orionagent.agents.handoff import AgentHandoff
        
        trace_id = None
        if record_trace:
            trace_id = tracer.start_trace("manager_ask", self.name, task, verbose=self.verbose, debug=self.debug)

        if not self._agents:
            error = "Error: No agents added to the manager."
            if record_trace:
                tracer.end_trace(trace_id, error)
            return (x for x in [error]) if stream else error

        context = None
        sid = self._session_manager.auto(self.user_id, "Manager")
        session = self._session_manager.load(self.user_id, "Manager", sid)
        if not session:
            from orionagent.memory.session import Session
            session = Session(self.user_id, "Manager", sid)

        if self.memory_config.mode != "none":
            self._memory_pipeline.process_turn(session, "user", task, self._model)
            context = self._memory_pipeline.build_context(session, current_task=task)

        # Enrich system instruction with agent roster
        agent_roster = "\n".join([f"- {a.name}: {a.role}. {a.description}" for a in self._agents])
        enriched_instruction = (
            f"{self.system_instruction}\n\n"
            f"You have access to the following agents:\n{agent_roster}\n\n"
            f"If a task matches an agent's expertise, the system will delegate it. "
            f"If the task is about YOU (your name, identity) or general greetings, "
            f"handle it directly."
        )

        result = self._strategy.execute(
            task=task,
            agents=self._agents,
            model=self._model,
            system_instruction=enriched_instruction,
            context=context,
            temperature=temperature if temperature is not None else self.temperature,
            tools=self.tools,
            stream=stream,
            async_mode=self.async_mode,
            verbose=self.verbose,
            debug=self.debug,
            record_trace=False,
            hitl=self.hitl,
        )

        
        # Handle Handoff objects (Direct Return)
        if isinstance(result, AgentHandoff):
            tracer.log_event("handoff_detected", result.target_agent, result.task, metadata={"source": result.source_agent})
            target = next((a for a in self._agents if a.name == result.target_agent), None)
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
                if self.verbose and record_trace:
                    tracer.print_summary()
            return _stream_and_log()
        else:
            if self.memory_config.mode != "none":
                self._memory_pipeline.process_turn(session, "assistant", result, self._model)
            if trace_id:
                tracer.end_trace(trace_id, result)
            if self.verbose and record_trace:
                tracer.print_summary()
            return result
    def chat(self, greeting: str = None, session_id: Optional[str] = None, temperature: Optional[float] = None):
        """Starts an interactive chat session with the manager."""
        from orionagent.chat import chat
        return chat(self, greeting=greeting, session_id=session_id, temperature=temperature)
