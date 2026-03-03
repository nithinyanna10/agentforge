"""Tests for the tool subsystem: ToolRegistry, schemas, and concrete tools."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentforge.tools.base import Tool, ToolResult, ToolRegistry
from agentforge.tools.code_executor import CodeExecutorTool
from agentforge.tools.file_ops import FileOpsTool
from agentforge.tools.api_caller import APICallerTool

from .conftest import MockTool


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------

def test_tool_registry_register_and_get():
    reg = ToolRegistry()
    tool = MockTool(tool_name="search")

    reg.register(tool)

    assert reg.has("search")
    assert reg.get("search") is tool
    assert len(reg.list_tools()) == 1


def test_tool_registry_get_missing():
    reg = ToolRegistry()

    with pytest.raises(KeyError, match="not registered"):
        reg.get("absent")


def test_tool_registry_duplicate_raises():
    reg = ToolRegistry()
    reg.register(MockTool(tool_name="dup"))

    with pytest.raises(ValueError, match="already registered"):
        reg.register(MockTool(tool_name="dup"))


# ---------------------------------------------------------------------------
# Schema generation
# ---------------------------------------------------------------------------

def test_tool_openai_schema():
    tool = MockTool(tool_name="calc", tool_description="Calculate stuff")

    schema = tool.to_openai_schema()

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "calc"
    assert schema["function"]["description"] == "Calculate stuff"
    assert "properties" in schema["function"]["parameters"]


def test_tool_anthropic_schema():
    tool = MockTool(tool_name="calc", tool_description="Calculate stuff")

    schema = tool.to_anthropic_schema()

    assert schema["name"] == "calc"
    assert schema["description"] == "Calculate stuff"
    assert "properties" in schema["input_schema"]


# ---------------------------------------------------------------------------
# CodeExecutorTool
# ---------------------------------------------------------------------------

async def test_code_executor_success():
    executor = CodeExecutorTool()

    result = await executor.execute(code='print("hello from test")', timeout=10)

    assert result.success is True
    assert "hello from test" in result.output


async def test_code_executor_timeout():
    executor = CodeExecutorTool()

    result = await executor.execute(code="import time; time.sleep(60)", timeout=1)

    assert result.success is False
    assert "timed out" in (result.error or "").lower()


# ---------------------------------------------------------------------------
# FileOpsTool
# ---------------------------------------------------------------------------

async def test_file_ops_read_write(tmp_path):
    tool = FileOpsTool(base_directory=tmp_path)

    write_result = await tool.execute(
        operation="write_file",
        path="greet.txt",
        content="Hello, AgentForge!",
    )
    assert write_result.success is True

    read_result = await tool.execute(operation="read_file", path="greet.txt")
    assert read_result.success is True
    assert read_result.output == "Hello, AgentForge!"


async def test_file_ops_list_directory(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")

    tool = FileOpsTool(base_directory=tmp_path)
    result = await tool.execute(operation="list_directory", path="")

    assert result.success is True
    assert "a.txt" in result.output
    assert "b.txt" in result.output


async def test_file_ops_path_traversal(tmp_path):
    tool = FileOpsTool(base_directory=tmp_path)

    result = await tool.execute(operation="read_file", path="../../etc/passwd")

    assert result.success is False
    assert "outside" in (result.error or "").lower() or "not a file" in (result.error or "").lower()


# ---------------------------------------------------------------------------
# APICallerTool (mocked httpx)
# ---------------------------------------------------------------------------

async def test_api_caller_get():
    tool = APICallerTool()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '{"status": "ok"}'
    mock_response.headers = {"content-type": "application/json"}
    mock_response.url = "https://api.example.com/health"

    mock_client_instance = AsyncMock()
    mock_client_instance.request.return_value = mock_response
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    with patch("agentforge.tools.api_caller.httpx.AsyncClient", return_value=mock_client_instance):
        result = await tool.execute(url="https://api.example.com/health", method="GET")

    assert result.success is True
    assert "ok" in result.output
    assert result.metadata["status_code"] == 200


async def test_api_caller_request_error():
    tool = APICallerTool()

    import httpx

    mock_client_instance = AsyncMock()
    mock_client_instance.request.side_effect = httpx.ConnectError("connection refused")
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)

    with patch("agentforge.tools.api_caller.httpx.AsyncClient", return_value=mock_client_instance):
        result = await tool.execute(url="https://unreachable.local/api")

    assert result.success is False
    assert "Request failed" in (result.error or "")
