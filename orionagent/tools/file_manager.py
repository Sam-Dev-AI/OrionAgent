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
def file_manager(action: FileAction, filepath: str, content: str) -> str:
    """Reads, writes, deletes, or lists local files. Essential for persistent data management. 
    Always use absolute paths when possible. Parent directories will be created automatically.

    Args:
        action: The operation (read, write, append, list, delete, create_dir).
        filepath: The path to the target file or directory.
        content: The data payload for write/append. Only needed for operations that modify files.
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
            print(f"DEBUG: File Manager WRITE called for {filepath}")
            if content is None: content = "" # Handle null from LLMs
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
