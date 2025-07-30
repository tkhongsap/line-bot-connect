"""
Unit tests for configuration version management.

This module tests the configuration versioning and rollback system
that provides safe configuration updates with rollback capabilities.
"""

import os
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock
import pytest

from src.config.version_manager import (
    ConfigurationVersionManager,
    ConfigurationVersion,
    VersionStatus,
    get_version_manager,
    create_config_version,
    rollback_config,
    list_config_versions,
    get_version_status
)


class TestConfigurationVersion:
    """Test the ConfigurationVersion data class."""
    
    def test_configuration_version_creation(self):
        """Test ConfigurationVersion creation and serialization."""
        timestamp = datetime.now()
        version = ConfigurationVersion(
            version_id="test_v20241201_120000",
            config_version="1.0.0",
            timestamp=timestamp,
            status=VersionStatus.ACTIVE,
            description="Test version",
            file_path="/path/to/config.json",
            checksum="abc123",
            size_bytes=1024,
            created_by="test_user",
            tags=["test", "manual"]
        )
        
        assert version.version_id == "test_v20241201_120000"
        assert version.config_version == "1.0.0"
        assert version.status == VersionStatus.ACTIVE
        assert version.rollback_safe is True
        assert "test" in version.tags
    
    def test_version_serialization(self):
        """Test version to_dict and from_dict methods."""
        timestamp = datetime.now()
        original_version = ConfigurationVersion(
            version_id="test_version",
            config_version="1.0.0",
            timestamp=timestamp,
            status=VersionStatus.BACKUP,
            description="Test version",
            file_path="/path/to/config.json",
            checksum="abc123",
            size_bytes=1024
        )
        
        # Convert to dict
        version_dict = original_version.to_dict()
        assert isinstance(version_dict, dict)
        assert version_dict['version_id'] == "test_version"
        assert isinstance(version_dict['timestamp'], str)
        
        # Convert back from dict
        restored_version = ConfigurationVersion.from_dict(version_dict)
        assert restored_version.version_id == original_version.version_id
        assert restored_version.timestamp == original_version.timestamp
        assert restored_version.status == original_version.status


class TestConfigurationVersionManager:
    """Test the ConfigurationVersionManager class."""
    
    def setup_method(self):
        """Set up test environment."""
        # Create temporary directory for versions
        self.test_dir = tempfile.mkdtemp()
        self.versions_dir = Path(self.test_dir) / "test_versions"
        
        # Clear global instance
        import src.config.version_manager
        src.config.version_manager._version_manager = None
        
        # Create test configuration data
        self.test_config_data = {
            "config_version": "1.0.0",
            "application": {
                "debug": True,
                "log_level": "INFO"
            },
            "line": {
                "channel_access_token": "***",
                "channel_secret": "***"
            }
        }
    
    def teardown_method(self):
        """Clean up test environment."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_version_manager_initialization(self):
        """Test ConfigurationVersionManager initialization."""
        manager = ConfigurationVersionManager(str(self.versions_dir))
        
        assert manager.versions_dir.exists()
        assert manager.max_versions == 50
        assert manager.auto_backup is True
        assert len(manager.versions) == 0
    
    def test_create_version(self):
        """Test creating configuration versions."""
        manager = ConfigurationVersionManager(str(self.versions_dir))
        
        # Mock configuration
        with patch('src.config.version_manager.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.config_version = "1.0.0"
            mock_config.to_dict.return_value = self.test_config_data
            mock_get_config.return_value = mock_config
            
            # Create version
            version_id = manager.create_version(
                description="Test version",
                tags=["test", "manual"],
                created_by="test_user"
            )
            
            assert version_id is not None
            assert version_id in manager.versions
            
            version = manager.versions[version_id]
            assert version.description == "Test version"
            assert version.created_by == "test_user"
            assert "test" in version.tags
            assert version.status == VersionStatus.BACKUP
            
            # Check version file was created
            version_file = Path(version.file_path)
            assert version_file.exists()
            
            # Check file content
            with open(version_file, 'r') as f:
                saved_data = json.load(f)
            assert saved_data == self.test_config_data
    
    def test_list_versions(self):
        """Test listing versions with filtering."""
        manager = ConfigurationVersionManager(str(self.versions_dir))
        
        with patch('src.config.version_manager.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.config_version = "1.0.0"
            mock_config.to_dict.return_value = self.test_config_data
            mock_get_config.return_value = mock_config
            
            # Create multiple versions
            v1 = manager.create_version(description="Version 1", tags=["test"])
            v2 = manager.create_version(description="Version 2", tags=["production"])
            v3 = manager.create_version(description="Version 3", tags=["test", "manual"])
            
            # Test listing all versions
            all_versions = manager.list_versions()
            assert len(all_versions) == 3
            
            # Test filtering by tags
            test_versions = manager.list_versions(tags=["test"])
            assert len(test_versions) == 2
            
            # Test limiting results
            limited_versions = manager.list_versions(limit=2)
            assert len(limited_versions) == 2
    
    def test_load_version_config(self):
        """Test loading configuration from versions."""
        manager = ConfigurationVersionManager(str(self.versions_dir))
        
        with patch('src.config.version_manager.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.config_version = "1.0.0"
            mock_config.to_dict.return_value = self.test_config_data
            mock_get_config.return_value = mock_config
            
            # Create version
            version_id = manager.create_version(description="Test version")
            
            # Load version config
            loaded_config = manager.load_version_config(version_id)
            assert loaded_config == self.test_config_data
            
            # Test loading non-existent version
            no_config = manager.load_version_config("nonexistent")
            assert no_config is None
    
    def test_rollback_to_version(self):
        """Test configuration rollback functionality."""
        manager = ConfigurationVersionManager(str(self.versions_dir))
        
        with patch('src.config.version_manager.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.config_version = "1.0.0"
            mock_config.to_dict.return_value = self.test_config_data
            mock_get_config.return_value = mock_config
            
            # Create version
            version_id = manager.create_version(description="Rollback target")
            
            # Test dry run rollback
            success = manager.rollback_to_version(version_id, dry_run=True)
            assert success is True
            
            # Test actual rollback
            with patch.object(manager, '_apply_config_rollback') as mock_apply:
                success = manager.rollback_to_version(version_id, dry_run=False)
                assert success is True
                mock_apply.assert_called_once()
                
                # Check version status changed to active
                version = manager.get_version(version_id)
                assert version.status == VersionStatus.ACTIVE
    
    def test_rollback_safety_checks(self):
        """Test rollback safety mechanisms."""
        manager = ConfigurationVersionManager(str(self.versions_dir))
        
        with patch('src.config.version_manager.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.config_version = "1.0.0"
            mock_config.to_dict.return_value = self.test_config_data
            mock_get_config.return_value = mock_config
            
            # Create unsafe version
            version_id = manager.create_version(description="Unsafe version")
            version = manager.get_version(version_id)
            version.rollback_safe = False
            
            # Test rollback fails for unsafe version
            success = manager.rollback_to_version(version_id)
            assert success is False
            
            # Test rollback fails for non-existent version
            success = manager.rollback_to_version("nonexistent")
            assert success is False
    
    def test_mark_version_active(self):
        """Test marking versions as active."""
        manager = ConfigurationVersionManager(str(self.versions_dir))
        
        with patch('src.config.version_manager.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.config_version = "1.0.0"
            mock_config.to_dict.return_value = self.test_config_data
            mock_get_config.return_value = mock_config
            
            # Create multiple versions
            v1 = manager.create_version(description="Version 1")
            v2 = manager.create_version(description="Version 2")
            
            # Mark v1 as active
            success = manager.mark_version_active(v1)
            assert success is True
            
            version1 = manager.get_version(v1)
            version2 = manager.get_version(v2)
            
            assert version1.status == VersionStatus.ACTIVE
            assert version2.status == VersionStatus.BACKUP
            
            # Mark v2 as active (should deactivate v1)
            manager.mark_version_active(v2)
            
            # Reload versions to check status
            version1 = manager.get_version(v1)
            version2 = manager.get_version(v2)
            
            assert version1.status == VersionStatus.BACKUP
            assert version2.status == VersionStatus.ACTIVE
    
    def test_delete_version(self):
        """Test version deletion."""
        manager = ConfigurationVersionManager(str(self.versions_dir))
        
        with patch('src.config.version_manager.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.config_version = "1.0.0"
            mock_config.to_dict.return_value = self.test_config_data
            mock_get_config.return_value = mock_config
            
            # Create version
            version_id = manager.create_version(description="To be deleted")
            version = manager.get_version(version_id)
            version_file_path = version.file_path
            
            # Verify file exists
            assert Path(version_file_path).exists()
            
            # Delete version
            success = manager.delete_version(version_id)
            assert success is True
            
            # Verify version removed
            assert manager.get_version(version_id) is None
            assert not Path(version_file_path).exists()
    
    def test_delete_active_version_protection(self):
        """Test protection against deleting active versions."""
        manager = ConfigurationVersionManager(str(self.versions_dir))
        
        with patch('src.config.version_manager.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.config_version = "1.0.0"
            mock_config.to_dict.return_value = self.test_config_data
            mock_get_config.return_value = mock_config
            
            # Create and activate version
            version_id = manager.create_version(description="Active version")
            manager.mark_version_active(version_id)
            
            # Try to delete active version (should fail)
            success = manager.delete_version(version_id)
            assert success is False
            
            # Force deletion should work
            success = manager.delete_version(version_id, force=True)
            assert success is True
    
    def test_export_import_version(self):
        """Test version export and import functionality."""
        manager = ConfigurationVersionManager(str(self.versions_dir))
        
        with patch('src.config.version_manager.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.config_version = "1.0.0"
            mock_config.to_dict.return_value = self.test_config_data
            mock_get_config.return_value = mock_config
            
            # Create version
            version_id = manager.create_version(description="Export test")
            
            # Export version
            export_path = os.path.join(self.test_dir, "exported_config.json")
            success = manager.export_version(version_id, export_path)
            assert success is True
            assert os.path.exists(export_path)
            
            # Import version
            imported_id = manager.import_version(
                export_path,
                description="Imported config",
                tags=["imported", "test"]
            )
            
            assert imported_id is not None
            imported_version = manager.get_version(imported_id)
            assert imported_version.description == "Imported config"
            assert "imported" in imported_version.tags
    
    def test_version_diff(self):
        """Test version difference calculation."""
        manager = ConfigurationVersionManager(str(self.versions_dir))
        
        # Create two different configs
        config1_data = {
            "config_version": "1.0.0",
            "setting1": "value1",
            "setting2": "value2"
        }
        
        config2_data = {
            "config_version": "1.1.0",
            "setting1": "new_value1",
            "setting3": "value3"
        }
        
        with patch('src.config.version_manager.get_config') as mock_get_config:
            # Create first version
            mock_config = MagicMock()
            mock_config.config_version = "1.0.0"
            mock_config.to_dict.return_value = config1_data
            mock_get_config.return_value = mock_config
            
            version1_id = manager.create_version(description="Version 1")
            
            # Create second version
            mock_config.config_version = "1.1.0"
            mock_config.to_dict.return_value = config2_data
            
            version2_id = manager.create_version(description="Version 2")
            
            # Get diff
            diff = manager.get_version_diff(version1_id, version2_id)
            
            assert diff is not None
            assert diff['version1'] == version1_id
            assert diff['version2'] == version2_id
            
            # Check differences
            assert 'setting3' in diff['added']
            assert 'setting2' in diff['removed']
            assert 'setting1' in diff['changed']
            assert 'config_version' in diff['changed']
    
    def test_cleanup_old_versions(self):
        """Test automatic cleanup of old versions."""
        manager = ConfigurationVersionManager(str(self.versions_dir))
        manager.max_versions = 3  # Set low limit for testing
        
        with patch('src.config.version_manager.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.config_version = "1.0.0"
            mock_config.to_dict.return_value = self.test_config_data
            mock_get_config.return_value = mock_config
            
            # Create more versions than the limit
            version_ids = []
            for i in range(5):
                version_id = manager.create_version(description=f"Version {i}")
                version_ids.append(version_id)
            
            # Should have cleaned up to max_versions
            assert len(manager.versions) == manager.max_versions
            
            # Oldest versions should be gone
            assert manager.get_version(version_ids[0]) is None
            assert manager.get_version(version_ids[1]) is None
            
            # Recent versions should remain
            assert manager.get_version(version_ids[-1]) is not None
    
    def test_get_status(self):
        """Test version manager status reporting."""
        manager = ConfigurationVersionManager(str(self.versions_dir))
        
        with patch('src.config.version_manager.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.config_version = "1.0.0"
            mock_config.to_dict.return_value = self.test_config_data
            mock_get_config.return_value = mock_config
            
            # Create and activate a version
            version_id = manager.create_version(description="Test version")
            manager.mark_version_active(version_id)
            
            status = manager.get_status()
            
            assert status['total_versions'] == 1
            assert status['active_version'] == version_id
            assert status['max_versions'] == manager.max_versions
            assert status['auto_backup'] is True
            assert isinstance(status['storage_used_mb'], float)


class TestGlobalVersionFunctions:
    """Test global version management functions."""
    
    def setup_method(self):
        """Set up test environment."""
        # Clear global instance
        import src.config.version_manager
        src.config.version_manager._version_manager = None
        
        self.test_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test environment."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_get_version_manager_singleton(self):
        """Test that get_version_manager returns the same instance."""
        manager1 = get_version_manager()
        manager2 = get_version_manager()
        
        assert manager1 is manager2
        assert isinstance(manager1, ConfigurationVersionManager)
    
    def test_create_config_version(self):
        """Test global create_config_version function."""
        with patch('src.config.version_manager.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.config_version = "1.0.0"
            mock_config.to_dict.return_value = {"test": "data"}
            mock_get_config.return_value = mock_config
            
            version_id = create_config_version(
                description="Global test",
                tags=["global", "test"]
            )
            
            assert version_id is not None
            
            manager = get_version_manager()
            version = manager.get_version(version_id)
            assert version.description == "Global test"
            assert version.created_by == "manual"
    
    def test_rollback_config(self):
        """Test global rollback_config function."""
        with patch('src.config.version_manager.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.config_version = "1.0.0"
            mock_config.to_dict.return_value = {"test": "data"}
            mock_get_config.return_value = mock_config
            
            # Create version to rollback to
            version_id = create_config_version(description="Rollback target")
            
            # Test rollback
            with patch.object(get_version_manager(), '_apply_config_rollback'):
                success = rollback_config(version_id, dry_run=True)
                assert success is True
    
    def test_list_config_versions(self):
        """Test global list_config_versions function."""
        with patch('src.config.version_manager.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.config_version = "1.0.0"
            mock_config.to_dict.return_value = {"test": "data"}
            mock_get_config.return_value = mock_config
            
            # Create some versions
            create_config_version(description="Version 1")
            create_config_version(description="Version 2")
            
            versions = list_config_versions(limit=5)
            assert len(versions) == 2
            assert all(isinstance(v, ConfigurationVersion) for v in versions)
    
    def test_get_version_status(self):
        """Test global get_version_status function."""
        status = get_version_status()
        
        assert isinstance(status, dict)
        assert 'total_versions' in status
        assert 'max_versions' in status
        assert 'auto_backup' in status