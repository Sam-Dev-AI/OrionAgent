import json
from datetime import datetime
import platform
from enum import Enum
from typing import Optional
from orionagent.tools.decorator import tool


class SysAction(Enum):
    TIME = "time"
    INFO = "info"
    CALCULATE = "calculate"


@tool
def system_tools(action: SysAction, expression: Optional[str] = None) -> str:
    """Accesses underlying OS system information, time, and computational utilities.

    Args:
        action (SysAction): The utility to run (time, info, or calculate).
        expression (str): The strict mathematical expression string for calculate (e.g. '5 * 2').
    """
    if isinstance(action, str):
        try:
            action = SysAction(action.lower())
        except ValueError:
            return f"Invalid action: {action}. Must be one of {[e.value for e in SysAction]}"

    try:
        if action == SysAction.TIME:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        elif action == SysAction.INFO:
            info = {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "python_version": platform.python_version()
            }
            return json.dumps(info, indent=2)

        elif action == SysAction.CALCULATE:
            if not expression:
                return "Error: mathematical expression is required for calculation."

            allowed_names = {"__builtins__": None}
            code = compile(expression, "<string>", "eval")
            for name in code.co_names:
                if name not in allowed_names:
                    raise NameError(f"Use of {name} not allowed")
            result = eval(code, {"__builtins__": None}, {})
            return str(result)

    except Exception as e:
        return f"System Tools Error ({action.value}): {str(e)}"

    return "Unhandled Action."
