"""LogicGuard for OrionAI.

Provides deterministic validation for Agent inputs and outputs.
Ensures agents adhere to strict reliability rules and can self-correct
if a guard fails.
"""

import functools
import json
from typing import Any, Callable, Optional, Union, Generator


class LogicGuardError(Exception):
    """Raised when a LogicGuard validation fails."""
    pass


def logic_guard(
    input_validator: Optional[Callable[[str], bool]] = None,
    output_validator: Optional[Callable[[str], bool]] = None,
    error_message: str = "Output did not meet quality requirements.",
    auto_retry: bool = True,
):
    """Decorator to wrap Agent.ask or similar methods with I/O validation.

    Args:
        input_validator:  Fn(task_str) -> bool. If False, raises error before LLM call.
        output_validator: Fn(response_str) -> bool. If False, triggers retry or error.
        error_message:    The message provided to the agent for self-correction.
        auto_retry:        If True, the agent is given one chance to fix the error.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 1. Extract task (usually first arg or in kwargs)
            if "task" in kwargs:
                task = kwargs["task"]
            elif len(args) > 0:
                # If wrapped as a method, args[0] might be self, args[1] is task
                # But if wrapped in __init__ on self.ask, func is ALREADY bound, so args[0] is task.
                task = args[0]
            else:
                raise LogicGuardError("Missing task argument for LogicGuard.")

            # 2. Input Validation
            if input_validator and not input_validator(task):
                raise LogicGuardError(f"Input rejected by LogicGuard: {task}")

            # 3. Primary Execution
            response = func(*args, **kwargs)

            # 4. Output Validation (Skip for generators/streaming for now)
            # LogicGuards strictly apply to full string outputs to ensure reliability.
            is_generator = isinstance(response, (Generator, type((i for i in []))))
            if output_validator and not is_generator:
                from orionagent.tracing import tracer
                # Try to find the agent instance to check for debug flag
                agent_instance = getattr(func, "__self__", None)
                if not agent_instance and args and hasattr(args[0], 'debug'):
                    agent_instance = args[0]
                    
                is_verbose = getattr(agent_instance, "verbose", False)
                is_debug = getattr(agent_instance, "debug", False)
                tracer.log_event("guard", f"Applying output guard", task, verbose=is_verbose, debug=is_debug)
                
                validation_result = output_validator(response)
                
                if isinstance(validation_result, str) or not validation_result:
                    # Determine the specific error message for retry/failure
                    current_error_message = validation_result if isinstance(validation_result, str) else error_message

                    if auto_retry:
                        # Get specific error message if validator is advanced
                        # We'll check if the validator failed with a specific reason
                        # For simple bool validators, we use the default error_message
                        
                        # Attempt self-correction
                        retry_task = f"{task}\n\n[GUARD FAILURE] {current_error_message}\nPlease correct your previous response."
                        
                        # Reconstruct new arguments carefully
                        new_args = list(args)
                        new_kwargs = kwargs.copy()
                        
                        if "task" in kwargs:
                            new_kwargs["task"] = retry_task
                        elif len(args) > 0:
                            # If wrapped as bound method on Agent, args[0] is task
                            new_args[0] = retry_task
                        else:
                            new_kwargs["task"] = retry_task
                            
                        response = func(*new_args, **new_kwargs)
                        
                        # Final check after retry
                        final_validation_result = output_validator(response)
                        if isinstance(final_validation_result, str):
                            raise LogicGuardError(f"LogicGuard failed after retry: {final_validation_result}")
                        elif not final_validation_result:
                            raise LogicGuardError(f"LogicGuard failed after retry: {current_error_message}")
                    else:
                        raise LogicGuardError(f"LogicGuard failed: {current_error_message}")

            return response
        return wrapper
    return decorator


# --- Common Validators ---

def is_json(text: str) -> bool:
    """Validator: Check if text is valid JSON."""
    try:
        cleaned = text.replace("```json", "").replace("```", "").strip()
        json.loads(cleaned)
        return True
    except:
        return False

def is_polite(text: str) -> bool:
    """Validator: Check for common polite phrases."""
    lowered = text.lower()
    polite_phrases = ["please", "thank you", "happy to help", "glad to assist", "sincerely"]
    return any(p in lowered for p in polite_phrases)

def is_short(text: str) -> bool:
    """Validator: Check if response is brief (max 3 sentences)."""
    sentences = [s for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    return len(sentences) <= 3

def is_long(text: str) -> bool:
    """Validator: Check if response is detailed (min 5 sentences)."""
    sentences = [s for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    return len(sentences) >= 5

def is_happy(text: str) -> bool:
    """Validator: Check for positive/enthusiastic tone."""
    lowered = text.lower()
    happy_words = ["happy", "great", "excellent", "amazing", "glad", "wonderful", "delighted", "awesome"]
    return any(w in lowered for w in happy_words)

def is_straight(text: str) -> Union[bool, str]:
    """Validator: Check for direct, no-fluff, no-emoji response.
    Returns True if valid, or a string with the reason for failure.
    """
    import re
    # Strictly no emojis
    emoji_pattern = re.compile(r"[\U00010000-\U0010ffff]", flags=re.UNICODE)
    found_emoji = emoji_pattern.search(text)
    if found_emoji:
        return f"Found emoji: '{found_emoji.group(0)}'. Output must have NO emojis."
        
    # No common LLM fluff/filler
    fluff = [
        "i hope this helps", "let me know if", "as an ai language model", 
        "is there anything else", "happy to assist", "would you like me to",
        "feel free to", "glad to help"
    ]
    lowered = text.lower()
    for f in fluff:
        if f in lowered:
            return f"Found conversational fluff: '{f}'. Output must be direct with no filler."
            
    return True

def contains_keywords(keywords: list):
    """Validator Factory: Check if text contains specific keywords."""
    def validator(text: str) -> bool:
        lowered = text.lower()
        return all(kw.lower() in lowered for kw in keywords)
    return validator


# --- DX Registry ---

GUARD_REGISTRY = {
    "json": (is_json, "Output must be valid JSON."),
    "polite": (is_polite, "Output must be polite and professional."),
    "short": (is_short, "Output must be very brief (max 3 sentences)."),
    "long": (is_long, "Output must be very detailed (min 5 sentences)."),
    "happy": (is_happy, "Output must have a very positive and enthusiastic tone."),
    "straight": (is_straight, "Output must be direct and strictly contain NO emojis and NO conversational fluff."),
}

def apply_guards(func, guard_configs: list):
    """Applies multiple logic guards to a function based on configs."""
    wrapped_func = func
    for config in guard_configs:
        if isinstance(config, str):
            if config in GUARD_REGISTRY:
                validator, msg = GUARD_REGISTRY[config]
                wrapped_func = logic_guard(output_validator=validator, error_message=msg)(wrapped_func)
        elif callable(config):
            wrapped_func = logic_guard(output_validator=config)(wrapped_func)
    return wrapped_func
