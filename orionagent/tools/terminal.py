import subprocess
from orionagent.tools.decorator import tool


@tool
def execute_command(command: str) -> str:
    """Runs shell commands directly on the host. Use for environment setup, package installation, and OS management.
    WARNING: Use with caution. Do not run destructive or recursive commands.

    Args:
        command: The full shell command to execute (e.g. 'pip install requests').
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
