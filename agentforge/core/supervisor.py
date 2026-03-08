"""Supervisor agent — coordinates sub-agents and synthesizes their outputs."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from agentforge.core.agent import Agent
from agentforge.llm.base import BaseLLMProvider, Message, Role
from agentforge.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class SupervisorConfig(BaseModel):
    """Configuration for the supervisor agent."""

    name: str = "supervisor"
    role: str = "supervisor"
    system_prompt: str = (
        "You are a supervisor that delegates tasks to specialized agents "
        "and synthesizes their results into a coherent final answer."
    )
    max_delegations: int = Field(default=5, ge=1, le=20)
    synthesis_model: str = "gpt-4o"


class DelegationRecord(BaseModel):
    """Record of one delegation to a sub-agent."""

    task: str
    delegated_to: str
    result: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SupervisorResult(BaseModel):
    """Result of a supervisor run."""

    task: str
    delegations: list[DelegationRecord] = Field(default_factory=list)
    final_answer: str = ""
    duration_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------


class Supervisor:
    """Coordinates multiple agents and synthesizes their outputs."""

    def __init__(
        self,
        config: SupervisorConfig,
        llm: BaseLLMProvider,
        agents: dict[str, Agent],
    ) -> None:
        self._config = config
        self._llm = llm
        self._agents = dict(agents)

    def add_agent(self, agent: Agent) -> None:
        self._agents[agent.name] = agent

    def remove_agent(self, name: str) -> None:
        self._agents.pop(name, None)

    @property
    def agents(self) -> dict[str, Agent]:
        return dict(self._agents)

    async def _decide_delegations(self, task: str) -> list[dict[str, str]]:
        """LLM call to decide which agents to call with what sub-tasks."""
        agent_list = ", ".join(self._agents.keys())
        prompt = f"""Given this user task, decide which specialized agents to call and with what sub-task. Available agents: {agent_list}.
Return a JSON array of delegations, each with "agent_name" and "sub_task". Maximum {self._config.max_delegations} delegations.

TASK:
{task}

Respond with JSON only (no markdown):
[
  {{ "agent_name": "<name>", "sub_task": "<task for that agent>" }},
  ...
]
"""
        messages = [
            Message(role=Role.SYSTEM, content=self._config.system_prompt),
            Message(role=Role.USER, content=prompt),
        ]
        resp = await self._llm.complete(messages)
        text = (resp.content or "").strip()
        try:
            json_match = re.search(r"\[[\s\S]*\]", text)
            if json_match:
                data = json.loads(json_match.group())
                return [{"agent_name": str(d.get("agent_name", "")), "sub_task": str(d.get("sub_task", ""))} for d in data][: self._config.max_delegations]
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Supervisor delegation parse error: %s", e)
        return []

    async def _synthesize(self, task: str, delegations: list[DelegationRecord]) -> str:
        """Synthesize all delegation results into a final answer."""
        parts = [f"Original task: {task}\n"]
        for i, d in enumerate(delegations, 1):
            parts.append(f"Result from {d.delegated_to}:\n{d.result}\n")
        prompt = "Synthesize the following agent results into one coherent, final answer for the user. Be concise and structured.\n\n" + "\n---\n".join(parts)
        messages = [
            Message(role=Role.SYSTEM, content="You are a synthesizer. Combine the given results into a single clear answer."),
            Message(role=Role.USER, content=prompt),
        ]
        resp = await self._llm.complete(messages)
        return (resp.content or "").strip()

    async def run(self, task: str) -> SupervisorResult:
        """Execute supervisor loop: decide delegations, run agents, synthesize."""
        import time
        start = time.monotonic()
        delegations_list = await self._decide_delegations(task)
        records: list[DelegationRecord] = []
        for d in delegations_list:
            agent_name = d.get("agent_name", "")
            sub_task = d.get("sub_task", "")
            if not agent_name or agent_name not in self._agents:
                continue
            agent = self._agents[agent_name]
            try:
                result = await agent.run(sub_task)
                records.append(DelegationRecord(task=sub_task, delegated_to=agent_name, result=result.answer))
            except Exception as e:
                logger.exception("Supervisor delegation failed: %s", e)
                records.append(DelegationRecord(task=sub_task, delegated_to=agent_name, result=f"[Error: {e}]"))
        final_answer = await self._synthesize(task, records) if records else "No delegations could be executed."
        duration = time.monotonic() - start
        return SupervisorResult(
            task=task,
            delegations=records,
            final_answer=final_answer,
            duration_seconds=duration,
        )
