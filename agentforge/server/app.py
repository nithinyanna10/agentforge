"""AgentForge FastAPI application with WebSocket streaming support."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from agentforge.server.routes import router

logger = logging.getLogger("agentforge.server")

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown hooks for the FastAPI application."""
    logger.info("AgentForge server starting up …")
    # Warm up any shared resources (connection pools, model caches, etc.)
    application.state.ready = True
    yield
    logger.info("AgentForge server shutting down …")
    application.state.ready = False


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    application = FastAPI(
        title="AgentForge API",
        description=(
            "REST + WebSocket API for the AgentForge multi-agent orchestration framework."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(router)

    # -----------------------------------------------------------------------
    # WebSocket — stream agent execution in real-time
    # -----------------------------------------------------------------------

    @application.websocket("/ws/stream")
    async def ws_stream(ws: WebSocket) -> None:
        await ws.accept()
        logger.info("WebSocket client connected")

        try:
            while True:
                payload = await ws.receive_json()
                task: str = payload.get("task", "")
                agent_name: str = payload.get("agent", "default")
                tools_list: list[str] = payload.get("tools", [])

                if not task:
                    await ws.send_json({"type": "error", "content": "No task provided."})
                    continue

                await ws.send_json({"type": "status", "content": "accepted"})

                try:
                    await _stream_execution(
                        ws,
                        task=task,
                        agent_name=agent_name,
                        tools_list=tools_list,
                    )
                except Exception as exc:
                    logger.exception("Error during streamed execution")
                    await ws.send_json({"type": "error", "content": str(exc)})

        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")

    return application


# ---------------------------------------------------------------------------
# Streaming helper
# ---------------------------------------------------------------------------


async def _stream_execution(
    ws: WebSocket,
    *,
    task: str,
    agent_name: str,
    tools_list: list[str],
) -> None:
    """Run an agent and push events over the WebSocket as JSON frames."""

    from agentforge.core.agent import Agent  # type: ignore[import-untyped]
    from agentforge.core.config import AgentConfig  # type: ignore[import-untyped]

    config = AgentConfig(name=agent_name, tools=tools_list)
    agent = Agent(config=config)

    async for event in agent.run_stream(task):
        frame: dict[str, object] = {"type": event.type}
        match event.type:
            case "thinking":
                frame["content"] = event.content
            case "tool_call":
                frame["tool"] = event.tool_name
                frame["args"] = event.tool_args
            case "tool_result":
                frame["content"] = event.content
            case "result":
                frame["content"] = event.content
            case "error":
                frame["content"] = event.content
            case _:
                frame["content"] = getattr(event, "content", "")

        await ws.send_json(frame)
        await asyncio.sleep(0)  # yield control

    await ws.send_json({"type": "done"})


# ---------------------------------------------------------------------------
# Module-level app instance (used by uvicorn)
# ---------------------------------------------------------------------------

app: FastAPI = create_app()
