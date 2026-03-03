"""AgentForge API routes — REST endpoints for agents, tools, and pipelines."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    task: str = Field(..., min_length=1, description="The task to execute")
    agent_name: str = Field("default", description="Name of the agent to use")
    tools: list[str] = Field(default_factory=list, description="Tool names to enable")
    model: str | None = Field(None, description="LLM model override")
    provider: str | None = Field(None, description="LLM provider override")


class EventResponse(BaseModel):
    type: str
    content: str = ""
    tool: str | None = None
    args: dict[str, Any] | None = None


class RunResponse(BaseModel):
    task: str
    agent: str
    events: list[EventResponse]
    final_answer: str


class PipelineRequest(BaseModel):
    yaml_content: str = Field(..., min_length=1, description="Pipeline YAML as a string")


class PipelineStepResult(BaseModel):
    step: str
    status: str
    output: str = ""


class PipelineResponse(BaseModel):
    steps: list[PipelineStepResult]
    success: bool


class AgentInfo(BaseModel):
    name: str
    description: str = ""
    model: str = ""
    provider: str = ""
    tools: list[str] = Field(default_factory=list)


class AgentListResponse(BaseModel):
    agents: list[AgentInfo]
    count: int


class ToolInfo(BaseModel):
    name: str
    description: str = ""
    version: str = ""


class ToolListResponse(BaseModel):
    tools: list[ToolInfo]
    count: int


class HealthResponse(BaseModel):
    status: str
    version: str


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api/v1", tags=["agentforge"])


# ---------------------------------------------------------------------------
# POST /api/v1/run
# ---------------------------------------------------------------------------


@router.post("/run", response_model=RunResponse, status_code=status.HTTP_200_OK)
async def run_task(body: RunRequest) -> RunResponse:
    """Run a task with a single agent and return the full result."""

    from agentforge.core.agent import Agent  # type: ignore[import-untyped]
    from agentforge.core.config import AgentConfig  # type: ignore[import-untyped]

    try:
        config = AgentConfig(
            name=body.agent_name,
            tools=body.tools,
            model=body.model or "auto",
            provider=body.provider or "auto",
        )
        agent = Agent(config=config)
        result = await agent.run(body.task)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    events = [
        EventResponse(
            type=ev.type,
            content=getattr(ev, "content", ""),
            tool=getattr(ev, "tool_name", None),
            args=getattr(ev, "tool_args", None),
        )
        for ev in result.events
    ]

    return RunResponse(
        task=body.task,
        agent=body.agent_name,
        events=events,
        final_answer=result.final_answer,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/pipeline
# ---------------------------------------------------------------------------


@router.post(
    "/pipeline",
    response_model=PipelineResponse,
    status_code=status.HTTP_200_OK,
)
async def run_pipeline(body: PipelineRequest) -> PipelineResponse:
    """Run a multi-step pipeline from a YAML string."""

    import yaml

    from agentforge.core.pipeline import Pipeline  # type: ignore[import-untyped]

    try:
        definition = yaml.safe_load(body.yaml_content)
    except yaml.YAMLError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid YAML: {exc}",
        ) from exc

    if not definition or "steps" not in definition:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="YAML must contain a 'steps' key.",
        )

    try:
        pipe = Pipeline.from_dict(definition)
        step_results: list[PipelineStepResult] = []

        async for event in pipe.execute_stream():
            if event.type == "step_complete":
                step_results.append(
                    PipelineStepResult(
                        step=event.step_name,
                        status="completed",
                        output=getattr(event, "content", ""),
                    )
                )
            elif event.type == "error":
                step_results.append(
                    PipelineStepResult(
                        step=getattr(event, "step_name", "unknown"),
                        status="failed",
                        output=event.content,
                    )
                )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    success = all(s.status == "completed" for s in step_results)
    return PipelineResponse(steps=step_results, success=success)


# ---------------------------------------------------------------------------
# GET /api/v1/agents
# ---------------------------------------------------------------------------


@router.get("/agents", response_model=AgentListResponse)
async def list_agents() -> AgentListResponse:
    """Return all registered agent configurations."""

    from agentforge.core.agent import Agent  # type: ignore[import-untyped]

    try:
        registered = Agent.registry()  # type: ignore[attr-defined]
    except Exception:
        registered = []

    agents = [
        AgentInfo(
            name=a.name,
            description=getattr(a, "description", ""),
            model=getattr(a, "model", ""),
            provider=getattr(a, "provider", ""),
            tools=[t.name for t in getattr(a, "tools", [])],
        )
        for a in registered
    ]
    return AgentListResponse(agents=agents, count=len(agents))


# ---------------------------------------------------------------------------
# GET /api/v1/tools
# ---------------------------------------------------------------------------


@router.get("/tools", response_model=ToolListResponse)
async def list_tools() -> ToolListResponse:
    """Return all available tools."""

    from agentforge.tools import Tool  # type: ignore[import-untyped]

    try:
        registry: list[type[Tool]] = Tool.registry()  # type: ignore[attr-defined]
    except Exception:
        registry = []

    tool_list = [
        ToolInfo(
            name=t.name,
            description=t.description,
            version=getattr(t, "version", ""),
        )
        for t in sorted(registry, key=lambda t: t.name)
    ]
    return ToolListResponse(tools=tool_list, count=len(tool_list))


# ---------------------------------------------------------------------------
# GET /api/v1/health
# ---------------------------------------------------------------------------


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health-check endpoint."""

    import importlib.metadata

    try:
        ver = importlib.metadata.version("agentforge")
    except importlib.metadata.PackageNotFoundError:
        ver = "0.1.0-dev"

    return HealthResponse(status="ok", version=ver)
