"""HTTP API calling tool built on httpx."""

from __future__ import annotations

from typing import Any

import httpx

from agentforge.tools.base import Tool, ToolResult

_ALLOWED_METHODS = frozenset({"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"})
_MAX_BODY_BYTES = 512 * 1024  # 512 KiB cap on returned body


class APICallerTool(Tool):
    """Make arbitrary HTTP requests and return the response."""

    @property
    def name(self) -> str:
        return "api_caller"

    @property
    def description(self) -> str:
        return "Send an HTTP request and return the status code, headers, and body."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The request URL.",
                },
                "method": {
                    "type": "string",
                    "enum": sorted(_ALLOWED_METHODS),
                    "description": "HTTP method.",
                    "default": "GET",
                },
                "headers": {
                    "type": "object",
                    "description": "Optional request headers.",
                    "additionalProperties": {"type": "string"},
                },
                "body": {
                    "type": "object",
                    "description": "Optional JSON request body (for POST/PUT/PATCH).",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Request timeout in seconds.",
                    "default": 30,
                },
            },
            "required": ["url"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        url: str = kwargs["url"]
        method: str = kwargs.get("method", "GET").upper()
        headers: dict[str, str] = kwargs.get("headers") or {}
        body: dict[str, Any] | None = kwargs.get("body")
        timeout: int = kwargs.get("timeout", 30)

        if method not in _ALLOWED_METHODS:
            return ToolResult(
                success=False,
                output="",
                error=f"Unsupported HTTP method: {method}",
            )

        try:
            async with httpx.AsyncClient(
                timeout=float(timeout),
                follow_redirects=True,
            ) as client:
                request_kwargs: dict[str, Any] = {
                    "method": method,
                    "url": url,
                    "headers": headers,
                }
                if body is not None and method in {"POST", "PUT", "PATCH"}:
                    request_kwargs["json"] = body

                resp = await client.request(**request_kwargs)

            body_text = resp.text[:_MAX_BODY_BYTES]
            resp_headers = dict(resp.headers)

            return ToolResult(
                success=True,
                output=body_text,
                metadata={
                    "status_code": resp.status_code,
                    "headers": resp_headers,
                    "url": str(resp.url),
                },
            )
        except httpx.HTTPStatusError as exc:
            return ToolResult(
                success=False,
                output=exc.response.text[:_MAX_BODY_BYTES],
                error=f"HTTP {exc.response.status_code}: {exc.response.reason_phrase}",
                metadata={"status_code": exc.response.status_code},
            )
        except httpx.RequestError as exc:
            return ToolResult(
                success=False,
                output="",
                error=f"Request failed: {exc}",
            )
