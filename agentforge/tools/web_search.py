"""Web search tool using DuckDuckGo HTML results."""

from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import quote_plus

import httpx

from agentforge.tools.base import Tool, ToolResult

_DDG_URL = "https://html.duckduckgo.com/html/"

_RESULT_PATTERN = re.compile(
    r'<a\s+rel="nofollow"\s+class="result__a"\s+href="(?P<url>[^"]+)"[^>]*>'
    r"(?P<title>.*?)</a>",
    re.DOTALL,
)
_SNIPPET_PATTERN = re.compile(
    r'<a\s+class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
    re.DOTALL,
)


def _strip_tags(text: str) -> str:
    """Remove HTML tags and decode entities."""
    return html.unescape(re.sub(r"<[^>]+>", "", text)).strip()


class WebSearchTool(Tool):
    """Search the web via DuckDuckGo and return formatted results."""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web using DuckDuckGo and return titles, URLs, and snippets."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return.",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        query: str = kwargs["query"]
        num_results: int = kwargs.get("num_results", 5)

        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; AgentForge/1.0)"},
            ) as client:
                resp = await client.post(
                    _DDG_URL,
                    data={"q": query, "b": ""},
                )
                resp.raise_for_status()

            results = self._parse_results(resp.text, num_results)
            if not results:
                return ToolResult(
                    success=True,
                    output="No results found.",
                    metadata={"query": query, "count": 0},
                )

            formatted = self._format_results(results)
            return ToolResult(
                success=True,
                output=formatted,
                metadata={"query": query, "count": len(results)},
            )
        except httpx.HTTPStatusError as exc:
            return ToolResult(
                success=False,
                output="",
                error=f"HTTP {exc.response.status_code}: {exc.response.reason_phrase}",
            )
        except httpx.RequestError as exc:
            return ToolResult(
                success=False,
                output="",
                error=f"Request failed: {exc}",
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_results(
        page_html: str, limit: int
    ) -> list[dict[str, str]]:
        titles_urls = _RESULT_PATTERN.findall(page_html)
        snippets = _SNIPPET_PATTERN.findall(page_html)

        results: list[dict[str, str]] = []
        for i, (url, raw_title) in enumerate(titles_urls[:limit]):
            snippet = _strip_tags(snippets[i]) if i < len(snippets) else ""
            results.append(
                {
                    "title": _strip_tags(raw_title),
                    "url": html.unescape(url),
                    "snippet": snippet,
                }
            )
        return results

    @staticmethod
    def _format_results(results: list[dict[str, str]]) -> str:
        lines: list[str] = []
        for idx, r in enumerate(results, 1):
            lines.append(f"{idx}. {r['title']}")
            lines.append(f"   URL: {r['url']}")
            if r["snippet"]:
                lines.append(f"   {r['snippet']}")
            lines.append("")
        return "\n".join(lines).rstrip()
