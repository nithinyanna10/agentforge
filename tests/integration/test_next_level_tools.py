"""
Integration tests for next-level tools: summarize, fetch_url, json_path, regex, env.
"""

from __future__ import annotations

import os
import pytest

from agentforge.tools.summarize import SummarizeTool
from agentforge.tools.fetch_url import FetchURLTool
from agentforge.tools.json_path import JSONPathTool
from agentforge.tools.regex_tool import RegexTool
from agentforge.tools.env_tool import EnvTool


@pytest.fixture
def summarize_tool() -> SummarizeTool:
    return SummarizeTool()


@pytest.fixture
def json_path_tool() -> JSONPathTool:
    return JSONPathTool()


@pytest.fixture
def regex_tool() -> RegexTool:
    return RegexTool()


@pytest.fixture
def env_tool() -> EnvTool:
    return EnvTool()


class TestSummarizeTool:
    """Tests for SummarizeTool."""

    @pytest.mark.asyncio
    async def test_summarize_head(self, summarize_tool: SummarizeTool) -> None:
        text = "Hello world. This is a test. " * 50
        result = await summarize_tool.execute(text=text, strategy="head", max_chars=50)
        assert result.success is True
        assert len(result.output) <= 51  # 50 + possible ellipsis
        assert "Hello" in result.output

    @pytest.mark.asyncio
    async def test_summarize_tail(self, summarize_tool: SummarizeTool) -> None:
        text = "Start. " + "Middle. " * 20 + "End."
        result = await summarize_tool.execute(text=text, strategy="tail", max_chars=20)
        assert result.success is True
        assert "End" in result.output or "…" in result.output

    @pytest.mark.asyncio
    async def test_summarize_sentences(self, summarize_tool: SummarizeTool) -> None:
        text = "First sentence. Second sentence. Third sentence. Fourth. Fifth."
        result = await summarize_tool.execute(text=text, strategy="sentences", max_sentences=2)
        assert result.success is True
        assert "First" in result.output and "Second" in result.output

    @pytest.mark.asyncio
    async def test_summarize_empty_text(self, summarize_tool: SummarizeTool) -> None:
        result = await summarize_tool.execute(text="", strategy="head")
        assert result.success is False
        assert "No text" in (result.error or "")

    @pytest.mark.asyncio
    async def test_summarize_unknown_strategy(self, summarize_tool: SummarizeTool) -> None:
        result = await summarize_tool.execute(text="Hi", strategy="invalid")
        assert result.success is False
        assert "strategy" in (result.error or "").lower()


class TestJSONPathTool:
    """Tests for JSONPathTool."""

    @pytest.mark.asyncio
    async def test_json_path_simple(self, json_path_tool: JSONPathTool) -> None:
        data = '{"name": "Alice", "age": 30}'
        result = await json_path_tool.execute(json_text=data, path="$.name")
        assert result.success is True
        assert "Alice" in result.output

    @pytest.mark.asyncio
    async def test_json_path_nested(self, json_path_tool: JSONPathTool) -> None:
        data = '{"user": {"profile": {"display_name": "Bob"}}}'
        result = await json_path_tool.execute(json_text=data, path="$.user.profile.display_name")
        assert result.success is True
        assert "Bob" in result.output

    @pytest.mark.asyncio
    async def test_json_path_invalid_json(self, json_path_tool: JSONPathTool) -> None:
        result = await json_path_tool.execute(json_text="not json", path="$.x")
        assert result.success is False
        assert "JSON" in (result.error or "")

    @pytest.mark.asyncio
    async def test_json_path_must_start_with_dollar(self, json_path_tool: JSONPathTool) -> None:
        result = await json_path_tool.execute(json_text='{"a":1}', path="a")
        assert result.success is False


class TestRegexTool:
    """Tests for RegexTool."""

    @pytest.mark.asyncio
    async def test_regex_find(self, regex_tool: RegexTool) -> None:
        text = "foo 123 bar 456 baz"
        result = await regex_tool.execute(text=text, pattern=r"\d+", mode="find")
        assert result.success is True
        assert "123" in result.output and "456" in result.output

    @pytest.mark.asyncio
    async def test_regex_replace(self, regex_tool: RegexTool) -> None:
        text = "hello world"
        result = await regex_tool.execute(text=text, pattern=r"world", mode="replace", replacement="there")
        assert result.success is True
        assert result.output == "hello there"

    @pytest.mark.asyncio
    async def test_regex_invalid_pattern(self, regex_tool: RegexTool) -> None:
        result = await regex_tool.execute(text="x", pattern="[invalid", mode="find")
        assert result.success is False


class TestEnvTool:
    """Tests for EnvTool."""

    @pytest.mark.asyncio
    async def test_env_list(self, env_tool: EnvTool) -> None:
        result = await env_tool.execute(action="list")
        assert result.success is True
        # May be empty or have some safe keys
        assert isinstance(result.output, str)

    @pytest.mark.asyncio
    async def test_env_get_missing_key(self, env_tool: EnvTool) -> None:
        result = await env_tool.execute(action="get", key="AGENTFORGE_TEST_NONEXISTENT_XYZ")
        assert result.success is True
        assert "not set" in result.output.lower() or "(not set)" in result.output

    @pytest.mark.asyncio
    async def test_env_get_safe_key(self, env_tool: EnvTool) -> None:
        os.environ["AGENTFORGE_TEST_SAFE"] = "value123"
        try:
            result = await env_tool.execute(action="get", key="AGENTFORGE_TEST_SAFE")
            assert result.success is True
            assert "value123" in result.output
        finally:
            os.environ.pop("AGENTFORGE_TEST_SAFE", None)

    @pytest.mark.asyncio
    async def test_env_get_masked_key_rejected(self, env_tool: EnvTool) -> None:
        result = await env_tool.execute(action="get", key="SECRET_KEY")
        assert result.success is False
        assert "not allowed" in (result.error or "").lower()
