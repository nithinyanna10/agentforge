"""Base64, hex, and URL encoding/decoding helpers."""

from __future__ import annotations

import base64
import binascii
from typing import Any
from urllib.parse import quote, unquote, quote_plus, unquote_plus

from agentforge.tools.base import Tool, ToolResult


class EncodingTool(Tool):
    """Encode or decode text using common encodings (base64, hex, URL)."""

    @property
    def name(self) -> str:
        return "encoding_tool"

    @property
    def description(self) -> str:
        return (
            "Encode or decode strings: base64, hex, url (standard or plus for query strings). "
            "Input is UTF-8 text unless decoding produces bytes reported as hex for invalid UTF-8."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "base64_encode",
                        "base64_decode",
                        "hex_encode",
                        "hex_decode",
                        "url_encode",
                        "url_decode",
                        "url_encode_plus",
                        "url_decode_plus",
                    ],
                },
                "text": {"type": "string", "description": "Text or encoded payload."},
            },
            "required": ["action", "text"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = (kwargs.get("action") or "").strip().lower()
        text = kwargs.get("text")
        if text is None:
            return ToolResult(success=False, output="", error="text is required.")
        raw = text if isinstance(text, str) else str(text)

        try:
            if action == "base64_encode":
                out = base64.b64encode(raw.encode("utf-8")).decode("ascii")
                return ToolResult(success=True, output=out)
            if action == "base64_decode":
                pad = (-len(raw)) % 4
                padded = raw + ("=" * pad)
                data = base64.b64decode(padded, validate=False)
                try:
                    out = data.decode("utf-8")
                except UnicodeDecodeError:
                    out = data.hex()
                return ToolResult(success=True, output=out, metadata={"utf8": out != data.hex()})
            if action == "hex_encode":
                out = raw.encode("utf-8").hex()
                return ToolResult(success=True, output=out)
            if action == "hex_decode":
                cleaned = "".join(c for c in raw.strip() if c in "0123456789abcdefABCDEF")
                if len(cleaned) % 2 == 1:
                    return ToolResult(success=False, output="", error="hex string must have even length.")
                data = bytes.fromhex(cleaned)
                try:
                    out = data.decode("utf-8")
                except UnicodeDecodeError:
                    out = data.hex()
                return ToolResult(success=True, output=out)
            if action == "url_encode":
                return ToolResult(success=True, output=quote(raw, safe=""))
            if action == "url_decode":
                return ToolResult(success=True, output=unquote(raw))
            if action == "url_encode_plus":
                return ToolResult(success=True, output=quote_plus(raw))
            if action == "url_decode_plus":
                return ToolResult(success=True, output=unquote_plus(raw))
        except (binascii.Error, ValueError) as e:
            return ToolResult(success=False, output="", error=str(e))

        return ToolResult(success=False, output="", error=f"Unknown action: {action}")
