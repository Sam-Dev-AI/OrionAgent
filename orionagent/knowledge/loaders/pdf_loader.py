from typing import List, Dict, Any
from orionagent.knowledge.loaders.base import BaseLoader

class PDFLoader(BaseLoader):
    """Loads text from PDF files."""
    
    def load(self, file_path: str) -> List[Dict[str, Any]]:
        from pypdf import PdfReader
        
        reader = PdfReader(file_path)
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text.strip():
                pages.append({
                    "text": text,
                    "metadata": {
                        "source": file_path,
                        "page": i + 1,
                        "type": "pdf"
                    }
                })
        return pages
