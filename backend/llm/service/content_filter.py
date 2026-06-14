"""Compress bulky tool-output regurgitation from persisted message content.

The live SSE stream is never touched — only the copy written to
Message.content in the DB gets filtered. This prevents the model's
tendency to dump raw file contents / search results into its response
from poisoning conversation history with multi-KB blobs.
"""

import re

_MAX_BLOCK_LINES = 20
_MAX_LINE_LENGTH = 120


def _min_indent(lines: list[str]) -> int:
    indent = 999
    for ln in lines:
        stripped = ln.lstrip()
        if stripped:
            indent = min(indent, len(ln) - len(stripped))
    return indent if indent < 999 else 0


def _collapse_code_fence_block(text: str, fence: str, label: str) -> str:
    lines = text.split("\n")
    result = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped == fence or stripped.startswith(fence) and stripped[len(fence):].lstrip().isidentifier():
            lang = stripped[len(fence):].strip()
            fence_end = i
            for j in range(i + 1, len(lines)):
                if lines[j].strip() == fence:
                    fence_end = j
                    break
            content_lines = lines[i + 1:fence_end]
            if len(content_lines) > _MAX_BLOCK_LINES:
                result.append(f"{fence}{lang}")
                result.append(f"[~s3~ {label}: {len(content_lines)} lines, compressed — not shown in history]")
                result.append(fence)
                i = fence_end + 1
                continue
        result.append(lines[i])
        i += 1
    return "\n".join(result)


def _collapse_line_numbered_blocks(text: str) -> str:
    lines = text.split("\n")
    result = []
    i = 0
    while i < len(lines):
        if re.match(r"^\s*\d{1,4}[:.]\s", lines[i]):
            block_start = i
            while i < len(lines) and re.match(r"^\s*\d{1,4}[:.]\s", lines[i][:_MAX_LINE_LENGTH]):
                i += 1
            block_lines = i - block_start
            if block_lines > _MAX_BLOCK_LINES:
                result.append(f"[~s3~ numbered-block: {block_lines} lines, compressed — not shown in history]")
            else:
                result.extend(lines[block_start:i])
        else:
            result.append(lines[i])
            i += 1
    return "\n".join(result)


def compress_tool_dumps(text: str, max_block_lines: int = _MAX_BLOCK_LINES) -> str:
    if not text or len(text) < 2000:
        return text

    result = _collapse_code_fence_block(text, "```", "code-block")
    result = _collapse_code_fence_block(result, "~~~", "code-block")
    result = _collapse_line_numbered_blocks(result)

    return result
