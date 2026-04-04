from typing import Any, List, Dict, Optional
from orionagent.tools.base_tool import Tool

class AgentRegistryTool(Tool):
    """Tool for the Manager to lookup available agents."""
    def __init__(self, manager: Any):
        super().__init__(
            name="agent_registry_lookup",
            description="List all available agents, their roles, and what tasks they are best suited for.",
            parameters={"type": "object", "properties": {}}
        )
        self.manager = manager

    def run(self, input_data: Any = None, **kwargs) -> str:
        if not self.manager.agents:
            return "No agents registered with the manager."
        
        roster = []
        for agent in self.manager._agents:
            name = getattr(agent, 'name', 'Unknown')
            role = getattr(agent, 'role', 'General Assistant')
            desc = getattr(agent, 'description', 'No description provided.')
            roster.append(f"- {name}: {role}. {desc}")
        return "\n".join(roster)

class MemorySummarizerTool(Tool):
    """Tool for the Manager to summarize the current conversation memory."""
    def __init__(self, manager: Any):
        super().__init__(
            name="memory_summarizer",
            description="Summarize the conversation so far to keep track of progress and key decisions.",
            parameters={"type": "object", "properties": {}}
        )
        self.manager = manager

    def run(self, input_data: Any = None, **kwargs) -> str:
        from orionagent.memory.session import Session
        # Get active session
        sid = self.manager._session_manager.auto(self.manager.user_id, self.manager.name)
        session = self.manager._session_manager.load(self.manager.user_id, self.manager.name, sid)
        
        if not session or not session.messages:
            return "No conversation history to summarize."
            
        summary = f"Session ID: {sid}\nTotal Messages: {len(session.messages)}\n"
        
        # Show recent messages as a snapshot
        recent = session.messages[-3:]
        summary += "\n--- Recent Dialogue ---\n"
        for msg in recent:
            content_preview = (msg['content'][:100] + '...') if len(msg['content']) > 100 else msg['content']
            summary += f"- {msg['role']}: {content_preview}\n"
        
        # Show global memory state
        if session.entities:
            summary += f"\n--- Global Facts ({len(session.entities)} stored) ---\n"
            for name, data in list(session.entities.items())[:5]:
                summary += f"- [{data.get('category', 'General')}] {name}: {data.get('value', '')}\n"
        
        if session.chunk_summaries:
            summary += f"\n--- Archived Chunks ({len(session.chunk_summaries)}) ---\n"
            for chunk in session.chunk_summaries[-2:]:
                summary += f"- {chunk[:150]}...\n"
        
        if session.recent_summary:
            summary += f"\n--- Recent Summary ---\n{session.recent_summary[:200]}\n"
            
        return f"Global Memory Context:\n{summary}"

class TaskStatusTool(Tool):
    """Tool for the Manager to check the status of delegated tasks."""
    def __init__(self, manager: Any):
        super().__init__(
            name="task_status_checker",
            description="Check the current status of the overall objective and delegated subtasks.",
            parameters={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Optional task ID to check."}
                }
            }
        )
        self.manager = manager

    def run(self, input_data: Any = None, **kwargs) -> str:
        task_id = None
        if isinstance(input_data, dict):
            task_id = input_data.get("task_id")
        elif isinstance(input_data, str):
            # rudimentary parsing if needed
            pass
        # Placeholder for task tracking; currently Orion is stateless across asks
        # but the Manager can reason about the sequence of events.
        return "All systems operational. Listening for delegation results."
