"""Task planner — decomposes complex tasks into structured sub-task graphs."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from agentforge.llm.base import BaseLLMProvider, Message, Role
from agentforge.utils.logging import get_logger

if TYPE_CHECKING:
    from agentforge.core.orchestrator import Orchestrator

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class SubTask(BaseModel):
    """A single step in a task plan."""

    id: str
    title: str
    description: str
    depends_on: list[str] = Field(default_factory=list)
    assigned_agent: str | None = None
    estimated_steps: int = 1
    priority: int = Field(default=3, ge=1, le=5)


class TaskPlan(BaseModel):
    """Full plan with goal and ordered subtasks."""

    goal: str
    subtasks: list[SubTask] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    estimated_total_steps: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanExecutionResult(BaseModel):
    """Result of executing a plan."""

    plan: TaskPlan
    results: dict[str, str] = Field(default_factory=dict)
    success: bool = True
    total_duration: float = 0.0
    errors: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


class Planner:
    """Decomposes goals into subtasks and optionally executes them."""

    def __init__(
        self,
        llm: BaseLLMProvider,
        orchestrator: Orchestrator | None = None,
    ) -> None:
        self._llm = llm
        self._orchestrator = orchestrator

    def _build_planning_prompt(
        self,
        goal: str,
        available_agents: list[str] | None,
        constraints: str,
    ) -> str:
        agents_str = ", ".join(available_agents) if available_agents else "general"
        prompt = f"""You are a task planner. Break down the following goal into clear, ordered subtasks.
Each subtask should have: id (short slug, e.g. step_1), title, description, depends_on (list of ids that must complete first), assigned_agent (one of: {agents_str}), estimated_steps (1-5), priority (1-5).
Dependencies must form a DAG (no cycles). First subtasks have empty depends_on.

GOAL:
{goal}
"""
        if constraints:
            prompt += f"\nCONSTRAINTS:\n{constraints}\n"
        prompt += """
Respond with JSON only (no markdown):
{
  "subtasks": [
    { "id": "step_1", "title": "...", "description": "...", "depends_on": [], "assigned_agent": "...", "estimated_steps": 1, "priority": 3 },
    ...
  ],
  "estimated_total_steps": <number>
}
"""
        return prompt

    async def create_plan(
        self,
        goal: str,
        available_agents: list[str] | None = None,
        constraints: str = "",
    ) -> TaskPlan:
        """Use the LLM to generate a structured plan from a goal."""
        prompt = self._build_planning_prompt(goal, available_agents, constraints)
        messages = [Message(role=Role.USER, content=prompt)]
        resp = await self._llm.complete(messages)
        text = (resp.content or "").strip()
        subtasks: list[SubTask] = []
        estimated_total = 0
        try:
            json_match = re.search(r"\{[\s\S]*\}", text)
            if json_match:
                data = json.loads(json_match.group())
                for st in data.get("subtasks", []):
                    subtasks.append(SubTask(
                        id=str(st.get("id", "")),
                        title=str(st.get("title", "")),
                        description=str(st.get("description", "")),
                        depends_on=list(st.get("depends_on", [])),
                        assigned_agent=st.get("assigned_agent"),
                        estimated_steps=int(st.get("estimated_steps", 1)),
                        priority=int(st.get("priority", 3)),
                    ))
                estimated_total = int(data.get("estimated_total_steps", len(subtasks)))
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Planner parse error: %s", e)
            subtasks = [SubTask(id="step_1", title="Single step", description=goal)]
            estimated_total = 1
        return TaskPlan(
            goal=goal,
            subtasks=subtasks,
            estimated_total_steps=estimated_total,
        )

    def _topological_order(self, plan: TaskPlan) -> list[SubTask]:
        """Kahn's algorithm for dependency order."""
        by_id = {s.id: s for s in plan.subtasks}
        in_degree = {s.id: 0 for s in plan.subtasks}
        for s in plan.subtasks:
            for dep in s.depends_on:
                if dep in in_degree:
                    in_degree[s.id] += 1
        queue = [sid for sid, d in in_degree.items() if d == 0]
        order: list[SubTask] = []
        while queue:
            sid = queue.pop(0)
            order.append(by_id[sid])
            for s in plan.subtasks:
                if sid in s.depends_on:
                    in_degree[s.id] -= 1
                    if in_degree[s.id] == 0:
                        queue.append(s.id)
        return order

    async def execute_plan(self, plan: TaskPlan) -> PlanExecutionResult:
        """Execute subtasks in dependency order; use orchestrator if set."""
        import time
        start = time.monotonic()
        order = self._topological_order(plan)
        results: dict[str, str] = {}
        errors: dict[str, str] = {}
        context: dict[str, str] = {}

        for sub in order:
            task_input = sub.description
            for dep in sub.depends_on:
                if dep in results:
                    task_input = f"Context from {dep}:\n{results[dep]}\n\nCurrent task: {task_input}"
            agent_name = sub.assigned_agent or "default"
            try:
                if self._orchestrator:
                    agent = self._orchestrator.get_agent(agent_name)
                    result = await agent.run(task_input)
                    results[sub.id] = result.answer
                else:
                    messages = [
                        Message(role=Role.SYSTEM, content="You are a helpful assistant. Complete the given task concisely."),
                        Message(role=Role.USER, content=task_input),
                    ]
                    resp = await self._llm.complete(messages)
                    results[sub.id] = resp.content or ""
            except Exception as e:
                errors[sub.id] = str(e)
                results[sub.id] = f"[Error: {e}]"

        total_duration = time.monotonic() - start
        success = len(errors) == 0
        return PlanExecutionResult(
            plan=plan,
            results=results,
            success=success,
            total_duration=total_duration,
            errors=errors,
        )

    async def plan_and_execute(
        self,
        goal: str,
        available_agents: list[str] | None = None,
    ) -> PlanExecutionResult:
        """Create a plan and execute it."""
        plan = await self.create_plan(goal, available_agents=available_agents)
        return await self.execute_plan(plan)
