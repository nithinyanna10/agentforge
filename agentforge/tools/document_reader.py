"""Document reader — extract text from PDF, DOCX, CSV, Markdown, and plain text files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentforge.tools.base import Tool, ToolResult

_DEFAULT_MAX_CHARS = 10_000


class DocumentReaderTool(Tool):
    """Read and extract text from documents (PDF, DOCX, CSV, TXT, MD)."""

    def __init__(self, base_directory: str | Path) -> None:
        self._base = Path(base_directory).resolve()
        if not self._base.is_dir():
            raise ValueError(f"Base directory does not exist: {self._base}")

    @property
    def name(self) -> str:
        return "document_reader"

    @property
    def description(self) -> str:
        return (
            "Read and extract text from documents (PDF, DOCX, CSV, TXT, MD). "
            "Supports chunking for large files. Sandboxed to a base directory."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path (required)."},
                "format": {
                    "type": "string",
                    "enum": ["auto", "pdf", "docx", "csv", "txt", "markdown"],
                    "description": "Format; 'auto' detects from extension.",
                },
                "max_chars": {"type": "integer", "description": "Max chars to return.", "default": 10000},
                "page": {"type": "integer", "description": "For PDF: specific page number (1-based)."},
                "sheet": {"type": "string", "description": "For CSV: sheet/section name."},
            },
            "required": ["path"],
        }

    def _safe_resolve(self, rel_path: str) -> Path | None:
        try:
            target = (self._base / rel_path).resolve()
        except (ValueError, OSError):
            return None
        if not str(target).startswith(str(self._base)):
            return None
        return target

    def _detect_format(self, path: Path) -> str:
        ext = path.suffix.lower()
        if ext == ".pdf":
            return "pdf"
        if ext in (".docx", ".doc"):
            return "docx"
        if ext == ".csv":
            return "csv"
        if ext in (".md", ".markdown"):
            return "markdown"
        return "txt"

    async def execute(self, **kwargs: Any) -> ToolResult:
        path = self._safe_resolve(kwargs.get("path", ""))
        if path is None:
            return ToolResult(success=False, output="", error="Path resolves outside base directory.")
        if not path.is_file():
            return ToolResult(success=False, output="", error=f"Not a file: {path.name}")
        fmt = (kwargs.get("format") or "auto").lower()
        if fmt == "auto":
            fmt = self._detect_format(path)
        max_chars = min(max(int(kwargs.get("max_chars", _DEFAULT_MAX_CHARS)), 100), 100_000)
        try:
            if fmt == "txt":
                out = await self._read_txt(path, max_chars)
            elif fmt == "csv":
                out = await self._read_csv(path, max_chars)
            elif fmt == "markdown":
                out = await self._read_txt(path, max_chars)
            elif fmt == "pdf":
                out = await self._read_pdf(path, max_chars, kwargs.get("page"))
            elif fmt == "docx":
                out = await self._read_docx(path, max_chars)
            else:
                out = await self._read_txt(path, max_chars)
            return ToolResult(success=True, output=out[:max_chars], metadata={"path": str(path.relative_to(self._base)), "format": fmt})
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _read_txt(self, path: Path, max_chars: int) -> str:
        return path.read_text(encoding="utf-8", errors="replace")[:max_chars]

    async def _read_csv(self, path: Path, max_chars: int) -> str:
        import csv
        rows: list[list[str]] = []
        with path.open(encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                rows.append(row)
                if sum(len(c) for c in row) + len(rows) * 2 > max_chars:
                    break
        lines = ["\t".join(r) for r in rows]
        return "\n".join(lines)[:max_chars]

    async def _read_pdf(self, path: Path, max_chars: int, page: int | None) -> str:
        try:
            from pypdf import PdfReader
        except ImportError:
            return f"[PDF: install pypdf to extract text from {path.name}]"
        reader = PdfReader(str(path))
        if page is not None and 1 <= page <= len(reader.pages):
            text = reader.pages[page - 1].extract_text() or ""
        else:
            text = ""
            for p in reader.pages:
                text += (p.extract_text() or "") + "\n"
                if len(text) >= max_chars:
                    break
        return text[:max_chars]

    async def _read_docx(self, path: Path, max_chars: int) -> str:
        try:
            from docx import Document
        except ImportError:
            return f"[DOCX: install python-docx to extract text from {path.name}]"
        doc = Document(str(path))
        parts = []
        for para in doc.paragraphs:
            parts.append(para.text)
            if sum(len(p) for p in parts) >= max_chars:
                break
        return "\n".join(parts)[:max_chars]
