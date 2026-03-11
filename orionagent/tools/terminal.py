import subprocess
from orionagent.tools.decorator import tool


@tool
def execute_command(command: str) -> str:
    """Executes a shell command on the host system.
    WARNING: You have ROOT/ADMIN level access to the underlying OS.
    Use with absolute extreme caution. You can delete critical files or break the system.
    Double-check the syntax of commands before running them. If you are unsure, DO NOT proceed.

    Args:
        command (str): The exact shell command to execute (e.g. 'dir' or 'ls -la').
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
