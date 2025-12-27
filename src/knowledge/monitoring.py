"""Source change detection and monitoring utilities.

This module provides the core functionality for detecting content changes
in registered sources. It implements a tiered detection strategy:

1. ETag comparison (cheapest - HEAD request only)
2. Last-Modified comparison (HEAD request)
3. Content hash comparison (requires full GET)

The Monitor Agent uses these utilities to queue sources for acquisition
when changes are detected.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Literal

import requests
from requests.exceptions import SSLError

from src.parsing import utils

if TYPE_CHECKING:
    from .storage import SourceEntry, SourceRegistry


# =============================================================================
# Constants
# =============================================================================

# Mapping from update_frequency to check interval
FREQUENCY_INTERVALS: dict[str, timedelta] = {
    "frequent": timedelta(hours=6),
    "daily": timedelta(hours=24),
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=30),
    "unknown": timedelta(hours=24),
}

# Maximum backoff interval (don't wait more than 7 days between checks)
MAX_BACKOFF_INTERVAL = timedelta(days=7)

# Maximum consecutive failures before marking source degraded
MAX_FAILURES_BEFORE_DEGRADED = 5


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(slots=True)
class PolitenessPolicy:
    """Rate limiting configuration per domain."""

    min_delay_seconds: float = 1.0  # Minimum delay between requests to same domain
    max_delay_seconds: float = 60.0  # Maximum delay (after backoff)
    backoff_factor: float = 2.0  # Multiply delay on failure
    max_failures: int = 5  # Failures before marking source degraded
    respect_robots_txt: bool = True  # Honor robots.txt crawl-delay
    user_agent: str = "speculum-principum-monitor/1.0"


@dataclass(slots=True)
class CheckResult:
    """Result of checking a source for changes."""

    source_url: str
    checked_at: datetime
    status: Literal["unchanged", "changed", "error", "skipped", "initial"]

    # HTTP response metadata
    http_status: int | None = None
    etag: str | None = None
    last_modified: str | None = None
    content_hash: str | None = None

    # Change details (if status == "changed" or "initial")
    detection_method: str | None = None  # "initial" | "etag" | "last_modified" | "content_hash"

    # Error details (if status == "error")
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "source_url": self.source_url,
            "checked_at": self.checked_at.isoformat(),
            "status": self.status,
            "http_status": self.http_status,
            "etag": self.etag,
            "last_modified": self.last_modified,
            "content_hash": self.content_hash,
            "detection_method": self.detection_method,
            "error_message": self.error_message,
        }


@dataclass(slots=True)
class ChangeDetection:
    """Represents a detected content change or initial acquisition need."""

    source_url: str  # URL that changed or needs acquisition
    source_name: str  # Human-readable name
    detected_at: datetime  # When change/need was detected

    # Detection context
    detection_method: str  # "initial" | "etag" | "last_modified" | "content_hash"
    change_type: str  # "initial" | "content" | "metadata"

    # Previous state (None for initial acquisition)
    previous_hash: str | None
    previous_checked: datetime | None

    # Current state
    current_etag: str | None
    current_last_modified: str | None
    current_hash: str | None

    # Classification
    urgency: str = "normal"  # "high" | "normal" | "low"

    @property
    def is_initial(self) -> bool:
        """True if this is an initial acquisition (no previous content)."""
        return self.change_type == "initial"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "source_url": self.source_url,
            "source_name": self.source_name,
            "detected_at": self.detected_at.isoformat(),
            "detection_method": self.detection_method,
            "change_type": self.change_type,
            "previous_hash": self.previous_hash,
            "previous_checked": self.previous_checked.isoformat() if self.previous_checked else None,
            "current_etag": self.current_etag,
            "current_last_modified": self.current_last_modified,
            "current_hash": self.current_hash,
            "urgency": self.urgency,
            "is_initial": self.is_initial,
        }


# =============================================================================
# Utility Functions
# =============================================================================


def calculate_next_check(source: "SourceEntry", check_failed: bool) -> datetime:
    """Calculate when to next check a source.
    
    Args:
        source: The source entry with update_frequency and check_failures
        check_failed: Whether the current check failed
        
    Returns:
        datetime: When the source should next be checked
    """
    base_interval = FREQUENCY_INTERVALS.get(
        source.update_frequency or "unknown",
        timedelta(hours=24),
    )

    if not check_failed:
        # Success: check after base interval
        return datetime.now(timezone.utc) + base_interval

    # Failure: exponential backoff
    # Use check_failures + 1 because we're calculating for after this failure
    failure_count = source.check_failures + 1
    backoff_multiplier = min(2**failure_count, 32)  # Cap at 32x
    backoff_interval = base_interval * backoff_multiplier

    # Don't wait more than 7 days between checks
    return datetime.now(timezone.utc) + min(backoff_interval, MAX_BACKOFF_INTERVAL)


def calculate_urgency(source: "SourceEntry", is_initial: bool) -> str:
    """Determine urgency level for a detection.
    
    Args:
        source: The source entry
        is_initial: Whether this is an initial acquisition
        
    Returns:
        str: Urgency level ("high", "normal", or "low")
    """
    if is_initial:
        # Initial acquisition urgency rules
        if source.source_type == "primary":
            return "high"
        if source.source_type == "derived" and source.is_official:
            return "normal"
        if source.source_type == "reference":
            return "low"
        return "normal"

    # Update monitoring urgency rules
    if source.source_type == "primary":
        return "high"
    
    # Boost urgency for recently added sources
    days_since_added = (datetime.now(timezone.utc) - source.added_at).days
    if days_since_added <= 7:
        if source.source_type == "derived":
            return "high"  # Boost from normal
        return "normal"  # Boost from low
    
    if source.source_type == "derived":
        return "normal"
    
    return "low"


# =============================================================================
# Source Monitor Class
# =============================================================================


@dataclass
class SourceMonitor:
    """Monitors sources for content changes.
    
    Uses a tiered detection strategy:
    1. ETag comparison (HEAD request)
    2. Last-Modified comparison (HEAD request)
    3. Content hash comparison (GET request, only if tiers 1-2 indicate change)
    """

    registry: "SourceRegistry"
    timeout: float = 10.0
    user_agent: str = "speculum-principum-monitor/1.0"
    _session: requests.Session = field(default_factory=requests.Session, repr=False)

    def __post_init__(self) -> None:
        """Initialize HTTP session with user agent."""
        self._session.headers["User-Agent"] = self.user_agent

    def get_sources_pending_initial(self) -> list["SourceEntry"]:
        """Return sources that need initial acquisition.
        
        These are sources where last_content_hash is None, meaning
        they have never been acquired.
        
        Returns:
            list[SourceEntry]: Sources needing initial acquisition
        """
        return [
            s
            for s in self.registry.list_sources(status="active")
            if s.last_content_hash is None
        ]

    def get_sources_due_for_check(self) -> list["SourceEntry"]:
        """Return sources that should be checked for updates.
        
        These are sources where:
        1. last_content_hash is not None (already acquired)
        2. next_check_after is None or has passed
        
        Returns:
            list[SourceEntry]: Sources due for update check
        """
        now = datetime.now(timezone.utc)
        return [
            s
            for s in self.registry.list_sources(status="active")
            if s.last_content_hash is not None
            and (s.next_check_after is None or s.next_check_after <= now)
        ]

    def check_source(
        self,
        source: "SourceEntry",
        force_full: bool = False,
    ) -> CheckResult:
        """Check a source for changes using tiered detection.
        
        Args:
            source: The source to check
            force_full: If True, skip tiered detection and do full hash comparison
            
        Returns:
            CheckResult: Result of the check
        """
        now = datetime.now(timezone.utc)

        # Mode 1: Initial acquisition (no previous hash)
        if source.last_content_hash is None:
            return CheckResult(
                source_url=source.url,
                checked_at=now,
                status="initial",
                detection_method="initial",
            )

        # Mode 2: Update monitoring with tiered detection
        try:
            if not force_full:
                # Tier 1: Check ETag
                etag_result = self._check_etag(source)
                if etag_result is not None:
                    if etag_result.status == "unchanged":
                        return etag_result
                    # ETag changed, proceed to verify with content hash

                # Tier 2: Check Last-Modified (if no ETag or ETag changed)
                modified_result = self._check_last_modified(source)
                if modified_result is not None:
                    if modified_result.status == "unchanged":
                        return modified_result
                    # Last-Modified indicates change, verify with content hash

            # Tier 3: Full content hash comparison
            return self._check_content_hash(source)

        except requests.Timeout:
            return CheckResult(
                source_url=source.url,
                checked_at=now,
                status="error",
                error_message="Request timed out",
            )
        except SSLError as e:
            return CheckResult(
                source_url=source.url,
                checked_at=now,
                status="error",
                error_message=f"SSL error: {e}",
            )
        except requests.RequestException as e:
            return CheckResult(
                source_url=source.url,
                checked_at=now,
                status="error",
                error_message=str(e),
            )

    def _check_etag(self, source: "SourceEntry") -> CheckResult | None:
        """Check if ETag has changed (Tier 1).
        
        Returns:
            CheckResult if ETag comparison is conclusive, None otherwise
        """
        if source.last_etag is None:
            # No previous ETag to compare
            return None

        now = datetime.now(timezone.utc)
        response = self._session.head(source.url, timeout=self.timeout, allow_redirects=True)
        current_etag = response.headers.get("ETag")

        if current_etag is None:
            # Server doesn't provide ETag anymore
            return None

        if current_etag == source.last_etag:
            return CheckResult(
                source_url=source.url,
                checked_at=now,
                status="unchanged",
                http_status=response.status_code,
                etag=current_etag,
            )

        # ETag changed - need to verify with content hash
        return CheckResult(
            source_url=source.url,
            checked_at=now,
            status="changed",
            http_status=response.status_code,
            etag=current_etag,
            detection_method="etag",
        )

    def _check_last_modified(self, source: "SourceEntry") -> CheckResult | None:
        """Check if Last-Modified has changed (Tier 2).
        
        Returns:
            CheckResult if Last-Modified comparison is conclusive, None otherwise
        """
        if source.last_modified_header is None:
            # No previous Last-Modified to compare
            return None

        now = datetime.now(timezone.utc)
        response = self._session.head(source.url, timeout=self.timeout, allow_redirects=True)
        current_last_modified = response.headers.get("Last-Modified")

        if current_last_modified is None:
            # Server doesn't provide Last-Modified anymore
            return None

        if current_last_modified == source.last_modified_header:
            return CheckResult(
                source_url=source.url,
                checked_at=now,
                status="unchanged",
                http_status=response.status_code,
                last_modified=current_last_modified,
            )

        # Last-Modified changed - need to verify with content hash
        return CheckResult(
            source_url=source.url,
            checked_at=now,
            status="changed",
            http_status=response.status_code,
            last_modified=current_last_modified,
            detection_method="last_modified",
        )

    def _check_content_hash(self, source: "SourceEntry") -> CheckResult:
        """Check if content hash has changed (Tier 3).
        
        This performs a full GET request and computes the content hash.
        """
        now = datetime.now(timezone.utc)
        response = self._session.get(source.url, timeout=self.timeout, allow_redirects=True)
        response.raise_for_status()

        current_hash = utils.sha256_bytes(response.content)
        current_etag = response.headers.get("ETag")
        current_last_modified = response.headers.get("Last-Modified")

        if current_hash == source.last_content_hash:
            return CheckResult(
                source_url=source.url,
                checked_at=now,
                status="unchanged",
                http_status=response.status_code,
                etag=current_etag,
                last_modified=current_last_modified,
                content_hash=current_hash,
            )

        return CheckResult(
            source_url=source.url,
            checked_at=now,
            status="changed",
            http_status=response.status_code,
            etag=current_etag,
            last_modified=current_last_modified,
            content_hash=current_hash,
            detection_method="content_hash",
        )

    def create_change_detection(
        self,
        source: "SourceEntry",
        result: CheckResult,
    ) -> ChangeDetection:
        """Create a ChangeDetection from a CheckResult.
        
        Args:
            source: The source that was checked
            result: The check result indicating change or initial
            
        Returns:
            ChangeDetection: The detection object for Issue creation
        """
        is_initial = result.status == "initial"
        change_type = "initial" if is_initial else "content"
        urgency = calculate_urgency(source, is_initial)

        return ChangeDetection(
            source_url=source.url,
            source_name=source.name,
            detected_at=result.checked_at,
            detection_method=result.detection_method or "initial",
            change_type=change_type,
            previous_hash=source.last_content_hash,
            previous_checked=source.last_checked,
            current_etag=result.etag,
            current_last_modified=result.last_modified,
            current_hash=result.content_hash,
            urgency=urgency,
        )
