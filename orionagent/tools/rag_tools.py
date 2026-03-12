from typing import Any
from orionagent.tools.base_tool import Tool
from orionagent.knowledge.knowledge_base import KnowledgeBase
import os

class IngestTool(Tool):
    """Tool for an agent to ingest a local file into its Knowledge Base."""
    
    def __init__(self, kb: KnowledgeBase):
        super().__init__(
            name="ingest_file",
            description="Ingests a local file (PDF, MD, TXT) OR raw text directly into the knowledge base for semantic retrieval.",
            parameters={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute path to the file."},
                    "text": {"type": "string", "description": "Raw text content to ingest (if no file)."}
                }
            }
        )
        self.kb = kb

    def run(self, input_data: Any):
        # Handle both direct call and dict-based tool call
        if isinstance(input_data, dict):
            file_path = input_data.get("file_path")
            text = input_data.get("text")
        else:
            file_path = input_data
            text = None

        if file_path:
            if not os.path.exists(file_path):
                # If it doesn't exist as a file, maybe it's the raw text being passed to file_path parameter by accident
                if len(file_path) > 100:
                    text = file_path
                    file_path = None
                else:
                    return f"Error: File not found at {file_path}"
        
        try:
            if file_path:
                self.kb.ingest_file(file_path)
                return f"Successfully ingested {os.path.basename(file_path)} into the knowledge base."
            elif text:
                self.kb.ingest_text(text)
                return "Successfully ingested raw text into the knowledge base."
            else:
                return "Error: No file_path or text provided for ingestion."
        except Exception as e:
            return f"Error ingesting into knowledge base: {str(e)}"

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
