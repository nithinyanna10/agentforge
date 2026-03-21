"""XML parsing and simple path extraction (ElementTree-based)."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from typing import Any
from xml.etree.ElementTree import Element

from agentforge.tools.base import Tool, ToolResult


class XmlTool(Tool):
    """Parse XML safely and query with simple slash paths or list tag names."""

    @property
    def name(self) -> str:
        return "xml_tool"

    @property
    def description(self) -> str:
        return (
            "Parse XML text to a summary tree, evaluate a simple path like /root/item/name, "
            "list elements by tag, or extract attributes."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["parse_summary", "path", "findall", "attribute"],
                    "description": (
                        "parse_summary: structure outline; path: first match text; "
                        "findall: all matching tags; attribute: read attr from path."
                    ),
                },
                "xml_text": {"type": "string", "description": "Well-formed XML string."},
                "path": {
                    "type": "string",
                    "description": "Absolute path from root, e.g. /feed/entry/title (leading slash optional).",
                },
                "tag_name": {
                    "type": "string",
                    "description": "For findall: local tag name (e.g. item).",
                },
                "attribute_name": {
                    "type": "string",
                    "description": "For attribute action.",
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Max depth for parse_summary (default 8).",
                },
            },
            "required": ["action", "xml_text"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = (kwargs.get("action") or "parse_summary").strip().lower()
        xml_text = kwargs.get("xml_text") or ""

        if not xml_text.strip():
            return ToolResult(success=False, output="", error="xml_text is empty.")

        try:
            root = ET.fromstring(xml_text.encode("utf-8"))
        except ET.ParseError as e:
            return ToolResult(success=False, output="", error=f"XML parse error: {e}")

        if action == "parse_summary":
            depth = int(kwargs.get("max_depth") or 8)
            summary = self._summarize(root, max_depth=depth)
            out = json.dumps(summary, indent=2)
            return ToolResult(success=True, output=out, metadata={"root_tag": root.tag})

        if action == "path":
            path = (kwargs.get("path") or "").strip()
            if not path:
                return ToolResult(success=False, output="", error="path is required.")
            node = self._find_by_path(root, path)
            if node is None:
                return ToolResult(success=False, output="", error="No element at path.")
            text = (node.text or "").strip()
            return ToolResult(
                success=True,
                output=text or "",
                metadata={"tag": node.tag, "attrib": dict(node.attrib)},
            )

        if action == "findall":
            tag = (kwargs.get("tag_name") or "").strip()
            if not tag:
                return ToolResult(success=False, output="", error="tag_name is required.")
            matches = [el for el in root.iter() if self._local_name(el.tag) == tag]
            texts = []
            for el in matches[:500]:
                t = "".join(el.itertext()).strip()
                texts.append(t[:2000])
            out = json.dumps({"count": len(matches), "texts": texts}, indent=2)
            return ToolResult(success=True, output=out, metadata={"match_count": len(matches)})

        if action == "attribute":
            path = (kwargs.get("path") or "").strip()
            attr = (kwargs.get("attribute_name") or "").strip()
            if not path or not attr:
                return ToolResult(success=False, output="", error="path and attribute_name required.")
            node = self._find_by_path(root, path)
            if node is None:
                return ToolResult(success=False, output="", error="No element at path.")
            val = node.attrib.get(attr)
            if val is None:
                return ToolResult(success=False, output="", error=f"Attribute '{attr}' not found.")
            return ToolResult(success=True, output=val)

        return ToolResult(success=False, output="", error=f"Unknown action: {action}")

    def _local_name(self, tag: str) -> str:
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    def _summarize(self, el: Element, *, max_depth: int, _depth: int = 0) -> dict[str, Any]:
        name = self._local_name(el.tag)
        if _depth >= max_depth:
            return {"tag": name, "truncated": True}
        children = list(el)
        child_tags: dict[str, int] = {}
        for c in children:
            ln = self._local_name(c.tag)
            child_tags[ln] = child_tags.get(ln, 0) + 1
        text_preview = (el.text or "").strip()
        if len(text_preview) > 120:
            text_preview = text_preview[:117] + "..."
        return {
            "tag": name,
            "text_preview": text_preview or None,
            "attributes": dict(el.attrib) if el.attrib else {},
            "child_tag_counts": child_tags,
            "children": [self._summarize(c, max_depth=max_depth, _depth=_depth + 1) for c in children[:50]],
        }

    def _find_by_path(self, root: Element, path: str) -> Element | None:
        path = path.strip()
        if path.startswith("/"):
            path = path[1:]
        segments = [s for s in path.split("/") if s]
        if not segments:
            return root
        current: Element | None = root
        if self._local_name(root.tag) != segments[0]:
            # Allow path to omit synthetic root wrapper
            pass
        idx = 0
        if current is not None and self._local_name(current.tag) == segments[0]:
            idx = 1
        else:
            idx = 0
        while idx < len(segments) and current is not None:
            part = segments[idx]
            m = re.match(r"^([^\[]+)(?:\[(\d+)\])?$", part)
            if not m:
                return None
            name, pos = m.group(1), m.group(2)
            matches = [c for c in list(current) if self._local_name(c.tag) == name]
            if not matches:
                return None
            if pos is not None:
                n = int(pos)
                current = matches[n] if n < len(matches) else None
            else:
                current = matches[0]
            idx += 1
        return current
