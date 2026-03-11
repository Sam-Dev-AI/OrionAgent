"""HandoffTool for OrionAI.

Enables agents to trigger stateful or stateless handoffs via standard
tool calling, making multi-agent coordination natural for the LLM.
"""

from typing import Any, Dict, Optional
from orionagent.tools import tool
from orionagent.agents.handoff import AgentHandoff

@tool
def trigger_handoff(
    target_agent: str,
    task: str,
    brief: str,
    state_json: Optional[str] = None
) -> str:
    """Request that the task be handed off to another specialized agent.

    Args:
        target_agent: Name of the agent to hand off to (e.g. 'writer', 'coder').
        task:         The specific instruction for the next agent.
        brief:        A concise summary of what has been done so far.
        state_json:   Optional JSON string of structured data to pass along.
    """
    import json
    state = {}
    if state_json:
        try:
            state = json.loads(state_json)
        except:
            pass
            
    # We return the AgentHandoff object directly. 
    # The Manager's orchestration loop will detect this return type.
    return AgentHandoff(
        target_agent=target_agent,
        task=task,
        brief=brief,
        state=state
    )
