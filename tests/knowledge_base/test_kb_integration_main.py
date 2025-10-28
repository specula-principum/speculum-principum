"""Integration tests for knowledge base CLI entry points."""
from __future__ import annotations

from pathlib import Path
import sys
import types

import pytest


def _ensure_optional_dependency_stubs() -> None:
    """Provide lightweight shims for optional parsing dependencies."""

    if "pypdf" not in sys.modules:
        pypdf_module = types.ModuleType("pypdf")

        class _PdfReader:  # pragma: no cover - simple stub
            def __init__(self, *args: object, **kwargs: object) -> None:
                del args, kwargs
                self.pages: list[object] = []
                self.metadata: dict[str, object] = {}
                self.is_encrypted = False

            def decrypt(self, *_: object, **__: object) -> None:
                self.is_encrypted = False

        setattr(pypdf_module, "PdfReader", _PdfReader)
        sys.modules["pypdf"] = pypdf_module

        pypdf_errors = types.ModuleType("pypdf.errors")

        class _PdfReadError(Exception):
            pass

        setattr(pypdf_errors, "PdfReadError", _PdfReadError)
        sys.modules["pypdf.errors"] = pypdf_errors

    if "docx" not in sys.modules:
        docx_module = types.ModuleType("docx")

        class _DocxDocument:  # pragma: no cover - simple stub
            sections: tuple[object, ...] = ()

        def _load_docx(_path: str) -> _DocxDocument:
            return _DocxDocument()

        setattr(docx_module, "Document", _load_docx)
        sys.modules["docx"] = docx_module

        docx_document_module = types.ModuleType("docx.document")
        setattr(docx_document_module, "Document", _DocxDocument)
        sys.modules["docx.document"] = docx_document_module

        docx_opc_module = types.ModuleType("docx.opc")
        sys.modules["docx.opc"] = docx_opc_module

        docx_opc_exceptions = types.ModuleType("docx.opc.exceptions")

        class _PackageNotFoundError(Exception):
            pass

        setattr(docx_opc_exceptions, "PackageNotFoundError", _PackageNotFoundError)
        sys.modules["docx.opc.exceptions"] = docx_opc_exceptions

        docx_oxml_module = types.ModuleType("docx.oxml")
        sys.modules["docx.oxml"] = docx_oxml_module

        docx_oxml_ns = types.ModuleType("docx.oxml.ns")
        setattr(docx_oxml_ns, "qn", lambda value: value)  # pragma: no cover - trivial stub
        sys.modules["docx.oxml.ns"] = docx_oxml_ns

        docx_table_module = types.ModuleType("docx.table")

        class _DocxTable:  # pragma: no cover - simple stub
            pass

        setattr(docx_table_module, "Table", _DocxTable)
        sys.modules["docx.table"] = docx_table_module

        docx_text_module = types.ModuleType("docx.text")
        sys.modules["docx.text"] = docx_text_module

        docx_text_paragraph = types.ModuleType("docx.text.paragraph")

        class _DocxParagraph:  # pragma: no cover - simple stub
            def __init__(self, text: str = "") -> None:
                self.text = text

        setattr(docx_text_paragraph, "Paragraph", _DocxParagraph)
        sys.modules["docx.text.paragraph"] = docx_text_paragraph

    if "trafilatura" not in sys.modules:
        trafilatura_module = types.ModuleType("trafilatura")

        def _extract(html: str, *, url: str | None = None) -> str:
            del url
            return html

        setattr(trafilatura_module, "extract", _extract)
        sys.modules["trafilatura"] = trafilatura_module


_ensure_optional_dependency_stubs()

from main import main as run_main


def test_main_kb_init_preview_lists_structure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = tmp_path / "kb"

    exit_code = run_main([
        "kb",
        "init",
        "--root",
        str(root),
    ])

    assert exit_code == 0

    captured = capsys.readouterr()
    output_lines = captured.out.strip().splitlines()
    # Ensure a representative subset of planned paths appear in the preview.
    expected_paths = {
        root / "index.md",
        root / "concepts",
        root / "concepts" / "index.md",
        root / "meta" / "methodology.md",
    }
    for path in expected_paths:
        assert str(path) in output_lines


def test_main_kb_init_apply_materializes_structure(tmp_path: Path) -> None:
    root = tmp_path / "kb"

    exit_code = run_main([
        "kb",
        "init",
        "--root",
        str(root),
        "--apply",
        "--title",
        "Custom Knowledge Base",
        "--description",
        "Custom description for IA testing.",
    ])

    assert exit_code == 0

    index_path = root / "index.md"
    assert index_path.exists()
    index_contents = index_path.read_text(encoding="utf-8")
    assert "Custom Knowledge Base" in index_contents
    assert "Custom description for IA testing." in index_contents

    # Ensure representative directories are created when --apply is used.
    for directory in (
        root / "concepts",
        root / "entities",
        root / "sources",
        root / "meta",
    ):
        assert directory.is_dir()


def test_main_kb_validate_taxonomy_success(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    taxonomy_path = tmp_path / "taxonomy.yaml"
    taxonomy_path.write_text(
        (
            "version: '1.0.0'\n"
            "methodology: information-architecture\n"
            "topics:\n"
            "  statecraft:\n"
            "    label: 'Statecraft'\n"
            "    definition: 'Governance practice'\n"
            "entity_types:\n"
            "  concept:\n"
            "    label: 'Concept'\n"
            "    properties: []\n"
            "relationship_types:\n"
            "  relates-to:\n"
            "    label: 'Relates To'\n"
            "    inverse: 'related-by'\n"
            "  related-by:\n"
            "    label: 'Related By'\n"
            "    inverse: 'relates-to'\n"
            "vocabulary:\n"
            "  statecraft:\n"
            "    preferred_term: 'statecraft'\n"
            "    alternate_terms: ['art-of-government']\n"
            "    related_terms: ['governance']\n"
        ),
        encoding="utf-8",
    )

    exit_code = run_main([
        "kb",
        "validate-taxonomy",
        "--taxonomy",
        str(taxonomy_path),
    ])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert captured.err == ""


def test_main_kb_validate_taxonomy_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    invalid_path = tmp_path / "invalid-taxonomy.yaml"
    invalid_path.write_text(
        "topics: []\nentity_types: {}\nrelationship_types: {}\nvocabulary: {}\n",
        encoding="utf-8",
    )

    exit_code = run_main([
        "kb",
        "validate-taxonomy",
        "--taxonomy",
        str(invalid_path),
    ])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Taxonomy requires mapping section" in captured.err


def test_main_kb_process_invokes_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    source_dir = tmp_path / "evidence"
    kb_root = tmp_path / "kb"
    source_dir.mkdir()
    kb_root.mkdir()

    captured: dict[str, object] = {}

    stage = types.SimpleNamespace(stage="analysis", metrics={"segments": 2.0}, warnings=())
    result = types.SimpleNamespace(success=True, stages=(stage,), errors=(), warnings=())

    def fake_run_process(options):
        captured["options"] = options
        return result

    monkeypatch.setattr("src.cli.commands.knowledge_base.run_process_workflow", fake_run_process)

    exit_code = run_main([
        "kb",
        "process",
        "--source",
        str(source_dir),
        "--kb-root",
        str(kb_root),
    ])

    assert exit_code == 0
    assert isinstance(captured["options"], object)
    options = captured["options"]
    assert getattr(options, "source_path") == source_dir
    assert getattr(options, "kb_root") == kb_root
    assert getattr(options, "extractors") is None

    output = capsys.readouterr().out
    assert "SUCCESS" in output
    assert "analysis: segments=2.0" in output


def test_main_kb_update_invokes_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    source_dir = tmp_path / "evidence"
    kb_root = tmp_path / "kb"
    source_dir.mkdir()
    kb_root.mkdir()

    captured: dict[str, object] = {}

    stage = types.SimpleNamespace(stage="transformation", metrics={"concepts": 1.0}, warnings=())
    result = types.SimpleNamespace(success=True, stages=(stage,), errors=(), warnings=())

    def fake_run_update(options):
        captured["options"] = options
        return result

    monkeypatch.setattr("src.cli.commands.knowledge_base.run_update_workflow", fake_run_update)

    kb_id = "concepts/statecraft/virtue"
    exit_code = run_main([
        "kb",
        "update",
        "--kb-id",
        kb_id,
        "--source",
        str(source_dir),
        "--kb-root",
        str(kb_root),
    ])

    assert exit_code == 0
    options = captured["options"]
    assert getattr(options, "kb_id") == kb_id
    assert getattr(options, "reextract") is True
    assert getattr(options, "rebuild_links") is False

    output = capsys.readouterr().out
    assert f"{kb_id}: SUCCESS" in output
    assert "transformation: concepts=1.0" in output


def test_main_kb_improve_invokes_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    kb_root = tmp_path / "kb"
    kb_root.mkdir()

    captured: dict[str, object] = {}

    result = types.SimpleNamespace(
        success=True,
        gaps=(),
        fixes_applied=("backlinks:1",),
        suggestions={"concepts/statecraft/virtue": ("add descriptive tags",)},
        metrics={"gaps_total": 0.0},
        report_path=tmp_path / "report.json",
    )

    def fake_run_improve(options):
        captured["options"] = options
        return result

    monkeypatch.setattr("src.cli.commands.knowledge_base.run_improve_workflow", fake_run_improve)

    exit_code = run_main([
        "kb",
        "improve",
        "--kb-root",
        str(kb_root),
        "--fix-links",
    ])

    assert exit_code == 0
    options = captured["options"]
    assert getattr(options, "kb_root") == kb_root
    assert getattr(options, "fix_links") is True

    output = capsys.readouterr().out
    assert "IMPROVEMENT SUCCESS" in output
    assert "Fixes applied" in output


def test_main_kb_export_graph_invokes_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    kb_root = tmp_path / "kb"
    kb_root.mkdir()
    output_path = tmp_path / "graph.json"

    captured: dict[str, object] = {}
    result = types.SimpleNamespace(
        format="json",
        nodes=2,
        edges=1,
        output_path=output_path,
        success=True,
    )

    def fake_run_export(options):
        captured["options"] = options
        return result

    monkeypatch.setattr("src.cli.commands.knowledge_base.run_export_graph_workflow", fake_run_export)

    exit_code = run_main([
        "kb",
        "export-graph",
        "--kb-root",
        str(kb_root),
        "--format",
        "json",
        "--output",
        str(output_path),
    ])

    assert exit_code == 0
    options = captured["options"]
    assert getattr(options, "kb_root") == kb_root
    assert getattr(options, "format") == "json"
    assert getattr(options, "output_path") == output_path

    output = capsys.readouterr().out
    assert "GRAPH EXPORT SUCCESS" in output
    assert str(output_path) in output
