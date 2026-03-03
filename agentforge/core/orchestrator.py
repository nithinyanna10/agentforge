"""Orchestrator — manages multiple agents and routes tasks between them."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, Field

from agentforge.core.agent import Agent, AgentResult
from agentforge.core.pipeline import Pipeline
from agentforge.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class OrchestratorResult(BaseModel):
    """Aggregated result from an orchestrated multi-agent run."""

    results: dict[str, AgentResult] = Field(default_factory=dict)
    execution_order: list[str] = Field(default_factory=list)
    merged_answer: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class Orchestrator:
    """Central coordinator that owns a registry of agents and can dispatch
    tasks in sequential, parallel, or pipelined fashion.
    """

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    # -- registration --------------------------------------------------------

    def register(self, agent: Agent) -> None:
        """Register an agent under its name."""
        if agent.name in self._agents:
            logger.warning("Overwriting existing agent %r", agent.name)
        self._agents[agent.name] = agent
        logger.info("Registered agent %r (role=%s)", agent.name, agent.role)

    def get_agent(self, name: str) -> Agent:
        """Retrieve a registered agent by name or raise ``KeyError``."""
        return self._agents[name]

    @property
    def agents(self) -> dict[str, Agent]:
        return dict(self._agents)

    # -- routing -------------------------------------------------------------

    def select_agent(self, task: str, role: str | None = None) -> Agent:
        """Pick the best agent for *task*.

        If *role* is provided, the first agent whose role matches is returned.
        Otherwise a simple keyword-overlap heuristic is used.
        """
        if role:
            for agent in self._agents.values():
                if agent.role == role:
                    return agent
            raise KeyError(f"No agent with role={role!r}")

        task_words = set(task.lower().split())
        scored: list[tuple[int, Agent]] = []
        for agent in self._agents.values():
            overlap = len(task_words & set(agent.role.lower().split()))
            scored.append((overlap, agent))
        scored.sort(key=lambda x: x[0], reverse=True)

        if not scored:
            raise RuntimeError("No agents registered")
        return scored[0][1]

    # -- execution modes -----------------------------------------------------

    async def run_single(self, agent_name: str, task: str) -> AgentResult:
        """Run a named agent on a single task."""
        agent = self.get_agent(agent_name)
        logger.info("Running agent %r on task: %s", agent_name, task[:80])
        return await agent.run(task)

    async def run_sequential(
        self,
        agent_names: list[str],
        task: str,
        *,
        chain: bool = False,
    ) -> OrchestratorResult:
        """Run agents one after another.

        If *chain* is ``True`` each agent receives the previous agent's answer
        appended to the original task, enabling agent-to-agent communication.
        """
        results: dict[str, AgentResult] = {}
        order: list[str] = []
        current_input = task

        for name in agent_names:
            agent = self.get_agent(name)
            result = await agent.run(current_input)
            results[name] = result
            order.append(name)

            if chain and result.answer:
                current_input = f"{task}\n\nContext from {name}:\n{result.answer}"

        merged = results[order[-1]].answer if order else ""
        return OrchestratorResult(
            results=results,
            execution_order=order,
            merged_answer=merged,
        )

    async def run_parallel(
        self,
        agent_names: list[str],
        task: str,
    ) -> OrchestratorResult:
        """Run multiple agents concurrently on the same task."""
        async def _run(name: str) -> tuple[str, AgentResult]:
            agent = self.get_agent(name)
            return name, await agent.run(task)

        pairs = await asyncio.gather(*[_run(n) for n in agent_names])
        results = dict(pairs)
        answers = [r.answer for _, r in pairs if r.answer]
        merged = "\n\n---\n\n".join(answers)

        return OrchestratorResult(
            results=results,
            execution_order=agent_names,
            merged_answer=merged,
        )

    # -- pipeline execution --------------------------------------------------

    async def run_pipeline(self, pipeline: Pipeline, initial_inputs: dict[str, Any] | None = None) -> OrchestratorResult:
        """Execute a ``Pipeline`` DAG, resolving dependencies in topological order."""
        context: dict[str, Any] = dict(initial_inputs or {})
        results: dict[str, AgentResult] = {}
        order: list[str] = []

        for layer in pipeline.resolve():
            coros = []
            layer_names: list[str] = []

            for step in layer:
                if step.condition and not step.condition(context):
                    logger.info("Skipping step %r (condition not met)", step.name)
                    continue

                task_input = self._map_inputs(step.input_map, context)
                agent = self.get_agent(step.agent_name)
                coros.append(agent.run(task_input))
                layer_names.append(step.name)

            layer_results = await asyncio.gather(*coros)

            for name, result in zip(layer_names, layer_results):
                results[name] = result
                context[name] = result.answer
                order.append(name)
                logger.info("Step %r complete (%0.2fs)", name, result.duration_seconds)

        merged = results[order[-1]].answer if order else ""
        return OrchestratorResult(
            results=results,
            execution_order=order,
            merged_answer=merged,
        )

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _map_inputs(input_map: dict[str, str], context: dict[str, Any]) -> str:
        """Build a task string by resolving ``input_map`` references against *context*."""
        if not input_map:
            return context.get("__task__", "")

        parts: list[str] = []
        for key, source in input_map.items():
            value = context.get(source, "")
            parts.append(f"{key}: {value}")
        return "\n".join(parts)

    def __repr__(self) -> str:
        return f"Orchestrator(agents={list(self._agents.keys())})"
