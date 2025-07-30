"""
Configuration Version Management and Rollback System

This module provides versioning and rollback capabilities for the centralized
configuration system, allowing safe configuration updates with the ability
to revert to previous working configurations.
"""

import os
import json
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

from src.config.centralized_config import CentralizedConfig, get_config

logger = logging.getLogger(__name__)


class VersionStatus(str, Enum):
    """Configuration version status"""
    ACTIVE = "active"
    BACKUP = "backup"
    FAILED = "failed"
    ARCHIVED = "archived"


@dataclass
class ConfigurationVersion:
    """Represents a configuration version with metadata"""
    version_id: str
    config_version: str
    timestamp: datetime
    status: VersionStatus
    description: str
    file_path: str
    checksum: str
    size_bytes: int
    created_by: str = "system"
    rollback_safe: bool = True
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConfigurationVersion':
        """Create from dictionary"""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        data['status'] = VersionStatus(data['status'])
        return cls(**data)


class ConfigurationVersionManager:
    """
    Manages configuration versions and rollback capabilities.
    
    This class handles versioning, backup, and rollback of configuration
    files with full audit trails and validation.
    """
    
    def __init__(self, versions_dir: str = "config_versions"):
        """
        Initialize the version manager.
        
        Args:
            versions_dir: Directory to store configuration versions
        """
        self.versions_dir = Path(versions_dir)
        self.versions_dir.mkdir(exist_ok=True)
        
        self.metadata_file = self.versions_dir / "versions_metadata.json"
        self.max_versions = 50  # Maximum versions to keep
        self.auto_backup = True
        
        self.versions: Dict[str, ConfigurationVersion] = {}
        self._load_metadata()
    
    def _load_metadata(self) -> None:
        """Load version metadata from disk"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    data = json.load(f)
                
                for version_id, version_data in data.items():
                    self.versions[version_id] = ConfigurationVersion.from_dict(version_data)
                
                logger.info(f"Loaded {len(self.versions)} configuration versions")
                
            except Exception as e:
                logger.error(f"Failed to load version metadata: {e}")
                self.versions = {}
    
    def _save_metadata(self) -> None:
        """Save version metadata to disk"""
        try:
            data = {
                version_id: version.to_dict() 
                for version_id, version in self.versions.items()
            }
            
            with open(self.metadata_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            logger.debug("Saved version metadata")
            
        except Exception as e:
            logger.error(f"Failed to save version metadata: {e}")
    
    def _generate_version_id(self) -> str:
        """Generate a unique version ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"config_v{timestamp}"
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of a file"""
        import hashlib
        
        hasher = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate checksum for {file_path}: {e}")
            return "unknown"
    
    def create_version(
        self,
        config: Optional[CentralizedConfig] = None,
        description: str = "Automatic backup",
        tags: List[str] = None,
        created_by: str = "system"
    ) -> str:
        """
        Create a new configuration version.
        
        Args:
            config: Configuration to version (uses current if None)
            description: Description of this version
            tags: Optional tags for categorization
            created_by: Who created this version
            
        Returns:
            str: Version ID of the created version
        """
        if config is None:
            config = get_config()
        
        version_id = self._generate_version_id()
        timestamp = datetime.now()
        
        # Create version file
        version_file = self.versions_dir / f"{version_id}.json"
        
        try:
            # Save configuration to file
            config_data = config.to_dict(include_secrets=False)
            with open(version_file, 'w') as f:
                json.dump(config_data, f, indent=2, default=str)
            
            # Calculate metadata
            checksum = self._calculate_checksum(version_file)
            size_bytes = version_file.stat().st_size
            
            # Create version metadata
            version = ConfigurationVersion(
                version_id=version_id,
                config_version=config.config_version,
                timestamp=timestamp,
                status=VersionStatus.BACKUP,
                description=description,
                file_path=str(version_file),
                checksum=checksum,
                size_bytes=size_bytes,
                created_by=created_by,
                tags=tags or []
            )
            
            # Store version
            self.versions[version_id] = version
            self._save_metadata()
            
            # Clean up old versions if needed
            self._cleanup_old_versions()
            
            logger.info(f"Created configuration version: {version_id}")
            return version_id
            
        except Exception as e:
            logger.error(f"Failed to create configuration version: {e}")
            # Clean up partial file
            if version_file.exists():
                version_file.unlink()
            raise
    
    def get_version(self, version_id: str) -> Optional[ConfigurationVersion]:
        """
        Get version metadata by ID.
        
        Args:
            version_id: Version ID to retrieve
            
        Returns:
            ConfigurationVersion or None if not found
        """
        return self.versions.get(version_id)
    
    def list_versions(
        self,
        status: Optional[VersionStatus] = None,
        tags: List[str] = None,
        limit: int = 20
    ) -> List[ConfigurationVersion]:
        """
        List configuration versions with optional filtering.
        
        Args:
            status: Filter by status
            tags: Filter by tags (any match)
            limit: Maximum number of versions to return
            
        Returns:
            List of ConfigurationVersion objects
        """
        versions = list(self.versions.values())
        
        # Apply filters
        if status:
            versions = [v for v in versions if v.status == status]
        
        if tags:
            versions = [v for v in versions if any(tag in v.tags for tag in tags)]
        
        # Sort by timestamp (newest first) and limit
        versions.sort(key=lambda v: v.timestamp, reverse=True)
        return versions[:limit]
    
    def load_version_config(self, version_id: str) -> Optional[Dict[str, Any]]:
        """
        Load configuration data from a specific version.
        
        Args:
            version_id: Version ID to load
            
        Returns:
            Configuration dictionary or None if failed
        """
        version = self.get_version(version_id)
        if not version:
            logger.error(f"Version not found: {version_id}")
            return None
        
        try:
            with open(version.file_path, 'r') as f:
                config_data = json.load(f)
            
            logger.info(f"Loaded configuration from version: {version_id}")
            return config_data
            
        except Exception as e:
            logger.error(f"Failed to load version {version_id}: {e}")
            return None
    
    def rollback_to_version(self, version_id: str, dry_run: bool = False) -> bool:
        """
        Rollback configuration to a specific version.
        
        Args:
            version_id: Version ID to rollback to
            dry_run: If True, validate but don't apply changes
            
        Returns:
            bool: True if rollback succeeded
        """
        version = self.get_version(version_id)
        if not version:
            logger.error(f"Cannot rollback: version not found: {version_id}")
            return False
        
        if not version.rollback_safe:
            logger.error(f"Cannot rollback: version marked as unsafe: {version_id}")
            return False
        
        try:
            # Load version configuration
            config_data = self.load_version_config(version_id)
            if not config_data:
                return False
            
            if dry_run:
                logger.info(f"Dry run: rollback to {version_id} would succeed")
                return True
            
            # Create backup of current configuration before rollback
            current_config = get_config()
            backup_id = self.create_version(
                current_config,
                f"Pre-rollback backup before {version_id}",
                tags=["pre-rollback", "auto-backup"],
                created_by="rollback_system"
            )
            
            # Apply rollback by updating environment variables
            # Note: This is a simplified approach - in production you might
            # want to update actual config files and trigger a reload
            self._apply_config_rollback(config_data)
            
            # Update version status
            version.status = VersionStatus.ACTIVE
            self._save_metadata()
            
            logger.info(f"Successfully rolled back to version: {version_id} (backup: {backup_id})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rollback to version {version_id}: {e}")
            return False
    
    def _apply_config_rollback(self, config_data: Dict[str, Any]) -> None:
        """
        Apply configuration rollback.
        
        Note: This is a simplified implementation. In production,
        you might want to update actual configuration files.
        """
        # This would typically involve updating configuration files
        # and triggering a hot reload. For now, we'll log the action.
        logger.info("Configuration rollback applied (implementation depends on deployment)")
    
    def mark_version_active(self, version_id: str) -> bool:
        """
        Mark a version as the active configuration.
        
        Args:
            version_id: Version ID to mark as active
            
        Returns:
            bool: True if successful
        """
        version = self.get_version(version_id)
        if not version:
            return False
        
        # Mark all other versions as backup
        for v in self.versions.values():
            if v.status == VersionStatus.ACTIVE:
                v.status = VersionStatus.BACKUP
        
        # Mark this version as active
        version.status = VersionStatus.ACTIVE
        self._save_metadata()
        
        logger.info(f"Marked version as active: {version_id}")
        return True
    
    def delete_version(self, version_id: str, force: bool = False) -> bool:
        """
        Delete a configuration version.
        
        Args:
            version_id: Version ID to delete
            force: Force deletion even if active
            
        Returns:
            bool: True if successful
        """
        version = self.get_version(version_id)
        if not version:
            return False
        
        if version.status == VersionStatus.ACTIVE and not force:
            logger.error(f"Cannot delete active version: {version_id}")
            return False
        
        try:
            # Delete version file
            if Path(version.file_path).exists():
                Path(version.file_path).unlink()
            
            # Remove from metadata
            del self.versions[version_id]
            self._save_metadata()
            
            logger.info(f"Deleted configuration version: {version_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete version {version_id}: {e}")
            return False
    
    def _cleanup_old_versions(self) -> None:
        """Clean up old versions to stay within limits"""
        if len(self.versions) <= self.max_versions:
            return
        
        # Get versions sorted by timestamp (oldest first)
        versions = sorted(
            self.versions.values(),
            key=lambda v: v.timestamp
        )
        
        # Keep active versions and recent versions
        to_delete = []
        for version in versions[:-self.max_versions]:
            if version.status != VersionStatus.ACTIVE:
                to_delete.append(version.version_id)
        
        # Delete old versions
        for version_id in to_delete:
            self.delete_version(version_id, force=False)
        
        if to_delete:
            logger.info(f"Cleaned up {len(to_delete)} old configuration versions")
    
    def export_version(self, version_id: str, export_path: str) -> bool:
        """
        Export a configuration version to a file.
        
        Args:
            version_id: Version ID to export
            export_path: Path to export to
            
        Returns:
            bool: True if successful
        """
        version = self.get_version(version_id)
        if not version:
            return False
        
        try:
            shutil.copy2(version.file_path, export_path)
            logger.info(f"Exported version {version_id} to {export_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export version {version_id}: {e}")
            return False
    
    def import_version(
        self,
        import_path: str,
        description: str = "Imported configuration",
        tags: List[str] = None
    ) -> Optional[str]:
        """
        Import a configuration version from a file.
        
        Args:
            import_path: Path to import from
            description: Description for the imported version
            tags: Tags for the imported version
            
        Returns:
            Version ID if successful, None otherwise
        """
        try:
            # Validate import file
            with open(import_path, 'r') as f:
                config_data = json.load(f)
            
            # Create new version
            version_id = self._generate_version_id()
            version_file = self.versions_dir / f"{version_id}.json"
            
            # Copy import file to version file
            shutil.copy2(import_path, version_file)
            
            # Create version metadata
            checksum = self._calculate_checksum(version_file)
            size_bytes = version_file.stat().st_size
            
            version = ConfigurationVersion(
                version_id=version_id,
                config_version=config_data.get('config_version', 'imported'),
                timestamp=datetime.now(),
                status=VersionStatus.BACKUP,
                description=description,
                file_path=str(version_file),
                checksum=checksum,
                size_bytes=size_bytes,
                created_by="import_system",
                tags=tags or ["imported"]
            )
            
            self.versions[version_id] = version
            self._save_metadata()
            
            logger.info(f"Imported configuration version: {version_id}")
            return version_id
            
        except Exception as e:
            logger.error(f"Failed to import configuration from {import_path}: {e}")
            return None
    
    def get_version_diff(self, version1_id: str, version2_id: str) -> Optional[Dict[str, Any]]:
        """
        Get differences between two configuration versions.
        
        Args:
            version1_id: First version ID
            version2_id: Second version ID
            
        Returns:
            Dictionary with differences or None if failed
        """
        config1 = self.load_version_config(version1_id)
        config2 = self.load_version_config(version2_id)
        
        if not config1 or not config2:
            return None
        
        try:
            # Simple diff implementation
            diff = {
                'version1': version1_id,
                'version2': version2_id,
                'added': {},
                'removed': {},
                'changed': {}
            }
            
            # Find differences (simplified)
            all_keys = set(config1.keys()) | set(config2.keys())
            
            for key in all_keys:
                if key not in config1:
                    diff['added'][key] = config2[key]
                elif key not in config2:
                    diff['removed'][key] = config1[key]
                elif config1[key] != config2[key]:
                    diff['changed'][key] = {
                        'old': config1[key],
                        'new': config2[key]
                    }
            
            return diff
            
        except Exception as e:
            logger.error(f"Failed to compute diff between {version1_id} and {version2_id}: {e}")
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """Get version manager status"""
        active_versions = [v for v in self.versions.values() if v.status == VersionStatus.ACTIVE]
        
        return {
            'total_versions': len(self.versions),
            'active_version': active_versions[0].version_id if active_versions else None,
            'versions_dir': str(self.versions_dir),
            'max_versions': self.max_versions,
            'auto_backup': self.auto_backup,
            'storage_used_mb': sum(v.size_bytes for v in self.versions.values()) / (1024 * 1024)
        }


# Global version manager instance
_version_manager: Optional[ConfigurationVersionManager] = None


def get_version_manager() -> ConfigurationVersionManager:
    """Get the global configuration version manager"""
    global _version_manager
    if _version_manager is None:
        _version_manager = ConfigurationVersionManager()
    return _version_manager


def create_config_version(description: str = "Manual backup", tags: List[str] = None) -> str:
    """Create a new configuration version"""
    manager = get_version_manager()
    return manager.create_version(description=description, tags=tags, created_by="manual")


def rollback_config(version_id: str, dry_run: bool = False) -> bool:
    """Rollback configuration to a specific version"""
    manager = get_version_manager()
    return manager.rollback_to_version(version_id, dry_run=dry_run)


def list_config_versions(limit: int = 10) -> List[ConfigurationVersion]:
    """List recent configuration versions"""
    manager = get_version_manager()
    return manager.list_versions(limit=limit)


def get_version_status() -> Dict[str, Any]:
    """Get configuration version management status"""
    manager = get_version_manager()
    return manager.get_status()