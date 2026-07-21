"""Frontier-style response layer — style block composition + per-intent depth hints.
No live NIM/DB; exercises build_context_messages + apply_context_budget directly.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("NVIDIA_API_KEY", "test-key")
os.environ.setdefault("DATABASE_URL",   "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("REDIS_URL",      "redis://localhost:6379/0")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")

from llm.service.context import (
    ANTI_FABRICATION,
    CUSTOM_PROMPT_BRIDGE,
    DEPTH_HINTS,
    STYLE_BLOCK,
    apply_context_budget,
    build_context_messages,
)


def _build(**kw):
    defaults = dict(
        memory_sheet="", project_summary="", retrieved_chunks=[],
        history_summary="", history=[],
    )
    defaults.update(kw)
    return build_context_messages(**defaults)


# ── first system message composition ─────────────────────────────────────────

def test_default_path_has_style_and_antifab():
    msgs = _build()
    head = msgs[0]
    assert head["role"] == "system"
    assert STYLE_BLOCK in head["content"]
    assert ANTI_FABRICATION in head["content"]
    assert head["content"].index(STYLE_BLOCK) < head["content"].index(ANTI_FABRICATION)


def test_custom_sysprompt_keeps_style_and_antifab():
    msgs = _build(system_prompt="You are a pirate.")
    head = msgs[0]["content"]
    assert STYLE_BLOCK in head
    assert ANTI_FABRICATION in head
    assert CUSTOM_PROMPT_BRIDGE in head
    assert "You are a pirate." in head
    # custom text comes after the defaults it may override
    assert head.index("You are a pirate.") > head.index(ANTI_FABRICATION)


def test_file_notice_path_composes_all():
    msgs = _build(file_names=["notes.md"], file_ids=["f1"])
    head = msgs[0]["content"]
    assert STYLE_BLOCK in head
    assert ANTI_FABRICATION in head
    assert "notes.md (id=f1)" in head

    msgs = _build(system_prompt="Custom.", file_names=["notes.md"], file_ids=["f1"])
    head = msgs[0]["content"]
    assert STYLE_BLOCK in head and ANTI_FABRICATION in head
    assert "Custom." in head and "notes.md (id=f1)" in head
    # file notice is last
    assert head.index("notes.md (id=f1)") > head.index("Custom.")


# ── per-intent depth hints ────────────────────────────────────────────────────

def test_intent_hint_appended_last():
    for intent in ("question", "task", "exploration"):
        msgs = _build(intent=intent)
        assert msgs[-1] == {"role": "system", "content": DEPTH_HINTS[intent]}

    # hint stays last even after the [FILE CONTEXT] block
    msgs = _build(intent="question", file_chunks=["chunk one"],
                  history=[{"role": "user", "content": "hi"}])
    assert msgs[-1]["content"] == DEPTH_HINTS["question"]
    assert "[FILE CONTEXT]" in msgs[-3]["content"]


def test_closing_hint_minimal_and_unknown_intent_none():
    msgs = _build(intent="closing")
    assert msgs[-1]["content"] == DEPTH_HINTS["closing"]
    assert "Do not re-answer" in DEPTH_HINTS["closing"]

    msgs = _build(intent="nonsense")
    assert msgs[-1]["role"] != "system" or DEPTH_HINTS.get("nonsense", "") == ""
    assert msgs[-1]["content"] not in DEPTH_HINTS.values()


def test_default_intent_is_question():
    msgs = _build()
    assert msgs[-1]["content"] == DEPTH_HINTS["question"]


# ── precedence guard ─────────────────────────────────────────────────────────

def test_precedence_clause_present():
    assert "Precedence" in STYLE_BLOCK
    assert "[USER STATE]" in STYLE_BLOCK
    assert "always wins" in STYLE_BLOCK


# ── budget allocator never drops the style head or the hint ──────────────────

def test_budget_never_drops_style_or_hint():
    msgs = _build(
        intent="exploration",
        memory_sheet="fact one\nfact two",
        project_summary="p" * 4000,
        retrieved_chunks=["r" * 4000],
        history_summary="h" * 4000,
        history=[{"role": "user", "content": "u" * 4000}],
        last_session="s" * 4000,
    )
    trimmed = apply_context_budget(list(msgs), context_window=2000)
    assert STYLE_BLOCK in trimmed[0]["content"]
    assert trimmed[-1]["content"] == DEPTH_HINTS["exploration"]
