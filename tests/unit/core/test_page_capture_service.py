import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.core.page_capture import PageCaptureService
from src.clients.search_client import SearchResult
from src.utils.config_manager import PageCaptureConfig


@pytest.fixture(autouse=True)
def patch_trafilatura(monkeypatch):
    extracted = {"value": "Sample captured content."}

    def fake_extract(html, **kwargs):
        return extracted["value"]

    monkeypatch.setattr("src.core.page_capture.trafilatura_extract", fake_extract)
    return extracted


@pytest.fixture
def page_capture_config(tmp_path):
    artifacts_dir = tmp_path / "artifacts"
    return PageCaptureConfig(
        enabled=True,
        artifacts_dir=str(artifacts_dir),
        store_raw_html=True,
        persist_artifacts=True,
        max_text_bytes=1024,
        timeout_seconds=5,
        retry_attempts=0,
        cache_ttl_minutes=60,
    )


@pytest.fixture
def search_result():
    return SearchResult(
        title="Example Discovery",
        link="https://example.com/article",
        snippet="Sample snippet",
        display_link="example.com",
        cache_id="cache123",
    )


def test_capture_disabled(monkeypatch, search_result):
    config = PageCaptureConfig(enabled=False, artifacts_dir="artifacts/discoveries")
    service = PageCaptureService(config)
    result = service.capture("Example Site", search_result)
    assert result.status == "disabled"
    assert result.artifact_dir is None


def test_capture_success_writes_artifacts(monkeypatch, page_capture_config, search_result, tmp_path):
    service = PageCaptureService(page_capture_config)
    response = Mock()
    response.status_code = 200
    response.text = "<html><body>Capture me</body></html>"
    service.session.get = Mock(return_value=response)

    result = service.capture("Example Site", search_result, excerpt_max_chars=80)

    assert result.status == "success"
    artifact_dir = Path(page_capture_config.artifacts_dir) / result.content_hash
    content_path = artifact_dir / "content.md"
    metadata_path = artifact_dir / "metadata.json"
    assert content_path.exists()
    assert metadata_path.exists()

    stored_text = content_path.read_text(encoding="utf-8")
    assert "Sample captured content" in stored_text

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["status"] == "success"
    assert metadata["artifact_dir"].endswith(result.content_hash)

    # Raw HTML stored when enabled
    raw_path = artifact_dir / "raw.html"
    assert raw_path.exists()


def test_capture_uses_cache(page_capture_config, search_result):
    config = PageCaptureConfig(**{**page_capture_config.__dict__, "cache_ttl_minutes": 60})
    service = PageCaptureService(config)
    response = Mock()
    response.status_code = 200
    response.text = "<html><body>Capture me</body></html>"
    service.session.get = Mock(return_value=response)

    first = service.capture("Example Site", search_result)
    second = service.capture("Example Site", search_result)

    assert first.status == "success"
    assert second.status == "success"
    # Under cache, session.get should only be called once
    service.session.get.assert_called_once()


def test_capture_truncates_large_content(monkeypatch, search_result, tmp_path, patch_trafilatura):
    config = PageCaptureConfig(
        enabled=True,
        artifacts_dir=str(tmp_path / "artifacts"),
        max_text_bytes=16,
        retry_attempts=0,
        cache_ttl_minutes=0,
        persist_artifacts=False,
    )
    service = PageCaptureService(config)
    long_text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit."
    patch_trafilatura["value"] = long_text
    response = Mock()
    response.status_code = 200
    response.text = "<html><body>Capture me</body></html>"
    service.session.get = Mock(return_value=response)

    result = service.capture("Example Site", search_result, excerpt_max_chars=20)
    assert result.status == "success"
    assert result.content_text is not None
    assert result.content_text.endswith("…")
    assert len(result.content_text.encode("utf-8")) <= config.max_text_bytes + 1


def test_capture_without_persistence_skips_artifacts(tmp_path, search_result, patch_trafilatura):
    config = PageCaptureConfig(
        enabled=True,
        artifacts_dir=str(tmp_path / "artifacts"),
        persist_artifacts=False,
        cache_ttl_minutes=0,
    )
    service = PageCaptureService(config)
    response = Mock()
    response.status_code = 200
    response.text = "<html><body>Capture me</body></html>"
    service.session.get = Mock(return_value=response)

    result = service.capture("Example Site", search_result)

    assert result.status == "success"
    assert result.artifact_dir is None
    assert result.content_text is not None
    assert not (Path(config.artifacts_dir) / result.content_hash).exists()