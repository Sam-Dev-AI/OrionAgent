import os
from typing import List, Dict, Any
from orionagent.knowledge.loaders.base import BaseLoader

class MarkdownLoader(BaseLoader):
    """Loads text from Markdown/Text files."""
    
    def load(self, file_path: str) -> List[Dict[str, Any]]:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        return [{
            "text": content,
            "metadata": {
                "source": file_path,
                "type": "markdown"
            }
        }]
