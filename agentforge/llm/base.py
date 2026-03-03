"""Abstract base class and shared models for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from agentforge.tools.base import Tool


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolCall(BaseModel):
    """A single tool/function invocation requested by the model."""

    id: str
    function_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Message(BaseModel):
    """Chat message exchanged with an LLM provider."""

    role: Role
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


class TokenUsage(BaseModel):
    """Token consumption for a single LLM call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMResponse(BaseModel):
    """Normalised response returned by every provider."""

    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: TokenUsage = Field(default_factory=TokenUsage)
    model: str = ""
    finish_reason: str = ""


class BaseLLMProvider(ABC):
    """Provider-agnostic interface that every LLM backend must implement."""

    def __init__(self, model: str, **kwargs: Any) -> None:
        self.model = model
        self.default_temperature: float = kwargs.get("temperature", 0.7)
        self.default_max_tokens: int = kwargs.get("max_tokens", 4096)

    @abstractmethod
    async def complete(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Send a chat-completion request and return the full response."""

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """Yield text chunks as the model generates them."""

    def format_tools(self, tools: list[Tool]) -> list[dict[str, Any]]:
        """Convert framework ``Tool`` objects into the provider's wire format.

        Subclasses should override this when the provider uses a non-OpenAI
        schema for tool definitions.  The default implementation produces the
        OpenAI function-calling format.
        """
        formatted: list[dict[str, Any]] = []
        for tool in tools:
            formatted.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                    },
                }
            )
        return formatted
