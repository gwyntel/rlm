"""Tests for RLM context store."""

import asyncio
import pytest

from rlm.store import RLMContextStore, RLMScope


def test_scope_set_get():
    scope = RLMScope(root_id="test")
    scope.set(0, "root context")
    scope.set(1, "sub context")
    assert scope.get(0) == "root context"
    assert scope.get(1) == "sub context"
    assert scope.get(2) is None


def test_scope_sub_results():
    scope = RLMScope(root_id="test")
    scope.add_sub_result(0, "sub answer 1")
    scope.add_sub_result(0, "sub answer 2")
    assert len(scope.sub_results[0]) == 2
    assert scope.sub_results[0][0] == "sub answer 1"


@pytest.mark.asyncio
async def test_store_root_scope():
    store = RLMContextStore()
    async with store.root_scope("root:abc") as scope:
        scope.set(0, "test")
        assert store.scope_count == 1
        assert store.get_scope("root:abc") is not None
    # After exit, scope is evicted
    assert store.scope_count == 0
    assert store.get_scope("root:abc") is None


@pytest.mark.asyncio
async def test_store_concurrent_roots():
    store = RLMContextStore()

    async def run_root(root_id: str):
        async with store.root_scope(root_id) as scope:
            scope.set(0, f"data-{root_id}")
            await asyncio.sleep(0.01)

    # Run two roots concurrently
    await asyncio.gather(
        run_root("root:a"),
        run_root("root:b"),
    )

    assert store.scope_count == 0


@pytest.mark.asyncio
async def test_store_eviction_on_exception():
    store = RLMContextStore()

    with pytest.raises(ValueError):
        async with store.root_scope("root:err") as scope:
            scope.set(0, "before error")
            raise ValueError("boom")

    assert store.scope_count == 0
    assert store.get_scope("root:err") is None


def test_active_roots():
    store = RLMContextStore()
    assert store.active_roots == []
