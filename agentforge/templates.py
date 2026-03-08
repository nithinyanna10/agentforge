"""Pre-built agent templates with role-appropriate prompts and tools."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from agentforge.core.agent import Agent, AgentConfig
from agentforge.tools.api_caller import APICallerTool
from agentforge.tools.code_executor import CodeExecutorTool
from agentforge.tools.file_ops import FileOpsTool
from agentforge.tools.web_search import WebSearchTool
from agentforge.tools.math_expression import MathExpressionTool
from agentforge.tools.datetime_tool import DateTimeTool

if TYPE_CHECKING:
    from agentforge.llm.base import BaseLLMProvider


def create_researcher(
    llm: BaseLLMProvider,
    name: str = "researcher",
    model: str | None = None,
) -> Agent:
    """Create an agent optimized for research: web search + API calls + date/math."""
    config = AgentConfig(
        name=name,
        role="researcher",
        system_prompt=(
            "You are a thorough researcher. Use web search and APIs to find accurate, "
            "up-to-date information. Cite sources when possible. Use datetime and math "
            "tools when dates or calculations are needed."
        ),
        model=model or getattr(llm, "model", "gpt-4o"),
        temperature=0.3,
        max_tokens=4096,
        max_react_steps=12,
    )
    tools = [
        WebSearchTool(),
        APICallerTool(),
        DateTimeTool(),
        MathExpressionTool(),
    ]
    return Agent(config=config, llm=llm, tools=tools)


def create_coder(
    llm: BaseLLMProvider,
    name: str = "coder",
    base_directory: str | Path | None = None,
    model: str | None = None,
) -> Agent:
    """Create an agent optimized for code: file ops + code execution + math."""
    config = AgentConfig(
        name=name,
        role="coder",
        system_prompt=(
            "You are an expert programmer. You can read and write files and execute code. "
            "Prefer small, correct steps. Use file_ops to navigate and edit files, "
            "code_executor to run Python when needed, and math_expression for calculations."
        ),
        model=model or getattr(llm, "model", "gpt-4o"),
        temperature=0.2,
        max_tokens=4096,
        max_react_steps=15,
    )
    tools = [
        CodeExecutorTool(),
        MathExpressionTool(),
    ]
    if base_directory is not None:
        base = Path(base_directory).resolve()
        if base.is_dir():
            tools.insert(0, FileOpsTool(base))
    return Agent(config=config, llm=llm, tools=tools)


def create_writer(
    llm: BaseLLMProvider,
    name: str = "writer",
    base_directory: str | Path | None = None,
    model: str | None = None,
) -> Agent:
    """Create an agent optimized for writing: file ops + web search for fact-checking."""
    config = AgentConfig(
        name=name,
        role="writer",
        system_prompt=(
            "You are a clear, engaging writer. You can read and write files. "
            "Use web_search to fact-check when needed. Structure your output with "
            "headings and lists when appropriate."
        ),
        model=model or getattr(llm, "model", "gpt-4o"),
        temperature=0.6,
        max_tokens=4096,
        max_react_steps=10,
    )
    tools = [WebSearchTool()]
    if base_directory is not None:
        base = Path(base_directory).resolve()
        if base.is_dir():
            tools.append(FileOpsTool(base))
    return Agent(config=config, llm=llm, tools=tools)


def create_general(
    llm: BaseLLMProvider,
    name: str = "assistant",
    model: str | None = None,
) -> Agent:
    """Create a general-purpose agent with common tools."""
    config = AgentConfig(
        name=name,
        role="general",
        system_prompt=(
            "You are a helpful AI assistant. You have access to web search, "
            "date/time, and math tools. Use them when they would help the user."
        ),
        model=model or getattr(llm, "model", "gpt-4o"),
        temperature=0.7,
        max_tokens=4096,
        max_react_steps=10,
    )
    tools = [
        WebSearchTool(),
        DateTimeTool(),
        MathExpressionTool(),
    ]
    return Agent(config=config, llm=llm, tools=tools)
