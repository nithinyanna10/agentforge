"""
Advanced API routes — readiness, metrics, config, and run history (next-level).
"""

from __future__ import annotations

import importlib.metadata
from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["agentforge-advanced"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ReadinessResponse(BaseModel):
    """Readiness probe response."""

    ready: bool = True
    checks: dict[str, bool] = Field(default_factory=dict)
    version: str = "0.1.0-dev"


class MetricsSummary(BaseModel):
    """Summary of server metrics (counters, gauges)."""

    counters: dict[str, int] = Field(default_factory=dict)
    gauges: dict[str, float] = Field(default_factory=dict)
    uptime_seconds: float = 0.0


class ConfigExportResponse(BaseModel):
    """Exported config (safe subset)."""

    pipeline_default_timeout_seconds: float | None = None
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    version: str = "0.1.0-dev"


class RunSummary(BaseModel):
    """Summary of a single run (for list endpoint)."""

    run_id: str = ""
    agent: str = ""
    task_preview: str = ""
    status: str = "unknown"
    created_at: str = ""


class RunListResponse(BaseModel):
    """List of runs (from RunStore when available)."""

    runs: list[RunSummary] = Field(default_factory=list)
    total: int = 0


class RunDetailResponse(BaseModel):
    """Full run detail for GET /runs/{run_id}."""

    run_id: str = ""
    agent_name: str = ""
    task: str = ""
    answer: str = ""
    tool_calls_json: str = "[]"
    thinking_steps_json: str = "[]"
    duration_seconds: float = 0.0
    created_at: str = ""
    metadata_json: str = "{}"


# ---------------------------------------------------------------------------
# GET /api/v1/readyz
# ---------------------------------------------------------------------------


@router.get("/readyz", response_model=ReadinessResponse, status_code=status.HTTP_200_OK)
async def readyz() -> ReadinessResponse:
    """Kubernetes-style readiness probe. Returns 200 when server can accept traffic."""
    try:
        ver = importlib.metadata.version("agentforge")
    except importlib.metadata.PackageNotFoundError:
        ver = "0.1.0-dev"
    return ReadinessResponse(
        ready=True,
        checks={"server": True, "config": True},
        version=ver,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/metrics
# ---------------------------------------------------------------------------


@router.get("/metrics", response_model=MetricsSummary, status_code=status.HTTP_200_OK)
async def metrics_summary() -> MetricsSummary:
    """Return a summary of metrics (counters and gauges) for monitoring."""
    try:
        from agentforge.observability import get_metrics
        m = get_metrics()
        return MetricsSummary(
            counters=getattr(m, "counters", {}),
            gauges=getattr(m, "gauges", {}),
            uptime_seconds=0.0,
        )
    except Exception:
        return MetricsSummary(counters={}, gauges={}, uptime_seconds=0.0)


# ---------------------------------------------------------------------------
# GET /api/v1/config
# ---------------------------------------------------------------------------


@router.get("/config", response_model=ConfigExportResponse, status_code=status.HTTP_200_OK)
async def get_config() -> ConfigExportResponse:
    """Return safe server/pipeline config (no secrets)."""
    try:
        ver = importlib.metadata.version("agentforge")
    except importlib.metadata.PackageNotFoundError:
        ver = "0.1.0-dev"
    return ConfigExportResponse(
        pipeline_default_timeout_seconds=300.0,
        server_host="0.0.0.0",
        server_port=8000,
        version=ver,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/runs
# ---------------------------------------------------------------------------


@router.get("/runs", response_model=RunListResponse, status_code=status.HTTP_200_OK)
async def list_runs(request: Request, limit: int = 50, offset: int = 0, agent_name: str | None = None) -> RunListResponse:
    """List recent runs from RunStore when available."""
    run_store = getattr(request.app.state, "run_store", None)
    if run_store is None:
        return RunListResponse(runs=[], total=0)
    try:
        stored = await run_store.list_recent(limit=limit, agent_name=agent_name)
        if offset > 0:
            stored = stored[offset:]
        runs = [
            RunSummary(
                run_id=s.run_id,
                agent=s.agent_name,
                task_preview=(s.task[:80] + "…") if len(s.task) > 80 else s.task,
                status="completed",
                created_at=s.created_at,
            )
            for s in stored
        ]
        return RunListResponse(runs=runs, total=len(runs))
    except Exception:
        return RunListResponse(runs=[], total=0)


# ---------------------------------------------------------------------------
# GET /api/v1/runs/{run_id}
# ---------------------------------------------------------------------------


@router.get("/runs/{run_id}", response_model=RunDetailResponse, status_code=status.HTTP_200_OK)
async def get_run(request: Request, run_id: str) -> RunDetailResponse | JSONResponse:
    """Get a single run by ID from RunStore."""
    run_store = getattr(request.app.state, "run_store", None)
    if run_store is None:
        return JSONResponse(status_code=404, content={"detail": "RunStore not configured"})
    try:
        stored = await run_store.get(run_id)
        if stored is None:
            return JSONResponse(status_code=404, content={"detail": "Run not found"})
        return RunDetailResponse(
            run_id=stored.run_id,
            agent_name=stored.agent_name,
            task=stored.task,
            answer=stored.answer,
            tool_calls_json=stored.tool_calls_json,
            thinking_steps_json=stored.thinking_steps_json,
            duration_seconds=stored.duration_seconds,
            created_at=stored.created_at,
            metadata_json=stored.metadata_json,
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})
