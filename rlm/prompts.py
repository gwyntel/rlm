"""
RLM Prompt Engineering — how we tell the LLM to decompose or answer.

No tools version: the LLM decides via structured output markers
whether to recurse or answer directly.
"""

# System prompt for the RLM reasoning engine
RLM_SYSTEM_PROMPT = """You are a Recursive Language Model (RLM) reasoning engine.

You receive tasks that may need decomposition into sub-tasks. For each task:

1. If the task is simple enough to answer directly, just answer it.
2. If the task needs decomposition, output EXACTLY ONE sub-task in this format:

    <<DECOMPOSE>>
    [describe the single sub-task here]
    <</DECOMPOSE>>

Rules:
- Decompose into ONE sub-task at a time (not multiple)
- The sub-task should be smaller/simpler than the current task
- Each sub-task gets its own fresh context window
- You can chain decomposition by having sub-tasks decompose further
- Prefer decomposition for: large codebases, multi-step analysis, 
  anything that would benefit from focused attention
- Answer directly for: simple lookups, short explanations, single-file questions
- Do NOT decompose if you're at maximum depth — answer directly

Current depth: {depth}
Maximum depth: {max_depth}
{at_max_depth}
"""

AT_MAX_DEPTH_NOTE = "\n⚠️ You are at maximum recursion depth. You MUST answer directly — do not decompose.\n"

# Markers for decomposition detection
DECOMPOSE_OPEN = "<<DECOMPOSE>>"
DECOMPOSE_CLOSE = "<</DECOMPOSE>>"


def build_system_prompt(depth: int, max_depth: int) -> str:
    """Build the system prompt with current depth info."""
    at_max = AT_MAX_DEPTH_NOTE if depth >= max_depth - 1 else ""
    return RLM_SYSTEM_PROMPT.format(
        depth=depth,
        max_depth=max_depth,
        at_max_depth=at_max,
    )


def build_user_prompt(prompt: str, prior_context: str | None = None, sub_results: list[str] | None = None) -> str:
    """Build the user prompt with optional prior context and sub-results."""
    parts = []

    if prior_context:
        parts.append(f"Previous context:\n{prior_context}\n")

    parts.append(f"Task: {prompt}")

    if sub_results:
        parts.append("Sub-task results:")
        for i, r in enumerate(sub_results, 1):
            parts.append(f"  [{i}] {r}")

    return "\n".join(parts)


def needs_decomposition(text: str) -> bool:
    """Check if the LLM output requests decomposition."""
    return DECOMPOSE_OPEN in text and DECOMPOSE_CLOSE in text


def extract_subprompt(text: str) -> str:
    """Extract the sub-task description from decomposition markers."""
    start = text.index(DECOMPOSE_OPEN) + len(DECOMPOSE_OPEN)
    end = text.index(DECOMPOSE_CLOSE)
    return text[start:end].strip()


def extract_direct_answer(text: str) -> str:
    """
    Extract the direct answer from LLM output.
    If it contains decomposition markers, strip them and return the rest.
    Otherwise return the full text.
    """
    if needs_decomposition(text):
        # Return text before/after the decompose block as context
        before = text[:text.index(DECOMPOSE_OPEN)].strip()
        after = text[text.index(DECOMPOSE_CLOSE) + len(DECOMPOSE_CLOSE):].strip()
        parts = [p for p in (before, after) if p]
        return "\n".join(parts) if parts else extract_subprompt(text)
    return text.strip()


def build_synthesis_prompt(original: str, sub_result: str) -> str:
    """Build prompt for synthesizing sub-result back into the parent task."""
    return f"""Original task: {original}

A sub-task was completed with this result:
{sub_result}

Synthesize this sub-result with the original task. Provide a complete answer that incorporates the sub-task's findings."""
