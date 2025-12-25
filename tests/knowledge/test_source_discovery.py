"""Unit tests for source discovery module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from src.knowledge.source_discovery import (
    DiscoveredUrl,
    SourceDiscoverer,
    _EXCLUDED_DOMAINS,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def discoverer() -> SourceDiscoverer:
    """Create a SourceDiscoverer with no storage."""
    return SourceDiscoverer(parsed_root=Path("/nonexistent"))


@pytest.fixture
def sample_markdown() -> str:
    """Sample markdown content with various URL formats."""
    return """
# Sample Document

This is a document with various links.

## Government Sources

Check out [USDA Report](https://www.usda.gov/reports/2025/agriculture.pdf) for details.
Also see <https://www.fda.gov/guidelines> for regulations.

## Educational Resources

The [University Study](https://research.stanford.edu/papers/study.html) provides analysis.
More at https://www.mit.edu/publications/whitepaper.pdf (bare URL).

## Commercial Sources

Visit [Company Site](https://example.com/products) for products.
Or try https://shop.example.net/catalog for the catalog.

## Social Media (should be excluded)

Follow us on [Twitter](https://twitter.com/example) and
[YouTube](https://youtube.com/channel/abc).

## Internal Links

See [Section 1](#section-1) and [local page](./local.html).
"""


# =============================================================================
# DiscoveredUrl Tests
# =============================================================================


class TestDiscoveredUrl:
    """Tests for DiscoveredUrl dataclass."""

    def test_domain_extraction(self) -> None:
        """Should extract domain from URL."""
        url = DiscoveredUrl(
            url="https://www.example.gov/path/to/doc.pdf",
            source_checksum="abc123",
            context="Sample context",
            link_text="Example Doc",
        )
        assert url.domain == "www.example.gov"

    def test_domain_type_government(self) -> None:
        """Should identify government domains."""
        url = DiscoveredUrl(
            url="https://www.usda.gov/reports",
            source_checksum="abc123",
            context="",
            link_text="",
        )
        assert url.domain_type == "government"

    def test_domain_type_education(self) -> None:
        """Should identify education domains."""
        url = DiscoveredUrl(
            url="https://research.stanford.edu/papers",
            source_checksum="abc123",
            context="",
            link_text="",
        )
        assert url.domain_type == "education"

    def test_domain_type_organization(self) -> None:
        """Should identify organization domains."""
        url = DiscoveredUrl(
            url="https://www.example.org/about",
            source_checksum="abc123",
            context="",
            link_text="",
        )
        assert url.domain_type == "organization"

    def test_domain_type_commercial(self) -> None:
        """Should identify commercial domains."""
        url = DiscoveredUrl(
            url="https://shop.example.com/products",
            source_checksum="abc123",
            context="",
            link_text="",
        )
        assert url.domain_type == "commercial"

    def test_domain_type_unknown(self) -> None:
        """Should return unknown for unrecognized TLDs."""
        url = DiscoveredUrl(
            url="https://example.xyz/page",
            source_checksum="abc123",
            context="",
            link_text="",
        )
        assert url.domain_type == "unknown"

    def test_domain_type_international_gov(self) -> None:
        """Should identify international government domains."""
        url = DiscoveredUrl(
            url="https://www.gov.uk/guidance",
            source_checksum="abc123",
            context="",
            link_text="",
        )
        assert url.domain_type == "government"


# =============================================================================
# URL Extraction Tests
# =============================================================================


class TestUrlExtraction:
    """Tests for URL extraction from markdown."""

    def test_extract_markdown_links(
        self,
        discoverer: SourceDiscoverer,
    ) -> None:
        """Should extract URLs from markdown link syntax."""
        markdown = "See [this page](https://example.gov/doc.pdf) for info."
        urls = discoverer.extract_urls(markdown, "checksum123")

        assert len(urls) == 1
        assert urls[0].url == "https://example.gov/doc.pdf"
        assert urls[0].link_text == "this page"
        assert urls[0].source_checksum == "checksum123"

    def test_extract_angle_bracket_urls(
        self,
        discoverer: SourceDiscoverer,
    ) -> None:
        """Should extract URLs from angle bracket syntax."""
        markdown = "Visit <https://example.edu/research> for details."
        urls = discoverer.extract_urls(markdown, "checksum123")

        assert len(urls) == 1
        assert urls[0].url == "https://example.edu/research"
        assert urls[0].link_text == ""

    def test_extract_bare_urls(
        self,
        discoverer: SourceDiscoverer,
    ) -> None:
        """Should extract bare URLs."""
        markdown = "More at https://example.org/info for reference."
        urls = discoverer.extract_urls(markdown, "checksum123")

        assert len(urls) == 1
        assert urls[0].url == "https://example.org/info"

    def test_extract_multiple_url_types(
        self,
        discoverer: SourceDiscoverer,
        sample_markdown: str,
    ) -> None:
        """Should extract URLs from all formats."""
        urls = discoverer.extract_urls(sample_markdown, "checksum123")

        # Should find government, education, and commercial URLs
        extracted_urls = {u.url for u in urls}

        assert "https://www.usda.gov/reports/2025/agriculture.pdf" in extracted_urls
        assert "https://www.fda.gov/guidelines" in extracted_urls
        assert "https://research.stanford.edu/papers/study.html" in extracted_urls
        assert "https://www.mit.edu/publications/whitepaper.pdf" in extracted_urls

    def test_deduplicates_urls(
        self,
        discoverer: SourceDiscoverer,
    ) -> None:
        """Should not return duplicate URLs."""
        markdown = """
        See [link1](https://example.gov/page).
        Also [link2](https://example.gov/page).
        And <https://example.gov/page>.
        """
        urls = discoverer.extract_urls(markdown, "checksum123")

        # Should deduplicate to single URL
        assert len(urls) == 1
        assert urls[0].url == "https://example.gov/page"

    def test_ignores_relative_urls(
        self,
        discoverer: SourceDiscoverer,
    ) -> None:
        """Should not extract relative URLs."""
        markdown = "See [local](./local.html) and [other](../other.md)."
        urls = discoverer.extract_urls(markdown, "checksum123")

        assert len(urls) == 0

    def test_ignores_anchor_links(
        self,
        discoverer: SourceDiscoverer,
    ) -> None:
        """Should not extract anchor-only links."""
        markdown = "See [Section](#section-1) for more."
        urls = discoverer.extract_urls(markdown, "checksum123")

        assert len(urls) == 0

    def test_extracts_context(
        self,
        discoverer: SourceDiscoverer,
    ) -> None:
        """Should extract surrounding context."""
        markdown = "Before text [Link](https://example.gov/doc) after text."
        urls = discoverer.extract_urls(markdown, "checksum123")

        assert len(urls) == 1
        assert "Before text" in urls[0].context
        assert "after text" in urls[0].context

    def test_http_and_https(
        self,
        discoverer: SourceDiscoverer,
    ) -> None:
        """Should extract both HTTP and HTTPS URLs."""
        markdown = """
        Secure: https://secure.example.gov/page
        Insecure: http://insecure.example.gov/page
        """
        urls = discoverer.extract_urls(markdown, "checksum123")

        assert len(urls) == 2
        extracted = {u.url for u in urls}
        assert "https://secure.example.gov/page" in extracted
        assert "http://insecure.example.gov/page" in extracted


# =============================================================================
# Candidate Filtering Tests
# =============================================================================


class TestCandidateFiltering:
    """Tests for filtering discovered URLs."""

    def test_excludes_registered_sources(
        self,
        discoverer: SourceDiscoverer,
    ) -> None:
        """Should exclude already-registered sources."""
        urls = [
            DiscoveredUrl("https://example.gov/new", "check1", "", ""),
            DiscoveredUrl("https://example.gov/existing", "check1", "", ""),
        ]
        registered = ["https://example.gov/existing"]

        filtered = discoverer.filter_candidates(urls, registered)

        assert len(filtered) == 1
        assert filtered[0].url == "https://example.gov/new"

    def test_excludes_social_media(
        self,
        discoverer: SourceDiscoverer,
    ) -> None:
        """Should exclude social media domains."""
        urls = [
            DiscoveredUrl("https://twitter.com/user", "check1", "", ""),
            DiscoveredUrl("https://facebook.com/page", "check1", "", ""),
            DiscoveredUrl("https://youtube.com/video", "check1", "", ""),
            DiscoveredUrl("https://example.gov/legit", "check1", "", ""),
        ]

        filtered = discoverer.filter_candidates(urls, [])

        assert len(filtered) == 1
        assert filtered[0].url == "https://example.gov/legit"

    def test_excludes_url_shorteners(
        self,
        discoverer: SourceDiscoverer,
    ) -> None:
        """Should exclude URL shortener domains."""
        urls = [
            DiscoveredUrl("https://bit.ly/abc123", "check1", "", ""),
            DiscoveredUrl("https://t.co/xyz789", "check1", "", ""),
            DiscoveredUrl("https://example.edu/legit", "check1", "", ""),
        ]

        filtered = discoverer.filter_candidates(urls, [])

        assert len(filtered) == 1
        assert filtered[0].url == "https://example.edu/legit"

    def test_domain_filter_pattern(
        self,
        discoverer: SourceDiscoverer,
    ) -> None:
        """Should apply domain filter regex."""
        urls = [
            DiscoveredUrl("https://example.gov/page", "check1", "", ""),
            DiscoveredUrl("https://other.edu/page", "check1", "", ""),
            DiscoveredUrl("https://shop.com/page", "check1", "", ""),
        ]

        # Filter to only .gov domains
        filtered = discoverer.filter_candidates(urls, [], domain_filter=r"\.gov$")

        assert len(filtered) == 1
        assert filtered[0].url == "https://example.gov/page"

    def test_domain_filter_multiple_patterns(
        self,
        discoverer: SourceDiscoverer,
    ) -> None:
        """Should support multiple domain patterns."""
        urls = [
            DiscoveredUrl("https://example.gov/page", "check1", "", ""),
            DiscoveredUrl("https://other.edu/page", "check1", "", ""),
            DiscoveredUrl("https://shop.com/page", "check1", "", ""),
        ]

        # Filter to .gov or .edu
        filtered = discoverer.filter_candidates(urls, [], domain_filter=r"\.gov$|\.edu$")

        assert len(filtered) == 2
        domains = {u.domain for u in filtered}
        assert domains == {"example.gov", "other.edu"}

    def test_normalizes_urls_for_comparison(
        self,
        discoverer: SourceDiscoverer,
    ) -> None:
        """Should normalize URLs when checking registered sources."""
        urls = [
            DiscoveredUrl("https://example.gov/page/", "check1", "", ""),  # trailing slash
        ]
        registered = ["https://example.gov/page"]  # no trailing slash

        filtered = discoverer.filter_candidates(urls, registered)

        assert len(filtered) == 0


# =============================================================================
# Credibility Scoring Tests
# =============================================================================


class TestCredibilityScoring:
    """Tests for credibility score calculation."""

    def test_government_domain_high_score(
        self,
        discoverer: SourceDiscoverer,
    ) -> None:
        """Government domains should score high."""
        url = DiscoveredUrl(
            url="https://www.usda.gov/reports/2025.pdf",
            source_checksum="check1",
            context="",
            link_text="",
        )
        score = discoverer.score_candidate(url)

        # Should be high: 0.5 base + 0.35 gov + 0.10 official + 0.05 https = 1.0
        assert score >= 0.9
        assert score <= 1.0

    def test_education_domain_high_score(
        self,
        discoverer: SourceDiscoverer,
    ) -> None:
        """Education domains should score moderately high."""
        url = DiscoveredUrl(
            url="https://research.stanford.edu/paper.pdf",
            source_checksum="check1",
            context="",
            link_text="",
        )
        score = discoverer.score_candidate(url)

        # Should be high: 0.5 base + 0.30 edu + 0.10 official + 0.05 https = 0.95
        assert score >= 0.85
        assert score <= 1.0

    def test_commercial_domain_lower_score(
        self,
        discoverer: SourceDiscoverer,
    ) -> None:
        """Commercial domains should score lower."""
        url = DiscoveredUrl(
            url="https://shop.example.com/product",
            source_checksum="check1",
            context="",
            link_text="",
        )
        score = discoverer.score_candidate(url)

        # Should be lower: 0.5 base - 0.10 commercial + 0.05 https = 0.45
        assert score >= 0.4
        assert score <= 0.5

    def test_http_penalty(
        self,
        discoverer: SourceDiscoverer,
    ) -> None:
        """HTTP (non-secure) should reduce score."""
        url_https = DiscoveredUrl(
            url="https://example.org/page",
            source_checksum="check1",
            context="",
            link_text="",
        )
        url_http = DiscoveredUrl(
            url="http://example.org/page",
            source_checksum="check1",
            context="",
            link_text="",
        )

        score_https = discoverer.score_candidate(url_https)
        score_http = discoverer.score_candidate(url_http)

        assert score_https > score_http

    def test_score_clamped_to_valid_range(
        self,
        discoverer: SourceDiscoverer,
    ) -> None:
        """Score should always be between 0.0 and 1.0."""
        # Government HTTPS should max out at 1.0
        url_high = DiscoveredUrl(
            url="https://www.cia.gov/documents",
            source_checksum="check1",
            context="",
            link_text="",
        )
        score_high = discoverer.score_candidate(url_high)
        assert 0.0 <= score_high <= 1.0

        # Unknown domain HTTP should have minimum score
        url_low = DiscoveredUrl(
            url="http://unknown.xyz/page",
            source_checksum="check1",
            context="",
            link_text="",
        )
        score_low = discoverer.score_candidate(url_low)
        assert 0.0 <= score_low <= 1.0

    def test_organization_domain_moderate_score(
        self,
        discoverer: SourceDiscoverer,
    ) -> None:
        """Organization domains should score moderately."""
        url = DiscoveredUrl(
            url="https://www.example.org/research",
            source_checksum="check1",
            context="",
            link_text="",
        )
        score = discoverer.score_candidate(url)

        # 0.5 base + 0.15 org + 0.05 https = 0.70
        assert score >= 0.65
        assert score <= 0.75


# =============================================================================
# Excluded Domains Tests
# =============================================================================


class TestExcludedDomains:
    """Tests for excluded domain list."""

    def test_social_platforms_in_exclusion_list(self) -> None:
        """Social media platforms should be in excluded domains."""
        # Verify exclusion list contains expected social platforms
        exclusion_set = set(_EXCLUDED_DOMAINS)
        social_domains = {"twitter.com", "x.com", "facebook.com", "instagram.com", "linkedin.com", "youtube.com"}
        assert social_domains.issubset(exclusion_set)

    def test_url_shorteners_in_exclusion_list(self) -> None:
        """URL shorteners should be in excluded domains."""
        exclusion_set = set(_EXCLUDED_DOMAINS)
        shortener_domains = {"bit.ly", "t.co", "tinyurl.com"}
        assert shortener_domains.issubset(exclusion_set)

    def test_code_hosts_in_exclusion_list(self) -> None:
        """Code hosting platforms should be in excluded domains."""
        exclusion_set = set(_EXCLUDED_DOMAINS)
        code_domains = {"github.com", "gitlab.com"}
        assert code_domains.issubset(exclusion_set)


# =============================================================================
# Integration Tests
# =============================================================================


class TestDiscoveryIntegration:
    """Integration tests for full discovery workflow."""

    def test_discover_from_nonexistent_document(
        self,
        discoverer: SourceDiscoverer,
    ) -> None:
        """Should return empty list for nonexistent document."""
        result = discoverer.discover_from_document("nonexistent")
        assert result == []

    def test_discover_all_with_no_storage(
        self,
        discoverer: SourceDiscoverer,
    ) -> None:
        """Should return empty list when storage not initialized."""
        result = discoverer.discover_all()
        assert result == []

    def test_full_workflow_with_temp_storage(
        self,
        tmp_path: Path,
        sample_markdown: str,
    ) -> None:
        """Should discover, filter, and score URLs from actual files."""
        # Create a minimal parsed document structure
        checksum = "test123"
        doc_dir = tmp_path / checksum
        doc_dir.mkdir()
        (doc_dir / "page-001.md").write_text(sample_markdown, encoding="utf-8")

        # Create manifest
        manifest = {
            "version": 1,
            "entries": [
                {
                    "source": "test.html",
                    "checksum": checksum,
                    "parser": "web",
                    "artifact_path": str(doc_dir),
                    "processed_at": "2025-12-24T00:00:00+00:00",
                    "status": "completed",
                }
            ],
        }
        import json
        (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

        discoverer = SourceDiscoverer(parsed_root=tmp_path)
        results = discoverer.discover_all(limit=10)

        # Should find some URLs
        assert len(results) > 0

        # Results should be sorted by score (descending)
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)

        # Government URLs should be near the top
        top_urls = [url.domain_type for url, _ in results[:3]]
        assert "government" in top_urls or "education" in top_urls
