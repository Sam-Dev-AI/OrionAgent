import subprocess
from orionagent.tools.decorator import tool


@tool
def execute_command(command: str) -> str:
    """Executes a shell command directly on the host system.
    
    INDUSTRIAL WARNING: You have direct OS access. 
    Use this for: Environment setup, package installation, starting services, or git operations.
    DO NOT use this for: Deleting uncontrolled files or running recursive destructive commands.

    Args:
        command: The full shell command to execute (e.g. 'pip install requests' or 'git status').
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return result.stdout if result.stdout else "Command executed successfully with no output."
        else:
            return f"Command Failed [{result.returncode}]:\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return "Execution timed out after 30 seconds."
    except Exception as e:
        return f"Execution error: {e}"
