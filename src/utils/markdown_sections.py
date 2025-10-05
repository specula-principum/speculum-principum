"""Utility helpers for manipulating Markdown sections in issue bodies."""

from __future__ import annotations

import re
from typing import Optional, Pattern

_SECTION_CACHE: dict[tuple[int, str], Pattern[str]] = {}


def _compile_section_pattern(level: int, heading: str) -> Pattern[str]:
    key = (level, heading)
    if key not in _SECTION_CACHE:
        escaped_heading = re.escape(heading.strip())
        pattern = rf"(?ms)(^{'#' * level}\s+{escaped_heading}\s*$\n?)(.*?)(?=^{'#' * level}\s+|^{'#' * (level - 1)}\s+|\Z)"
        _SECTION_CACHE[key] = re.compile(pattern)
    return _SECTION_CACHE[key]


def upsert_section(markdown: str, heading: str, new_content: str, *, level: int = 2) -> str:
    """Insert or replace the content of a Markdown section.

    Args:
        markdown: Existing Markdown content.
        heading: Heading text without the leading hashes (e.g. "AI Assessment").
        new_content: Content to place under the heading. It may span multiple lines.
        level: Heading level to target (default: 2 → ``##``).

    Returns:
        Updated Markdown content with the section replaced or appended.
    """

    heading_line = f"{'#' * level} {heading}".rstrip()
    stripped_content = new_content.strip()
    replacement_block = f"{heading_line}\n\n{stripped_content}\n"

    if not markdown:
        return f"{replacement_block}\n"

    pattern = _compile_section_pattern(level, heading)

    if pattern.search(markdown):
        # Replace existing section content
        def _replace(_: re.Match[str]) -> str:
            return f"{heading_line}\n\n{stripped_content}\n\n"

        updated = pattern.sub(_replace, markdown, count=1)
    else:
        separator = "\n\n" if markdown.endswith("\n") else "\n\n"
        updated = f"{markdown}{separator}{replacement_block}\n"

    # Normalise triple newlines left by replacement
    updated = re.sub(r"\n{3,}", "\n\n", updated).strip() + "\n"
    return updated


def extract_section(markdown: str, heading: str, *, level: int = 2) -> Optional[str]:
    """Return the content within a Markdown section if it exists.

    Args:
        markdown: Markdown document to inspect.
        heading: Heading text without leading hashes.
        level: Heading level (default ``##``).

    Returns:
        Section contents with surrounding whitespace trimmed, or ``None`` if missing.
    """

    if not markdown:
        return None

    pattern = _compile_section_pattern(level, heading)
    match = pattern.search(markdown)
    if not match:
        return None

    # Group 2 captures the body between the heading and the next section
    content = match.group(2).strip()
    return content or None
