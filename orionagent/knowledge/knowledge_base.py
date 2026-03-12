import os
import uuid
from typing import List, Dict, Any, Optional
from orionagent.knowledge.loaders.pdf_loader import PDFLoader
from orionagent.knowledge.loaders.markdown_loader import MarkdownLoader

class KnowledgeBase:
    """Manages a dedicated knowledge collection in ChromaDB."""
    
    def __init__(self, persistence_path: str = "memory/chroma_db", collection_name: str = "orion_knowledge"):
        import chromadb
        self.client = chromadb.PersistentClient(path=persistence_path)
        self.collection = self.client.get_or_create_collection(name=collection_name)
        self._loaders = {
            ".pdf": PDFLoader(),
            ".md": MarkdownLoader(),
            ".txt": MarkdownLoader()
        }

    def ingest_file(self, file_path: str, metadata: Optional[Dict[str, Any]] = None):
        """Load, chunk, and index a file."""
        ext = os.path.splitext(file_path)[1].lower()
        loader = self._loaders.get(ext)
        if not loader:
            raise ValueError(f"No loader for extension: {ext}")
            
        docs = loader.load(file_path)
        
        # Simple chunking for now (one chunk per page/file)
        # In a real 'Advanced' RAG, we'd use recursive character splitting.
        # Let's add basic chunking logic here.
        
        final_docs = []
        final_metas = []
        final_ids = []
        
        for doc in docs:
            text = doc["text"]
            meta = doc["metadata"]
            if metadata:
                meta.update(metadata)
            
            # Simple recursive splitting implementation
            chunks = self._chunk_text(text, chunk_size=1000, overlap=100)
            
            for i, chunk in enumerate(chunks):
                chunk_meta = meta.copy()
                chunk_meta["chunk"] = i
                final_docs.append(chunk)
                final_metas.append(chunk_meta)
                final_ids.append(str(uuid.uuid4()))
                
        if final_docs:
            self.collection.add(
                documents=final_docs,
                metadatas=final_metas,
                ids=final_ids
            )
            
    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """Simple sliding window chunker."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap
            if start >= len(text):
                break
        return chunks

    def query(self, text: str, n_results: int = 5, where: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Retrieve relevant document chunks."""
        results = self.collection.query(
            query_texts=[text],
            n_results=n_results,
            where=where
        )
        
        memories = []
        if not results["documents"] or not results["documents"][0]:
            return []
            
        for i in range(len(results["documents"][0])):
            memories.append({
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {}
            })
        return memories
