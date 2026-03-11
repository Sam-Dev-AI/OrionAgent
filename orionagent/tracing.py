"""TraceManager for OrionAI.

Provides lightweight telemetry for debugging and performance monitoring.
Captures every agent turn, tool call, and decision point into a structured
trace log that can be exported to JSON.
"""

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class TraceEvent:
    event_type: str  # "agent_ask", "tool_call", "plan_step", "handoff"
    name: str
    input_data: Any
    output_data: Any = None
    duration: float = 0.0
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))


class TraceManager:
    """Singleton registry for framework-level telemetry.

    Usage:
        from orionagent.tracing import tracer
        with tracer.trace("agent_ask", "researcher", task):
            ...
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TraceManager, cls).__new__(cls)
            cls._instance.events = []
            cls._instance.active_traces = {}
            cls._instance._last_printed_idx = 0
            cls._instance.debug = False # Global debug flag
        return cls._instance

    def log_event(self, event_type: str, name: str, input_data: Any, 
                  output_data: Any = None, duration: float = 0.0, 
                  metadata: Dict[str, Any] = None, verbose: bool = False,
                  debug: bool = False) -> TraceEvent:
        """Manually log a completed event."""
        event = TraceEvent(
            event_type=event_type,
            name=name,
            input_data=input_data,
            output_data=output_data,
            duration=duration,
            metadata=metadata or {}
        )
        self.events.append(event)
        
        # Real-time debug logging
        if debug or self.debug:
            self._print_debug_tag(event_type, name)
            
        elif verbose:
            DIM = "\033[90m"
            RESET = "\033[0m"
            tag = f"[{event_type.upper()}]"
            print(f"{DIM}{tag:12} {name}{RESET}")
            
        return event

    def start_trace(self, event_type: str, name: str, input_data: Any, 
                    metadata: Dict[str, Any] = None, verbose: bool = False,
                    debug: bool = False) -> str:
        """Start a timed trace and return its ID."""
        trace_id = str(uuid.uuid4())
        self.active_traces[trace_id] = {
            "type": event_type,
            "name": name,
            "input": input_data,
            "start": time.time(),
            "metadata": metadata or {}
        }
        
        # Real-time debug logging
        if debug or self.debug:
            self._print_debug_tag(event_type, name)

        elif verbose:
            DIM = "\033[90m"
            RESET = "\033[0m"
            tag = f"[{event_type.upper()}]"
            print(f"{DIM}{tag:12} {name}{RESET}")
            
        return trace_id

    def end_trace(self, trace_id: str, output_data: Any) -> Optional[TraceEvent]:
        """End a timed trace and log the final event."""
        data = self.active_traces.pop(trace_id, None)
        if not data:
            return None

        duration = time.time() - data["start"]
        return self.log_event(
            event_type=data["type"],
            name=data["name"],
            input_data=data["input"],
            output_data=output_data,
            duration=duration,
            metadata=data["metadata"]
        )

    def _print_debug_tag(self, event_type: str, name: str):
        """Print clean user-facing debug tags."""
        # Map internal types to user tags
        mapping = {
            "plan": "PLAN",
            "tool": "TOOL",
            "guard": "GUARD",
            "memory": "MEMORY",
            "agent_ask": "AGENT",
            "manager_ask": "MANAGER"
        }
        tag_label = mapping.get(event_type, event_type.upper())
        
        # Use simple bold text for debug mode
        print(f"\033[1m[{tag_label}]\033[0m {name}")

    def print_summary(self):
        """Print a human-readable summary of new events since the last print."""
        if not self.events or self._last_printed_idx >= len(self.events):
            return

        DIM = "\033[90m"
        RESET = "\033[0m"

        print(f"\n{DIM}--- TRACE SUMMARY ---")
        for e in self.events[self._last_printed_idx:]:
            dur = f"({e.duration:.2f}s)" if e.duration > 0 else ""
            print(f"{DIM}[{e.event_type.upper()}] {e.name} {dur}")
            
            if isinstance(e.input_data, str):
                inp = e.input_data[:50].replace('\n', ' ') + "..." if len(e.input_data) > 50 else e.input_data.replace('\n', ' ')
                print(f"  In:  {inp}")
            
            if isinstance(e.output_data, str):
                out = e.output_data[:50].replace('\n', ' ') + "..." if len(e.output_data) > 50 else e.output_data.replace('\n', ' ')
                print(f"  Out: {out}")
        
        print(f"---------------------{RESET}")
        self._last_printed_idx = len(self.events)

    def clear(self):
        """Reset the event history."""
        self.events = []
        self.active_traces = {}
        self._last_printed_idx = 0


# Global tracer instance
tracer = TraceManager()
