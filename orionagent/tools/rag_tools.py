from typing import Any
from orionagent.tools.base_tool import Tool
from orionagent.knowledge.knowledge_base import KnowledgeBase
import os

class IngestTool(Tool):
    """Tool for an agent to ingest a local file into its Knowledge Base."""
    
    def __init__(self, kb: KnowledgeBase):
        super().__init__(
            name="ingest_file",
            description="Ingests a local file (PDF, MD, TXT) into the knowledge base for semantic retrieval.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute path to the file."}
                },
                "required": ["file_path"]
            }
        )
        self.kb = kb

    def run(self, input_data: Any):
        # Handle both direct call and dict-based tool call
        if isinstance(input_data, dict):
            file_path = input_data.get("file_path")
        else:
            file_path = input_data

        if not file_path or not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"
        try:
            self.kb.ingest_file(file_path)
            return f"Successfully ingested {os.path.basename(file_path)} into the knowledge base."
        except Exception as e:
            return f"Error ingesting file: {str(e)}"

class QueryKnowledgeTool(Tool):
    """Tool for an agent to query its Knowledge Base."""
    
    def __init__(self, kb: KnowledgeBase):
        super().__init__(
            name="query_knowledge",
            description="Searches the knowledge base for relevant information on a topic.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."}
                },
                "required": ["query"]
            }
        )
        self.kb = kb

    def run(self, input_data: Any):
        if isinstance(input_data, dict):
            query = input_data.get("query")
        else:
            query = input_data

        if not query:
            return "Error: No query provided."

        results = self.kb.query(query)
        if not results:
            return "No relevant information found in the knowledge base."
            
        output = "Relevant snippets from your knowledge base:\n"
        for r in results:
            content = r["content"]
            meta = r["metadata"]
            source = meta.get("source", "Unknown")
            output += f"\n--- Source: {os.path.basename(str(source))} ---\n{content}\n"
        return output
