"""
RLM Context Store — call-tree-scoped lifetime, not wall-clock TTL.

Context lives exactly as long as the root invocation is active.
Evicts atomically when depth 0 returns (via asynccontextmanager finally).
"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RLMScope:
    """Isolated scope for one root RLM invocation."""
    root_id: str
    # depth -> accumulated context string
    store: dict[int, str] = field(default_factory=dict)
    # depth -> list of sub-call results that bubbled up
    sub_results: dict[int, list[str]] = field(default_factory=dict)
    # metadata for observability
    meta: dict[str, Any] = field(default_factory=dict)

    def set(self, depth: int, value: str) -> None:
        self.store[depth] = value

    def get(self, depth: int) -> str | None:
        return self.store.get(depth)

    def add_sub_result(self, depth: int, result: str) -> None:
        if depth not in self.sub_results:
            self.sub_results[depth] = []
        self.sub_results[depth].append(result)


class RLMContextStore:
    """
    Manages RLM scopes. Each root invocation gets an isolated scope
    that lives exactly as long as the call tree is active.
    """

    def __init__(self) -> None:
        self._scopes: dict[str, RLMScope] = {}

    @asynccontextmanager
    async def root_scope(self, root_id: str):
        """Create an isolated scope that auto-evicts when the root completes."""
        scope = RLMScope(root_id=root_id)
        self._scopes[root_id] = scope
        try:
            yield scope
        finally:
            # atomic eviction — even if exception or client disconnect
            self._scopes.pop(root_id, None)

    def get_scope(self, root_id: str) -> RLMScope | None:
        """Look up a scope (for observability/debugging)."""
        return self._scopes.get(root_id)

    @property
    def active_roots(self) -> list[str]:
        """Currently active root IDs."""
        return list(self._scopes.keys())

    @property
    def scope_count(self) -> int:
        return len(self._scopes)
