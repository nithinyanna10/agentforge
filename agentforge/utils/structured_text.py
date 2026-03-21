"""Extract structure from plain text, Markdown-like content, and code documentation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CodeFence:
    """A fenced code block (```lang ... ```)."""

    language: str | None
    body: str
    start_line: int
    end_line: int


@dataclass(frozen=True)
class MarkdownHeading:
    """ATX-style heading (# .. ######)."""

    level: int
    text: str
    line_index: int


@dataclass(frozen=True)
class MarkdownLink:
    """Inline [text](url) link."""

    text: str
    url: str
    line_index: int


@dataclass
class OutlineNode:
    """Hierarchical outline from headings."""

    level: int
    title: str
    line_index: int
    children: list[OutlineNode] = field(default_factory=list)


_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def split_paragraphs(text: str, *, blank_lines: int = 2) -> list[str]:
    """Split text on two or more newlines (configurable)."""
    if blank_lines < 1:
        blank_lines = 1
    sep = "\n" * blank_lines
    parts = text.split(sep)
    return [p.strip() for p in parts if p.strip()]


def normalize_whitespace(text: str, *, collapse_lines: bool = False) -> str:
    """Collapse runs of spaces; optionally join broken lines within paragraphs."""
    lines = text.splitlines()
    if not collapse_lines:
        return "\n".join(" ".join(line.split()) for line in lines)
    paras = split_paragraphs(text, blank_lines=2)
    return "\n\n".join(" ".join(p.split()) for p in paras)


def extract_fenced_code_blocks(text: str) -> list[CodeFence]:
    """Parse triple-backtick fences; language is optional on opening line."""
    lines = text.splitlines()
    blocks: list[CodeFence] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^```([\w\+\-\.#]*)\s*$", line)
        if not m:
            i += 1
            continue
        lang = m.group(1).strip() or None
        start = i
        i += 1
        body_lines: list[str] = []
        while i < len(lines):
            if lines[i].strip().startswith("```"):
                break
            body_lines.append(lines[i])
            i += 1
        end = i
        if i < len(lines) and lines[i].strip().startswith("```"):
            i += 1
        blocks.append(
            CodeFence(
                language=lang,
                body="\n".join(body_lines),
                start_line=start + 1,
                end_line=end + 1,
            )
        )
    return blocks


def extract_markdown_headings(text: str) -> list[MarkdownHeading]:
    """Extract ATX headings; line_index is 0-based."""
    out: list[MarkdownHeading] = []
    for idx, line in enumerate(text.splitlines()):
        m = _HEADING_RE.match(line.rstrip())
        if not m:
            continue
        level = len(m.group(1))
        title = m.group(2).strip()
        out.append(MarkdownHeading(level=level, text=title, line_index=idx))
    return out


def extract_markdown_links(text: str) -> list[MarkdownLink]:
    """Find [text](url) links (not reference-style)."""
    out: list[MarkdownLink] = []
    for i, line in enumerate(text.splitlines()):
        for m in _LINK_RE.finditer(line):
            out.append(MarkdownLink(text=m.group(1), url=m.group(2), line_index=i))
    return out


def build_heading_outline(headings: list[MarkdownHeading]) -> list[OutlineNode]:
    """Build a tree from a flat heading list (assumes document order)."""
    if not headings:
        return []
    stack: list[OutlineNode] = []
    roots: list[OutlineNode] = []
    for h in headings:
        node = OutlineNode(level=h.level, title=h.text, line_index=h.line_index)
        while stack and stack[-1].level >= h.level:
            stack.pop()
        if not stack:
            roots.append(node)
        else:
            stack[-1].children.append(node)
        stack.append(node)
    return roots


def outline_to_text(nodes: list[OutlineNode], *, indent: str = "  ") -> str:
    """Render outline as indented text."""
    lines: list[str] = []

    def walk(nlist: list[OutlineNode], depth: int) -> None:
        for n in nlist:
            lines.append(f"{indent * depth}- {n.title} (L{n.line_index + 1})")
            walk(n.children, depth + 1)

    walk(nodes, 0)
    return "\n".join(lines)


def count_words(text: str) -> int:
    """Approximate word count (alphanumeric tokens)."""
    return len(re.findall(r"\b[\w\'\-]+\b", text))


def estimate_reading_minutes(text: str, wpm: int = 220) -> float:
    """Rough reading time in minutes."""
    if wpm <= 0:
        return 0.0
    return round(count_words(text) / wpm, 2)


def extract_bullet_lines(text: str, markers: tuple[str, ...] = ("-", "*", "+")) -> list[str]:
    """Lines that look like bullet list items."""
    out: list[str] = []
    for line in text.splitlines():
        s = line.lstrip()
        for m in markers:
            if s.startswith(m + " ") or s.startswith(m + "\t"):
                out.append(s[len(m) :].strip())
                break
    return out


def extract_numbered_items(text: str) -> list[str]:
    """Lines like '1. item' or '2) item'."""
    out: list[str] = []
    num = re.compile(r"^\s*(\d+)[.)]\s+(.+)$")
    for line in text.splitlines():
        m = num.match(line)
        if m:
            out.append(m.group(2).strip())
    return out


def strip_markdown_inline(text: str) -> str:
    """Remove common inline md: `code`, **bold**, *italic*, [l](u)."""
    s = text
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    return s


def line_index_map(text: str) -> dict[int, str]:
    """Map 1-based line number to line content."""
    return {i + 1: line for i, line in enumerate(text.splitlines())}


def find_line_ranges_for_substrings(text: str, needle: str) -> list[tuple[int, int]]:
    """Return (start_line, end_line) 1-based for each occurrence of needle (line span)."""
    if not needle:
        return []
    lines = text.splitlines()
    joined = "\n".join(lines)
    out: list[tuple[int, int]] = []
    start = 0
    while True:
        idx = joined.find(needle, start)
        if idx < 0:
            break
        before = joined[:idx]
        start_line = before.count("\n") + 1
        span_lines = needle.count("\n")
        end_line = start_line + span_lines
        out.append((start_line, end_line))
        start = idx + 1
    return out


def truncate_with_ellipsis(text: str, max_chars: int, suffix: str = "…") -> str:
    """Truncate to max_chars, accounting for suffix length."""
    if max_chars <= 0:
        return suffix
    if len(text) <= max_chars:
        return text
    take = max(0, max_chars - len(suffix))
    return text[:take] + suffix


def slugify_title(title: str, max_length: int = 80) -> str:
    """ASCII-ish slug for anchors."""
    s = title.lower().strip()
    s = re.sub(r"[^a-z0-9\s\-]", "", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:max_length] if max_length else s


def merge_adjacent_code_fences(blocks: list[CodeFence], *, same_language_only: bool = True) -> list[CodeFence]:
    """Optionally merge consecutive fences (same language) — returns copy."""
    if not blocks:
        return []
    merged: list[CodeFence] = [blocks[0]]
    for b in blocks[1:]:
        prev = merged[-1]
        if (
            same_language_only
            and b.language == prev.language
            and b.start_line == prev.end_line + 1
        ):
            merged[-1] = CodeFence(
                language=prev.language,
                body=prev.body + "\n" + b.body,
                start_line=prev.start_line,
                end_line=b.end_line,
            )
        else:
            merged.append(b)
    return merged


def text_stats(text: str) -> dict[str, Any]:
    """Aggregate statistics for arbitrary text."""
    lines = text.splitlines()
    nonempty = [ln for ln in lines if ln.strip()]
    return {
        "char_count": len(text),
        "line_count": len(lines),
        "non_empty_line_count": len(nonempty),
        "word_count": count_words(text),
        "paragraph_count": len(split_paragraphs(text)),
        "heading_count": len(extract_markdown_headings(text)),
        "link_count": len(extract_markdown_links(text)),
        "code_fence_count": len(extract_fenced_code_blocks(text)),
    }
