"""Date/time and timezone utilities — no external APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any

from agentforge.tools.base import Tool, ToolResult


class DateTimeTool(Tool):
    """Get current date/time, format dates, or convert timezones."""

    @property
    def name(self) -> str:
        return "datetime"

    @property
    def description(self) -> str:
        return (
            "Get current date and time, format a timestamp, or convert between timezones. "
            "Use for 'what time is it', 'current date', or 'convert 3pm EST to UTC'."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["now", "format", "convert"],
                    "description": "now = current time in a timezone; format = format an ISO timestamp; convert = convert between timezones.",
                },
                "timezone": {
                    "type": "string",
                    "description": "IANA timezone (e.g. America/New_York, UTC). Used for 'now' and 'convert'.",
                },
                "timestamp": {
                    "type": "string",
                    "description": "ISO format timestamp for 'format' or 'convert'.",
                },
                "format_string": {
                    "type": "string",
                    "description": "strftime format for 'format' (e.g. '%Y-%m-%d %H:%M').",
                },
                "to_timezone": {
                    "type": "string",
                    "description": "Target IANA timezone for 'convert'.",
                },
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = (kwargs.get("action") or "now").strip().lower()

        try:
            if action == "now":
                tz_name = (kwargs.get("timezone") or "UTC").strip()
                tz = ZoneInfo(tz_name) if tz_name else timezone.utc
                now = datetime.now(tz)
                return ToolResult(
                    success=True,
                    output=now.isoformat(),
                    metadata={"timezone": str(tz), "iso": now.isoformat()},
                )
            if action == "format":
                ts_str = kwargs.get("timestamp") or ""
                fmt = kwargs.get("format_string") or "%Y-%m-%d %H:%M:%S %Z"
                if not ts_str:
                    return ToolResult(success=False, output="", error="'timestamp' required for format")
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                return ToolResult(
                    success=True,
                    output=dt.strftime(fmt),
                    metadata={"format": fmt},
                )
            if action == "convert":
                ts_str = kwargs.get("timestamp") or ""
                to_tz_name = (kwargs.get("to_timezone") or "UTC").strip()
                if not ts_str:
                    return ToolResult(success=False, output="", error="'timestamp' and 'to_timezone' required for convert")
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                to_tz = ZoneInfo(to_tz_name)
                converted = dt.astimezone(to_tz)
                return ToolResult(
                    success=True,
                    output=converted.isoformat(),
                    metadata={"to_timezone": to_tz_name},
                )
            return ToolResult(success=False, output="", error=f"Unknown action: {action}")
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc))
