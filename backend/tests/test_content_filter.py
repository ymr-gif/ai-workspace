"""Unit tests for S3 content filter — run with: pytest backend/tests/test_content_filter.py -v"""

import pytest
from llm.service.content_filter import compress_tool_dumps

# Pad short texts past the 2000-char early-exit guard
_PAD = "x" * 2500


def _mk(body: str) -> str:
    """Prefix text with padding to exceed the 2000-char quick-exit threshold."""
    return _PAD + "\n" + body


def test_short_text_passes_through():
    """Text under 2000 chars is returned unchanged."""
    short = "Hello, this is a short response."
    assert compress_tool_dumps(short) == short


def test_empty_text():
    assert compress_tool_dumps("") == ""
    assert compress_tool_dumps(None) is None


def test_small_code_block_unchanged():
    """Code blocks under 20 lines are not compressed."""
    text = "Here is the result:\n```python\nx = 1\ny = 2\n```\nDone."
    assert compress_tool_dumps(_mk(text)) == _mk(text)


def test_large_code_block_compressed():
    """Code blocks over 20 lines are replaced with a compact reference."""
    lines = [f"line {i}" for i in range(25)]
    body = "\n".join(lines)
    text = f"Here is the file:\n```\n{body}\n```\nEnd."
    result = compress_tool_dumps(_mk(text))
    assert "[~s3~ code-block: 25 lines, compressed" in result
    assert "line 0" not in result
    assert "line 24" not in result


def test_large_code_block_with_lang_compressed():
    """Language tag on the fence is preserved in the placeholder."""
    lines = [f"def foo{i}: pass" for i in range(30)]
    body = "\n".join(lines)
    text = f"```python\n{body}\n```"
    result = compress_tool_dumps(_mk(text))
    assert "[~s3~ code-block: 30 lines, compressed" in result
    assert "def foo0" not in result


def test_large_line_numbered_block_compressed():
    """Consecutive numbered lines over 20 are compressed."""
    lines = [f"{i}: content line {i}" for i in range(25)]
    body = "\n".join(lines)
    text = f"Results:\n{body}\nDone."
    result = compress_tool_dumps(_mk(text))
    assert "[~s3~ numbered-block: 25 lines, compressed" in result
    assert "0: content" not in result


def test_mixed_content():
    """Short prose before large blocks — only the large blocks are compressed."""
    preamble = "Here is what I found:\n\n"
    code_lines = [f"print({i})" for i in range(30)]
    code_block = "```\n" + "\n".join(code_lines) + "\n```"
    text = preamble + code_block + "\n\nLet me know if you need changes."
    result = compress_tool_dumps(_mk(text))
    assert "[~s3~ code-block: 30 lines, compressed" in result
    assert "Here is what I found:" in result
    assert "Let me know if you need changes." in result
    assert "print(0)" not in result


def test_no_false_positive_short_numbered():
    """Short numbered list (under threshold) is untouched."""
    text = "Steps:\n1: first\n2: second\n3: third\nDone."
    assert compress_tool_dumps(_mk(text)) == _mk(text)


def test_multiple_large_blocks():
    """Multiple large blocks are each compressed independently."""
    a_lines = "\n".join([f"a{i}" for i in range(25)])
    b_lines = "\n".join([f"{i}: val" for i in range(30)])
    text = f"File A:\n```\n{a_lines}\n```\nFile B:\n{b_lines}\nEnd."
    result = compress_tool_dumps(_mk(text))
    assert "[~s3~ code-block: 25 lines" in result
    assert "[~s3~ numbered-block: 30 lines" in result


def test_tilde_fence_also_detected():
    lines = [f"line {i}" for i in range(22)]
    body = "\n".join(lines)
    text = f"```\n{body}\n```"
    result = compress_tool_dumps(_mk(text))
    assert "[~s3~ code-block:" in result
