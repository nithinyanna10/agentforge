"""Centralised, env-driven configuration via Pydantic Settings."""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables.

    A ``.env`` file in the working directory (or the path given by
    ``env_file``) is read automatically via *python-dotenv*.
    """

    # -- general -------------------------------------------------------------
    app_name: str = "AgentForge"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # -- LLM providers -------------------------------------------------------
    openai_api_key: str = ""
    openai_org_id: str = ""
    openai_model: str = "gpt-4o"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # -- default model params ------------------------------------------------
    default_temperature: float = 0.7
    default_max_tokens: int = 4096

    # -- memory & storage ----------------------------------------------------
    sqlite_db_path: str = "agentforge_memory.db"
    chroma_persist_dir: str = ".chroma"
    chroma_collection: str = "agentforge_memory"

    # -- networking / API server ---------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "*"

    # -- misc ----------------------------------------------------------------
    max_concurrent_agents: int = 10
    pipeline_timeout_seconds: int = 300

    model_config = {
        "env_prefix": "AGENTFORGE_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton ``Settings`` instance.

    Environment variables and the ``.env`` file are read once on first call.
    """
    return Settings()
