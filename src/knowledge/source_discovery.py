"""URL extraction and source discovery from parsed documents."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List
from urllib.parse import urlparse

from src import paths
from src.parsing.storage import ParseStorage


@dataclass(slots=True)
class DiscoveredUrl:
    """Represents a URL discovered in a document."""

    url: str
    source_checksum: str  # Checksum of document where discovered
    context: str  # Surrounding text for context
    link_text: str  # The text used in the markdown link

    @property
    def domain(self) -> str:
        """Extract the domain from the URL."""
        parsed = urlparse(self.url)
        return parsed.netloc.lower()

    @property
    def domain_type(self) -> str:
        """Classify the domain type."""
        domain = self.domain
        if domain.endswith(".gov") or ".gov." in domain:
            return "government"
        if domain.endswith(".edu") or ".edu." in domain:
            return "education"
        if domain.endswith(".org"):
            return "organization"
        if domain.endswith(".mil"):
            return "military"
        if any(domain.endswith(tld) for tld in [".com", ".net", ".io", ".co"]):
            return "commercial"
        return "unknown"


# URL patterns for extraction
_MARKDOWN_LINK_PATTERN = re.compile(
    r'\[([^\]]*)\]\(([^)]+)\)',  # [text](url)
    re.IGNORECASE,
)
_ANGLE_BRACKET_PATTERN = re.compile(
    r'<(https?://[^>]+)>',  # <url>
    re.IGNORECASE,
)
_BARE_URL_PATTERN = re.compile(
    r'(?<![(<\[])(https?://[^\s)\]>]+)',  # bare URLs not in markdown/angle
    re.IGNORECASE,
)

# Domains to exclude (social media, URL shorteners, etc.)
_EXCLUDED_DOMAINS = {
    "twitter.com",
    "x.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "linkedin.com",
    "youtube.com",
    "youtu.be",
    "bit.ly",
    "t.co",
    "goo.gl",
    "tinyurl.com",
    "ow.ly",
    "buff.ly",
    "is.gd",
    "v.gd",
    "github.com",
    "gitlab.com",
    "githubusercontent.com",
}

# Official domain patterns that boost credibility
_OFFICIAL_DOMAIN_PATTERNS = [
    r"\.gov$",
    r"\.gov\.[a-z]{2}$",
    r"\.edu$",
    r"\.edu\.[a-z]{2}$",
    r"\.mil$",
    r"\.int$",
    r"\.un\.org$",
    r"\.who\.int$",
    r"\.europa\.eu$",
]


class SourceDiscoverer:
    """Discovers potential source URLs from parsed documents."""

    def __init__(self, parsed_root: Path | None = None) -> None:
        """Initialize the discoverer.

        Args:
            parsed_root: Root directory for parsed documents.
                         Defaults to evidence/parsed/.
        """
        self.parsed_root = parsed_root or paths.get_evidence_root() / "parsed"
        self._storage = ParseStorage(self.parsed_root) if self.parsed_root.exists() else None

    def extract_urls(self, markdown: str, source_checksum: str) -> List[DiscoveredUrl]:
        """Extract all URLs from markdown content.

        Args:
            markdown: The markdown content to scan.
            source_checksum: Checksum of the source document.

        Returns:
            List of discovered URLs with metadata.
        """
        discovered: List[DiscoveredUrl] = []
        seen_urls: set[str] = set()

        # Extract markdown links [text](url)
        for match in _MARKDOWN_LINK_PATTERN.finditer(markdown):
            link_text = match.group(1)
            url = match.group(2).strip()

            if not self._is_valid_url(url):
                continue

            normalized = self._normalize_url(url)
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)

            context = self._extract_context(markdown, match.start(), match.end())
            discovered.append(DiscoveredUrl(
                url=normalized,
                source_checksum=source_checksum,
                context=context,
                link_text=link_text,
            ))

        # Extract angle bracket URLs <url>
        for match in _ANGLE_BRACKET_PATTERN.finditer(markdown):
            url = match.group(1).strip()

            if not self._is_valid_url(url):
                continue

            normalized = self._normalize_url(url)
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)

            context = self._extract_context(markdown, match.start(), match.end())
            discovered.append(DiscoveredUrl(
                url=normalized,
                source_checksum=source_checksum,
                context=context,
                link_text="",
            ))

        # Extract bare URLs
        for match in _BARE_URL_PATTERN.finditer(markdown):
            url = match.group(1).strip()

            if not self._is_valid_url(url):
                continue

            normalized = self._normalize_url(url)
            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)

            context = self._extract_context(markdown, match.start(), match.end())
            discovered.append(DiscoveredUrl(
                url=normalized,
                source_checksum=source_checksum,
                context=context,
                link_text="",
            ))

        return discovered

    def filter_candidates(
        self,
        urls: List[DiscoveredUrl],
        registered_sources: List[str],
        domain_filter: str | None = None,
    ) -> List[DiscoveredUrl]:
        """Filter to unregistered, high-integrity candidates.

        Args:
            urls: List of discovered URLs.
            registered_sources: List of already-registered source URLs.
            domain_filter: Optional regex pattern to filter domains.

        Returns:
            Filtered list of candidate URLs.
        """
        registered_set = {self._normalize_url(u) for u in registered_sources}
        domain_regex = re.compile(domain_filter, re.IGNORECASE) if domain_filter else None

        candidates: List[DiscoveredUrl] = []
        for url in urls:
            normalized = self._normalize_url(url.url)

            # Skip already registered
            if normalized in registered_set:
                continue

            # Skip excluded domains
            if url.domain in _EXCLUDED_DOMAINS:
                continue

            # Apply domain filter if provided
            if domain_regex and not domain_regex.search(url.domain):
                continue

            candidates.append(url)

        return candidates

    def score_candidate(self, url: DiscoveredUrl) -> float:
        """Calculate preliminary credibility score based on domain characteristics.

        The score is based on:
        - Domain type (government, education, etc.)
        - Whether the domain matches official patterns
        - Protocol (HTTPS preferred)

        Args:
            url: The discovered URL to score.

        Returns:
            Score between 0.0 and 1.0.
        """
        score = 0.5  # Base score

        # Domain type scoring
        domain_type = url.domain_type
        if domain_type == "government":
            score += 0.35
        elif domain_type == "education":
            score += 0.30
        elif domain_type == "military":
            score += 0.35
        elif domain_type == "organization":
            score += 0.15
        elif domain_type == "commercial":
            score -= 0.10

        # Check for official domain patterns
        if self._is_official_domain(url.domain):
            score += 0.10

        # HTTPS bonus
        if url.url.startswith("https://"):
            score += 0.05
        else:
            score -= 0.10

        # Clamp to valid range
        return max(0.0, min(1.0, score))

    def discover_from_document(
        self,
        checksum: str,
        registered_sources: List[str] | None = None,
        domain_filter: str | None = None,
    ) -> List[tuple[DiscoveredUrl, float]]:
        """Discover and score URLs from a specific parsed document.

        Args:
            checksum: Checksum of the document to scan.
            registered_sources: Already-registered source URLs to exclude.
            domain_filter: Optional regex pattern to filter domains.

        Returns:
            List of (DiscoveredUrl, score) tuples, sorted by score descending.
        """
        if self._storage is None:
            return []

        registered = registered_sources or []

        # Get the manifest entry to find the artifact path
        manifest = self._storage.manifest()
        entry = manifest.get(checksum)
        if entry is None:
            return []

        # Find the artifact directory from the manifest
        artifact_path = self.parsed_root / entry.artifact_path
        if artifact_path.is_file():
            artifact_dir = artifact_path.parent
        else:
            artifact_dir = artifact_path

        if not artifact_dir.exists():
            return []

        all_urls: List[DiscoveredUrl] = []
        for md_file in artifact_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                urls = self.extract_urls(content, checksum)
                all_urls.extend(urls)
            except OSError:
                continue

        # Filter and deduplicate
        candidates = self.filter_candidates(all_urls, registered, domain_filter)

        # Score and sort
        scored = [(url, self.score_candidate(url)) for url in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)

        return scored

    def discover_all(
        self,
        registered_sources: List[str] | None = None,
        domain_filter: str | None = None,
        limit: int | None = None,
    ) -> List[tuple[DiscoveredUrl, float]]:
        """Discover URLs from all parsed documents.

        Args:
            registered_sources: Already-registered source URLs to exclude.
            domain_filter: Optional regex pattern to filter domains.
            limit: Maximum number of results to return.

        Returns:
            List of (DiscoveredUrl, score) tuples, sorted by score descending.
        """
        if self._storage is None:
            return []

        registered = registered_sources or []
        all_scored: List[tuple[DiscoveredUrl, float]] = []

        # Get all checksums from manifest
        manifest = self._storage.manifest()
        for checksum in manifest.entries:
            scored = self.discover_from_document(checksum, registered, domain_filter)
            all_scored.extend(scored)

        # Deduplicate by URL (keep highest score)
        url_to_best: dict[str, tuple[DiscoveredUrl, float]] = {}
        for url, score in all_scored:
            normalized = self._normalize_url(url.url)
            if normalized not in url_to_best or score > url_to_best[normalized][1]:
                url_to_best[normalized] = (url, score)

        # Sort by score descending
        results = sorted(url_to_best.values(), key=lambda x: x[1], reverse=True)

        if limit is not None:
            results = results[:limit]

        return results

    def _is_valid_url(self, url: str) -> bool:
        """Check if a URL is valid for source consideration."""
        # Must be http or https
        if not url.startswith(("http://", "https://")):
            return False

        # Must have a valid domain
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                return False
            # Skip internal anchors
            if parsed.path == "" and parsed.fragment:
                return False
        except ValueError:
            return False

        return True

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication."""
        # Remove trailing slash
        url = url.rstrip("/")

        # Remove common tracking parameters
        parsed = urlparse(url)
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        return clean_url.lower()

    def _extract_context(self, text: str, start: int, end: int, context_chars: int = 100) -> str:
        """Extract surrounding context for a match."""
        context_start = max(0, start - context_chars)
        context_end = min(len(text), end + context_chars)

        context = text[context_start:context_end]

        # Clean up newlines and extra whitespace
        context = " ".join(context.split())

        # Add ellipsis if truncated
        if context_start > 0:
            context = "..." + context
        if context_end < len(text):
            context = context + "..."

        return context

    def _is_official_domain(self, domain: str) -> bool:
        """Check if domain matches official domain patterns."""
        for pattern in _OFFICIAL_DOMAIN_PATTERNS:
            if re.search(pattern, domain, re.IGNORECASE):
                return True
        return False
