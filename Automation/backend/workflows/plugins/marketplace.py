"""
Plugin Marketplace - Plugin Discovery and Distribution

This module provides marketplace functionality for plugin discovery,
distribution, and management including local and remote repositories.
"""

import os
import json
import uuid
import logging
import hashlib
import requests
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import tempfile
import zipfile

from .plugin_manifest import PluginManifest, TrustLevel, PluginType
from .plugin_system import PluginSystem
from ..security_validators import PayloadSecurityValidator


logger = logging.getLogger(__name__)


class MarketplaceError(Exception):
    """Base exception for marketplace-related errors."""
    pass


class PluginNotFoundError(MarketplaceError):
    """Raised when a plugin is not found in the marketplace."""
    pass


class MarketplaceType(Enum):
    """Types of marketplaces."""
    LOCAL = "local"         # Local file-based marketplace
    REMOTE = "remote"       # Remote HTTP-based marketplace
    HYBRID = "hybrid"       # Combination of local and remote


@dataclass
class PluginRating:
    """Plugin rating and review information."""
    plugin_id: str
    version: str
    rating: float  # 1.0 to 5.0
    review_count: int
    reviews: List[Dict[str, Any]]
    last_updated: str


@dataclass
class PluginDownloadStats:
    """Plugin download statistics."""
    plugin_id: str
    total_downloads: int
    monthly_downloads: int
    weekly_downloads: int
    daily_downloads: int
    last_download: str


@dataclass
class MarketplaceEntry:
    """Represents a plugin entry in the marketplace."""
    plugin_id: str
    manifest: PluginManifest
    package_url: str
    package_hash: str
    signature_url: Optional[str]
    rating: Optional[PluginRating]
    download_stats: Optional[PluginDownloadStats]
    featured: bool = False
    verified: bool = False
    published_at: str = None
    updated_at: str = None
    
    def __post_init__(self):
        if self.published_at is None:
            self.published_at = datetime.utcnow().isoformat()
        if self.updated_at is None:
            self.updated_at = self.published_at


class LocalMarketplace:
    """
    Local file-based marketplace for plugin management.
    """
    
    def __init__(self, marketplace_directory: str = None):
        self.marketplace_directory = marketplace_directory or os.path.join(
            os.path.dirname(__file__), '..', '..', 'marketplace'
        )
        self.plugins_index_file = os.path.join(self.marketplace_directory, 'plugins.json')
        self.packages_directory = os.path.join(self.marketplace_directory, 'packages')
        
        # Ensure directories exist
        os.makedirs(self.marketplace_directory, exist_ok=True)
        os.makedirs(self.packages_directory, exist_ok=True)
        
        # Load plugins index
        self.plugins_index: Dict[str, MarketplaceEntry] = {}
        self._load_plugins_index()
        
        logger.info(f"Local marketplace initialized: {self.marketplace_directory}")
    
    def publish_plugin(self, plugin_package: Union[str, bytes], 
                      publisher_id: str, featured: bool = False) -> str:
        """
        Publish a plugin to the local marketplace.
        
        Args:
            plugin_package: Path to plugin package or package bytes
            publisher_id: ID of the publisher
            featured: Whether to feature the plugin
            
        Returns:
            Plugin ID of published plugin
        """
        logger.info(f"Publishing plugin to local marketplace by {publisher_id}")
        
        try:
            # Extract and validate plugin
            with tempfile.TemporaryDirectory() as temp_dir:
                # Extract package
                if isinstance(plugin_package, str):
                    with zipfile.ZipFile(plugin_package, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                    package_path = plugin_package
                else:
                    # Create temporary file for bytes
                    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_file:
                        temp_file.write(plugin_package)
                        package_path = temp_file.name
                    
                    with zipfile.ZipFile(package_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                
                # Load manifest
                manifest_path = os.path.join(temp_dir, 'plugin.json')
                if not os.path.exists(manifest_path):
                    raise MarketplaceError("Plugin manifest not found")
                
                with open(manifest_path, 'r') as f:
                    manifest_data = json.load(f)
                
                manifest = PluginManifest.from_dict(manifest_data)
                
                # Validate manifest
                validation_errors = manifest.validate()
                if validation_errors:
                    raise MarketplaceError(f"Manifest validation failed: {validation_errors}")
                
                # Calculate package hash
                with open(package_path, 'rb') as f:
                    package_hash = hashlib.sha256(f.read()).hexdigest()
                
                # Copy package to marketplace
                package_filename = f"{manifest.plugin_id}_{manifest.version}.zip"
                marketplace_package_path = os.path.join(self.packages_directory, package_filename)
                
                if isinstance(plugin_package, str):
                    import shutil
                    shutil.copy2(package_path, marketplace_package_path)
                else:
                    with open(marketplace_package_path, 'wb') as f:
                        f.write(plugin_package)
                
                # Create marketplace entry
                entry = MarketplaceEntry(
                    plugin_id=manifest.plugin_id,
                    manifest=manifest,
                    package_url=f"file://{marketplace_package_path}",
                    package_hash=package_hash,
                    signature_url=None,  # TODO: Handle signatures
                    rating=None,
                    download_stats=PluginDownloadStats(
                        plugin_id=manifest.plugin_id,
                        total_downloads=0,
                        monthly_downloads=0,
                        weekly_downloads=0,
                        daily_downloads=0,
                        last_download=""
                    ),
                    featured=featured,
                    verified=manifest.trust_level in [TrustLevel.VERIFIED, TrustLevel.OFFICIAL]
                )
                
                # Add to index
                self.plugins_index[manifest.plugin_id] = entry
                
                # Save index
                self._save_plugins_index()
                
                logger.info(f"Plugin published to local marketplace: {manifest.plugin_id} v{manifest.version}")
                
                return manifest.plugin_id
                
        except Exception as e:
            error_msg = f"Failed to publish plugin: {str(e)}"
            logger.error(error_msg)
            raise MarketplaceError(error_msg)
    
    def search_plugins(self, query: str = "", category: str = "", 
                      plugin_type: PluginType = None, limit: int = 50) -> List[MarketplaceEntry]:
        """
        Search for plugins in the local marketplace.
        
        Args:
            query: Search query string
            category: Plugin category filter
            plugin_type: Plugin type filter
            limit: Maximum number of results
            
        Returns:
            List of matching marketplace entries
        """
        results = []
        
        for entry in self.plugins_index.values():
            manifest = entry.manifest
            
            # Apply filters
            if category and manifest.category != category:
                continue
            
            if plugin_type and manifest.plugin_type != plugin_type:
                continue
            
            # Apply search query
            if query:
                query_lower = query.lower()
                searchable_text = f"{manifest.name} {manifest.description} {' '.join(manifest.keywords)}".lower()
                
                if query_lower not in searchable_text:
                    continue
            
            results.append(entry)
            
            if len(results) >= limit:
                break
        
        # Sort by relevance (featured first, then by rating, then by downloads)
        results.sort(key=lambda x: (
            -int(x.featured),
            -(x.rating.rating if x.rating else 0),
            -(x.download_stats.total_downloads if x.download_stats else 0)
        ))
        
        return results
    
    def get_plugin(self, plugin_id: str) -> Optional[MarketplaceEntry]:
        """Get a specific plugin from the marketplace."""
        return self.plugins_index.get(plugin_id)
    
    def download_plugin(self, plugin_id: str, downloader_id: str) -> bytes:
        """
        Download a plugin package from the local marketplace.
        
        Args:
            plugin_id: Plugin ID to download
            downloader_id: ID of the downloader
            
        Returns:
            Plugin package bytes
        """
        entry = self.get_plugin(plugin_id)
        if not entry:
            raise PluginNotFoundError(f"Plugin not found: {plugin_id}")
        
        # Read package file
        if entry.package_url.startswith('file://'):
            package_path = entry.package_url[7:]  # Remove 'file://' prefix
            
            if not os.path.exists(package_path):
                raise MarketplaceError(f"Plugin package file not found: {package_path}")
            
            with open(package_path, 'rb') as f:
                package_data = f.read()
            
            # Update download stats
            if entry.download_stats:
                entry.download_stats.total_downloads += 1
                entry.download_stats.daily_downloads += 1
                entry.download_stats.last_download = datetime.utcnow().isoformat()
                self._save_plugins_index()
            
            logger.info(f"Plugin downloaded: {plugin_id} by {downloader_id}")
            
            return package_data
        
        else:
            raise MarketplaceError(f"Unsupported package URL: {entry.package_url}")
    
    def get_categories(self) -> List[str]:
        """Get list of available plugin categories."""
        categories = set()
        for entry in self.plugins_index.values():
            categories.add(entry.manifest.category)
        return sorted(list(categories))
    
    def get_featured_plugins(self, limit: int = 10) -> List[MarketplaceEntry]:
        """Get featured plugins."""
        featured = [entry for entry in self.plugins_index.values() if entry.featured]
        featured.sort(key=lambda x: -(x.rating.rating if x.rating else 0))
        return featured[:limit]
    
    def get_popular_plugins(self, limit: int = 10) -> List[MarketplaceEntry]:
        """Get popular plugins by download count."""
        popular = list(self.plugins_index.values())
        popular.sort(key=lambda x: -(x.download_stats.total_downloads if x.download_stats else 0))
        return popular[:limit]
    
    def _load_plugins_index(self):
        """Load plugins index from file."""
        if os.path.exists(self.plugins_index_file):
            try:
                with open(self.plugins_index_file, 'r') as f:
                    index_data = json.load(f)
                
                for plugin_id, entry_data in index_data.items():
                    # Reconstruct marketplace entry
                    manifest_data = entry_data['manifest']
                    manifest = PluginManifest.from_dict(manifest_data)
                    
                    rating_data = entry_data.get('rating')
                    rating = PluginRating(**rating_data) if rating_data else None
                    
                    stats_data = entry_data.get('download_stats')
                    download_stats = PluginDownloadStats(**stats_data) if stats_data else None
                    
                    entry = MarketplaceEntry(
                        plugin_id=plugin_id,
                        manifest=manifest,
                        package_url=entry_data['package_url'],
                        package_hash=entry_data['package_hash'],
                        signature_url=entry_data.get('signature_url'),
                        rating=rating,
                        download_stats=download_stats,
                        featured=entry_data.get('featured', False),
                        verified=entry_data.get('verified', False),
                        published_at=entry_data.get('published_at'),
                        updated_at=entry_data.get('updated_at')
                    )
                    
                    self.plugins_index[plugin_id] = entry
                
                logger.info(f"Loaded {len(self.plugins_index)} plugins from index")
                
            except Exception as e:
                logger.error(f"Failed to load plugins index: {e}")
                self.plugins_index = {}
    
    def _save_plugins_index(self):
        """Save plugins index to file."""
        try:
            index_data = {}
            
            for plugin_id, entry in self.plugins_index.items():
                entry_data = {
                    'manifest': entry.manifest.to_dict(),
                    'package_url': entry.package_url,
                    'package_hash': entry.package_hash,
                    'signature_url': entry.signature_url,
                    'featured': entry.featured,
                    'verified': entry.verified,
                    'published_at': entry.published_at,
                    'updated_at': entry.updated_at
                }
                
                if entry.rating:
                    entry_data['rating'] = asdict(entry.rating)
                
                if entry.download_stats:
                    entry_data['download_stats'] = asdict(entry.download_stats)
                
                index_data[plugin_id] = entry_data
            
            with open(self.plugins_index_file, 'w') as f:
                json.dump(index_data, f, indent=2)
            
            logger.debug("Plugins index saved")
            
        except Exception as e:
            logger.error(f"Failed to save plugins index: {e}")


class RemoteMarketplace:
    """
    Remote HTTP-based marketplace for plugin management.
    """
    
    def __init__(self, marketplace_url: str, api_key: str = None):
        self.marketplace_url = marketplace_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        
        if api_key:
            self.session.headers.update({'Authorization': f'Bearer {api_key}'})
        
        logger.info(f"Remote marketplace initialized: {marketplace_url}")
    
    def search_plugins(self, query: str = "", category: str = "", 
                      plugin_type: PluginType = None, limit: int = 50) -> List[MarketplaceEntry]:
        """
        Search for plugins in the remote marketplace.
        
        Args:
            query: Search query string
            category: Plugin category filter
            plugin_type: Plugin type filter
            limit: Maximum number of results
            
        Returns:
            List of matching marketplace entries
        """
        params = {
            'limit': limit
        }
        
        if query:
            params['q'] = query
        
        if category:
            params['category'] = category
        
        if plugin_type:
            params['type'] = plugin_type.value
        
        try:
            response = self.session.get(f"{self.marketplace_url}/api/plugins/search", params=params)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for plugin_data in data.get('plugins', []):
                manifest = PluginManifest.from_dict(plugin_data['manifest'])
                
                rating_data = plugin_data.get('rating')
                rating = PluginRating(**rating_data) if rating_data else None
                
                stats_data = plugin_data.get('download_stats')
                download_stats = PluginDownloadStats(**stats_data) if stats_data else None
                
                entry = MarketplaceEntry(
                    plugin_id=plugin_data['plugin_id'],
                    manifest=manifest,
                    package_url=plugin_data['package_url'],
                    package_hash=plugin_data['package_hash'],
                    signature_url=plugin_data.get('signature_url'),
                    rating=rating,
                    download_stats=download_stats,
                    featured=plugin_data.get('featured', False),
                    verified=plugin_data.get('verified', False),
                    published_at=plugin_data.get('published_at'),
                    updated_at=plugin_data.get('updated_at')
                )
                
                results.append(entry)
            
            return results
            
        except requests.RequestException as e:
            logger.error(f"Failed to search remote marketplace: {e}")
            raise MarketplaceError(f"Remote marketplace search failed: {e}")
    
    def get_plugin(self, plugin_id: str) -> Optional[MarketplaceEntry]:
        """Get a specific plugin from the remote marketplace."""
        try:
            response = self.session.get(f"{self.marketplace_url}/api/plugins/{plugin_id}")
            
            if response.status_code == 404:
                return None
            
            response.raise_for_status()
            plugin_data = response.json()
            
            manifest = PluginManifest.from_dict(plugin_data['manifest'])
            
            rating_data = plugin_data.get('rating')
            rating = PluginRating(**rating_data) if rating_data else None
            
            stats_data = plugin_data.get('download_stats')
            download_stats = PluginDownloadStats(**stats_data) if stats_data else None
            
            entry = MarketplaceEntry(
                plugin_id=plugin_data['plugin_id'],
                manifest=manifest,
                package_url=plugin_data['package_url'],
                package_hash=plugin_data['package_hash'],
                signature_url=plugin_data.get('signature_url'),
                rating=rating,
                download_stats=download_stats,
                featured=plugin_data.get('featured', False),
                verified=plugin_data.get('verified', False),
                published_at=plugin_data.get('published_at'),
                updated_at=plugin_data.get('updated_at')
            )
            
            return entry
            
        except requests.RequestException as e:
            logger.error(f"Failed to get plugin from remote marketplace: {e}")
            raise MarketplaceError(f"Remote marketplace access failed: {e}")
    
    def download_plugin(self, plugin_id: str, downloader_id: str) -> bytes:
        """
        Download a plugin package from the remote marketplace.
        
        Args:
            plugin_id: Plugin ID to download
            downloader_id: ID of the downloader
            
        Returns:
            Plugin package bytes
        """
        try:
            # Get plugin info first
            entry = self.get_plugin(plugin_id)
            if not entry:
                raise PluginNotFoundError(f"Plugin not found: {plugin_id}")
            
            # Download package
            response = self.session.get(entry.package_url)
            response.raise_for_status()
            
            package_data = response.content
            
            # Verify hash
            actual_hash = hashlib.sha256(package_data).hexdigest()
            if actual_hash != entry.package_hash:
                raise MarketplaceError(f"Package hash mismatch for {plugin_id}")
            
            # Record download
            self.session.post(
                f"{self.marketplace_url}/api/plugins/{plugin_id}/download",
                json={'downloader_id': downloader_id}
            )
            
            logger.info(f"Plugin downloaded from remote marketplace: {plugin_id}")
            
            return package_data
            
        except requests.RequestException as e:
            logger.error(f"Failed to download plugin from remote marketplace: {e}")
            raise MarketplaceError(f"Remote plugin download failed: {e}")


class HybridMarketplace:
    """
    Hybrid marketplace that combines local and remote marketplaces.
    """
    
    def __init__(self, local_marketplace: LocalMarketplace, 
                 remote_marketplace: RemoteMarketplace):
        self.local = local_marketplace
        self.remote = remote_marketplace
        
        logger.info("Hybrid marketplace initialized")
    
    def search_plugins(self, query: str = "", category: str = "", 
                      plugin_type: PluginType = None, limit: int = 50,
                      include_remote: bool = True) -> List[MarketplaceEntry]:
        """
        Search for plugins in both local and remote marketplaces.
        
        Args:
            query: Search query string
            category: Plugin category filter
            plugin_type: Plugin type filter
            limit: Maximum number of results
            include_remote: Whether to include remote results
            
        Returns:
            List of matching marketplace entries
        """
        # Search local first
        local_results = self.local.search_plugins(query, category, plugin_type, limit)
        
        if not include_remote:
            return local_results
        
        # Search remote
        try:
            remote_limit = max(0, limit - len(local_results))
            if remote_limit > 0:
                remote_results = self.remote.search_plugins(query, category, plugin_type, remote_limit)
                
                # Filter out duplicates (prefer local versions)
                local_ids = {entry.plugin_id for entry in local_results}
                unique_remote = [entry for entry in remote_results if entry.plugin_id not in local_ids]
                
                return local_results + unique_remote
            
        except MarketplaceError as e:
            logger.warning(f"Remote marketplace search failed: {e}")
        
        return local_results
    
    def get_plugin(self, plugin_id: str, prefer_local: bool = True) -> Optional[MarketplaceEntry]:
        """Get a plugin, preferring local or remote based on preference."""
        if prefer_local:
            # Try local first
            entry = self.local.get_plugin(plugin_id)
            if entry:
                return entry
            
            # Fall back to remote
            try:
                return self.remote.get_plugin(plugin_id)
            except MarketplaceError:
                return None
        else:
            # Try remote first
            try:
                entry = self.remote.get_plugin(plugin_id)
                if entry:
                    return entry
            except MarketplaceError:
                pass
            
            # Fall back to local
            return self.local.get_plugin(plugin_id)
    
    def download_plugin(self, plugin_id: str, downloader_id: str, 
                       prefer_local: bool = True) -> bytes:
        """Download a plugin, preferring local or remote based on preference."""
        if prefer_local:
            # Try local first
            try:
                return self.local.download_plugin(plugin_id, downloader_id)
            except (PluginNotFoundError, MarketplaceError):
                pass
            
            # Fall back to remote
            return self.remote.download_plugin(plugin_id, downloader_id)
        else:
            # Try remote first
            try:
                return self.remote.download_plugin(plugin_id, downloader_id)
            except (PluginNotFoundError, MarketplaceError):
                pass
            
            # Fall back to local
            return self.local.download_plugin(plugin_id, downloader_id)


class MarketplaceManager:
    """
    Main marketplace manager that coordinates plugin discovery and installation.
    """
    
    def __init__(self, plugin_system: PluginSystem, marketplace_config: Dict[str, Any] = None):
        self.plugin_system = plugin_system
        self.config = marketplace_config or {}
        
        # Initialize marketplaces based on configuration
        self.local_marketplace = LocalMarketplace(
            self.config.get('local_directory')
        )
        
        remote_config = self.config.get('remote')
        if remote_config:
            self.remote_marketplace = RemoteMarketplace(
                remote_config['url'],
                remote_config.get('api_key')
            )
            
            self.marketplace = HybridMarketplace(
                self.local_marketplace,
                self.remote_marketplace
            )
        else:
            self.marketplace = self.local_marketplace
        
        logger.info("Marketplace manager initialized")
    
    def install_from_marketplace(self, plugin_id: str, installed_by: str, 
                               version: str = None) -> str:
        """
        Install a plugin from the marketplace.
        
        Args:
            plugin_id: Plugin ID to install
            installed_by: User installing the plugin
            version: Specific version to install (latest if None)
            
        Returns:
            Installed plugin ID
        """
        # Find plugin in marketplace
        entry = self.marketplace.get_plugin(plugin_id)
        if not entry:
            raise PluginNotFoundError(f"Plugin not found in marketplace: {plugin_id}")
        
        # Check version compatibility if specified
        if version and entry.manifest.version != version:
            raise MarketplaceError(f"Version {version} not available for {plugin_id}")
        
        # Download plugin package
        package_data = self.marketplace.download_plugin(plugin_id, installed_by)
        
        # Install through plugin system
        return self.plugin_system.install_plugin(package_data, installed_by)
    
    def search_marketplace(self, query: str = "", **kwargs) -> List[MarketplaceEntry]:
        """Search the marketplace for plugins."""
        return self.marketplace.search_plugins(query, **kwargs)
    
    def get_marketplace_stats(self) -> Dict[str, Any]:
        """Get marketplace statistics."""
        if hasattr(self.marketplace, 'local'):
            # Hybrid marketplace
            local_count = len(self.marketplace.local.plugins_index)
            try:
                remote_results = self.marketplace.remote.search_plugins(limit=1000)
                remote_count = len(remote_results)
            except:
                remote_count = 0
            
            return {
                'type': 'hybrid',
                'local_plugins': local_count,
                'remote_plugins': remote_count,
                'total_unique': local_count + remote_count  # Approximate
            }
        else:
            # Local only
            return {
                'type': 'local',
                'total_plugins': len(self.marketplace.plugins_index),
                'categories': len(self.marketplace.get_categories())
            }