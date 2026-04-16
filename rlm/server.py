"""
RLM — Recursive Language Model via FastMCP.

No-tools implementation: pure recursion + sampling + call-tree-scoped store.
The LLM decides whether to decompose or answer directly via structured markers.
"""

import uuid
import logging

from fastmcp import FastMCP, Context

from .store import RLMContextStore
from .prompts import (
    build_system_prompt,
    build_user_prompt,
    needs_decomposition,
    extract_subprompt,
    extract_direct_answer,
    build_synthesis_prompt,
)

logger = logging.getLogger("rlm")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DEFAULT_MAX_DEPTH = 4
DEFAULT_MAX_TOKENS = 4096
DEFAULT_THINKING_BUDGET = 2048

# ---------------------------------------------------------------------------
# Global store
# ---------------------------------------------------------------------------
store = RLMContextStore()

# ---------------------------------------------------------------------------
# FastMCP server
# ---------------------------------------------------------------------------
mcp = FastMCP(
    "RLM",
    instructions=(
        "Recursive Language Model — decomposes complex tasks into sub-tasks, "
        "each getting its own context window via MCP sampling. "
        "No tools, no sandbox — just pure recursive reasoning."
    ),
)


# ---------------------------------------------------------------------------
# Core recursion
# ---------------------------------------------------------------------------
async def _rlm_recurse(
    ctx: Context,
    scope,  # RLMScope — avoiding circular import
    prompt: str,
    depth: int,
    max_depth: int,
    max_tokens: int,
) -> str:
    """Recursively decompose tasks via sampling."""

    # Pull prior context from this depth (if re-entered)
    prior = scope.get(depth)
    sub_results = scope.sub_results.get(depth, [])

    # Build prompts
    sys_prompt = build_system_prompt(depth, max_depth)
    usr_prompt = build_user_prompt(prompt, prior_context=prior, sub_results=sub_results)

    # Sample the host LLM
    logger.info(f"[RLM] depth={depth} root={scope.root_id} sampling...")
    result = await ctx.sample(
        messages=usr_prompt,
        system_prompt=sys_prompt,
        max_tokens=max_tokens,
    )
    result_text = result.text if hasattr(result, 'text') else str(result)

    # Store at this depth
    scope.set(depth, result_text)

    # Check: decompose or answer?
    if needs_decomposition(result_text) and depth < max_depth - 1:
        sub_prompt = extract_subprompt(result_text)
        logger.info(f"[RLM] depth={depth} root={scope.root_id} decomposing → depth={depth+1}")

        # Recurse — serialized, awaited
        sub_result = await _rlm_recurse(
            ctx, scope, sub_prompt, depth + 1, max_depth, max_tokens
        )

        # Record sub-result at this depth
        scope.add_sub_result(depth, sub_result)

        # Synthesize sub-result back into parent task
        synth_prompt = build_synthesis_prompt(prompt, sub_result)
        synth = await ctx.sample(
            messages=synth_prompt,
            system_prompt=sys_prompt,
            max_tokens=max_tokens,
        )
        synthesis = synth.text if hasattr(synth, 'text') else str(synth)

        # Update stored result
        scope.set(depth, synthesis)
        return synthesis

    # Direct answer
    answer = extract_direct_answer(result_text)
    scope.set(depth, answer)
    return answer


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------
@mcp.tool()
async def rlm_query(
    ctx: Context,
    prompt: str,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    """Recursive Language Model query — decomposes complex tasks into sub-tasks, each getting its own fresh context window.

    Args:
        prompt: The task or question to reason about
        max_depth: Maximum recursion depth (default 4)
        max_tokens: Max tokens per sampling call (default 4096)
    """
    # Unique root per invocation — concurrent roots are isolated
    root_id = f"{ctx.request_id or 'manual'}:{uuid.uuid4().hex[:8]}"

    async with store.root_scope(root_id) as scope:
        scope.meta["prompt"] = prompt
        scope.meta["max_depth"] = max_depth
        logger.info(f"[RLM] root={root_id} starting (max_depth={max_depth})")

        result = await _rlm_recurse(
            ctx, scope, prompt, depth=0, max_depth=max_depth, max_tokens=max_tokens
        )

        logger.info(f"[RLM] root={root_id} completed")
        return result


@mcp.tool()
async def rlm_status(ctx: Context) -> str:
    """Check RLM server status — active roots, configuration."""
    return (
        f"RLM Server Status\n"
        f"  Active roots: {store.scope_count}\n"
        f"  Root IDs: {store.active_roots}\n"
        f"  Default max_depth: {DEFAULT_MAX_DEPTH}\n"
        f"  Default max_tokens: {DEFAULT_MAX_TOKENS}\n"
    )
