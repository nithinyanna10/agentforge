"""CSV / TSV parsing, statistics, and column projection tool."""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from typing import Any

from agentforge.tools.base import Tool, ToolResult


class CsvTool(Tool):
    """Parse delimited text, infer delimiter, compute stats, or emit JSON rows."""

    @property
    def name(self) -> str:
        return "csv_tool"

    @property
    def description(self) -> str:
        return (
            "Parse CSV/TSV text: return rows as JSON, column statistics, or projected columns. "
            "Delimiter auto-detected from comma, tab, semicolon, or pipe when not specified."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["parse", "stats", "to_json", "select_columns"],
                    "description": (
                        "parse: first N rows preview; stats: per-column counts/types; "
                        "to_json: all rows as JSON array; select_columns: keep listed columns."
                    ),
                },
                "text": {"type": "string", "description": "Raw delimited text."},
                "delimiter": {
                    "type": "string",
                    "description": "Single character delimiter, or empty for auto-detect.",
                },
                "has_header": {
                    "type": "boolean",
                    "description": "First row is header (default true).",
                },
                "max_rows": {
                    "type": "integer",
                    "description": "For parse action: max rows to return (default 50).",
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "For select_columns: header names to keep.",
                },
            },
            "required": ["action", "text"],
        }

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = (kwargs.get("action") or "parse").strip().lower()
        text = kwargs.get("text") or ""
        delim_raw = kwargs.get("delimiter")
        has_header = bool(kwargs.get("has_header", True))
        max_rows = int(kwargs.get("max_rows") or 50)
        columns_filter = kwargs.get("columns")

        if action not in ("parse", "stats", "to_json", "select_columns"):
            return ToolResult(success=False, output="", error=f"Unknown action: {action}")

        if not text.strip():
            return ToolResult(success=False, output="", error="text is empty.")

        delimiter = self._resolve_delimiter(delim_raw, text)
        reader, headers = self._read_rows(text, delimiter, has_header)

        if action == "parse":
            rows = []
            for i, row in enumerate(reader):
                if i >= max(1, max_rows):
                    break
                rows.append(row)
            out = json.dumps(
                {"delimiter": delimiter, "headers": headers, "rows": rows, "preview_count": len(rows)},
                indent=2,
            )
            return ToolResult(success=True, output=out, metadata={"delimiter": delimiter})

        if action == "to_json":
            all_rows: list[dict[str, str]] = []
            for row in reader:
                if headers:
                    all_rows.append({h: row[i] if i < len(row) else "" for i, h in enumerate(headers)})
                else:
                    all_rows.append({str(i): v for i, v in enumerate(row)})
            out = json.dumps(all_rows, indent=2)
            return ToolResult(
                success=True,
                output=out,
                metadata={"row_count": len(all_rows)},
            )

        if action == "stats":
            return self._stats(reader, headers)

        if action == "select_columns":
            if not isinstance(columns_filter, list) or not columns_filter:
                return ToolResult(
                    success=False,
                    output="",
                    error="columns must be a non-empty list of header names.",
                )
            if not headers:
                return ToolResult(success=False, output="", error="has_header must be true for select_columns.")
            idx_map = {}
            for name in columns_filter:
                if name not in headers:
                    return ToolResult(success=False, output="", error=f"Unknown column: {name}")
                idx_map[name] = headers.index(name)
            projected: list[dict[str, str]] = []
            for row in reader:
                projected.append({name: row[idx_map[name]] if idx_map[name] < len(row) else "" for name in columns_filter})
            out = json.dumps(projected, indent=2)
            return ToolResult(success=True, output=out, metadata={"row_count": len(projected)})

        return ToolResult(success=False, output="", error="unreachable")

    def _resolve_delimiter(self, delim_raw: Any, text: str) -> str:
        if isinstance(delim_raw, str) and len(delim_raw) == 1:
            return delim_raw
        sample = text[:4096]
        scores: dict[str, int] = {",": 0, "\t": 0, ";": 0, "|": 0}
        for d in scores:
            scores[d] = sample.count(d)
        best = max(scores, key=scores.get)
        if scores[best] == 0:
            return ","
        return best

    def _read_rows(
        self,
        text: str,
        delimiter: str,
        has_header: bool,
    ) -> tuple[csv.reader, list[str] | None]:
        stream = io.StringIO(text)
        reader = csv.reader(stream, delimiter=delimiter)
        rows_iter = iter(reader)
        headers: list[str] | None = None
        if has_header:
            try:
                first = next(rows_iter)
            except StopIteration:
                empty = csv.reader(io.StringIO(""))
                return empty, []
            headers = [h.strip() for h in first]

            def gen() -> Any:
                for row in rows_iter:
                    yield row

            return gen(), headers
        return reader, None

    def _stats(self, reader: Any, headers: list[str] | None) -> ToolResult:
        col_values: dict[str, list[str]] = {}
        row_count = 0
        if headers:
            for h in headers:
                col_values[h] = []
            for row in reader:
                row_count += 1
                for i, h in enumerate(headers):
                    col_values[h].append(row[i] if i < len(row) else "")
        else:
            for row in reader:
                row_count += 1
                for i, cell in enumerate(row):
                    key = f"col_{i}"
                    col_values.setdefault(key, []).append(cell)

        summary: dict[str, Any] = {"row_count": row_count, "columns": {}}
        for name, vals in col_values.items():
            non_empty = [v for v in vals if v.strip()]
            types = Counter(self._guess_type(v) for v in non_empty)
            summary["columns"][name] = {
                "non_empty_count": len(non_empty),
                "empty_count": len(vals) - len(non_empty),
                "unique_approx": len(set(non_empty)),
                "inferred_types": dict(types),
                "sample": non_empty[:5],
            }
        return ToolResult(success=True, output=json.dumps(summary, indent=2), metadata={"row_count": row_count})

    def _guess_type(self, value: str) -> str:
        s = value.strip()
        if not s:
            return "empty"
        try:
            int(s)
            return "integer"
        except ValueError:
            pass
        try:
            float(s)
            return "float"
        except ValueError:
            pass
        if s.lower() in ("true", "false", "yes", "no"):
            return "boolean_like"
        return "string"
