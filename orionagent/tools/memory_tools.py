from orionagent.tools.base_tool import Tool
from orionagent.memory.manager import AgentMemoryProxy

class SaveMemoryTool(Tool):
    """A tool that allows the agent to explicitly save facts to long-term memory."""
    
    name = "save_memory"
    description = "Saves an important fact or preference to long-term memory for future retrieval."
    parameters = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The specific fact or preference to save (e.g., 'User is allergic to peanuts')."
            },
            "category": {
                "type": "string",
                "description": "An optional category for the fact (e.g., 'preference', 'project_detail')."
            }
        },
        "required": ["content"]
    }

    def __init__(self, memory_proxy: AgentMemoryProxy, user_id: str):
        self.memory = memory_proxy
        self.user_id = user_id

    def execute(self, **kwargs) -> str:
        content = kwargs.get("content")
        category = kwargs.get("category", "general")
        
        if not content:
            return "Failed: Content to save must be provided."
            
        self.memory.add(text=content, importance=7, metadata={"category": category})
        return f"Successfully saved to long-term memory: '{content}'"


class SearchMemoryTool(Tool):
    """A tool that allows the agent to explicitly search long-term memory."""
    
    name = "search_memory"
    description = "Searches the user's long-term memory for past facts, preferences, or conversations."
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to look for in memory."
            }
        },
        "required": ["query"]
    }

    def __init__(self, memory_proxy: AgentMemoryProxy, user_id: str):
        self.memory = memory_proxy
        self.user_id = user_id

    def execute(self, **kwargs) -> str:
        query = kwargs.get("query")
        if not query:
            return "Failed: Search query must be provided."
            
        # Actually we need to search using the agent's persistent db directly
        # because the proxy view() method brings up all limit. But since we need query based:
        db = self.memory._get_persistent_db()
        if not db:
            return "Failed: Persistent memory is not enabled."
            
        results = db.search(query=query, user_id=self.user_id, agent_id=self.memory.agent.name, limit=5, min_importance=1)
        if not results:
            return "No relevant memories found."
            
        return "Found the following memories:\n" + "\n".join([f"- {r['content']}" for r in results])
