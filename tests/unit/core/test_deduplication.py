"""
Unit tests for the deduplication module
"""

import pytest
import tempfile
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch

from src.core.deduplication import (
    ProcessedEntry, DeduplicationManager, create_url_fingerprint, 
    merge_deduplication_files
)
from src.clients.search_client import SearchResult


class TestProcessedEntry:
    """Test the ProcessedEntry class"""
    
    def test_processed_entry_creation(self):
        """Test creating a ProcessedEntry"""
        entry = ProcessedEntry(
            url="https://example.com/page",
            title="Test Page",
            site_name="Example Site"
        )
        
        assert entry.url == "https://example.com/page"
        assert entry.title == "Test Page"
        assert entry.site_name == "Example Site"
        assert entry.issue_number is None
        assert isinstance(entry.processed_at, datetime)
        assert len(entry.content_hash) == 16
        assert entry.normalized_url == "https://example.com/page"
    
    def test_processed_entry_with_issue(self):
        """Test creating ProcessedEntry with issue number"""
        entry = ProcessedEntry(
            url="https://example.com/page",
            title="Test Page",
            site_name="Example Site",
            issue_number=42
        )
        
        assert entry.issue_number == 42
    
    def test_content_hash_generation(self):
        """Test that content hash is generated consistently"""
        entry1 = ProcessedEntry(
            url="https://example.com/page",
            title="Test Page",
            site_name="Example Site"
        )
        
        entry2 = ProcessedEntry(
            url="https://example.com/page",
            title="Test Page",
            site_name="Example Site"
        )
        
        assert entry1.content_hash == entry2.content_hash
    
    def test_content_hash_different_for_different_content(self):
        """Test that different content produces different hashes"""
        entry1 = ProcessedEntry(
            url="https://example.com/page1",
            title="Test Page",
            site_name="Example Site"
        )
        
        entry2 = ProcessedEntry(
            url="https://example.com/page2",
            title="Test Page",
            site_name="Example Site"
        )
        
        assert entry1.content_hash != entry2.content_hash
    
    def test_to_dict(self):
        """Test converting ProcessedEntry to dictionary"""
        entry = ProcessedEntry(
            url="https://example.com/page",
            title="Test Page",
            site_name="Example Site",
            issue_number=42
        )
        
        data = entry.to_dict()
        
        assert data['url'] == "https://example.com/page"
        assert data['title'] == "Test Page"
        assert data['site_name'] == "Example Site"
        assert data['issue_number'] == 42
        assert 'processed_at' in data
        assert 'content_hash' in data
        assert 'normalized_url' in data
    
    def test_from_dict(self):
        """Test creating ProcessedEntry from dictionary"""
        data = {
            'url': "https://example.com/page",
            'title': "Test Page",
            'site_name': "Example Site",
            'issue_number': 42,
            'processed_at': datetime.utcnow().isoformat(),
            'content_hash': 'testhash123456',
            'normalized_url': "https://example.com/page"
        }
        
        entry = ProcessedEntry.from_dict(data)
        
        assert entry.url == "https://example.com/page"
        assert entry.title == "Test Page"
        assert entry.site_name == "Example Site"
        assert entry.issue_number == 42
        assert entry.content_hash == 'testhash123456'


class TestDeduplicationManager:
    """Test the DeduplicationManager class"""
    
    def test_manager_creation_no_file(self):
        """Test creating manager when storage file doesn't exist"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = os.path.join(temp_dir, "test_processed.json")
            manager = DeduplicationManager(storage_path=storage_path)
            
            assert len(manager.processed_entries) == 0
            assert len(manager.url_to_hash) == 0
            assert len(manager.title_hashes) == 0
    
    def test_manager_creation_with_existing_file(self):
        """Test creating manager with existing storage file"""
        # Create test data
        test_entries = [
            {
                'url': "https://example.com/page1",
                'title': "Test Page 1",
                'site_name': "Example Site",
                'issue_number': 1,
                'processed_at': datetime.utcnow().isoformat(),
                'content_hash': 'hash1',
                'normalized_url': "https://example.com/page1"
            },
            {
                'url': "https://example.com/page2",
                'title': "Test Page 2",
                'site_name': "Example Site",
                'issue_number': 2,
                'processed_at': datetime.utcnow().isoformat(),
                'content_hash': 'hash2',
                'normalized_url': "https://example.com/page2"
            }
        ]
        
        test_data = {
            'metadata': {
                'last_updated': datetime.utcnow().isoformat(),
                'total_entries': 2
            },
            'entries': test_entries
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_data, f)
            f.flush()
            
            try:
                manager = DeduplicationManager(storage_path=f.name)
                
                assert len(manager.processed_entries) == 2
                assert 'hash1' in manager.processed_entries
                assert 'hash2' in manager.processed_entries
                assert len(manager.url_to_hash) == 2
                assert len(manager.title_hashes) == 2
                
            finally:
                os.unlink(f.name)
    
    def test_manager_loads_legacy_entries_without_capture_metadata(self):
        """Legacy storage files without capture data should still load."""
        legacy_entry = {
            'url': "https://example.com/legacy",
            'title': "Legacy Page",
            'site_name': "Legacy Site",
            'processed_at': datetime.utcnow().isoformat(),
            'content_hash': 'legacyhash123456',
        }
        legacy_data = {
            'metadata': {'last_updated': datetime.utcnow().isoformat(), 'total_entries': 1},
            'entries': [legacy_entry],
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as handle:
            json.dump(legacy_data, handle)
            temp_path = handle.name

        try:
            manager = DeduplicationManager(storage_path=temp_path)
            entry = manager.get_entry_by_hash('legacyhash123456')
            assert entry is not None
            assert entry.artifact_path is None
            assert entry.capture_status is None

            manager.save_processed_entries()

            saved_data = json.loads(Path(temp_path).read_text(encoding='utf-8'))
            saved_entry = saved_data['entries'][0]
            assert 'artifact_path' in saved_entry
            assert 'capture_status' in saved_entry
        finally:
            os.unlink(temp_path)

    def test_mark_result_processed(self):
        """Test marking a search result as processed"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = os.path.join(temp_dir, "test_processed.json")
            manager = DeduplicationManager(storage_path=storage_path)
            
            result = SearchResult(
                title="Test Page",
                link="https://example.com/page",
                snippet="Test snippet"
            )
            
            entry = manager.mark_result_processed(result, "Example Site", issue_number=42)
            
            assert entry.url == "https://example.com/page"
            assert entry.title == "Test Page"
            assert entry.site_name == "Example Site"
            assert entry.issue_number == 42
            
            # Check it was added to the manager
            assert entry.content_hash in manager.processed_entries
            assert entry.normalized_url in manager.url_to_hash
            assert entry.content_hash in manager.title_hashes
    
    def test_is_result_processed_new_result(self):
        """Test checking if a new result is processed"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = os.path.join(temp_dir, "test_processed.json")
            manager = DeduplicationManager(storage_path=storage_path)
            
            result = SearchResult(
                title="New Page",
                link="https://example.com/new",
                snippet="New snippet"
            )
            
            assert manager.is_result_processed(result, "Example Site") is False
    
    def test_is_result_processed_existing_result(self):
        """Test checking if an existing result is processed"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = os.path.join(temp_dir, "test_processed.json")
            manager = DeduplicationManager(storage_path=storage_path)
            
            result = SearchResult(
                title="Test Page",
                link="https://example.com/page",
                snippet="Test snippet"
            )
            
            # Mark as processed first
            manager.mark_result_processed(result, "Example Site")
            
            # Check if it's detected as processed
            assert manager.is_result_processed(result, "Example Site") is True
    
    def test_filter_new_results(self):
        """Test filtering search results to only new ones"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = os.path.join(temp_dir, "test_processed.json")
            manager = DeduplicationManager(storage_path=storage_path)
            
            # Create test results
            result1 = SearchResult("Page 1", "https://example.com/page1", "Snippet 1")
            result2 = SearchResult("Page 2", "https://example.com/page2", "Snippet 2")
            result3 = SearchResult("Page 3", "https://example.com/page3", "Snippet 3")
            
            all_results = [result1, result2, result3]
            
            # Mark result2 as processed
            manager.mark_result_processed(result2, "Example Site")
            
            # Filter results
            new_results = manager.filter_new_results(all_results, "Example Site")
            
            assert len(new_results) == 2
            assert result1 in new_results
            assert result3 in new_results
            assert result2 not in new_results
    
    def test_save_and_load_processed_entries(self):
        """Test saving and loading processed entries"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = os.path.join(temp_dir, "test_processed.json")
            
            # Create manager and add some entries
            manager1 = DeduplicationManager(storage_path=storage_path)
            
            result1 = SearchResult("Page 1", "https://example.com/page1", "Snippet 1")
            result2 = SearchResult("Page 2", "https://example.com/page2", "Snippet 2")
            
            manager1.mark_result_processed(result1, "Site 1", issue_number=1)
            manager1.mark_result_processed(result2, "Site 2", issue_number=2)
            
            # Save entries
            manager1.save_processed_entries()
            
            # Create new manager and load entries
            manager2 = DeduplicationManager(storage_path=storage_path)
            
            assert len(manager2.processed_entries) == 2
            assert manager2.is_result_processed(result1, "Site 1") is True
            assert manager2.is_result_processed(result2, "Site 2") is True
    
    def test_cleanup_old_entries(self):
        """Test cleaning up old entries"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = os.path.join(temp_dir, "test_processed.json")
            manager = DeduplicationManager(storage_path=storage_path, retention_days=7)
            artifacts_dir = Path(temp_dir) / "artifacts" / "discoveries"
            artifacts_dir.mkdir(parents=True)
            manager.set_artifacts_base_dir(artifacts_dir)
            
            # Create old and new entries
            old_result = SearchResult("Old Page", "https://example.com/old", "Old snippet")
            new_result = SearchResult("New Page", "https://example.com/new", "New snippet")
            
            # Mark old result with old timestamp
            old_entry = manager.mark_result_processed(old_result, "Site", issue_number=1)
            old_entry.processed_at = datetime.utcnow() - timedelta(days=10)
            old_entry.artifact_path = f"{artifacts_dir.name}/{old_entry.content_hash}"
            (artifacts_dir / old_entry.content_hash).mkdir(parents=True, exist_ok=True)
            manager.processed_entries[old_entry.content_hash] = old_entry
            
            # Mark new result
            manager.mark_result_processed(new_result, "Site", issue_number=2)
            
            initial_count = len(manager.processed_entries)
            assert initial_count == 2
            
            # Cleanup
            manager._cleanup_old_entries()
            
            # Should have removed the old entry
            assert len(manager.processed_entries) == 1
            assert manager.is_result_processed(new_result, "Site") is True
            assert manager.is_result_processed(old_result, "Site") is False
            assert not (artifacts_dir / old_entry.content_hash).exists()
    
    def test_get_processed_stats(self):
        """Test getting processed statistics"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = os.path.join(temp_dir, "test_processed.json")
            manager = DeduplicationManager(storage_path=storage_path)
            
            # Add some entries
            result1 = SearchResult("Page 1", "https://example.com/page1", "Snippet 1")
            result2 = SearchResult("Page 2", "https://example.com/page2", "Snippet 2")
            result3 = SearchResult("Page 3", "https://example.com/page3", "Snippet 3")
            
            entry1 = manager.mark_result_processed(result1, "Site A", issue_number=1)
            entry1.capture_status = "success"
            entry1.artifact_path = f"artifacts/discoveries/{entry1.content_hash}"

            entry2 = manager.mark_result_processed(result2, "Site A", issue_number=2)
            entry2.capture_status = "failed"

            entry3 = manager.mark_result_processed(result3, "Site B")  # No issue number
            entry3.capture_status = None
            
            stats = manager.get_processed_stats()
            
            assert stats['total_entries'] == 3
            assert stats['entries_with_issues'] == 2
            assert stats['entries_by_site']['Site A'] == 2
            assert stats['entries_by_site']['Site B'] == 1
            assert 'oldest_entry' in stats
            assert 'newest_entry' in stats
            assert stats['capture_status_counts']['success'] == 1
            assert stats['capture_status_counts']['failed'] == 1
            assert stats['capture_status_counts']['unknown'] == 1
            summary = stats['capture_summary']
            assert summary['success'] == 1
            assert summary['failures'] == 1
            assert summary['unknown'] == 1
            assert summary['persisted_artifacts'] == 1
            assert summary['total_attempts'] == 2
    



class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_create_url_fingerprint(self):
        """Test creating URL fingerprint"""
        fingerprint1 = create_url_fingerprint("https://example.com/page", "Test Title")
        fingerprint2 = create_url_fingerprint("https://example.com/page", "Test Title")
        
        assert fingerprint1 == fingerprint2
        assert len(fingerprint1) == 16
    
    def test_create_url_fingerprint_different_urls(self):
        """Test that different URLs produce different fingerprints"""
        fingerprint1 = create_url_fingerprint("https://example.com/page1", "Test Title")
        fingerprint2 = create_url_fingerprint("https://example.com/page2", "Test Title")
        
        assert fingerprint1 != fingerprint2
    
    def test_merge_deduplication_files(self):
        """Test merging multiple deduplication files"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create two test files
            file1_path = os.path.join(temp_dir, "file1.json")
            file2_path = os.path.join(temp_dir, "file2.json")
            output_path = os.path.join(temp_dir, "merged.json")
            
            # Create test data for file 1
            data1 = {
                'metadata': {'total_entries': 1},
                'entries': [
                    {
                        'url': "https://example.com/page1",
                        'title': "Page 1",
                        'site_name': "Site A",
                        'processed_at': datetime.utcnow().isoformat(),
                        'content_hash': 'hash1',
                        'normalized_url': "https://example.com/page1"
                    }
                ]
            }
            
            # Create test data for file 2
            data2 = {
                'metadata': {'total_entries': 1},
                'entries': [
                    {
                        'url': "https://example.com/page2",
                        'title': "Page 2",
                        'site_name': "Site B",
                        'processed_at': datetime.utcnow().isoformat(),
                        'content_hash': 'hash2',
                        'normalized_url': "https://example.com/page2"
                    }
                ]
            }
            
            # Write test files
            with open(file1_path, 'w') as f:
                json.dump(data1, f)
            with open(file2_path, 'w') as f:
                json.dump(data2, f)
            
            # Merge files
            merge_deduplication_files([file1_path, file2_path], output_path)
            
            # Verify merged file
            with open(output_path, 'r') as f:
                merged_data = json.load(f)
            
            assert merged_data['metadata']['total_entries'] == 2
            assert len(merged_data['entries']) == 2
            
            # Check that both entries are present
            urls = [entry['url'] for entry in merged_data['entries']]
            assert "https://example.com/page1" in urls
            assert "https://example.com/page2" in urls
    
    def test_merge_deduplication_files_with_duplicates(self):
        """Test merging files with duplicate entries (should keep most recent)"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file1_path = os.path.join(temp_dir, "file1.json")
            file2_path = os.path.join(temp_dir, "file2.json")
            output_path = os.path.join(temp_dir, "merged.json")
            
            old_time = (datetime.utcnow() - timedelta(hours=1)).isoformat()
            new_time = datetime.utcnow().isoformat()
            
            # Both files have same entry (same hash) but different timestamps
            data1 = {
                'metadata': {'total_entries': 1},
                'entries': [
                    {
                        'url': "https://example.com/page",
                        'title': "Page Title",
                        'site_name': "Site",
                        'processed_at': old_time,
                        'content_hash': 'samehash',
                        'normalized_url': "https://example.com/page",
                        'issue_number': 1
                    }
                ]
            }
            
            data2 = {
                'metadata': {'total_entries': 1},
                'entries': [
                    {
                        'url': "https://example.com/page",
                        'title': "Page Title",
                        'site_name': "Site",
                        'processed_at': new_time,
                        'content_hash': 'samehash',
                        'normalized_url': "https://example.com/page",
                        'issue_number': 2
                    }
                ]
            }
            
            with open(file1_path, 'w') as f:
                json.dump(data1, f)
            with open(file2_path, 'w') as f:
                json.dump(data2, f)
            
            merge_deduplication_files([file1_path, file2_path], output_path)
            
            with open(output_path, 'r') as f:
                merged_data = json.load(f)
            
            # Should have only one entry (the more recent one)
            assert merged_data['metadata']['total_entries'] == 1
            assert len(merged_data['entries']) == 1
            assert merged_data['entries'][0]['issue_number'] == 2  # More recent
            assert merged_data['entries'][0]['processed_at'] == new_time


class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_manager_with_corrupted_file(self):
        """Test manager behavior with corrupted storage file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            f.flush()
            
            try:
                # Should handle corrupted file gracefully
                manager = DeduplicationManager(storage_path=f.name)
                assert len(manager.processed_entries) == 0
                
                # Should have created a backup file
                backup_files = [name for name in os.listdir(os.path.dirname(f.name)) 
                               if name.startswith(os.path.basename(f.name) + '.backup.')]
                assert len(backup_files) == 1
                
            finally:
                # Cleanup
                if os.path.exists(f.name):
                    os.unlink(f.name)
                for backup_file in backup_files:
                    backup_path = os.path.join(os.path.dirname(f.name), backup_file)
                    if os.path.exists(backup_path):
                        os.unlink(backup_path)
    
    def test_empty_search_results_list(self):
        """Test handling empty search results"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = os.path.join(temp_dir, "test_processed.json")
            manager = DeduplicationManager(storage_path=storage_path)
            
            empty_results = manager.filter_new_results([], "Site")
            assert empty_results == []
    
    def test_get_stats_empty_manager(self):
        """Test getting stats from empty manager"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = os.path.join(temp_dir, "test_processed.json")
            manager = DeduplicationManager(storage_path=storage_path)
            
            stats = manager.get_processed_stats()
            
            assert stats['total_entries'] == 0
            assert stats['entries_by_site'] == {}
            assert stats['entries_with_issues'] == 0
            assert stats['oldest_entry'] is None
            assert stats['newest_entry'] is None
            assert stats['capture_status_counts'] == {}
            assert stats['capture_summary']['total_attempts'] == 0
            assert stats['capture_summary']['success'] == 0
            assert stats['capture_summary']['failures'] == 0