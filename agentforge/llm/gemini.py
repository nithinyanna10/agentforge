"""Google Gemini LLM provider (Gemini 1.5 Pro/Flash via REST API)."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from agentforge.llm.base import (
    BaseLLMProvider,
    LLMResponse,
    Message,
    Role,
    TokenUsage,
    ToolCall,
)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider via REST generateContent / streamGenerateContent."""

    def __init__(
        self,
        model: str = "gemini-1.5-pro",
        *,
        api_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model, **kwargs)
        self._api_key = api_key or __import__("os").environ.get("GOOGLE_API_KEY", "")

    def _url(self, stream: bool = False) -> str:
        path = "streamGenerateContent" if stream else "generateContent"
        return f"{GEMINI_BASE}/models/{self.model}:{path}"

    def _to_gemini_contents(self, messages: list[Message]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for msg in messages:
            if msg.role == Role.SYSTEM:
                continue
            role = "user" if msg.role in (Role.USER, Role.SYSTEM) else "model"
            if msg.role == Role.TOOL:
                role = "user"
                part = {"functionResponse": {"name": "tool", "response": {"result": msg.content or ""}}}
            else:
                part = {"text": msg.content or ""}
            out.append({"role": role, "parts": [part]})
        return out

    def _system_instruction(self, messages: list[Message]) -> str:
        for m in messages:
            if m.role == Role.SYSTEM and m.content:
                return m.content
        return ""

    def _build_body(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None,
        temperature: float | None,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        contents = self._to_gemini_contents(messages)
        system_instruction = self._system_instruction(messages)
        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature if temperature is not None else self.default_temperature,
                "maxOutputTokens": max_tokens or self.default_max_tokens,
            },
        }
        if system_instruction:
            body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        if tools:
            body["tools"] = [{"functionDeclarations": [self._gemini_declaration(t) for t in tools]}]
        return body

    def _gemini_declaration(self, tool: dict[str, Any]) -> dict[str, Any]:
        fn = tool.get("function", tool) if "function" in tool else tool
        if isinstance(fn, dict):
            name = fn.get("name", "")
            desc = fn.get("description", "")
            params = fn.get("parameters", fn.get("input_schema", {}))
        else:
            name = getattr(fn, "name", "")
            desc = getattr(fn, "description", "")
            params = getattr(fn, "parameters", {})
        return {"name": name, "description": desc, "parameters": params}

    def format_tools(self, tools: Any) -> list[dict[str, Any]]:
        from agentforge.tools.base import Tool
        result = []
        for t in tools:
            if isinstance(t, Tool):
                result.append({"name": t.name, "description": t.description, "parameters": t.parameters})
            else:
                result.append(t)
        return result

    @retry(
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
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
        body = self._build_body(messages, tools, temperature, max_tokens)
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                self._url(stream=False),
                params={"key": self._api_key},
                json=body,
            )
            r.raise_for_status()
            data = r.json()
        candidate = (data.get("candidates") or [{}])[0]
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        text = ""
        tool_calls: list[ToolCall] = []
        for p in parts:
            if "text" in p:
                text += p["text"]
            if "functionCall" in p:
                fc = p["functionCall"]
                tool_calls.append(ToolCall(
                    id=fc.get("name", "") + "_" + __import__("uuid").uuid4().hex[:8],
                    function_name=fc.get("name", ""),
                    arguments=dict(fc.get("args", {})),
                ))
        usage_meta = data.get("usageMetadata", {})
        usage = TokenUsage(
            prompt_tokens=int(usage_meta.get("promptTokenCount", 0)),
            completion_tokens=int(usage_meta.get("candidatesTokenCount", usage_meta.get("completionTokenCount", 0))),
            total_tokens=int(usage_meta.get("totalTokenCount", 0)),
        )
        return LLMResponse(
            content=text,
            tool_calls=tool_calls,
            usage=usage,
            model=self.model,
            finish_reason=candidate.get("finishReason", "STOP"),
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        body = self._build_body(messages, tools, temperature, max_tokens)
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                self._url(stream=True),
                params={"key": self._api_key, "alt": "sse"},
                json=body,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:].strip()
                        if chunk == "[DONE]" or not chunk:
                            continue
                        try:
                            data = json.loads(chunk)
                            for c in data.get("candidates", []):
                                for p in c.get("content", {}).get("parts", []):
                                    if "text" in p:
                                        yield p["text"]
                        except json.JSONDecodeError:
                            pass
