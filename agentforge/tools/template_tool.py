"""Jinja2 template rendering tool for dynamic prompts and text generation."""

from __future__ import annotations

import json
from typing import Any

from jinja2 import Environment, StrictUndefined, TemplateError, select_autoescape

from agentforge.tools.base import Tool, ToolResult


class TemplateTool(Tool):
    """Render Jinja2 templates with a JSON context; optionally validate syntax only."""

    def __init__(self) -> None:
        self._env = Environment(
            autoescape=select_autoescape(enabled_extensions=("html", "xml")),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    @property
    def name(self) -> str:
        return "template_render"

    @property
    def description(self) -> str:
        return (
            "Render a Jinja2 template string with a JSON object context, or validate template syntax. "
            "Use for dynamic prompts, emails, and structured text. Context must be JSON."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["render", "validate_syntax"],
                    "description": "render: produce output; validate_syntax: check template only.",
                },
                "template_text": {"type": "string", "description": "Jinja2 template source."},
                "context_json": {
                    "type": "string",
                    "description": "JSON object string used as template context (ignored for validate_syntax).",
                },
            },
            "required": ["action", "template_text"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = (kwargs.get("action") or "render").strip().lower()
        template_text = kwargs.get("template_text") or ""
        context_raw = kwargs.get("context_json")

        if action not in ("render", "validate_syntax"):
            return ToolResult(
                success=False,
                output="",
                error="action must be 'render' or 'validate_syntax'.",
            )

        if not template_text.strip():
            return ToolResult(success=False, output="", error="template_text is empty.")

        if action == "validate_syntax":
            try:
                self._env.parse(template_text)
            except TemplateError as e:
                return ToolResult(success=False, output="", error=f"Template syntax error: {e}")
            return ToolResult(
                success=True,
                output="syntax_ok",
                metadata={"validated": True},
            )

        ctx: dict[str, Any] = {}
        if context_raw:
            if isinstance(context_raw, dict):
                ctx = context_raw
            else:
                try:
                    parsed = json.loads(str(context_raw))
                except json.JSONDecodeError as e:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Invalid context_json: {e}",
                    )
                if not isinstance(parsed, dict):
                    return ToolResult(
                        success=False,
                        output="",
                        error="context_json must decode to a JSON object.",
                    )
                ctx = parsed

        try:
            tmpl = self._env.from_string(template_text)
            rendered = tmpl.render(**ctx)
        except TemplateError as e:
            return ToolResult(success=False, output="", error=f"Template error: {e}")
        except Exception as e:  # pragma: no cover - strict undefined etc.
            return ToolResult(success=False, output="", error=str(e))

        return ToolResult(
            success=True,
            output=rendered,
            metadata={"bytes": len(rendered.encode("utf-8"))},
        )
