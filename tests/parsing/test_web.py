"""Tests for the web parser implementation."""

from __future__ import annotations

import pytest
import responses

from src.parsing import registry
from src.parsing.base import ParseTarget, ParserError
from src.parsing.web import WebParser, web_parser


def _sample_html(title: str = "Sample Title", body: str = "Hello world") -> str:
    return f"""
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


def test_web_parser_extracts_remote_content() -> None:
    url = "https://example.com/article"
    html = _sample_html(body="Remote content body")

    parser = WebParser()
    target = ParseTarget(source=url, is_remote=True)

    with responses.RequestsMock() as mock:
        mock.add(
            responses.GET,
            url,
            body=html,
            status=200,
            content_type="text/html; charset=utf-8",
        )

        assert parser.detect(target)
        document = parser.extract(target)

    assert document.segments
    combined = "\n".join(document.segments)
    assert "Remote content body" in combined
    assert document.metadata["status_code"] == 200
    assert document.metadata["content_type"] == "text/html"
    encoding = document.metadata["encoding"]
    assert encoding
    assert encoding.lower() == "utf-8"

    markdown = parser.to_markdown(document)
    assert "Remote content body" in markdown


def test_web_parser_handles_http_error() -> None:
    url = "https://example.com/bad"
    parser = WebParser()
    target = ParseTarget(source=url, is_remote=True)

    with responses.RequestsMock() as mock:
        mock.add(responses.GET, url, status=500)

        with pytest.raises(ParserError):
            parser.extract(target)


def test_web_parser_extracts_local_file(tmp_path) -> None:
    html_path = tmp_path / "sample.html"
    html_path.write_text(_sample_html(body="Local file body"), encoding="utf-8")

    parser = WebParser()
    target = ParseTarget(source=str(html_path))

    assert parser.detect(target)

    document = parser.extract(target)

    assert any("Local file body" in segment for segment in document.segments)
    assert document.metadata["file_size"] == html_path.stat().st_size
    assert document.metadata["content_type"] in {None, "text/html", "application/xhtml+xml"}


def test_web_parser_warns_when_extraction_is_empty(monkeypatch, tmp_path) -> None:
    html_path = tmp_path / "empty.html"
    html_path.write_text("<html><body></body></html>", encoding="utf-8")

    parser = WebParser()
    target = ParseTarget(source=str(html_path))

    def _fake_extract(_html: str, url: str | None = None) -> str | None:
        return None

    monkeypatch.setattr("trafilatura.extract", _fake_extract)

    document = parser.extract(target)

    assert not document.segments
    assert any("No extractable text" in warning for warning in document.warnings)


def test_web_parser_registration_supports_remote_targets(tmp_path) -> None:
    url = "https://example.com/registry"
    html = _sample_html(body="Registry content")

    with responses.RequestsMock() as mock:
        mock.add(
            responses.GET,
            url,
            body=html,
            status=200,
            content_type="text/html",
        )

        target = ParseTarget(source=url, is_remote=True)
        parser = registry.require_parser(target)
        assert parser.name == web_parser.name
        document = parser.extract(target)

    assert any("Registry content" in segment for segment in document.segments)