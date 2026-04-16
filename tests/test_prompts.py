"""Tests for RLM prompt engineering."""

import pytest

from rlm.prompts import (
    build_system_prompt,
    build_user_prompt,
    needs_decomposition,
    extract_subprompt,
    extract_direct_answer,
    build_synthesis_prompt,
    AT_MAX_DEPTH_NOTE,
)


def test_system_prompt_depth_0():
    sp = build_system_prompt(depth=0, max_depth=4)
    assert "Current depth: 0" in sp
    assert "Maximum depth: 4" in sp
    assert "⚠️" not in sp


def test_system_prompt_at_max_depth():
    sp = build_system_prompt(depth=3, max_depth=4)
    assert "⚠️" in sp
    assert AT_MAX_DEPTH_NOTE.strip() in sp


def test_system_prompt_below_max():
    sp = build_system_prompt(depth=2, max_depth=4)
    assert "⚠️" not in sp


def test_user_prompt_basic():
    up = build_user_prompt("Analyze the codebase")
    assert "Task: Analyze the codebase" in up


def test_user_prompt_with_context():
    up = build_user_prompt("Analyze the codebase", prior_context="Previous findings: ...")
    assert "Previous context:" in up
    assert "Previous findings: ..." in up


def test_user_prompt_with_sub_results():
    up = build_user_prompt("Synthesize", sub_results=["auth has 3 issues", "API has 2 issues"])
    assert "Sub-task results:" in up
    assert "[1] auth has 3 issues" in up
    assert "[2] API has 2 issues" in up


def test_needs_decomposition_yes():
    text = "I need to dig deeper. <<DECOMPOSE>>Check the auth module<</DECOMPOSE>> Then synthesize."
    assert needs_decomposition(text) is True


def test_needs_decomposition_no():
    text = "The answer is 42."
    assert needs_decomposition(text) is False


def test_needs_decomposition_partial_marker():
    text = "Let me <<DECOMPOSE>> but never close it"
    assert needs_decomposition(text) is False


def test_extract_subprompt():
    text = "Thinking... <<DECOMPOSE>>\nAnalyze the JWT validation logic\n<</DECOMPOSE>> Continue."
    assert extract_subprompt(text) == "Analyze the JWT validation logic"


def test_extract_subprompt_multiline():
    text = "<<DECOMPOSE>>\nCheck auth module\nFocus on token expiry\n<</DECOMPOSE>>"
    result = extract_subprompt(text)
    assert "Check auth module" in result
    assert "Focus on token expiry" in result


def test_extract_direct_answer():
    assert extract_direct_answer("The answer is 42.") == "The answer is 42."


def test_extract_direct_answer_from_decomposition():
    text = "Some preamble. <<DECOMPOSE>>sub task<</DECOMPOSE>> Some postamble."
    result = extract_direct_answer(text)
    assert "Some preamble" in result
    assert "Some postamble" in result
    # The decompose block content should NOT be in the direct answer
    assert "sub task" not in result or "Some" in result


def test_build_synthesis_prompt():
    sp = build_synthesis_prompt("Original task", "Sub-task found 3 issues")
    assert "Original task" in sp
    assert "Sub-task found 3 issues" in sp
    assert "Synthesize" in sp
