# Contributing

Thanks for your interest in RLM! Here's how to get started.

## Development Setup

```bash
# Clone and install
git clone https://github.com/gwyntel/rlm.git
cd rlm
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v

# Run the server locally
fastmcp run rlm.server:mcp
```

## Architecture Overview

The server is intentionally minimal — three files:

- **`rlm/store.py`** — `RLMContextStore` + `RLMScope`. Call-tree-scoped context lifetime via async context managers.
- **`rlm/prompts.py`** — Prompt engineering. System prompt construction, decomposition detection, sub-prompt extraction.
- **`rlm/server.py`** — FastMCP server. `rlm_query` tool, `_rlm_recurse` core loop, `rlm_status` status tool.

### Adding Features

The server uses MCP sampling for all LLM calls (`ctx.sample()`). This means:

1. **No API keys** in the server process — the host holds credentials
2. **Sampling is sequential** — each `await ctx.sample()` blocks before proceeding
3. **Context is scoped** — don't store state outside `RLMScope` or it'll outlive the call tree

### Sandbox Backends (Planned)

The `Sandbox` interface is the seam for pluggable execution environments:

1. **RestrictedPython** — easy namespace threading, leaky isolation
2. **subprocess + JSON** — real isolation, serializable state only (recommended default)
3. **Docker exec** — true isolation, full namespace via mounted tmpfs

When adding a sandbox backend, implement the `execute(code: str) -> str` interface and register it.

## Submitting Changes

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Add tests if applicable
5. Submit a PR with a clear description

## License

By contributing, you agree your code will be licensed under AGPL-3.0-or-later.
