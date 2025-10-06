"""Page content capture and enrichment pipeline for site monitoring."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests
from requests import Response

try:
    from trafilatura import extract as trafilatura_extract
except ImportError:  # pragma: no cover - dependency not installed
    trafilatura_extract = None

from ..clients.search_client import SearchResult, normalize_url
from .deduplication import create_url_fingerprint
from ..utils.config_manager import PageCaptureConfig

logger = logging.getLogger(__name__)


@dataclass
class PageCaptureResult:
    """Result of attempting to capture page content for a discovery."""

    status: str
    content_hash: str
    artifact_dir: Optional[Path]
    content_path: Optional[Path]
    metadata_path: Optional[Path]
    content_text: Optional[str]
    excerpt: Optional[str]
    metadata: Dict[str, object]
    source: Optional[str] = None
    error: Optional[str] = None

    @property
    def artifact_path_str(self) -> Optional[str]:
        return str(self.artifact_dir) if self.artifact_dir else None


class PageCaptureService:
    """Fetch, extract, and persist page content for search discoveries."""

    GOOGLE_CACHE_TEMPLATE = "https://webcache.googleusercontent.com/search?q=cache:%s:%s"

    def __init__(self, config: PageCaptureConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.user_agent})
        self.persist_artifacts = getattr(config, "persist_artifacts", False)
        self.base_dir = Path(config.artifacts_dir).resolve()
        self.cache: Dict[str, Tuple[datetime, PageCaptureResult]] = {}

        if self.persist_artifacts:
            try:
                self.base_dir.mkdir(parents=True, exist_ok=True)
            except Exception as exc:  # pragma: no cover - filesystem edge case
                logger.error("Failed to create artifacts directory %s: %s", self.base_dir, exc)
                raise

    def capture(
        self,
        site_name: str,
        result: SearchResult,
        excerpt_max_chars: int = 320,
    ) -> PageCaptureResult:
        """Capture page content and persist artifacts for the given result."""

        normalized_url = normalize_url(result.link)
        content_hash = create_url_fingerprint(result.link, result.title)

        metadata: Dict[str, object] = {
            "site_name": site_name,
            "url": result.link,
            "normalized_url": normalized_url,
            "title": result.title,
            "cache_id": result.cache_id,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

        if not self.config.enabled:
            metadata["status"] = "disabled"
            return PageCaptureResult(
                status="disabled",
                content_hash=content_hash,
                artifact_dir=None,
                content_path=None,
                metadata_path=None,
                content_text=None,
                excerpt=None,
                metadata=metadata,
            )

        if trafilatura_extract is None:
            error = "trafilatura dependency is not installed"
            metadata.update({"status": "failed", "error": error})
            logger.warning("Page capture disabled because trafilatura is missing")
            return PageCaptureResult(
                status="failed",
                content_hash=content_hash,
                artifact_dir=None,
                content_path=None,
                metadata_path=None,
                content_text=None,
                excerpt=None,
                metadata=metadata,
                error=error,
            )

        cached = self._get_cached(content_hash)
        if cached:
            logger.debug("Using cached page capture for %s", normalized_url)
            cached.metadata = {**cached.metadata, "cache_hit": True}
            return cached

        response, source, error = self._download_content(result)
        if response is None:
            metadata.update({"status": "failed", "error": error, "source": source})
            return PageCaptureResult(
                status="failed",
                content_hash=content_hash,
                artifact_dir=None,
                content_path=None,
                metadata_path=None,
                content_text=None,
                excerpt=None,
                metadata=metadata,
                source=source,
                error=error,
            )

        html = response.text
        metadata.update({
            "http_status": response.status_code,
            "content_bytes_raw": len(html.encode("utf-8")),
            "source": source,
        })

        try:
            content = self._extract_content(html, result.link)
        except Exception as exc:  # pragma: no cover - extractor edge case
            error = f"extract_failed: {exc}"
            metadata.update({"status": "failed", "error": error})
            logger.warning("Failed to extract content for %s: %s", result.link, exc)
            return PageCaptureResult(
                status="failed",
                content_hash=content_hash,
                artifact_dir=None,
                content_path=None,
                metadata_path=None,
                content_text=None,
                excerpt=None,
                metadata=metadata,
                source=source,
                error=error,
            )

        if not content:
            metadata.update({"status": "empty"})
            return PageCaptureResult(
                status="empty",
                content_hash=content_hash,
                artifact_dir=None,
                content_path=None,
                metadata_path=None,
                content_text=None,
                excerpt=None,
                metadata=metadata,
                source=source,
            )

        sanitized_text = self._limit_bytes(content)
        excerpt = self._build_excerpt(sanitized_text, excerpt_max_chars)

        if not self.persist_artifacts:
            metadata.update(
                {
                    "status": "success",
                    "content_bytes_stored": 0,
                    "persisted": False,
                }
            )

            result_obj = PageCaptureResult(
                status="success",
                content_hash=content_hash,
                artifact_dir=None,
                content_path=None,
                metadata_path=None,
                content_text=sanitized_text,
                excerpt=excerpt,
                metadata=metadata,
                source=source,
            )
        else:
            artifact_dir = self.base_dir / content_hash
            artifact_dir.mkdir(parents=True, exist_ok=True)

            content_path = artifact_dir / "content.md"
            metadata_path = artifact_dir / "metadata.json"

            content_path.write_text(sanitized_text, encoding="utf-8")

            relative_dir = Path(self.config.artifacts_dir) / content_hash
            metadata.update(
                {
                    "status": "success",
                    "content_bytes_stored": len(sanitized_text.encode("utf-8")),
                    "artifact_dir": str(relative_dir),
                    "persisted": True,
                }
            )

            metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

            if self.config.store_raw_html:
                raw_path = artifact_dir / "raw.html"
                raw_path.write_text(html, encoding="utf-8")

            result_obj = PageCaptureResult(
                status="success",
                content_hash=content_hash,
                artifact_dir=artifact_dir,
                content_path=content_path,
                metadata_path=metadata_path,
                content_text=sanitized_text,
                excerpt=excerpt,
                metadata=metadata,
                source=source,
            )

        self._store_cache(content_hash, result_obj)
        return result_obj

    def _get_cached(self, content_hash: str) -> Optional[PageCaptureResult]:
        if self.config.cache_ttl_minutes <= 0:
            return None
        cached = self.cache.get(content_hash)
        if not cached:
            return None
        cached_at, result = cached
        if datetime.now(timezone.utc) - cached_at > timedelta(minutes=self.config.cache_ttl_minutes):
            self.cache.pop(content_hash, None)
            return None
        return result

    def _store_cache(self, content_hash: str, result: PageCaptureResult) -> None:
        if self.config.cache_ttl_minutes <= 0:
            return
        self.cache[content_hash] = (datetime.now(timezone.utc), result)

    def _download_content(self, result: SearchResult) -> Tuple[Optional[Response], Optional[str], Optional[str]]:
        last_error: Optional[str] = None
        for attempt in range(self.config.retry_attempts + 1):
            try:
                response = self.session.get(result.link, timeout=self.config.timeout_seconds)
                if response.status_code == 200 and response.text:
                    return response, "origin", None
                last_error = f"http_status={response.status_code}"
            except requests.RequestException as exc:
                last_error = f"request_error:{exc}"
                logger.debug("Request attempt %s failed for %s: %s", attempt + 1, result.link, exc)

        if result.cache_id:
            cache_url = self.GOOGLE_CACHE_TEMPLATE % (result.cache_id, result.link)
            try:
                response = self.session.get(cache_url, timeout=self.config.timeout_seconds)
                if response.status_code == 200 and response.text:
                    return response, "google-cache", None
                last_error = f"google_cache_status={response.status_code}"
            except requests.RequestException as exc:
                last_error = f"google_cache_error:{exc}"
                logger.debug("Google cache fetch failed for %s: %s", result.link, exc)

        return None, "origin", last_error or "unavailable"

    def _extract_content(self, html: str, url: str) -> Optional[str]:
        if trafilatura_extract is None:
            return None
        extracted = trafilatura_extract(
            html,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
            output_format="txt",
            url=url,
        )
        if extracted:
            return extracted.strip()
        return None

    def _limit_bytes(self, text: str) -> str:
        max_bytes = self.config.max_text_bytes
        encoded = text.encode("utf-8")
        if len(encoded) <= max_bytes:
            return text.strip()

        ellipsis = "…"
        ellipsis_bytes = ellipsis.encode("utf-8")
        budget = max_bytes - len(ellipsis_bytes)

        if budget <= 0:
            truncated_ellipsis = ellipsis_bytes[:max_bytes].decode("utf-8", errors="ignore")
            return truncated_ellipsis or ""

        truncated = encoded[:budget]
        sanitized = truncated.decode("utf-8", errors="ignore").rstrip()

        # Ensure we don't exceed the byte budget after trimming
        while sanitized and len(sanitized.encode("utf-8")) > budget:
            sanitized = sanitized[:-1]

        if not sanitized:
            return ellipsis

        return f"{sanitized}{ellipsis}"

    @staticmethod
    def _build_excerpt(text: Optional[str], max_chars: int) -> Optional[str]:
        if not text:
            return None
        summary = text.strip().replace("\n", " ")
        if len(summary) <= max_chars:
            return summary
        truncated = summary[: max_chars].rsplit(" ", 1)[0]
        return truncated.strip() + "…"