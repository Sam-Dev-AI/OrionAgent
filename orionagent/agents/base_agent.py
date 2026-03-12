"""Base agent module for OrionAI.

system_instruction is stored once on the agent and passed to the
provider on every ask() call via the provider-native mechanism
(Gemini: GenerateContentConfig, OpenAI: system role, Ollama: system field).
This means those tokens are NOT re-billed per call -- significant savings
on long-running agents.
"""

from typing import Generator, List, Optional, Union, Callable, Dict, Any
from orionagent.tools.base_tool import Tool
from orionagent.tools.tool_executor import ToolExecutor
from orionagent.models.base_provider import ModelProvider
from orionagent.tools.memory_tools import SaveMemoryTool, SearchMemoryTool

# New memory imports
from orionagent.memory.config import MemoryConfig
from orionagent.memory.session import SessionManager, Session
from orionagent.memory.manager import MemoryPipeline, AgentMemoryProxy
from orionagent.memory.storage.sqlite_storage import SQLiteStorage
from orionagent.knowledge.knowledge_base import KnowledgeBase
from orionagent.tools.rag_tools import IngestTool, QueryKnowledgeTool



class Agent:
    """Base class for every OrionAI agent.

    Args:
        name:               Unique name for the agent.
        role:               Short role description (used for routing).
        description:        Longer description of capabilities.
        system_instruction: Persistent system prompt (token-efficient).
        tools:              List of Tool objects this agent can use.
        use_default_tools:  If True, auto-load all 5 built-in tools.
        model:              LLM provider instance.
        memory:             Memory config string ("session", "long_term", "chroma") or dict. Defaults to "session".
        user_id:            User identifier for memory scoping.
        strategy:           Strategy name(s) for self-learning/planning.
        max_refinements:    Max retries for self-learn strategy.
    """

    def __init__(
        self,
        name: str = "Assistant",
        role: str = "AI Assistant",
        description: str = "",
        system_instruction: Optional[str] = None,
        tools: Optional[List[Tool]] = None,
        use_default_tools: bool = False,
        model: Optional[Union[str, ModelProvider]] = None,
        memory: Union[str, Dict[str, Any], MemoryConfig] = "session",
        user_id: str = "default_user",
        strategy: Optional[Union[str, List[str]]] = None,
        max_refinements: int = 2,
        guards: Optional[List[Union[str, Callable]]] = None,
        verbose: bool = False,
        async_mode: bool = True,
        debug: bool = False,
        knowledge: Optional[Union[str, KnowledgeBase]] = None,
    ):
        self.name = name
        self.role = role
        self.description = description
        self.system_instruction = system_instruction
        self.async_mode = async_mode
        self.debug = debug
        
        if isinstance(model, str):
            from orionagent.models.model import Model
            self.model = Model(provider=model, debug=self.debug)
        else:
            self.model = model
            
        self.user_id = user_id
        # Inherit verbose and debug from model if not explicitly set
        self.verbose = verbose or (getattr(self.model, "verbose", False) if self.model else False)
        self.debug = debug or (getattr(self.model, "debug", False) if self.model else False)

        # --- Memory setup ---
        if isinstance(memory, MemoryConfig):
            self.memory_config = memory
        elif isinstance(memory, dict):
            self.memory_config = MemoryConfig.from_dict(memory)
        else:
            # Treats strings and defaults (session) the same
            self.memory_config = MemoryConfig(mode=memory)
            
        import os
        self._session_manager = SessionManager(base_dir=self.memory_config.storage_path)
        
        # Storage Selection (Hierarchical)
        if self.memory_config.mode in ["persistent", "long_term", "chroma"]:
            db_file = os.path.join(self.memory_config.storage_path, "orionagent.db")
            # chroma mode is the ultimate level (SQLite + Chroma)
            use_vdb = (self.memory_config.mode == "chroma")
            self._persistent_db = SQLiteStorage(db_path=db_file, use_chroma=use_vdb)
        else:
            self._persistent_db = None

            
        self._memory_pipeline = MemoryPipeline(self.memory_config, self._persistent_db)
        
        # Public proxy for developers to call agent.memory.view(), etc.
        self.memory = AgentMemoryProxy(self)

        # --- Tool setup ---
        self.tools = list(tools) if tools else []

        if use_default_tools:
            self._merge_default_tools()

        self.tool_executor = ToolExecutor(async_mode=self.async_mode)

        # --- Knowledge / RAG setup ---
        if isinstance(knowledge, str):
            self.knowledge = KnowledgeBase(collection_name=knowledge)
        else:
            self.knowledge = knowledge

        if self.knowledge:
            self.tools.append(IngestTool(self.knowledge))
            self.tools.append(QueryKnowledgeTool(self.knowledge))

        # --- Strategy ---
        from orionagent.agents.strategies import get_strategy
        self._strategy = get_strategy(strategy, max_refinements=max_refinements)

        # --- Logic Guards (Simple DX) ---
        if guards:
            from orionagent.agents.guards import apply_guards
            self.ask = apply_guards(self.ask, guards)

        # --- Memory tools (auto-injected) ---
        if self.memory_config.mode in ["persistent", "chroma"]:
            self.tools.append(SaveMemoryTool(self.memory, self.user_id))
            self.tools.append(SearchMemoryTool(self.memory, self.user_id))

    # ------------------------------------------------------------------
    # Default tools auto-loading
    # ------------------------------------------------------------------

    def _merge_default_tools(self):
        """Merge built-in tools, skipping any already present by name."""
        from orionagent.tools import default_tools

        existing_names = {t.name for t in self.tools}
        for dt in default_tools:
            if dt.name not in existing_names:
                self.tools.append(dt)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ask(
        self,
        task: str,
        stream: bool = True,
        use_strategy: bool = True,
        session_id: Optional[str] = None,
        record_memory: bool = True,
        record_trace: bool = True,
        priority: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Union[str, Generator[str, None, None]]:
        """Execute a task."""
        from orionagent.tracing import tracer
        trace_id = None
        if record_trace:
            trace_id = tracer.start_trace("agent_ask", self.name, task, verbose=self.verbose, debug=self.debug)

        # Session loading
        sid = session_id or self._session_manager.auto(self.user_id, self.name)
        session = self._session_manager.load(self.user_id, self.name, sid)
        if not session:
            session = Session(self.user_id, self.name, sid)

        # Update session priority if provided or use config default
        session.priority = priority or self.memory_config.priority

        prompt = task
        if self.memory_config.mode != "none":
            if record_memory:
                self._memory_pipeline.process_turn(session, "user", task, self.model)
            context = self._memory_pipeline.build_context(session, current_task=task)
            if context:
                prompt = f"{context}\n\n==== CURRENT TASK ====\n{task}"

        if use_strategy and self._strategy:
            res = self._strategy.execute(
                task=prompt,
                agents=[self],
                model=self.model,
                system_instruction=self.system_instruction,
                temperature=temperature,
                tools=self.tools,
                stream=stream,
                async_mode=self.async_mode,
                verbose=self.verbose,
                debug=self.debug,
                record_trace=False # Strategy internally calls agents, so we don't want deep traces
            )
            # Log the intent (result) if not streaming. If streaming, the strategy handles generator.
            if not stream:
                if self.memory_config.mode != "none" and record_memory:
                    self._memory_pipeline.process_turn(session, "assistant", res, self.model)
                if trace_id:
                    tracer.end_trace(trace_id, res)
            
            # Since strategies yield directly if stream=True, we must wrap it to log
            if stream:
                def _trace_generator_strategy():
                    full_res = []
                    for chunk in res:
                        full_res.append(chunk)
                        yield chunk
                    res_str = "".join(full_res)
                    if trace_id:
                        tracer.end_trace(trace_id, res_str)
                    if self.verbose and record_trace: 
                        tracer.print_summary()
                return _trace_generator_strategy()
                
            if not stream:
                if self.memory_config.mode != "none" and record_memory:
                    self._memory_pipeline.process_turn(session, "assistant", res, self.model)
                if trace_id:
                    tracer.end_trace(trace_id, res)
            
            return res

        if stream:
            # For streaming, we wrap the generator to end the trace
            def _trace_generator():
                full_res = []
                for chunk in self._ask_stream(prompt, session, temperature=temperature):
                    full_res.append(chunk)
                    yield chunk
                res_str = "".join(full_res)
                if self.memory_config.mode != "none" and record_memory:
                    self._memory_pipeline.process_turn(session, "assistant", res_str, self.model)
                if trace_id:
                    tracer.end_trace(trace_id, res_str)
                if self.verbose and record_trace:
                    tracer.print_summary()
            return _trace_generator()

        res = self._ask_full(prompt, session, temperature=temperature)
        if self.memory_config.mode != "none" and record_memory:
            self._memory_pipeline.process_turn(session, "assistant", res, self.model)
        if trace_id:
            tracer.end_trace(trace_id, res)
        
        if self.verbose and record_trace:
            tracer.print_summary()
            
        return res

    def chat(self, greeting: str = None, session_id: Optional[str] = None, priority: Optional[str] = None, temperature: Optional[float] = None):
        """Starts an interactive chat session with this agent."""
        from orionagent.chat import chat
        return chat(self, greeting=greeting, session_id=session_id, priority=priority, temperature=temperature)

    # ------------------------------------------------------------------
    # Tool access
    # ------------------------------------------------------------------

    def use_tool(self, tool_name: str, input_data) -> str:
        """Run a tool via the centralised ToolExecutor."""
        from orionagent.tracing import tracer
        trace_id = tracer.start_trace("tool_call_agent", tool_name, input_data, verbose=self.verbose, debug=self.debug)
        res = self.tool_executor.execute(tool_name, input_data, self.tools)
        tracer.end_trace(trace_id, res)
        return res

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ask_full(self, prompt: str, session: Session, temperature: Optional[float] = None) -> str:
        if self.model:
            response = self.model.generate(
                prompt=prompt,
                system_instruction=self.system_instruction,
                temperature=temperature,
                tools=self.tools if self.tools else None,
            )
            # Log agent's response to memory only if we are the leaf execution
            # But actually, the top-level ask will log the assistant response if record_memory is True,
            # or we log it here if record_memory is passed down.
            # We don't have record_memory in _ask_full. Let's pass it!
            return response

        return f"{self.name} processing task: {prompt}"

    def _ask_stream(self, prompt: str, session: Session, temperature: Optional[float] = None) -> Generator[str, None, None]:
        if self.model:
            full_response = []
            for chunk in self.model.generate_stream(
                prompt=prompt,
                system_instruction=self.system_instruction,
                temperature=temperature,
                tools=self.tools if self.tools else None,
            ):
                full_response.append(chunk)
                yield chunk

            # Handled similarly.
        else:
            yield f"{self.name} processing task: {prompt}"
