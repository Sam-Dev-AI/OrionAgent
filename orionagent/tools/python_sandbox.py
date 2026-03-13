import subprocess
from orionagent.tools.decorator import tool


@tool
def python_sandbox(code: str) -> str:
    """A Dynamic Reasoning Engine for executing complex Python logic in a secure sandbox.
    Use this for tasks that require algorithmic thinking, data processing, or simulation.

    When to use:
    - solving complex math (e.g., n-th prime, matrix operations).
    - manipulating large text blocks or JSON data dynamically.
    - writing and running temporary scripts to verify a hypothesis.

    Example Code:
    ```python
    def is_prime(n): ...
    print([x for x in range(2, 100) if is_prime(x)])
    ```

    Args:
        code: The complete, valid Python 3 code snippet to execute. Use print() for output.
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
