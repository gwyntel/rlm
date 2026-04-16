"""Top-level entrypoint for FastMCP Cloud deployment.

FastMCP Cloud loads the entrypoint as a FILE (not a module),
so relative imports in rlm/server.py break. This file bridges
that gap by importing from the installed rlm package.
"""
from rlm.server import mcp  # noqa: F401
