"""AgentForge - Multi-agent orchestration framework for AI-powered automation pipelines."""

from agentforge.core.agent import Agent, AgentConfig, AgentResult
from agentforge.core.orchestrator import Orchestrator
from agentforge.core.pipeline import Pipeline, PipelineStep
from agentforge.core.run_store import RunStore, StoredRun
from agentforge.ext import (
    get_registered_tools,
    get_agent_factory,
    list_agent_factories,
    register_tool,
    register_agent_factory,
    discover_plugins,
)
from agentforge.templates import (
    create_researcher,
    create_coder,
    create_writer,
    create_general,
)

# Register built-in tools so CLI and ext discovery see them
from agentforge.tools import (
    WebSearchTool,
    CodeExecutorTool,
    FileOpsTool,
    APICallerTool,
    SqlQueryTool,
    ShellCommandTool,
    DateTimeTool,
    MathExpressionTool,
)

for _tool_cls in (
    WebSearchTool,
    CodeExecutorTool,
    FileOpsTool,
    APICallerTool,
    SqlQueryTool,
    ShellCommandTool,
    DateTimeTool,
    MathExpressionTool,
):
    register_tool(_tool_cls)
discover_plugins()

__version__ = "0.2.0"
__all__ = [
    "Agent",
    "AgentConfig",
    "AgentResult",
    "Orchestrator",
    "Pipeline",
    "PipelineStep",
    "RunStore",
    "StoredRun",
    "create_researcher",
    "create_coder",
    "create_writer",
    "create_general",
    "get_registered_tools",
    "get_agent_factory",
    "list_agent_factories",
    "register_tool",
    "register_agent_factory",
    "discover_plugins",
    "__version__",
]
