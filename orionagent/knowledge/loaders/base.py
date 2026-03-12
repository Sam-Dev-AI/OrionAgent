import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseLoader(ABC):
    """Abstract base class for document loaders."""
    
    @abstractmethod
    def load(self, source: str) -> List[Dict[str, Any]]:
        """Load data from source and return as list of dicts with 'text' and 'metadata'."""
        pass
