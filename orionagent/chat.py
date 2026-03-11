"""OrionAI chat() -- one-line interactive loop for Agent or Manager.

Usage:

    from orionagent import Agent, Manager, chat
    from orionagent.models import Gemini

    # Single agent chat:
    agent = Agent(name="bot", role="assistant", model=Gemini(...))
    chat(agent)

    # Multi-agent chat:
    manager = Manager(model=llm, agents=[...])
    chat(manager)
"""

from typing import Union, Optional


def chat(
    target: Union["Agent", "Manager"],
    greeting: str = None,
    session_id: Optional[str] = None,
    priority: Optional[str] = None,
) -> None:
    """Start an interactive chat loop with an Agent or Manager.

    Args:
        target:   An Agent or Manager instance. Both support `.ask(task, stream=True)`.
        greeting: Optional greeting to display at startup.
        session_id: Optional session ID.
        priority: Optional session priority ('low', 'normal', 'high').
    """
    name = getattr(target, "name", "OrionAI")

    if greeting:
        print(greeting)
    else:
        print(f"\n--- {name} Chat ---")
        print("Type 'exit' or 'quit' to stop.\n")

    # Check if target has a model with print_session_tokens (for token reporting)
    llm = getattr(target, "_model", None) or getattr(target, "model", None)

    while True:
        try:
            task = input("You: ").strip()
            if not task:
                continue
            if task.lower() in ("exit", "quit"):
                print("Goodbye!")
                break

            print(f"\n{name}:", end=" ")
            for chunk in target.ask(task, stream=True, session_id=session_id, priority=priority):
                print(chunk, end="", flush=True)
            print("\n")

            # Print session tokens if the model supports it AND token counting is enabled
            if llm and hasattr(llm, "print_session_tokens") and getattr(llm, "token_count", False):
                llm.print_session_tokens()
                llm.reset_tokens()

        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")
