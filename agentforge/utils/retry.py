"""
Retry and backoff utilities for AgentForge (next-level).

Provides async and sync retry decorators with exponential backoff,
jitter, and configurable exceptions.
"""

from __future__ import annotations

import asyncio
import random
import time
from functools import wraps
from typing import Any, Callable, TypeVar, Tuple, Type

from agentforge.utils.logging import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def retry_async(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    jitter: float = 0.1,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
) -> Callable[[F], F]:
    """Decorator that retries an async function with exponential backoff and jitter."""

    def decorator(fn: F) -> F:
        @wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await fn(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt == max_attempts:
                        raise
                    wait = delay * (backoff ** (attempt - 1))
                    if jitter > 0:
                        wait *= 1.0 + random.uniform(-jitter, jitter)
                    wait = max(0.01, wait)
                    logger.warning(
                        "Retry attempt %d/%d for %s failed: %s; waiting %.2fs",
                        attempt,
                        max_attempts,
                        fn.__name__,
                        e,
                        wait,
                    )
                    await asyncio.sleep(wait)
            raise last_exc  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator


def retry_sync(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    jitter: float = 0.1,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
) -> Callable[[F], F]:
    """Decorator that retries a sync function with exponential backoff and jitter."""

    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt == max_attempts:
                        raise
                    wait = delay * (backoff ** (attempt - 1))
                    if jitter > 0:
                        wait *= 1.0 + random.uniform(-jitter, jitter)
                    wait = max(0.01, wait)
                    logger.warning(
                        "Retry attempt %d/%d for %s failed: %s; waiting %.2fs",
                        attempt,
                        max_attempts,
                        fn.__name__,
                        e,
                        wait,
                    )
                    time.sleep(wait)
            raise last_exc  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator
