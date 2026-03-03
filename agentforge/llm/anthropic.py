"""Anthropic LLM provider with tool-use and streaming support."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from anthropic import AsyncAnthropic, APIError, APITimeoutError, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from agentforge.llm.base import (
    BaseLLMProvider,
    LLMResponse,
    Message,
    Role,
    TokenUsage,
    ToolCall,
)

if TYPE_CHECKING:
    from agentforge.tools.base import Tool

logger = logging.getLogger(__name__)

_RETRYABLE = (APITimeoutError, RateLimitError)


class AnthropicProvider(BaseLLMProvider):
    """Wraps the Anthropic async messages API."""

    def __init__(self, model: str = "claude-sonnet-4-20250514", *, api_key: str | None = None, **kwargs: Any) -> None:
        super().__init__(model, **kwargs)
        self._client = AsyncAnthropic(api_key=api_key)

    # -- internal helpers -----------------------------------------------------

    @staticmethod
    def _split_system(messages: list[Message]) -> tuple[str | None, list[dict[str, Any]]]:
        """Separate the system prompt (Anthropic takes it as a top-level arg)."""
        system: str | None = None
        chat: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == Role.SYSTEM:
                system = msg.content
                continue

            if msg.role == Role.TOOL and msg.tool_call_id:
                chat.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.tool_call_id,
                                "content": msg.content or "",
                            }
                        ],
                    }
                )
                continue

            entry: dict[str, Any] = {"role": msg.role.value, "content": msg.content or ""}
            if msg.tool_calls:
                entry["content"] = [
                    {"type": "text", "text": msg.content or ""},
                    *[
                        {
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.function_name,
                            "input": tc.arguments,
                        }
                        for tc in msg.tool_calls
                    ],
                ]
            chat.append(entry)
        return system, chat

    @staticmethod
    def _parse_content_blocks(blocks: list[Any]) -> tuple[str, list[ToolCall]]:
        """Extract text and tool_use blocks from an Anthropic response."""
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in blocks:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        function_name=block.name,
                        arguments=block.input if isinstance(block.input, dict) else {},
                    )
                )
        return "\n".join(text_parts), tool_calls

    def format_tools(self, tools: list[Tool]) -> list[dict[str, Any]]:
        """Convert framework tools to Anthropic's tool schema."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
            }
            for tool in tools
        ]

    # -- public interface -----------------------------------------------------

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def complete(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Send a message request to Anthropic."""
        system, chat_messages = self._split_system(messages)
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": chat_messages,
            "temperature": temperature if temperature is not None else self.default_temperature,
            "max_tokens": max_tokens or self.default_max_tokens,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        try:
            resp = await self._client.messages.create(**kwargs)
        except APIError as exc:
            logger.error("Anthropic API error: %s", exc)
            raise

        content, tool_calls = self._parse_content_blocks(resp.content)

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            usage=TokenUsage(
                prompt_tokens=resp.usage.input_tokens,
                completion_tokens=resp.usage.output_tokens,
                total_tokens=resp.usage.input_tokens + resp.usage.output_tokens,
            ),
            model=resp.model,
            finish_reason=resp.stop_reason or "",
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream text deltas from Anthropic."""
        system, chat_messages = self._split_system(messages)
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": chat_messages,
            "temperature": temperature if temperature is not None else self.default_temperature,
            "max_tokens": max_tokens or self.default_max_tokens,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        try:
            async with self._client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield text
        except APIError as exc:
            logger.error("Anthropic streaming error: %s", exc)
            raise
