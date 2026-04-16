"""Base Tool class for OrionAI.

Every tool (built-in or user-created) inherits from this.
Provides a consistent interface for the ToolExecutor and LLM providers.
"""


class Tool:
    """Abstract base for all OrionAI tools.

    Attributes:
        name:        Unique identifier used by the LLM to invoke the tool.
        description: Short description sent to the LLM as part of the schema.
        parameters:  JSON Schema dict describing expected arguments.
        cacheable:   If True, the ToolExecutor may cache results for
                     identical (name, args) pairs within a single turn.
    """

    def __init__(
        self,
        name: str = "",
        description: str = "",
        parameters: dict = None,
        cacheable: bool = False,
    ):
        self.name = name
        self.description = description
        # Default to a valid empty object schema for LLM compatibility
        self.parameters = parameters or {
            "type": "object",
            "properties": {}
        }
        self.cacheable = cacheable

    def run(self, input_data) -> str:
        """Execute the tool. Override in subclasses.

        Args:
            input_data: Either a JSON string or a dict of arguments.

        Returns:
            A string result.
        """
        raise NotImplementedError("Tools must implement the run method.")

    def __repr__(self) -> str:
        return f"<Tool: {self.name}>"
