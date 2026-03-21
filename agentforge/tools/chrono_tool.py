"""Expose time parsing utilities to agents as a tool."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from agentforge.tools.base import Tool, ToolResult
from agentforge.utils import chrono as chrono_util


class ChronoTool(Tool):
    """Parse relative English time phrases, ISO8601 strings, and business-day helpers."""

    @property
    def name(self) -> str:
        return "chrono_tool"

    @property
    def description(self) -> str:
        return (
            "Time helpers: resolve phrases like 'in 2 hours' or '3 days ago' to UTC ISO; "
            "parse ISO8601; add business days; format human-readable durations."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "relative",
                        "parse_iso",
                        "business_days_add",
                        "human_duration",
                        "merge_intervals",
                    ],
                },
                "phrase": {"type": "string", "description": "For relative: English phrase."},
                "base_iso": {"type": "string", "description": "Optional anchor for relative (ISO8601)."},
                "iso_string": {"type": "string", "description": "For parse_iso."},
                "start_date": {"type": "string", "description": "YYYY-MM-DD for business_days_add."},
                "days": {"type": "integer", "description": "Business days to add (can be negative)."},
                "seconds": {"type": "number", "description": "For human_duration: timedelta seconds."},
                "intervals_json": {
                    "type": "string",
                    "description": "For merge_intervals: JSON array of [start_iso, end_iso] pairs.",
                },
            },
            "required": ["action"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = (kwargs.get("action") or "").strip().lower()

        if action == "relative":
            phrase = kwargs.get("phrase") or ""
            base_iso = kwargs.get("base_iso")
            now = None
            if base_iso:
                try:
                    now = chrono_util.parse_iso8601_utc(str(base_iso))
                except ValueError as e:
                    return ToolResult(success=False, output="", error=f"base_iso: {e}")
            try:
                res = chrono_util.parse_relative_time(str(phrase), now=now)
            except ValueError as e:
                return ToolResult(success=False, output="", error=str(e))
            out = json.dumps(
                {
                    "resolved_iso": chrono_util.format_rfc3339(res.resolved),
                    "delta_seconds": res.delta.total_seconds(),
                    "matched": res.matched,
                },
                indent=2,
            )
            return ToolResult(success=True, output=out)

        if action == "parse_iso":
            s = kwargs.get("iso_string") or ""
            try:
                dt = chrono_util.parse_iso8601_utc(str(s))
            except ValueError as e:
                return ToolResult(success=False, output="", error=str(e))
            return ToolResult(success=True, output=chrono_util.format_rfc3339(dt))

        if action == "business_days_add":
            sd = kwargs.get("start_date") or ""
            days = int(kwargs.get("days") or 0)
            try:
                d = date.fromisoformat(str(sd).strip())
            except ValueError as e:
                return ToolResult(success=False, output="", error=f"start_date: {e}")
            result = chrono_util.business_days_add(d, days)
            return ToolResult(success=True, output=result.isoformat())

        if action == "human_duration":
            sec = float(kwargs.get("seconds") or 0)
            from datetime import timedelta

            text = chrono_util.human_duration(timedelta(seconds=sec))
            return ToolResult(success=True, output=text)

        if action == "merge_intervals":
            raw = kwargs.get("intervals_json") or "[]"
            try:
                pairs = json.loads(raw)
            except json.JSONDecodeError as e:
                return ToolResult(success=False, output="", error=str(e))
            if not isinstance(pairs, list):
                return ToolResult(success=False, output="", error="intervals_json must be a JSON array.")
            intervals: list[tuple[datetime, datetime]] = []
            for item in pairs:
                if not isinstance(item, (list, tuple)) or len(item) != 2:
                    return ToolResult(success=False, output="", error="each interval must be [start, end].")
                a, b = item
                try:
                    da = chrono_util.parse_iso8601_utc(str(a))
                    db = chrono_util.parse_iso8601_utc(str(b))
                except ValueError as e:
                    return ToolResult(success=False, output="", error=str(e))
                intervals.append((da, db))
            merged = chrono_util.merge_intervals(intervals)
            out = json.dumps(
                [[chrono_util.format_rfc3339(s), chrono_util.format_rfc3339(e)] for s, e in merged],
                indent=2,
            )
            return ToolResult(success=True, output=out)

        return ToolResult(success=False, output="", error=f"Unknown action: {action}")
