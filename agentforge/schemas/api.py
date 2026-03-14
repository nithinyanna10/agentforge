"""
API request/response schemas for AgentForge (next-level).

Centralizes Pydantic models for REST API validation and OpenAPI docs.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RunRequestSchema(BaseModel):
    """Request body for POST /api/v1/run."""

    task: str = Field(..., min_length=1, max_length=50_000, description="The task to execute")
    agent_name: str = Field(default="default", max_length=128)
    tools: list[str] = Field(default_factory=list, max_length=50)
    model: str | None = Field(default=None, max_length=128)
    provider: str | None = Field(default=None, max_length=64)


class EventItemSchema(BaseModel):
    """Single event in a run response."""

    type: str = Field(..., max_length=64)
    content: str = Field(default="", max_length=100_000)
    tool: str | None = Field(default=None, max_length=128)
    args: dict[str, Any] | None = Field(default=None)


class RunResponseSchema(BaseModel):
    """Response for POST /api/v1/run."""

    task: str = Field(...)
    agent: str = Field(...)
    events: list[EventItemSchema] = Field(default_factory=list)
    final_answer: str = Field(default="", max_length=500_000)


class PipelineRequestSchema(BaseModel):
    """Request body for POST /api/v1/pipeline."""

    yaml_content: str = Field(..., min_length=1, max_length=500_000, description="Pipeline YAML as string")


class StepResultSchema(BaseModel):
    """Result of a single pipeline step."""

    step: str = Field(...)
    status: str = Field(...)
    output: str = Field(default="", max_length=100_000)


class PipelineResponseSchema(BaseModel):
    """Response for POST /api/v1/pipeline."""

    steps: list[StepResultSchema] = Field(default_factory=list)
    success: bool = Field(...)


class HealthSchema(BaseModel):
    """Response for GET /api/v1/health."""

    status: str = Field(..., pattern="^(ok|degraded|error)$")
    version: str = Field(default="0.1.0-dev")


class ErrorDetailSchema(BaseModel):
    """Single error detail (e.g. validation)."""

    loc: list[str] = Field(default_factory=list)
    msg: str = Field(...)
    type: str = Field(default="value_error")


class ErrorSchema(BaseModel):
    """Error response body."""

    detail: str | list[ErrorDetailSchema] = Field(...)
    status_code: int = Field(default=500)
    correlation_id: str | None = Field(default=None)
