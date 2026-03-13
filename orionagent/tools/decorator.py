"""@tool decorator for OrionAI.

Turns any plain Python function into a Tool with auto-generated
JSON Schema from type hints and docstrings.

Usage:
    from orionagent.tools import tool

    @tool
    def greet(name: str, excited: bool = False) -> str:
        \"\"\"Greet someone by name.

        Args:
            name: The person's name.
            excited: If True, add an exclamation mark.
        \"\"\"
        suffix = "!" if excited else "."
        return f"Hello, {name}{suffix}"
"""

import inspect
import json
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union, get_args, get_origin
from orionagent.tools.base_tool import Tool


# ------------------------------------------------------------------
# Type → JSON Schema mapping
# ------------------------------------------------------------------

def _type_to_schema(py_type: Type) -> Dict[str, Any]:
    """Convert a Python type hint to a JSON Schema fragment."""
    origin = get_origin(py_type)
    args = get_args(py_type)

    if py_type == str:
        return {"type": "string"}
    elif py_type == int:
        return {"type": "integer"}
    elif py_type == float:
        return {"type": "number"}
    elif py_type == bool:
        return {"type": "boolean"}
    elif origin == list or origin == List:
        item_schema = _type_to_schema(args[0]) if args else {}
        return {"type": "array", "items": item_schema}
    elif origin == dict or origin == Dict:
        return {"type": "object"}
    elif type(py_type) == type and issubclass(py_type, Enum):
        return {"type": "string", "enum": [e.value for e in py_type]}
    else:
        return {"type": "string"}


def _is_optional(annotation) -> bool:
    """Check if a type annotation is Optional[X] (i.e. Union[X, None])."""
    origin = get_origin(annotation)
    if origin is Union:
        args = get_args(annotation)
        return type(None) in args
    return False


def _unwrap_optional(annotation):
    """Extract X from Optional[X]."""
    args = get_args(annotation)
    non_none = [a for a in args if a is not type(None)]
    return non_none[0] if non_none else str


# ------------------------------------------------------------------
# Docstring parser
# ------------------------------------------------------------------

def _parse_docstring(docstring: str) -> tuple:
    """Parse Google-style docstrings into (description, {param: desc})."""
    if not docstring:
        return "", {}

    lines = docstring.strip().split("\n")
    main_desc = []
    param_descs = {}

    in_args = False
    current_arg = None
    current_arg_desc = []

    for line in lines:
        line = line.strip()
        if not line:
            if current_arg:
                param_descs[current_arg] = " ".join(current_arg_desc)
                current_arg = None
                current_arg_desc = []
            continue

        if line.lower() in ("args:", "arguments:", "parameters:"):
            in_args = True
            continue

        if in_args:
            if ":" in line and not line.startswith(" "):
                if current_arg:
                    param_descs[current_arg] = " ".join(current_arg_desc)

                parts = line.split(":", 1)
                current_arg = parts[0].strip()
                if " " in current_arg or "(" in current_arg:
                    current_arg = current_arg.split(" ")[0].split("(")[0].strip()

                current_arg_desc = [parts[1].strip()] if parts[1].strip() else []
            elif current_arg:
                current_arg_desc.append(line)
        else:
            main_desc.append(line)

    if current_arg:
        param_descs[current_arg] = " ".join(current_arg_desc)

    return " ".join(main_desc), param_descs


# ------------------------------------------------------------------
# FunctionTool -- wraps any callable
# ------------------------------------------------------------------

class FunctionTool(Tool):
    """A Tool backed by a plain Python function.

    Automatically generates JSON Schema from inspect.signature and
    docstring parsing. Handles both `str` (JSON) and `dict` input.
    """

    def __init__(self, func: Callable, cacheable: bool = False):
        self._func = func
        self.signature = inspect.signature(func)

        doc_desc, param_descs = _parse_docstring(func.__doc__)

        properties = {}
        required = []

        for param_name, param in self.signature.parameters.items():
            if param_name in ("self", "cls", "kwargs", "args"):
                continue

            annotation = param.annotation

            # Detect Optional[X] and unwrap
            if annotation != inspect.Parameter.empty and _is_optional(annotation):
                inner_type = _unwrap_optional(annotation)
                param_schema = _type_to_schema(inner_type)
                param_schema["nullable"] = True
            elif annotation != inspect.Parameter.empty:
                param_schema = _type_to_schema(annotation)
            else:
                param_schema = {"type": "string"}

            if param_name in param_descs:
                param_schema["description"] = param_descs[param_name]

            properties[param_name] = param_schema

            # Only require params with no default AND not Optional
            if param.default == inspect.Parameter.empty and not (
                annotation != inspect.Parameter.empty and _is_optional(annotation)
            ):
                required.append(param_name)

        super().__init__(
            name=func.__name__,
            description=doc_desc or f"Executes the {func.__name__} function.",
            parameters={
                "type": "object",
                "properties": properties,
                **({"required": required} if required else {}),
            },
            cacheable=cacheable,
        )

    def run(self, input_data=None) -> str:
        """Execute the wrapped function.

        Args:
            input_data: A JSON string OR a dict of keyword arguments.
                        If None/{}/empty, calls the function with no args.
        """
        # --- Parse input_data into kwargs ---
        if isinstance(input_data, dict):
            kwargs = input_data  # Already parsed (e.g. from Gemini)
        elif isinstance(input_data, str) and input_data.strip():
            try:
                kwargs = json.loads(input_data)
            except json.JSONDecodeError:
                kwargs = {}
        else:
            kwargs = {}

        # --- Validate required params ---
        required = self.parameters.get("required", [])
        missing = [r for r in required if r not in kwargs]
        if missing:
            return f"Error: tool '{self.name}' missing required params: {missing}"

        # --- Execute ---
        try:
            result = self._func(**kwargs)
            return str(result)
        except TypeError as e:
            # Catch argument mismatch errors with a helpful message
            return f"Error: tool '{self.name}' argument error: {e}"
        except Exception as e:
            return f"Error executing tool '{self.name}': {e}"


    def __call__(self, *args, **kwargs):
        """Allow calling the tool directly as a function."""
        return self._func(*args, **kwargs)


# ------------------------------------------------------------------
# Public decorator
# ------------------------------------------------------------------

def tool(func: Callable = None, *, cacheable: bool = False) -> FunctionTool:
    """Decorator that converts a function into an OrionAI Tool.

    Usage:
        @tool
        def my_func(x: str) -> str: ...

        @tool(cacheable=True)
        def deterministic_func(x: int) -> str: ...
    """
    if func is not None:
        # @tool  (no parentheses)
        return FunctionTool(func)

    # @tool(cacheable=True)  (with parentheses)
    def wrapper(fn: Callable) -> FunctionTool:
        return FunctionTool(fn, cacheable=cacheable)
    return wrapper
