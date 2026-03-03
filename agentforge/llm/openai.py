"""OpenAI LLM provider with function-calling and streaming support."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from openai import AsyncOpenAI, APIError, APITimeoutError, RateLimitError
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
    TokenUsage,
    ToolCall,
)

logger = logging.getLogger(__name__)

_RETRYABLE = (APITimeoutError, RateLimitError)


class OpenAIProvider(BaseLLMProvider):
    """Wraps the OpenAI async chat-completions API."""

    def __init__(self, model: str = "gpt-4o", *, api_key: str | None = None, **kwargs: Any) -> None:
        super().__init__(model, **kwargs)
        self._client = AsyncOpenAI(api_key=api_key, **{k: v for k, v in kwargs.items() if k not in ("temperature", "max_tokens")})

    # -- internal helpers -----------------------------------------------------

    @staticmethod
    def _to_openai_messages(messages: list[Message]) -> list[dict[str, Any]]:
        """Map internal ``Message`` objects to the OpenAI wire format."""
        out: list[dict[str, Any]] = []
        for msg in messages:
            entry: dict[str, Any] = {"role": msg.role.value, "content": msg.content or ""}
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function_name,
                            "arguments": json.dumps(tc.arguments),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            if msg.tool_call_id:
                entry["tool_call_id"] = msg.tool_call_id
            out.append(entry)
        return out

    @staticmethod
    def _parse_tool_calls(raw_calls: list[Any] | None) -> list[ToolCall]:
        if not raw_calls:
            return []
        parsed: list[ToolCall] = []
        for tc in raw_calls:
            try:
                args = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, AttributeError):
                args = {}
            parsed.append(ToolCall(id=tc.id, function_name=tc.function.name, arguments=args))
        return parsed

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
        """Send a chat-completion request to OpenAI."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": self._to_openai_messages(messages),
            "temperature": temperature if temperature is not None else self.default_temperature,
            "max_tokens": max_tokens or self.default_max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            resp = await self._client.chat.completions.create(**kwargs)
        except APIError as exc:
            logger.error("OpenAI API error: %s", exc)
            raise

        choice = resp.choices[0]
        usage = resp.usage

        return LLMResponse(
            content=choice.message.content or "",
            tool_calls=self._parse_tool_calls(choice.message.tool_calls),
            usage=TokenUsage(
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                total_tokens=usage.total_tokens if usage else 0,
            ),
            model=resp.model,
            finish_reason=choice.finish_reason or "",
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream text chunks from an OpenAI completion."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": self._to_openai_messages(messages),
            "temperature": temperature if temperature is not None else self.default_temperature,
            "max_tokens": max_tokens or self.default_max_tokens,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = await self._client.chat.completions.create(**kwargs)
            async for chunk in response:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
        except APIError as exc:
            logger.error("OpenAI streaming error: %s", exc)
            raise
