"""YAML/JSON parse and dump tool (next-level)."""

from __future__ import annotations

import json
from typing import Any

from agentforge.tools.base import Tool, ToolResult

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


class YamlTool(Tool):
    """Parse YAML or JSON string to JSON string, or dump a JSON string to YAML."""

    @property
    def name(self) -> str:
        return "yaml_json"

    @property
    def description(self) -> str:
        return "Parse YAML or JSON text to JSON; or dump JSON string to YAML. Use format: yaml_to_json, json_to_yaml, or parse (auto-detect)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Input YAML or JSON string."},
                "format": {
                    "type": "string",
                    "enum": ["yaml_to_json", "json_to_yaml", "parse"],
                    "description": "Conversion direction or auto-detect.",
                    "default": "parse",
                },
            },
            "required": ["text"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        text = kwargs.get("text") or ""
        fmt = (kwargs.get("format") or "parse").strip().lower()

        if not text.strip():
            return ToolResult(success=False, output="", error="No text provided.")

        try:
            if fmt == "parse":
                stripped = text.strip()
                if stripped.startswith("{"):
                    data = json.loads(text)
                    out = json.dumps(data, indent=2)
                elif _HAS_YAML:
                    data = yaml.safe_load(text)
                    out = json.dumps(data, indent=2)
                else:
                    return ToolResult(success=False, output="", error="PyYAML not installed; use JSON input.")
            elif fmt == "yaml_to_json":
                if not _HAS_YAML:
                    return ToolResult(success=False, output="", error="PyYAML not installed.")
                data = yaml.safe_load(text)
                out = json.dumps(data, indent=2)
            elif fmt == "json_to_yaml":
                if not _HAS_YAML:
                    return ToolResult(success=False, output="", error="PyYAML not installed.")
                data = json.loads(text)
                out = yaml.dump(data, default_flow_style=False, allow_unicode=True)
            else:
                return ToolResult(success=False, output="", error=f"Unknown format: {fmt}.")
            return ToolResult(success=True, output=out, metadata={"format": fmt})
        except json.JSONDecodeError as e:
            return ToolResult(success=False, output="", error=f"JSON error: {e}")
        except Exception as e:
            if _HAS_YAML and type(e).__name__ == "YAMLError":
                return ToolResult(success=False, output="", error=f"YAML error: {e}")
            return ToolResult(success=False, output="", error=str(e))
