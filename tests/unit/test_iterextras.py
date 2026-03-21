"""Tests for iterextras utilities."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from agentforge.utils import iterextras as ie


def test_unique_preserve_order() -> None:
    assert ie.unique_preserve_order([3, 1, 3, 2]) == [3, 1, 2]
    assert ie.unique_preserve_order([{"a": 1}, {"a": 2}], key=lambda x: x["a"]) == [{"a": 1}, {"a": 2}]


def test_interleave() -> None:
    assert list(ie.interleave([1, 3], [2, 4])) == [1, 2, 3, 4]
    assert list(ie.interleave([1], [2, 3])) == [1, 2, 3]


def test_take_drop_while() -> None:
    assert list(ie.take_while(lambda x: x < 3, [1, 2, 3, 1])) == [1, 2]
    assert list(ie.drop_while(lambda x: x < 3, [1, 2, 3, 1])) == [3, 1]


def test_peekable() -> None:
    p = ie.PeekableIterator([10, 20])
    assert p.peek() == 10
    assert next(p) == 10
    assert next(p) == 20


def test_flatten_pairwise() -> None:
    assert list(ie.flatten_once([[1, 2], [3]])) == [1, 2, 3]
    assert list(ie.pairwise([1, 2, 3])) == [(1, 2), (2, 3)]


def test_running_max() -> None:
    assert list(ie.running_max([3.0, 1.0, 5.0, 2.0])) == [3.0, 3.0, 5.0, 5.0]


@pytest.mark.asyncio
async def test_async_batches() -> None:
    async def gen() -> AsyncIterator[int]:
        for x in range(5):
            yield x

    out = []
    async for b in ie.async_batches(gen(), 2):
        out.append(b)
    assert out == [[0, 1], [2, 3], [4]]


def test_chunk_by_predicate() -> None:
    items = [1, 2, 10, 11, 20]
    chunks = list(ie.chunk_by_predicate(items, lambda x: x >= 10))
    # Each boundary item starts a new chunk once a prior chunk exists.
    assert chunks == [[1, 2], [10], [11], [20]]
