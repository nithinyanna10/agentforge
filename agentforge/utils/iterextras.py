"""Iterator helpers: batching, windowing, peekable adapters, and deduplication."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable, Iterable, Iterator
from typing import Any, TypeVar

T = TypeVar("T")


def batches(iterable: Iterable[T], size: int) -> Iterator[list[T]]:
    """Yield lists of up to *size* items from *iterable*."""
    if size < 1:
        raise ValueError("size must be >= 1")
    batch: list[T] = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def windowed(iterable: Iterable[T], n: int, *, partial: bool = True) -> Iterator[tuple[T, ...]]:
    """Rolling window of length n over iterable."""
    if n < 1:
        raise ValueError("n must be >= 1")
    buf: list[T] = []
    it = iter(iterable)
    for _ in range(n):
        try:
            buf.append(next(it))
        except StopIteration:
            if partial and buf:
                yield tuple(buf)
            return
    yield tuple(buf)
    for x in it:
        buf = buf[1:] + [x]
        yield tuple(buf)


def unique_preserve_order(items: Iterable[T], key: Callable[[T], Any] | None = None) -> list[T]:
    """Deduplicate while keeping first occurrence order."""
    seen: set[Any] = set()
    out: list[T] = []
    for item in items:
        k = key(item) if key is not None else item
        if k in seen:
            continue
        seen.add(k)
        out.append(item)
    return out


def interleave(a: Iterable[T], b: Iterable[T]) -> Iterator[T]:
    """Interleave two iterables until one is exhausted; remainder from the longer one."""
    ia, ib = iter(a), iter(b)
    while True:
        try:
            xa = next(ia)
        except StopIteration:
            yield from ib
            return
        try:
            xb = next(ib)
        except StopIteration:
            yield xa
            yield from ia
            return
        yield xa
        yield xb


def take_while(predicate: Callable[[T], bool], iterable: Iterable[T]) -> Iterator[T]:
    """Yield items while predicate(item) is true."""
    for item in iterable:
        if not predicate(item):
            break
        yield item


def drop_while(predicate: Callable[[T], bool], iterable: Iterable[T]) -> Iterator[T]:
    """Skip items while predicate holds, then yield the rest."""
    it = iter(iterable)
    for item in it:
        if not predicate(item):
            yield item
            break
    yield from it


_MISSING = object()


class PeekableIterator(Iterable[T]):
    """Iterator with optional peek of next value."""

    def __init__(self, iterable: Iterable[T]) -> None:
        self._it = iter(iterable)
        self._buf: object = _MISSING

    def __iter__(self) -> Iterator[T]:
        return self

    def __next__(self) -> T:
        if self._buf is not _MISSING:
            v = self._buf
            self._buf = _MISSING
            return v  # type: ignore[return-value]
        return next(self._it)

    def peek(self, default: T | None = None) -> T | None:
        """Return next item without consuming, or default if exhausted."""
        if self._buf is not _MISSING:
            return self._buf  # type: ignore[return-value]
        try:
            self._buf = next(self._it)
            return self._buf  # type: ignore[return-value]
        except StopIteration:
            return default


async def async_batches(
    stream: AsyncIterator[T],
    size: int,
) -> AsyncIterator[list[T]]:
    """Async batching for async iterators."""
    if size < 1:
        raise ValueError("size must be >= 1")
    batch: list[T] = []
    async for item in stream:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def flatten_once(nested: Iterable[Iterable[T]]) -> Iterator[T]:
    """One level of flattening."""
    for inner in nested:
        yield from inner


def chunk_by_predicate(items: Iterable[T], boundary: Callable[[T], bool]) -> Iterator[list[T]]:
    """Split when boundary(item) is True (first item after split starts new chunk)."""
    chunk: list[T] = []
    for item in items:
        if boundary(item) and chunk:
            yield chunk
            chunk = [item]
        else:
            chunk.append(item)
    if chunk:
        yield chunk


def running_max(values: Iterable[float]) -> Iterator[float]:
    """Cumulative maximum."""
    m = float("-inf")
    for v in values:
        m = max(m, v)
        yield m


def pairwise(iterable: Iterable[T]) -> Iterator[tuple[T, T]]:
    """(a,b), (b,c), ..."""
    it = iter(iterable)
    try:
        prev = next(it)
    except StopIteration:
        return
    for x in it:
        yield (prev, x)
        prev = x
