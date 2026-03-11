import subprocess
from orionagent.tools.decorator import tool


@tool
def execute_python(code: str) -> str:
    """Runs a snippet of python code in an isolated subprocess and returns stdout/stderr.
    Use this strictly for complex execution or dynamic problem solving.

    Args:
        code (str): The valid python code to execute.
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
