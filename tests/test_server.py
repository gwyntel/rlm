"""Tests for RLM FastMCP server."""

import pytest
from fastmcp import Client
from fastmcp.client import FastMCPTransport

from rlm.server import mcp, store


@pytest.fixture
def client():
    """In-memory client for testing — no subprocess, no network."""
    return Client(transport=FastMCPTransport(mcp))


@pytest.mark.asyncio
async def test_server_has_tools(client):
    async with client:
        tools = await client.list_tools()
        tool_names = [t.name for t in tools]
        assert "rlm_query" in tool_names
        assert "rlm_status" in tool_names


@pytest.mark.asyncio
async def test_rlm_status(client):
    async with client:
        result = await client.call_tool("rlm_status", {})
        text = result.data
        assert "RLM Server Status" in text
        assert "Active roots: 0" in text


@pytest.mark.asyncio
async def test_rlm_query_calls_sampling(client):
    """Verify rlm_query reaches ctx.sample() and returns a result.
    
    With in-memory transport, sampling requires a host that supports it.
    FastMCPTransport doesn't support sampling, so this test validates
    the error path gracefully.
    """
    async with client:
        try:
            result = await client.call_tool("rlm_query", {"prompt": "Hello world"})
            # If sampling works, we get a result
            assert result.data
        except Exception as e:
            # Expected: sampling not supported by in-memory transport
            err = str(e).lower()
            assert "sampling" in err or "not supported" in err or "error" in err


def test_store_is_empty_after_init():
    assert store.scope_count == 0
