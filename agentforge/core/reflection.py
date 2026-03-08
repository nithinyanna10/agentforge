"""Reflection loop — agent critiques its own output and improves iteratively."""

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


class ReflectionConfig(BaseModel):
    """Configuration for the reflection loop."""

    max_iterations: int = Field(default=3, ge=1, le=10)
    improvement_threshold: float = Field(default=7.0, ge=0, le=10)
    critic_model: str = "gpt-4o"
    verbose: bool = False


class ReflectionStep(BaseModel):
    """One iteration of reflect-and-improve."""

    iteration: int
    draft: str
    critique: str
    score: float
    improvements: list[str] = Field(default_factory=list)


class ReflectionResult(BaseModel):
    """Final result after reflection loop."""

    task: str
    final_answer: str
    steps: list[ReflectionStep] = Field(default_factory=list)
    converged: bool = False
    total_iterations: int = 0


# ---------------------------------------------------------------------------
# Reflection agent
# ---------------------------------------------------------------------------


class ReflectionAgent:
    """Wraps an agent with a critic that iteratively improves the response."""

    def __init__(
        self,
        agent: Agent,
        critic_llm: BaseLLMProvider | None = None,
        config: ReflectionConfig | None = None,
    ) -> None:
        self._agent = agent
        self._critic_llm = critic_llm or agent.llm
        self._config = config or ReflectionConfig()

    async def _critique(self, task: str, response: str) -> tuple[float, str, list[str]]:
        """Return (score, critique_text, list of improvements)."""
        prompt = f"""You are a critical evaluator. Score this response to the given task from 0 to 10, then list specific improvements.

TASK:
{task}

RESPONSE:
{response}

Respond with JSON only (no markdown):
{{ "score": <0-10>, "critique": "<brief critique>", "improvements": ["<s1>", "<s2>", ...] }}
"""
        messages = [Message(role=Role.USER, content=prompt)]
        resp = await self._critic_llm.complete(messages)
        text = (resp.content or "").strip()
        score = 0.0
        critique = ""
        improvements: list[str] = []
        try:
            json_match = re.search(r"\{[\s\S]*\}", text)
            if json_match:
                data = json.loads(json_match.group())
                score = float(data.get("score", 0))
                critique = str(data.get("critique", ""))
                improvements = list(data.get("improvements", []))
        except Exception as e:
            logger.warning("Reflection critique parse error: %s", e)
        return score, critique, improvements

    async def _improve(
        self,
        task: str,
        draft: str,
        critique: str,
        improvements: list[str],
    ) -> str:
        """Generate an improved version given the critique."""
        imp_text = "\n".join(f"- {i}" for i in improvements) if improvements else critique
        prompt = f"""Original task: {task}

Previous draft:
{draft}

Critique and improvements:
{imp_text}

Provide an improved response that addresses the critique. Output only the improved response, no meta-commentary.
"""
        messages = [
            Message(role=Role.SYSTEM, content="You improve drafts based on critique. Output only the improved text."),
            Message(role=Role.USER, content=prompt),
        ]
        resp = await self._critic_llm.complete(messages)
        return (resp.content or draft).strip()

    async def run(self, task: str) -> ReflectionResult:
        """Run agent, then iterate: critique -> improve until score >= threshold or max iterations."""
        steps: list[ReflectionStep] = []
        result = await self._agent.run(task)
        draft = result.answer
        for i in range(self._config.max_iterations):
            score, critique, improvements = await self._critique(task, draft)
            steps.append(ReflectionStep(iteration=i + 1, draft=draft, critique=critique, score=score, improvements=improvements))
            if score >= self._config.improvement_threshold:
                return ReflectionResult(
                    task=task,
                    final_answer=draft,
                    steps=steps,
                    converged=True,
                    total_iterations=i + 1,
                )
            if i == self._config.max_iterations - 1:
                break
            draft = await self._improve(task, draft, critique, improvements)
        return ReflectionResult(
            task=task,
            final_answer=draft,
            steps=steps,
            converged=False,
            total_iterations=len(steps),
        )
