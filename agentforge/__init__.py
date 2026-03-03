"""AgentForge - Multi-agent orchestration framework for AI-powered automation pipelines."""

from agentforge.core.agent import Agent
from agentforge.core.orchestrator import Orchestrator
from agentforge.core.pipeline import Pipeline, PipelineStep

__version__ = "0.1.0"
__all__ = ["Agent", "Orchestrator", "Pipeline", "PipelineStep", "__version__"]
