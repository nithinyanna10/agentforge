"""
Sanitization utilities for AgentForge (next-level).

Safe truncation, redaction of secrets, and string cleaning for logs and tool outputs.
"""

from __future__ import annotations

import re
from typing import Any


def truncate(text: str, max_length: int = 500, suffix: str = "…") -> str:
    """Truncate a string to max_length, appending suffix if truncated."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def redact_secrets(text: str, replacement: str = "***") -> str:
    """Replace common secret-like patterns with a placeholder."""
    patterns = [
        (re.compile(r"\b(?:api[_-]?key|apikey)\s*[:=]\s*['\"]?[\w-]+", re.I), f"api_key={replacement}"),
        (re.compile(r"\b(?:password|passwd|pwd)\s*[:=]\s*['\"]?[^\s'\"]+", re.I), f"password={replacement}"),
        (re.compile(r"\b(?:token|secret)\s*[:=]\s*['\"]?[\w.-]+", re.I), f"token={replacement}"),
        (re.compile(r"sk-[a-zA-Z0-9]{20,}", re.I), "sk-***"),
        (re.compile(r"qg_[a-zA-Z0-9]+", re.I), "qg_***"),
    ]
    out = text
    for pat, repl in patterns:
        out = pat.sub(repl, out)
    return out


def sanitize_for_log(obj: Any, max_str: int = 200) -> Any:
    """Recursively sanitize an object for safe logging (truncate strings, redact)."""
    if isinstance(obj, str):
        return redact_secrets(truncate(obj, max_str))
    if isinstance(obj, dict):
        return {k: sanitize_for_log(v, max_str) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_for_log(x, max_str) for x in obj]
    return obj
