"""
AgentForge core config — API/CLI-friendly configuration and validation.

Re-exports AgentConfig from agent for backward compatibility and adds
optional fields used by the server and CLI (model, provider, tools as list of names).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agentforge.core.agent import AgentConfig as _AgentConfig


class AgentConfig(_AgentConfig):
    """Extended agent configuration for API and CLI usage.

    Adds optional provider and tools (list of tool names) so that
    the server/CLI can construct agents without full LLM/tool instances.
    """

    provider: str = Field(default="auto", description="LLM provider: openai, anthropic, ollama, auto")
    tools: list[str] = Field(default_factory=list, description="Tool names to enable for this agent")

    def to_agent_config(self) -> _AgentConfig:
        """Convert to the core AgentConfig used by Agent (drops extra fields)."""
        return _AgentConfig(
            name=self.name,
            role=getattr(self, "role", "general"),
            system_prompt=getattr(self, "system_prompt", "You are a helpful AI assistant."),
            model=getattr(self, "model", "gpt-4o"),
            temperature=getattr(self, "temperature", 0.7),
            max_tokens=getattr(self, "max_tokens", 4096),
            max_react_steps=getattr(self, "max_react_steps", 10),
            retry_attempts=getattr(self, "retry_attempts", 3),
        )


class PipelineConfig(BaseModel):
    """Configuration for pipeline execution (timeouts, concurrency, retries)."""

    default_timeout_seconds: float | None = Field(default=300.0, ge=1.0, le=3600.0)
    max_concurrent_layers: int = Field(default=4, ge=1, le=32)
    default_retries: int = Field(default=1, ge=0, le=10)
    fail_fast: bool = Field(default=False, description="Stop pipeline on first step failure")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ServerConfig(BaseModel):
    """Server-level configuration (host, port, CORS, auth)."""

    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    api_key_header: str = Field(default="x-api-key")
    require_api_key: bool = Field(default=False)
    request_timeout_seconds: float = Field(default=120.0, ge=1.0, le=600.0)
    max_request_body_size: int = Field(default=1_000_000, ge=1024)
