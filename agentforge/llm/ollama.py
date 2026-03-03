"""Ollama LLM provider for local models via the Ollama HTTP API."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from agentforge.llm.base import (
    BaseLLMProvider,
    LLMResponse,
    Message,
    TokenUsage,
    ToolCall,
)

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:11434"
_DEFAULT_TIMEOUT = 120.0


class OllamaProvider(BaseLLMProvider):
    """Talks to a local Ollama instance over its REST API."""

    def __init__(
        self,
        model: str = "llama3",
        *,
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = _DEFAULT_TIMEOUT,
        **kwargs: Any,
    ) -> None:
        super().__init__(model, **kwargs)
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=timeout)

    async def close(self) -> None:
        await self._client.aclose()

    # -- internal helpers -----------------------------------------------------

    @staticmethod
    def _to_ollama_messages(messages: list[Message]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for msg in messages:
            entry: dict[str, Any] = {"role": msg.role.value, "content": msg.content or ""}
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "function": {
                            "name": tc.function_name,
                            "arguments": tc.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]
            out.append(entry)
        return out

    @staticmethod
    def _parse_tool_calls(raw_calls: list[dict[str, Any]] | None) -> list[ToolCall]:
        if not raw_calls:
            return []
        parsed: list[ToolCall] = []
        for tc in raw_calls:
            func = tc.get("function", {})
            args = func.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            parsed.append(
                ToolCall(
                    id=tc.get("id", ""),
                    function_name=func.get("name", ""),
                    arguments=args,
                )
            )
        return parsed

    # -- public interface -----------------------------------------------------

    async def complete(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Send a chat request to Ollama's ``/api/chat`` endpoint."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._to_ollama_messages(messages),
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else self.default_temperature,
            },
        }
        if max_tokens or self.default_max_tokens:
            payload["options"]["num_predict"] = max_tokens or self.default_max_tokens
        if tools:
            payload["tools"] = tools

        try:
            resp = await self._client.post("/api/chat", json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("Ollama HTTP error %s: %s", exc.response.status_code, exc.response.text)
            raise
        except httpx.RequestError as exc:
            logger.error("Ollama request error: %s", exc)
            raise

        data = resp.json()
        msg = data.get("message", {})

        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)

        return LLMResponse(
            content=msg.get("content", ""),
            tool_calls=self._parse_tool_calls(msg.get("tool_calls")),
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
            model=data.get("model", self.model),
            finish_reason=data.get("done_reason", "stop") if data.get("done") else "length",
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream text chunks from Ollama's ``/api/chat`` endpoint."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._to_ollama_messages(messages),
            "stream": True,
            "options": {
                "temperature": temperature if temperature is not None else self.default_temperature,
            },
        }
        if max_tokens or self.default_max_tokens:
            payload["options"]["num_predict"] = max_tokens or self.default_max_tokens
        if tools:
            payload["tools"] = tools

        try:
            async with self._client.stream("POST", "/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
                    if chunk.get("done"):
                        break
        except httpx.HTTPStatusError as exc:
            logger.error("Ollama streaming HTTP error %s: %s", exc.response.status_code, exc.response.text)
            raise
        except httpx.RequestError as exc:
            logger.error("Ollama streaming request error: %s", exc)
            raise
