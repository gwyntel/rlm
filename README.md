# RLM — Recursive Language Model

A Recursive Language Model server built on [FastMCP](https://gofastmcp.com) with [MCP sampling](https://modelcontextprotocol.io/specification/2025-11-25/server/sampling).

> **Inspired by** [axon](https://github.com/Diogenesoftoronto/axon) by [Diogenesoftoronto](https://github.com/Diogenesoftoronto) — a Recursive Language Model engine in Rust. The RLM concept and architecture originate from their work and the [Zhang/Kraska/Khattab paper on recursive LLM decomposition](https://arxiv.org/abs/2504.01922).

## What It Does

RLM decomposes complex tasks into sub-tasks, each getting its own fresh context window via MCP sampling. The root LLM orchestrates, sub-LLMs handle focused sub-problems, results bubble back up.

**The key insight:** context window size is the wrong abstraction to scale. Instead, decompose problems recursively — each sub-LLM gets a scoped context, results flow back up the call tree.

## Architecture

```
┌─────────────────────────────────────┐
│  Host (Claude Code, Hermes, etc.)   │
│  ┌───────────────────────────────┐  │
│  │  API keys live here           │  │
│  │  LLM connection lives here   │  │
│  └───────────────────────────────┘  │
│         │ ctx.sample()             │
│         ▼                           │
│  ┌───────────────────────────────┐  │
│  │  RLM FastMCP Server          │  │
│  │  ┌─────────────────────────┐ │  │
│  │  │  Call-tree-scoped store │ │  │
│  │  │  depth 0: root task     │ │  │
│  │  │  depth 1: sub-task A    │ │  │
│  │  │  depth 2: sub-task A.1  │ │  │
│  │  └─────────────────────────┘ │  │
│  │  No API keys. No disk I/O.  │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

### Call-Tree-Scoped Lifetime

Context doesn't use wall-clock TTL. It lives exactly as long as the root invocation is active and **evicts atomically when depth 0 returns** — like stack frames, but explicit in the heap.

```python
# Every root invocation gets an isolated scope
async with store.root_scope(root_id) as scope:
    result = await _rlm_recurse(ctx, scope, prompt, depth=0, ...)
# ← scope is gone here. no orphans, no leaks, no tuning.
```

### MCP Sampling = Zero Credential Surface

The server never holds API keys. It calls `ctx.sample()` which routes through the host's LLM connection. The host executes the completion, the server just gets the result.

```python
# In the RLM tool — server never sees credentials
result = await ctx.sample(
    messages=prompt,
    system_prompt=sys_prompt,
    max_tokens=4096,
)
```

### Decomposition Protocol

The LLM decides whether to decompose or answer directly via structured markers:

```
<<DECOMPOSE>>
Analyze the authentication module for security issues
<</DECOMPOSE>>
```

If decomposition is requested, the server:
1. Extracts the sub-prompt
2. Recurses via `ctx.sample()` at depth+1
3. Synthesizes the sub-result back into the parent task

If at maximum depth, the LLM is instructed to answer directly.

## Installation

```bash
pip install -e .
```

Or from PyPI (once published):

```bash
pip install rlm
```

## Usage

### Local (stdio) — for Claude Desktop, Cursor, etc.

```bash
fastmcp run rlm.server:mcp
```

### Local (HTTP) — for development and testing

```bash
fastmcp run rlm.server:mcp --transport http --port 8000
```

### Remote — Prefect Horizon

Push to GitHub → deploy at [horizon.prefect.io](https://horizon.prefect.io) → get a `https://<name>.fastmcp.app/mcp` URL.

See [Deployment](#deployment) below.

### MCP Tools

| Tool | Description |
|------|-------------|
| `rlm_query` | Recursive decomposition query. Give it a complex task, it decomposes and solves. |
| `rlm_status` | Server status — active roots, configuration. |

#### `rlm_query` Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `prompt` | `str` | required | The task or question to reason about |
| `max_depth` | `int` | `4` | Maximum recursion depth |
| `max_tokens` | `int` | `4096` | Max tokens per sampling call |

## Example

```
User: "Audit this 400-file codebase for security vulnerabilities"

RLM depth 0: "This is too large for one context window."
           → DECOMPOSE: "Analyze the authentication and authorization modules"

RLM depth 1: "Found 3 issues in auth module..."
           → DECOMPOSE: "Deep dive into the JWT validation logic"

RLM depth 2: "JWT validation has a critical flaw — no expiry check..."

RLM depth 1: Synthesizes depth 2 result into auth audit
           → "Authentication issues: [JWT flaw + 2 others]..."

RLM depth 0: Synthesizes depth 1 result into full audit
           → "Security audit complete. Critical: 1, High: 3, Medium: 7..."
```

## Configuration

Configuration is via tool parameters at invocation time. No config files, no environment variables, no API keys needed in the server.

| Setting | Default | Description |
|---------|---------|-------------|
| `max_depth` | 4 | Maximum recursion depth before forcing direct answers |
| `max_tokens` | 4096 | Maximum tokens per LLM sampling call |

## Deployment

### Prefect Horizon (Recommended for Production)

1. Push this repo to GitHub
2. Sign in to [horizon.prefect.io](https://horizon.prefect.io) with GitHub
3. Select the repo → set entrypoint to `rlm.server:mcp`
4. Deploy → server goes live at `https://<name>.fastmcp.app/mcp`

Features:
- Auto-redeploys on push to `main`
- Preview deployments for PRs
- Built-in OAuth 2.1 authentication
- Scale to zero when idle

### Self-Hosted (HTTP)

```bash
fastmcp run rlm.server:mcp --transport http --host 0.0.0.0 --port 8000
```

### Docker

```bash
docker build -t rlm .
docker run -p 8000:8000 rlm
```

## How It Differs from axon

| Feature | axon (Rust) | RLM (Python/FastMCP) |
|---------|-------------|----------------------|
| Language | Rust | Python |
| MCP transport | Hand-rolled stdio | FastMCP decorators |
| LLM calls | Direct API (env var keys) | MCP sampling (host-mediated, zero credentials) |
| Context store | Flat files on disk | In-memory, call-tree-scoped |
| Context lifetime | Manual cleanup | Automatic — evicts with root scope |
| Sandbox | ouros (embedded Python in Rust) | Not yet (planned) |
| Token budget | None | Per-call max_tokens |
| Recursion control | `--max-depth`, `--max-iterations` | `max_depth` parameter |

## Roadmap

- [ ] **Sandbox backends** — RestrictedPython (lightweight), subprocess+JSON (default), Docker (paranoid)
- [ ] **Token budget per depth** — different token limits at different recursion depths
- [ ] **Structured decomposition** — `result_type` with Pydantic models for typed sub-results
- [ ] **Parallel decomposition** — spawn multiple sub-tasks at the same depth
- [ ] **Observability** — logging/tracing for the full call tree
- [ ] **Persistence** — optional SQLite backend for context store (survives server restart)

## Credits

- **[Diogenesoftoronto/axon](https://github.com/Diogenesoftoronto/axon)** — Original RLM implementation in Rust. The recursive decomposition architecture, the `llm_query()` → sub-RLM spawning pattern, and the depth-guarded recursion model all originate from this project.
- **[Zhang, Kraska, Khattab — Recursive Language Models](https://arxiv.org/abs/2504.01922)** — The academic paper formalizing recursive LLM decomposition.
- **[FastMCP](https://gofastmcp.com)** — The Python MCP framework that makes this server trivially deployable.
- **[Model Context Protocol](https://modelcontextprotocol.io)** — The spec that makes sampling possible, enabling zero-credential server-side LLM calls.

## License

AGPL-3.0-or-later — see [LICENSE](LICENSE).

This is a clean rewrite (Python, not a Rust port), but we license under AGPL in the same spirit as axon to give back to the commons.
