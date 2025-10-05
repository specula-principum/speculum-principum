from src.utils.markdown_sections import extract_section, upsert_section


def test_upsert_section_replaces_existing_block():
    original = """# Title

## AI Assessment

_Pending content._

## Other Section

Keep this.
"""

    updated = upsert_section(original, "AI Assessment", "**Summary**\n- Updated insight")

    assert "_Pending content._" not in updated
    assert "## AI Assessment" in updated
    assert "**Summary**" in updated
    assert "## Other Section" in updated


def test_upsert_section_appends_when_missing():
    original = "# Title\n\nContent here.\n"

    updated = upsert_section(original, "AI Assessment", "Line one\nLine two")

    assert updated.strip().endswith("Line two")
    assert "## AI Assessment" in updated
    # Ensure original content untouched
    assert updated.startswith(original.strip())


def test_upsert_section_handles_empty_markdown():
    updated = upsert_section("", "AI Assessment", "Details")

    assert updated.startswith("## AI Assessment")
    assert "Details" in updated


def test_extract_section_returns_content():
    markdown = """# Title

## AI Assessment

Line one

## Specialist Guidance

Another section
"""

    content = extract_section(markdown, "AI Assessment")

    assert content is not None
    assert "Line one" in content


def test_extract_section_missing_returns_none():
    markdown = "# Title\n\nContent."

    assert extract_section(markdown, "AI Assessment") is None
