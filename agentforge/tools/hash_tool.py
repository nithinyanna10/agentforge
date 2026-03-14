"""Hash and encoding utilities tool — checksums and base64 (next-level)."""

from __future__ import annotations

import base64
import hashlib
from typing import Any

from agentforge.tools.base import Tool, ToolResult


class HashTool(Tool):
    """Compute hash (MD5, SHA1, SHA256) or Base64 encode/decode text."""

    @property
    def name(self) -> str:
        return "hash"

    @property
    def description(self) -> str:
        return "Compute hash (md5, sha1, sha256) of text or file content, or base64 encode/decode text."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["hash", "base64_encode", "base64_decode"],
                    "description": "Action to perform.",
                },
                "text": {"type": "string", "description": "Input text (for hash or encode/decode)."},
                "algorithm": {
                    "type": "string",
                    "enum": ["md5", "sha1", "sha256"],
                    "description": "Hash algorithm (for action hash).",
                    "default": "sha256",
                },
            },
            "required": ["action", "text"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = (kwargs.get("action") or "").strip().lower()
        text = kwargs.get("text") or ""
        algorithm = (kwargs.get("algorithm") or "sha256").strip().lower()

        if action == "hash":
            try:
                if algorithm == "md5":
                    h = hashlib.md5(text.encode("utf-8")).hexdigest()
                elif algorithm == "sha1":
                    h = hashlib.sha1(text.encode("utf-8")).hexdigest()
                elif algorithm == "sha256":
                    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
                else:
                    return ToolResult(success=False, output="", error=f"Unknown algorithm: {algorithm}")
                return ToolResult(success=True, output=h, metadata={"algorithm": algorithm})
            except Exception as e:
                return ToolResult(success=False, output="", error=str(e))
        elif action == "base64_encode":
            try:
                out = base64.b64encode(text.encode("utf-8")).decode("ascii")
                return ToolResult(success=True, output=out, metadata={"action": "encode"})
            except Exception as e:
                return ToolResult(success=False, output="", error=str(e))
        elif action == "base64_decode":
            try:
                out = base64.b64decode(text.encode("ascii")).decode("utf-8")
                return ToolResult(success=True, output=out, metadata={"action": "decode"})
            except Exception as e:
                return ToolResult(success=False, output="", error=str(e))
        else:
            return ToolResult(success=False, output="", error=f"Unknown action: {action}")
