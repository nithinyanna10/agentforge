"""Base tool abstraction and registry for AgentForge."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Structured result returned by every tool execution."""

    success: bool
    output: str
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Tool(ABC):
    """Abstract base class that every AgentForge tool must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the tool."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what the tool does."""

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        """JSON Schema describing the tool's accepted parameters."""

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Run the tool with the given parameters and return a result."""

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert this tool to the OpenAI function-calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_anthropic_schema(self) -> dict[str, Any]:
        """Convert this tool to the Anthropic tool-use format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }


class ToolRegistry:
    """Thread-safe registry that maps tool names to :class:`Tool` instances."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool instance, keyed by its ``name``."""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        """Retrieve a registered tool by name.

        Raises:
            KeyError: If no tool with *name* is registered.
        """
        try:
            return self._tools[name]
        except KeyError:
            raise KeyError(f"Tool '{name}' is not registered") from None

    def list_tools(self) -> list[Tool]:
        """Return all registered tools in registration order."""
        return list(self._tools.values())

    def has(self, name: str) -> bool:
        """Return ``True`` if a tool with *name* is registered."""
        return name in self._tools
