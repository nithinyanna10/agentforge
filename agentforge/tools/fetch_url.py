"""Fetch URL tool — retrieve and optionally extract text from a URL."""

from __future__ import annotations

import re
from typing import Any

import httpx

from agentforge.tools.base import Tool, ToolResult


class FetchURLTool(Tool):
    """Fetch content from a URL and return raw body or stripped text."""

    @property
    def name(self) -> str:
        return "fetch_url"

    @property
    def description(self) -> str:
        return "Fetch content from a URL. Returns raw body or, if strip_html is true, text with HTML tags removed."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to fetch (http or https)."},
                "strip_html": {
                    "type": "boolean",
                    "description": "If true, remove HTML tags and normalize whitespace.",
                    "default": True,
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters to return (default 50000).",
                    "default": 50000,
                },
                "timeout_seconds": {
                    "type": "number",
                    "description": "Request timeout in seconds (default 30).",
                    "default": 30,
                },
            },
            "required": ["url"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        url = (kwargs.get("url") or "").strip()
        strip_html = bool(kwargs.get("strip_html", True))
        max_chars = max(100, min(500_000, int(kwargs.get("max_chars", 50000))))
        timeout = max(5.0, min(60.0, float(kwargs.get("timeout_seconds", 30))))

        if not url:
            return ToolResult(success=False, output="", error="No URL provided.")
        if not url.startswith(("http://", "https://")):
            return ToolResult(success=False, output="", error="URL must start with http:// or https://.")

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=timeout,
                headers={"User-Agent": "AgentForge-FetchURL/1.0"},
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                body = resp.text
        except httpx.HTTPStatusError as e:
            return ToolResult(success=False, output="", error=f"HTTP error: {e.response.status_code}")
        except httpx.RequestError as e:
            return ToolResult(success=False, output="", error=f"Request failed: {e}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

        if strip_html:
            body = self._strip_html(body)
        body = body[:max_chars]
        if len(resp.text) > max_chars:
            body += "\n… [truncated]"

        return ToolResult(
            success=True,
            output=body,
            metadata={"url": url, "content_type": resp.headers.get("content-type", ""), "length": len(body)},
        )

    @staticmethod
    def _strip_html(html: str) -> str:
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
