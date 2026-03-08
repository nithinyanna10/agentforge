"""Token-bucket rate limiter for LLM providers — prevents quota exhaustion."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from pydantic import BaseModel, Field

from agentforge.llm.base import BaseLLMProvider, Message
from agentforge.utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class RateLimitConfig(BaseModel):
    """Token-bucket rate limit configuration."""

    requests_per_minute: int = 60
    tokens_per_minute: int = 100_000
    burst_multiplier: float = 1.5


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


class RateLimiter:
    """Token-bucket implementation for requests and tokens."""

    def __init__(self, config: RateLimitConfig | None = None) -> None:
        self._config = config or RateLimitConfig()
        self._request_bucket = float(self._config.requests_per_minute * self._config.burst_multiplier)
        self._request_capacity = self._request_bucket
        self._request_refill = self._config.requests_per_minute / 60.0
        self._token_bucket = float(self._config.tokens_per_minute * self._config.burst_multiplier)
        self._token_capacity = self._token_bucket
        self._token_refill = self._config.tokens_per_minute / 60.0
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()
        self._total_requests = 0
        self._total_wait_seconds = 0.0

    def _refill(self, now: float) -> None:
        elapsed = now - self._last_refill
        self._last_refill = now
        self._request_bucket = min(
            self._request_capacity,
            self._request_bucket + elapsed * self._request_refill,
        )
        self._token_bucket = min(
            self._token_capacity,
            self._token_bucket + elapsed * self._token_refill,
        )

    async def acquire(self, estimated_tokens: int = 100) -> float:
        """Block until one request and estimated_tokens are available. Returns wait time in seconds."""
        wait_time = 0.0
        while True:
            now = time.monotonic()
            async with self._lock:
                self._refill(now)
                if self._request_bucket >= 1.0 and self._token_bucket >= estimated_tokens:
                    self._request_bucket -= 1.0
                    self._token_bucket -= estimated_tokens
                    self._total_requests += 1
                    self._total_wait_seconds += wait_time
                    return wait_time
                need_request = max(0, 1.0 - self._request_bucket)
                need_tokens = max(0, estimated_tokens - self._token_bucket)
                refill_seconds_request = need_request / self._request_refill if self._request_refill else 0
                refill_seconds_tokens = need_tokens / self._token_refill if self._token_refill else 0
                sleep_for = min(max(refill_seconds_request, refill_seconds_tokens, 0.05), 60.0)
            await asyncio.sleep(sleep_for)
            wait_time += sleep_for

    async def release(self, actual_tokens: int) -> None:
        """Optionally refund tokens if actual usage was less than estimated."""
        if actual_tokens <= 0:
            return
        async with self._lock:
            self._refill(time.monotonic())
            refund = min(actual_tokens, self._token_capacity - self._token_bucket)
            if refund > 0:
                self._token_bucket += refund

    def stats(self) -> dict[str, Any]:
        """Current bucket levels and totals."""
        now = time.monotonic()
        self._refill(now)
        return {
            "request_bucket": round(self._request_bucket, 2),
            "token_bucket": round(self._token_bucket, 0),
            "total_requests": self._total_requests,
            "total_wait_seconds": round(self._total_wait_seconds, 2),
        }


# ---------------------------------------------------------------------------
# Rate-limited provider wrapper
# ---------------------------------------------------------------------------


def _estimate_tokens(messages: list[Message]) -> int:
    """Rough token estimate: ~4 chars per token."""
    total = 0
    for m in messages:
        if m.content:
            total += len(m.content)
        if m.tool_calls:
            for tc in m.tool_calls:
                total += len(tc.function_name) + len(str(tc.arguments))
    return max(100, total // 4)


class RateLimitedProvider(BaseLLMProvider):
    """Wraps a BaseLLMProvider and enforces rate limits before each call."""

    def __init__(
        self,
        provider: BaseLLMProvider,
        rate_limiter: RateLimiter | None = None,
        config: RateLimitConfig | None = None,
    ) -> None:
        super().__init__(
            provider.model,
            temperature=getattr(provider, "default_temperature", 0.7),
            max_tokens=getattr(provider, "default_max_tokens", 4096),
        )
        self._provider = provider
        self._limiter = rate_limiter or RateLimiter(config=config or RateLimitConfig())

    @property
    def model(self) -> str:
        return self._provider.model

    async def complete(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Any:
        from agentforge.llm.base import LLMResponse
        est = _estimate_tokens(messages) + (max_tokens or 4096)
        await self._limiter.acquire(estimated_tokens=est)
        try:
            resp = await self._provider.complete(
                messages,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            actual = getattr(resp, "usage", None)
            if actual and hasattr(actual, "total_tokens"):
                await self._limiter.release(actual.total_tokens)
            return resp
        except Exception:
            await self._limiter.release(est)
            raise

    async def stream(
        self,
        messages: list[Message],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> Any:
        est = _estimate_tokens(messages) + (max_tokens or 4096)
        await self._limiter.acquire(estimated_tokens=est)
        return self._provider.stream(
            messages,
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def format_tools(self, tools: Any) -> list[dict[str, Any]]:
        return self._provider.format_tools(tools)
