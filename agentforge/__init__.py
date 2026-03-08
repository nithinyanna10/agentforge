"""AgentForge - Multi-agent orchestration framework for AI-powered automation pipelines."""

from agentforge.core.agent import Agent, AgentConfig, AgentResult
from agentforge.core.orchestrator import Orchestrator
from agentforge.core.pipeline import Pipeline, PipelineStep
from agentforge.core.run_store import RunStore, StoredRun
from agentforge.core.cache import (
    BaseCache,
    InMemoryCache,
    DiskCache,
    CacheMiddleware,
    make_cache_key,
    CacheKey,
    CacheEntry,
)
from agentforge.core.rate_limiter import RateLimiter, RateLimitConfig, RateLimitedProvider
from agentforge.core.evaluator import Evaluator, EvalResult, EvalCriterion, EvalScore
from agentforge.core.planner import Planner, TaskPlan, SubTask, PlanExecutionResult
from agentforge.core.supervisor import Supervisor, SupervisorConfig, SupervisorResult
from agentforge.core.reflection import ReflectionAgent, ReflectionConfig, ReflectionResult
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
from agentforge.observability import get_tracer, get_metrics

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
    GitHubTool,
    DocumentReaderTool,
    ImageGenTool,
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
    GitHubTool,
    DocumentReaderTool,
    ImageGenTool,
):
    register_tool(_tool_cls)
discover_plugins()

__version__ = "0.3.0"
__all__ = [
    "Agent",
    "AgentConfig",
    "AgentResult",
    "Orchestrator",
    "Pipeline",
    "PipelineStep",
    "RunStore",
    "StoredRun",
    "BaseCache",
    "InMemoryCache",
    "DiskCache",
    "CacheMiddleware",
    "make_cache_key",
    "CacheKey",
    "CacheEntry",
    "RateLimiter",
    "RateLimitConfig",
    "RateLimitedProvider",
    "Evaluator",
    "EvalResult",
    "EvalCriterion",
    "EvalScore",
    "Planner",
    "TaskPlan",
    "SubTask",
    "PlanExecutionResult",
    "Supervisor",
    "SupervisorConfig",
    "SupervisorResult",
    "ReflectionAgent",
    "ReflectionConfig",
    "ReflectionResult",
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
    "get_tracer",
    "get_metrics",
    "__version__",
]
