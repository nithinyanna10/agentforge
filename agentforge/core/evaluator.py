"""Agent output evaluator — uses an LLM judge to score responses on multiple criteria."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from agentforge.llm.base import BaseLLMProvider, Message, Role
from agentforge.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Criteria and scores
# ---------------------------------------------------------------------------


class EvalCriterion(BaseModel):
    """Single evaluation dimension with rubric."""

    name: str
    description: str
    weight: float = 1.0
    rubric: str = "Score 0-10: 0=unacceptable, 5=adequate, 10=excellent."


class EvalScore(BaseModel):
    """Score for one criterion."""

    criterion: str
    score: float = Field(ge=0, le=10)
    reasoning: str = ""
    suggestions: list[str] = Field(default_factory=list)


class EvalResult(BaseModel):
    """Full evaluation result with overall grade."""

    task: str
    response: str
    scores: list[EvalScore] = Field(default_factory=list)
    overall_score: float = 0.0
    grade: str = "F"
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    evaluator_model: str = ""

    def model_post_init(self, __context: Any) -> None:
        if self.scores:
            self.overall_score = sum(s.score for s in self.scores) / len(self.scores)
            self.grade = _score_to_grade(self.overall_score)


def _score_to_grade(score: float) -> str:
    if score >= 9.0:
        return "A"
    if score >= 8.0:
        return "B"
    if score >= 7.0:
        return "C"
    if score >= 6.0:
        return "D"
    return "F"


# ---------------------------------------------------------------------------
# Built-in criterion sets
# ---------------------------------------------------------------------------


HELPFULNESS_CRITERIA = [
    EvalCriterion(
        name="helpfulness",
        description="How useful and actionable is the response?",
        weight=1.0,
        rubric="0=not helpful, 10=fully addresses the user need.",
    ),
    EvalCriterion(
        name="accuracy",
        description="Are the facts and claims correct?",
        weight=1.0,
        rubric="0=factually wrong, 10=fully accurate.",
    ),
    EvalCriterion(
        name="completeness",
        description="Does it cover what was asked?",
        weight=0.8,
        rubric="0=missing key points, 10=complete.",
    ),
    EvalCriterion(
        name="conciseness",
        description="Is it appropriately concise without being terse?",
        weight=0.5,
        rubric="0=rambling or too short, 10=well-balanced.",
    ),
]

CODE_CRITERIA = [
    EvalCriterion(name="correctness", description="Does the code solve the problem?", weight=1.5, rubric="0=broken, 10=correct."),
    EvalCriterion(name="readability", description="Is the code clear and maintainable?", weight=1.0, rubric="0=unreadable, 10=clear."),
    EvalCriterion(name="efficiency", description="Reasonable time/space complexity?", weight=0.8, rubric="0=poor, 10=appropriate."),
    EvalCriterion(name="security", description="No obvious vulnerabilities?", weight=1.0, rubric="0=unsafe, 10=safe."),
]

RESEARCH_CRITERIA = [
    EvalCriterion(name="accuracy", description="Factual accuracy of claims.", weight=1.2, rubric="0=wrong, 10=accurate."),
    EvalCriterion(name="citations", description="Are sources cited where needed?", weight=1.0, rubric="0=none, 10=proper."),
    EvalCriterion(name="depth", description="Depth of analysis.", weight=1.0, rubric="0=superficial, 10=thorough."),
    EvalCriterion(name="objectivity", description="Balanced and objective?", weight=0.8, rubric="0=biased, 10=objective."),
]


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


class Evaluator:
    """LLM-based evaluator for agent responses."""

    def __init__(
        self,
        llm: BaseLLMProvider,
        criteria: list[EvalCriterion] | None = None,
    ) -> None:
        self._llm = llm
        self._criteria = criteria or HELPFULNESS_CRITERIA

    def _build_prompt(self, task: str, response: str, context: str) -> str:
        criteria_text = "\n".join(
            f"- {c.name} (weight {c.weight}): {c.description}\n  Rubric: {c.rubric}"
            for c in self._criteria
        )
        prompt = f"""You are an expert evaluator. Score the following response on each criterion.

TASK:
{task}

RESPONSE TO EVALUATE:
{response}
"""
        if context:
            prompt += f"\nCONTEXT (optional):\n{context}\n"
        prompt += f"""
CRITERIA:
{criteria_text}

Respond with a JSON object only, no markdown:
{{
  "scores": [
    {{ "criterion": "<name>", "score": <0-10>, "reasoning": "<brief>", "suggestions": ["<s1>", "<s2>"] }},
    ...
  ]
}}
"""
        return prompt

    async def evaluate(self, task: str, response: str, context: str = "") -> EvalResult:
        """Evaluate a single task/response pair."""
        prompt = self._build_prompt(task, response, context)
        messages = [Message(role=Role.USER, content=prompt)]
        resp = await self._llm.complete(messages)
        text = (resp.content or "").strip()
        scores: list[EvalScore] = []
        try:
            json_match = re.search(r"\{[\s\S]*\}", text)
            if json_match:
                data = json.loads(json_match.group())
                for s in data.get("scores", []):
                    scores.append(EvalScore(
                        criterion=str(s.get("criterion", "")),
                        score=float(s.get("score", 0)),
                        reasoning=str(s.get("reasoning", "")),
                        suggestions=list(s.get("suggestions", [])),
                    ))
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Evaluator parse error: %s", e)
        overall = sum(s.score for s in scores) / len(scores) if scores else 0.0
        grade = _score_to_grade(overall)
        return EvalResult(
            task=task,
            response=response,
            scores=scores,
            overall_score=overall,
            grade=grade,
            evaluator_model=resp.model or self._llm.model,
        )

    async def compare(self, task: str, response_a: str, response_b: str) -> dict[str, Any]:
        """A/B comparison: which response is better and why."""
        prompt = f"""You are an expert evaluator. Compare these two responses to the same task and decide which is better.

TASK:
{task}

RESPONSE A:
{response_a}

RESPONSE B:
{response_b}

Respond with JSON only:
{{ "winner": "A" or "B", "reason": "<brief explanation>", "score_a": <0-10>, "score_b": <0-10> }}
"""
        messages = [Message(role=Role.USER, content=prompt)]
        resp = await self._llm.complete(messages)
        text = (resp.content or "").strip()
        try:
            json_match = re.search(r"\{[\s\S]*\}", text)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        return {"winner": "unknown", "reason": "Parse failed", "score_a": 0, "score_b": 0}

    async def batch_evaluate(
        self,
        items: list[tuple[str, str]],
        context: str = "",
    ) -> list[EvalResult]:
        """Evaluate multiple task/response pairs concurrently."""
        import asyncio
        tasks = [self.evaluate(task, response, context) for task, response in items]
        return list(await asyncio.gather(*tasks))
