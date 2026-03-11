import os
from enum import Enum
from typing import Optional
from orionagent.tools.decorator import tool

class FileAction(Enum):
    READ = "read"
    WRITE = "write"
    APPEND = "append"
    LIST = "list"
    DELETE = "delete"
    CREATE_DIR = "create_dir"

@tool
def file_manager(action: FileAction, filepath: str, content: Optional[str] = None) -> str:
    """A comprehensive OS file manager for listing, reading, and modifying files/directories.
    
    Args:
        action (FileAction): The exact action to perform (read, write, append, list, delete, create_dir).
        filepath (str): The absolute or relative path to the file or directory.
        content (str): The text content to write or append (required for write/append actions).
    """
    if isinstance(action, str):
        try:
            action = FileAction(action.lower())
        except ValueError:
            return f"Invalid action: {action}. Must be one of {[e.value for e in FileAction]}"

    try:
        if action == FileAction.READ:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
                
        elif action == FileAction.WRITE:
            if content is None: return "Error: content is required for write action."
            os.makedirs(os.path.dirname(os.path.abspath(filepath)) or ".", exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully wrote to {filepath}"
            
        elif action == FileAction.APPEND:
            if content is None: return "Error: content is required for append action."
            os.makedirs(os.path.dirname(os.path.abspath(filepath)) or ".", exist_ok=True)
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(content)
            return f"Successfully appended to {filepath}"
            
        elif action == FileAction.LIST:
            items = os.listdir(filepath)
            return "\n".join(items) if items else "Directory is empty."
            
        elif action == FileAction.DELETE:
            if os.path.isdir(filepath):
                os.rmdir(filepath)
            else:
                os.remove(filepath)
            return f"Successfully deleted {filepath}"
            
        elif action == FileAction.CREATE_DIR:
            os.makedirs(filepath, exist_ok=True)
            return f"Successfully created directory {filepath}"
            
    except Exception as e:
        return f"File Manager Error ({action.value}): {str(e)}"
    
    return "Unhandled Action."
