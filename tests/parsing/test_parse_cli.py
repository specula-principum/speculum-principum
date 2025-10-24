"""End-to-end tests for the parsing CLI surface in main.py."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Iterable

from docx import Document as DocxBuilder  # type: ignore[import]

from main import main as main_entry


def _write_pdf(path: Path, text: str) -> None:
    path.write_bytes(_build_pdf_bytes(text))


def _build_pdf_bytes(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", r"\(").replace(")", r"\)")
    stream = f"BT\n/F1 24 Tf\n72 720 Td\n({escaped}) Tj\nET\n"

    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = (
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    )
    stream_bytes = stream.encode("latin-1")
    obj4 = (
        f"4 0 obj\n<< /Length {len(stream_bytes)} >>\nstream\n".encode("ascii")
        + stream_bytes
        + b"endstream\nendobj\n"
    )
    obj5 = b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    obj6 = b"6 0 obj\n<< /Producer (speculum-principum tests) >>\nendobj\n"

    header = b"%PDF-1.4\n"
    objects = [obj1, obj2, obj3, obj4, obj5, obj6]

    content = bytearray()
    content.extend(header)

    offsets = [0]
    for obj in objects:
        offsets.append(len(content))
        content.extend(obj)

    xref_pos = len(content)
    content.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    content.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        content.extend(f"{offset:010} 00000 n \n".encode("ascii"))

    trailer = (
        f"trailer\n<< /Root 1 0 R /Info 6 0 R /Size {len(offsets)} >>\n".encode("ascii")
        + f"startxref\n{xref_pos}\n%%EOF\n".encode("ascii")
    )
    content.extend(trailer)
    return bytes(content)


def _write_docx(path: Path, title: str, paragraphs: Iterable[str]) -> None:
    document = DocxBuilder()
    document.add_heading(title, level=1)
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    document.save(str(path))


def _write_html(path: Path, title: str, body: str) -> None:
    html = f"""
    <html>
      <head><title>{title}</title></head>
      <body>
        <article>
          <h1>{title}</h1>
          <p>{body}</p>
        </article>
      </body>
    </html>
    """.strip()
    path.write_text(html, encoding="utf-8")


def _load_manifest_entries(output_root: Path) -> list[dict[str, object]]:
    manifest_path = output_root / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return list(payload.get("entries", []))


def test_parse_cli_pdf_subcommand(tmp_path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    pdf_path = workspace / "example.pdf"
    _write_pdf(pdf_path, "CLI PDF content")

    output_root = workspace / "artifacts"

    exit_code = main_entry([
        "parse",
        "--output-root",
        str(output_root),
        "pdf",
        str(pdf_path),
    ])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[completed]" in captured.out
    assert "via pdf" in captured.out

    resolved_output = output_root.resolve()
    entries = _load_manifest_entries(resolved_output)
    assert len(entries) == 1

    entry = entries[0]
    assert entry["parser"] == "pdf"

    artifact_path = resolved_output / entry["artifact_path"]
    assert artifact_path.exists()
    metadata = entry.get("metadata")
    if metadata:
        assert isinstance(metadata, dict)
        assert "page_files" not in metadata
    segment_files = sorted(
        path for path in artifact_path.parent.glob("*.md") if path.name != "index.md"
    )
    assert segment_files, "expected at least one segment artifact"
    page_path = segment_files[0]
    artifact_text = page_path.read_text(encoding="utf-8")
    assert "CLI PDF content" in artifact_text
    assert "warnings:" not in artifact_text


def test_parse_cli_docx_subcommand(tmp_path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    docx_path = workspace / "example.docx"
    _write_docx(docx_path, "CLI DOCX Document", ["First paragraph", "Second paragraph"])

    output_root = workspace / "docx-output"

    exit_code = main_entry([
        "parse",
        "--output-root",
        str(output_root),
        "docx",
        str(docx_path),
    ])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[completed]" in captured.out
    assert "via docx" in captured.out

    resolved_output = output_root.resolve()
    entries = _load_manifest_entries(resolved_output)
    assert len(entries) == 1

    entry = entries[0]
    assert entry["parser"] == "docx"
    artifact_path = resolved_output / entry["artifact_path"]
    assert artifact_path.exists()
    metadata = entry.get("metadata")
    if metadata:
        assert isinstance(metadata, dict)
        assert "page_files" not in metadata
    segment_files = sorted(
        path for path in artifact_path.parent.glob("*.md") if path.name != "index.md"
    )
    assert segment_files, "expected at least one segment artifact"
    page_contents = [path.read_text(encoding="utf-8") for path in segment_files]
    assert any("CLI DOCX Document" in text for text in page_contents)
    assert any("First paragraph" in text for text in page_contents)
    assert any("Second paragraph" in text for text in page_contents)
    assert any("page_unit: segment" in text for text in page_contents)
    assert all("warnings:" not in text for text in page_contents)


def test_parse_cli_web_subcommand_with_local_html(tmp_path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    html_path = workspace / "page.html"
    _write_html(html_path, "CLI HTML Title", "Body content from HTML")

    output_root = workspace / "web-output"

    exit_code = main_entry([
        "parse",
        "--output-root",
        str(output_root),
        "web",
        str(html_path),
    ])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "[completed]" in captured.out
    assert "via web" in captured.out

    resolved_output = output_root.resolve()
    entries = _load_manifest_entries(resolved_output)
    assert len(entries) == 1

    entry = entries[0]
    assert entry["parser"] == "web"
    artifact_path = resolved_output / entry["artifact_path"]
    assert artifact_path.exists()
    metadata = entry.get("metadata")
    if metadata:
        assert isinstance(metadata, dict)
        assert "page_files" not in metadata
    segment_files = sorted(
        path for path in artifact_path.parent.glob("*.md") if path.name != "index.md"
    )
    assert segment_files, "expected at least one segment artifact"
    page_path = segment_files[0]
    content = page_path.read_text(encoding="utf-8")
    assert "Body content from HTML" in content
    assert "warnings:" not in content


def test_parse_cli_web_subcommand_with_remote_url(tmp_path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    output_root = workspace / "remote-output"
    remote_url = "https://example.com/articles/remote"
    html_body = "<html><body><article><h1>Remote Title</h1><p>Remote body text.</p></article></body></html>"

    captured_headers: dict[str, object] = {}

    class StubResponse:
        def __init__(self, url: str) -> None:
            self.status_code = 200
            self.url = url
            self.headers = {"Content-Type": "text/html"}
            self.encoding = "utf-8"
            self._text = html_body

        @property
        def text(self) -> str:
            return self._text

        @property
        def content(self) -> bytes:
            return self._text.encode("utf-8")

    class StubSession:
        def get(self, url: str, timeout: float, headers: dict[str, str]):
            _ = timeout
            captured_headers["headers"] = headers
            captured_headers["url"] = url
            return StubResponse(url)

    from src.parsing import web as web_module

    stub_session = StubSession()

    def _stub_ensure_session(_self):
        return stub_session

    monkeypatch.setattr(web_module.WebParser, "_ensure_session", _stub_ensure_session)

    exit_code = main_entry([
        "parse",
        "--output-root",
        str(output_root),
        "web",
        remote_url,
    ])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    assert "[completed]" in captured.out
    assert captured_headers["url"] == remote_url
    headers = captured_headers["headers"]
    assert isinstance(headers, dict)
    assert "User-Agent" in headers

    resolved_output = output_root.resolve()
    entries = _load_manifest_entries(resolved_output)
    assert len(entries) == 1

    entry = entries[0]
    assert entry["parser"] == "web"
    assert entry.get("status_code") == 200 or entry.get("status") == "completed"
    artifact_path = resolved_output / entry["artifact_path"]
    assert artifact_path.exists()
    metadata = entry.get("metadata")
    if metadata:
        assert isinstance(metadata, dict)
        assert "page_files" not in metadata
    segment_files = sorted(
        path for path in artifact_path.parent.glob("*.md") if path.name != "index.md"
    )
    assert segment_files, "expected at least one segment artifact"
    page_path = segment_files[0]
    artifact_text = page_path.read_text(encoding="utf-8")
    assert "Remote Title" in artifact_text
    assert "Remote body text." in artifact_text
    assert "warnings:" not in artifact_text


def test_parse_cli_scan_subcommand_processes_multiple_targets(tmp_path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    evidence_root = workspace / "evidence"
    evidence_root.mkdir()

    pdf_path = evidence_root / "scan.pdf"
    docx_path = evidence_root / "scan.docx"
    html_path = evidence_root / "scan.html"

    _write_pdf(pdf_path, "Scan PDF body")
    _write_docx(docx_path, "Scan DOCX", ["List item one", "List item two"])
    _write_html(html_path, "Scan HTML", "HTML body text")

    output_root = workspace / "scan-output"

    exit_code = main_entry([
        "parse",
        "--output-root",
        str(output_root),
        "scan",
    ])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    assert captured.out.count("[completed]") == 3

    resolved_output = output_root.resolve()
    entries = _load_manifest_entries(resolved_output)
    assert len(entries) == 3

    parsers = {entry["parser"] for entry in entries}
    assert parsers == {"pdf", "docx", "web"}

    for entry in entries:
        artifact_path = resolved_output / entry["artifact_path"]
        assert artifact_path.exists(), f"Missing artifact for {entry['source']}"


def test_parse_cli_scan_layers_config_and_cli_overrides(tmp_path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    config_dir = workspace / "config"
    config_dir.mkdir()
    config_payload = textwrap.dedent(
        """
        scan:
          suffixes:
            - .pdf
          include:
            - "*.pdf"
          exclude:
            - "ignore/*"
        """
    ).strip()
    (config_dir / "parsing.yaml").write_text(config_payload, encoding="utf-8")

    evidence_root = workspace / "evidence"
    evidence_root.mkdir()

    _write_pdf(evidence_root / "keep.pdf", "Layered PDF body")
    _write_docx(evidence_root / "keep.docx", "Layered DOCX", ["Paragraph content"])
    ignore_dir = evidence_root / "ignore"
    ignore_dir.mkdir()
    _write_pdf(ignore_dir / "hidden.pdf", "Previously excluded PDF")

    output_root = workspace / "layered-output"

    exit_code = main_entry([
        "parse",
        "--output-root",
        str(output_root),
        "scan",
        "--suffix",
        ".docx",
        "--include",
        "*.docx",
        "--clear-config-exclude",
    ])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    assert captured.out.count("[completed]") == 3

    resolved_output = output_root.resolve()
    entries = _load_manifest_entries(resolved_output)
    assert len(entries) == 3
    parsers = {entry["parser"] for entry in entries}
    assert parsers == {"pdf", "docx"}
    assert any(Path(str(entry["source"])).name == "hidden.pdf" for entry in entries)


def test_parse_cli_scan_can_clear_config_patterns(tmp_path, monkeypatch, capsys) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    config_dir = workspace / "config"
    config_dir.mkdir()
    config_payload = textwrap.dedent(
        """
        scan:
          suffixes:
            - .pdf
          include:
            - "*.pdf"
        """
    ).strip()
    (config_dir / "parsing.yaml").write_text(config_payload, encoding="utf-8")

    evidence_root = workspace / "evidence"
    evidence_root.mkdir()
    _write_pdf(evidence_root / "keep.pdf", "Config PDF body")
    _write_docx(evidence_root / "keep.docx", "Config DOCX", ["Another paragraph"])

    output_root = workspace / "cleared-output"

    exit_code = main_entry([
        "parse",
        "--output-root",
        str(output_root),
        "scan",
        "--suffix",
        ".docx",
        "--include",
        "*.docx",
        "--clear-config-suffixes",
        "--clear-config-include",
    ])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    assert captured.out.count("[completed]") == 1

    resolved_output = output_root.resolve()
    entries = _load_manifest_entries(resolved_output)
    assert len(entries) == 1
    entry = entries[0]
    assert entry["parser"] == "docx"
    assert Path(str(entry["source"])).name == "keep.docx"

