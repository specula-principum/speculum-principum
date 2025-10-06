"""
Deduplication System
Manages tracking of processed URLs and prevents duplicate GitHub issues
"""

import json
import logging
import hashlib
import os
import shutil
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Any, Union
from pathlib import Path

from ..clients.search_client import SearchResult, normalize_url


logger = logging.getLogger(__name__)


class ProcessedEntry:
    """Represents a processed search result entry"""
    
    def __init__(
        self,
        url: str,
        title: str,
        site_name: str,
        issue_number: Optional[int] = None,
        processed_at: Optional[datetime] = None,
        artifact_path: Optional[str] = None,
        capture_status: Optional[str] = None,
    ):
        self.url = url
        self.normalized_url = normalize_url(url)
        self.title = title
        self.site_name = site_name
        self.issue_number = issue_number
        self.processed_at = processed_at or datetime.utcnow()
        self.content_hash = self._generate_content_hash()
        self.artifact_path = artifact_path
        self.capture_status = capture_status
    
    def _generate_content_hash(self) -> str:
        """Generate hash from URL and title for deduplication"""
        content = f"{self.normalized_url}|{self.title.lower().strip()}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'url': self.url,
            'normalized_url': self.normalized_url,
            'title': self.title,
            'site_name': self.site_name,
            'issue_number': self.issue_number,
            'processed_at': self.processed_at.isoformat(),
            'content_hash': self.content_hash,
            'artifact_path': self.artifact_path,
            'capture_status': self.capture_status,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessedEntry':
        """Create ProcessedEntry from dictionary"""
        entry = cls(
            url=data['url'],
            title=data['title'],
            site_name=data['site_name'],
            issue_number=data.get('issue_number'),
            processed_at=datetime.fromisoformat(data['processed_at']),
            artifact_path=data.get('artifact_path'),
            capture_status=data.get('capture_status'),
        )
        # Use stored hash if available, otherwise regenerate
        if 'content_hash' in data:
            entry.content_hash = data['content_hash']
        return entry
    
    def __str__(self):
        return f"ProcessedEntry(url='{self.url}', site='{self.site_name}', issue=#{self.issue_number})"
    
    def __repr__(self):
        return self.__str__()


class DeduplicationManager:
    """Manages deduplication of search results and GitHub issues"""
    
    def __init__(self, storage_path: str = "processed_urls.json", 
                 retention_days: int = 30):
        self.storage_path = Path(storage_path)
        self.retention_days = retention_days
        self.processed_entries: Dict[str, ProcessedEntry] = {}
        self.url_to_hash: Dict[str, str] = {}  # Maps normalized URLs to content hashes
        self.title_hashes: Set[str] = set()  # Track similar titles
        self.artifacts_base_dir: Optional[Path] = None
        
        self._load_processed_entries()
        logger.info(f"Initialized deduplication manager with {len(self.processed_entries)} entries")

    def set_artifacts_base_dir(self, artifacts_dir: Optional[Union[str, Path]]) -> None:
        """Set the base directory for stored capture artifacts."""

        if not artifacts_dir:
            self.artifacts_base_dir = None
            return

        try:
            base_path = Path(artifacts_dir).resolve()
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning("Failed to resolve artifacts directory %s: %s", artifacts_dir, exc)
            self.artifacts_base_dir = None
            return

        self.artifacts_base_dir = base_path
    
    def _load_processed_entries(self) -> None:
        """Load processed entries from storage file"""
        if not self.storage_path.exists():
            logger.info(f"Storage file {self.storage_path} doesn't exist, starting fresh")
            return
        
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
            
            entries_data = data.get('entries', [])
            for entry_data in entries_data:
                try:
                    entry = ProcessedEntry.from_dict(entry_data)
                    self.processed_entries[entry.content_hash] = entry
                    self.url_to_hash[entry.normalized_url] = entry.content_hash
                    self.title_hashes.add(entry.content_hash)
                except Exception as e:
                    logger.warning(f"Error loading processed entry: {e}")
                    continue
            
            logger.info(f"Loaded {len(self.processed_entries)} processed entries from storage")
            
            # Clean up old entries
            self._cleanup_old_entries()
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing storage file {self.storage_path}: {e}")
            # Backup corrupted file and start fresh
            backup_path = f"{self.storage_path}.backup.{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            self.storage_path.rename(backup_path)
            logger.warning(f"Corrupted storage file backed up to {backup_path}")
        except Exception as e:
            logger.error(f"Error loading processed entries: {e}")
    
    def _cleanup_old_entries(self) -> None:
        """Remove entries older than retention period"""
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
        old_hashes = [
            content_hash for content_hash, entry in self.processed_entries.items()
            if entry.processed_at < cutoff_date
        ]
        
        for content_hash in old_hashes:
            entry = self.processed_entries.pop(content_hash)
            self.url_to_hash.pop(entry.normalized_url, None)
            self.title_hashes.discard(content_hash)
            self._remove_capture_artifacts(entry.artifact_path)
        
        if old_hashes:
            logger.info(f"Cleaned up {len(old_hashes)} old entries (older than {self.retention_days} days)")
    
    def _remove_capture_artifacts(self, artifact_path: Optional[str]) -> None:
        """Delete stored capture artifacts associated with a processed entry."""

        if not artifact_path or not self.artifacts_base_dir:
            return

        target_path = Path(artifact_path)
        candidates = []

        if target_path.is_absolute():
            candidates.append(target_path)
        else:
            candidates.append(self.artifacts_base_dir / target_path.name)
            candidates.append(self.artifacts_base_dir / target_path)

        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except (OSError, RuntimeError):  # pragma: no cover - filesystem failures
                continue

            try:
                resolved.relative_to(self.artifacts_base_dir)
            except ValueError:
                continue

            if resolved.exists() and resolved.is_dir():
                try:
                    shutil.rmtree(resolved)
                    logger.debug("Removed capture artifacts at %s", resolved)
                except OSError as exc:  # pragma: no cover - filesystem edge case
                    logger.warning("Failed to remove capture artifacts at %s: %s", resolved, exc)
                finally:
                    return
    
    def save_processed_entries(self) -> None:
        """Save processed entries to storage file"""
        try:
            # Ensure directory exists
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'metadata': {
                    'last_updated': datetime.utcnow().isoformat(),
                    'total_entries': len(self.processed_entries),
                    'retention_days': self.retention_days
                },
                'entries': [entry.to_dict() for entry in self.processed_entries.values()]
            }
            
            # Write to temporary file first, then rename (atomic operation)
            temp_path = f"{self.storage_path}.tmp"
            with open(temp_path, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=2, ensure_ascii=False)
            
            # Atomic rename
            os.rename(temp_path, self.storage_path)
            
            logger.debug(f"Saved {len(self.processed_entries)} processed entries to {self.storage_path}")
            
        except Exception as e:
            logger.error(f"Error saving processed entries: {e}")
            raise
    
    def is_result_processed(self, result: SearchResult, site_name: str) -> bool:
        """
        Check if a search result has already been processed
        
        Args:
            result: SearchResult to check
            site_name: Name of the site this result came from
            
        Returns:
            True if the result has been processed before
        """
        # Create temporary entry to generate hash
        temp_entry = ProcessedEntry(
            url=result.link,
            title=result.title,
            site_name=site_name
        )
        
        # Check if we've seen this exact content before
        if temp_entry.content_hash in self.processed_entries:
            logger.debug(f"Result already processed: {result.link}")
            return True
        
        # Check for similar URLs (different query params, etc.)
        normalized_url = normalize_url(result.link)
        if normalized_url in self.url_to_hash:
            existing_hash = self.url_to_hash[normalized_url]
            existing_entry = self.processed_entries.get(existing_hash)
            if existing_entry:
                logger.debug(f"Similar URL already processed: {result.link} -> {existing_entry.url}")
                return True
        
        return False
    
    def mark_result_processed(
        self,
        result: SearchResult,
        site_name: str,
        issue_number: Optional[int] = None,
        artifact_path: Optional[str] = None,
        capture_status: Optional[str] = None,
    ) -> ProcessedEntry:
        """
        Mark a search result as processed
        
        Args:
            result: SearchResult that was processed
            site_name: Name of the site this result came from
            issue_number: GitHub issue number if an issue was created
            
        Returns:
            ProcessedEntry object
        """
        entry = ProcessedEntry(
            url=result.link,
            title=result.title,
            site_name=site_name,
            issue_number=issue_number,
            artifact_path=artifact_path,
            capture_status=capture_status,
        )
        
        # Store the entry
        self.processed_entries[entry.content_hash] = entry
        self.url_to_hash[entry.normalized_url] = entry.content_hash
        self.title_hashes.add(entry.content_hash)
        
        logger.debug(f"Marked result as processed: {result.link} (issue #{issue_number})")
        
        return entry
    
    def filter_new_results(self, results: List[SearchResult], site_name: str) -> List[SearchResult]:
        """
        Filter search results to only include new/unprocessed ones
        
        Args:
            results: List of SearchResult objects
            site_name: Name of the site these results came from
            
        Returns:
            List of new SearchResult objects
        """
        new_results = []
        
        for result in results:
            if not self.is_result_processed(result, site_name):
                new_results.append(result)
        
        logger.info(f"Filtered {len(results)} results to {len(new_results)} new results for site '{site_name}'")
        
        return new_results

    def get_entry_by_hash(self, content_hash: str) -> Optional[ProcessedEntry]:
        """Retrieve a processed entry by its content hash."""
        return self.processed_entries.get(content_hash)

    def get_entry_by_url(self, url: str) -> Optional[ProcessedEntry]:
        """Retrieve a processed entry by normalized URL."""
        if not url:
            return None
        normalized = normalize_url(url)
        existing_hash = self.url_to_hash.get(normalized)
        if not existing_hash:
            return None
        return self.processed_entries.get(existing_hash)
    
    def get_processed_stats(self) -> Dict[str, Any]:
        """Get statistics about processed entries"""
        if not self.processed_entries:
            empty_capture_summary = {
                'total_attempts': 0,
                'success': 0,
                'failures': 0,
                'empty': 0,
                'disabled': 0,
                'unknown': 0,
                'persisted_artifacts': 0,
            }
            return {
                'total_entries': 0,
                'entries_by_site': {},
                'entries_with_issues': 0,
                'oldest_entry': None,
                'newest_entry': None,
                'retention_days': self.retention_days,
                'capture_status_counts': {},
                'capture_summary': empty_capture_summary,
            }
        
        entries_by_site = {}
        entries_with_issues = 0
        oldest_entry = min(self.processed_entries.values(), key=lambda e: e.processed_at)
        newest_entry = max(self.processed_entries.values(), key=lambda e: e.processed_at)
        capture_status_counts: Dict[str, int] = defaultdict(int)
        captures_with_artifacts = 0
        
        for entry in self.processed_entries.values():
            site_name = entry.site_name
            if site_name not in entries_by_site:
                entries_by_site[site_name] = 0
            entries_by_site[site_name] += 1
            
            if entry.issue_number is not None:
                entries_with_issues += 1

            status_key = (entry.capture_status or 'unknown').lower()
            capture_status_counts[status_key] += 1

            if entry.artifact_path:
                captures_with_artifacts += 1

        non_attempt_statuses = {'unknown', 'disabled', None}
        failure_statuses = {'failed', 'error'}

        total_attempts = sum(
            count for status, count in capture_status_counts.items() if status not in non_attempt_statuses
        )
        failure_count = sum(capture_status_counts.get(status, 0) for status in failure_statuses)

        capture_summary = {
            'total_attempts': total_attempts,
            'success': capture_status_counts.get('success', 0),
            'failures': failure_count,
            'empty': capture_status_counts.get('empty', 0),
            'disabled': capture_status_counts.get('disabled', 0),
            'unknown': capture_status_counts.get('unknown', 0),
            'persisted_artifacts': captures_with_artifacts,
            'failed_breakdown': {
                'failed': capture_status_counts.get('failed', 0),
                'error': capture_status_counts.get('error', 0),
            },
        }
        
        return {
            'total_entries': len(self.processed_entries),
            'entries_by_site': entries_by_site,
            'entries_with_issues': entries_with_issues,
            'oldest_entry': oldest_entry.processed_at.isoformat(),
            'newest_entry': newest_entry.processed_at.isoformat(),
            'retention_days': self.retention_days,
            'capture_status_counts': dict(capture_status_counts),
            'capture_summary': capture_summary,
        }
    

    

    
    def cleanup_storage(self) -> None:
        """Manual cleanup of storage (removes old entries and saves)"""
        original_count = len(self.processed_entries)
        self._cleanup_old_entries()
        self.save_processed_entries()
        
        removed_count = original_count - len(self.processed_entries)
        if removed_count > 0:
            logger.info(f"Cleanup completed: removed {removed_count} old entries")
        else:
            logger.info("Cleanup completed: no old entries to remove")


def create_url_fingerprint(url: str, title: str = "") -> str:
    """
    Create a unique fingerprint for a URL and title combination
    
    This is used for deduplication when you need a simple hash
    without creating a full ProcessedEntry object.
    
    Args:
        url: URL to fingerprint
        title: Optional title to include in fingerprint
        
    Returns:
        16-character hash string
    """
    normalized_url = normalize_url(url)
    content = f"{normalized_url}|{title.lower().strip()}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]


def merge_deduplication_files(file_paths: List[str], output_path: str) -> None:
    """
    Merge multiple deduplication storage files into one
    
    This is useful if you have multiple instances running or want to
    combine historical data.
    
    Args:
        file_paths: List of paths to deduplication files to merge
        output_path: Path where merged file will be saved
    """
    all_entries = {}
    
    for file_path in file_paths:
        if not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}")
            continue
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
            
            entries_data = data.get('entries', [])
            for entry_data in entries_data:
                try:
                    entry = ProcessedEntry.from_dict(entry_data)
                    # Use the most recent entry if duplicates exist
                    existing = all_entries.get(entry.content_hash)
                    if not existing or entry.processed_at > existing.processed_at:
                        all_entries[entry.content_hash] = entry
                except Exception as e:
                    logger.warning(f"Error loading entry from {file_path}: {e}")
                    
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
    
    # Save merged data
    merged_data = {
        'metadata': {
            'last_updated': datetime.utcnow().isoformat(),
            'total_entries': len(all_entries),
            'merged_from': file_paths,
            'retention_days': 30
        },
        'entries': [entry.to_dict() for entry in all_entries.values()]
    }
    
    with open(output_path, 'w', encoding='utf-8') as file:
        json.dump(merged_data, file, indent=2, ensure_ascii=False)
    
    logger.info(f"Merged {len(file_paths)} files into {output_path} with {len(all_entries)} unique entries")