import subprocess
from orionagent.tools.decorator import tool


@tool
def python_sandbox(code: str) -> str:
    """Executes Python code in a secure subprocess. Use for math, logic, and data transformation.
    Always use print() to see output.

    Args:
        code: The complete, valid Python 3 code snippet to execute.
    """
    try:
        result = subprocess.run(
            ["python", "-c", code],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error [{result.returncode}]:\n{result.stderr}"
    except subprocess.TimeoutExpired:
        return "Execution timed out after 10 seconds."
    except Exception as e:
        return f"Execution error: {e}"
