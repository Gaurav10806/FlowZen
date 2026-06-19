"""
Plugin Manifest - Plugin Metadata and Configuration

This module defines the plugin manifest format and validation for
third-party plugin packages.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict, field
from enum import Enum
from datetime import datetime


logger = logging.getLogger(__name__)


class PluginType(Enum):
    """Types of plugins supported by the system."""
    NODE = "node"           # Provides workflow nodes
    TRIGGER = "trigger"     # Provides workflow triggers
    TOOL = "tool"          # Provides AI agent tools
    MIXED = "mixed"        # Provides multiple types


class PluginStatus(Enum):
    """Plugin installation and runtime status."""
    INSTALLED = "installed"     # Installed but not enabled
    ENABLED = "enabled"         # Enabled but not loaded
    LOADED = "loaded"          # Loaded and active
    DISABLED = "disabled"      # Disabled by user/admin
    ERROR = "error"           # Error state
    UNLOADED = "unloaded"     # Unloaded from memory


class TrustLevel(Enum):
    """Plugin trust levels for security and permissions."""
    UNTRUSTED = "untrusted"     # No special permissions
    COMMUNITY = "community"     # Community-verified
    VERIFIED = "verified"       # Platform-verified
    OFFICIAL = "official"       # Official platform plugins


@dataclass
class PluginAuthor:
    """Plugin author information."""
    name: str
    email: str
    website: Optional[str] = None
    organization: Optional[str] = None


@dataclass
class PluginDependency:
    """Plugin dependency specification."""
    name: str
    version: str
    optional: bool = False
    source: str = "marketplace"  # marketplace, pypi, git, etc.


@dataclass
class PluginPermissions:
    """Plugin permission requirements."""
    network_access: bool = False
    file_system_access: bool = False
    database_access: bool = False
    external_apis: List[str] = field(default_factory=list)
    allowed_imports: List[str] = field(default_factory=list)
    resource_limits: Dict[str, Any] = field(default_factory=dict)
    custom_permissions: List[str] = field(default_factory=list)


@dataclass
class PluginCompatibility:
    """Plugin compatibility requirements."""
    min_platform_version: str
    max_platform_version: Optional[str] = None
    python_version: str = ">=3.8"
    required_features: List[str] = field(default_factory=list)
    conflicting_plugins: List[str] = field(default_factory=list)


@dataclass
class PluginProvides:
    """What the plugin provides to the platform."""
    nodes: List[str] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    apis: List[str] = field(default_factory=list)


@dataclass
class PluginManifest:
    """
    Complete plugin manifest specification.
    
    This defines all metadata, dependencies, permissions, and configuration
    required for a plugin to be installed and executed safely.
    """
    
    # Basic Information
    plugin_id: str
    name: str
    version: str
    description: str
    author: PluginAuthor
    
    # Plugin Configuration
    plugin_type: PluginType
    main_module: str
    provides: PluginProvides
    
    # Security and Permissions
    permissions: PluginPermissions
    trust_level: TrustLevel = TrustLevel.UNTRUSTED
    requires_signature: bool = True
    
    # Compatibility
    compatibility: PluginCompatibility = None
    
    # Dependencies
    dependencies: List[PluginDependency] = field(default_factory=list)
    
    # Metadata
    homepage: Optional[str] = None
    repository: Optional[str] = None
    documentation: Optional[str] = None
    license: str = "MIT"
    keywords: List[str] = field(default_factory=list)
    category: str = "general"
    
    # Marketplace Information
    icon: Optional[str] = None
    screenshots: List[str] = field(default_factory=list)
    changelog: Optional[str] = None
    
    # Runtime Configuration
    config_schema: Dict[str, Any] = field(default_factory=dict)
    default_config: Dict[str, Any] = field(default_factory=dict)
    
    # Validation
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def __post_init__(self):
        """Post-initialization validation and setup."""
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()
        
        if self.updated_at is None:
            self.updated_at = self.created_at
        
        if self.compatibility is None:
            self.compatibility = PluginCompatibility(min_platform_version="1.0.0")
        
        # Validate plugin ID format
        if not self._is_valid_plugin_id(self.plugin_id):
            raise ValueError(f"Invalid plugin ID format: {self.plugin_id}")
        
        # Validate version format
        if not self._is_valid_version(self.version):
            raise ValueError(f"Invalid version format: {self.version}")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PluginManifest':
        """
        Create PluginManifest from dictionary data.
        
        Args:
            data: Dictionary containing manifest data
            
        Returns:
            PluginManifest instance
        """
        # Convert nested objects
        if 'author' in data and isinstance(data['author'], dict):
            data['author'] = PluginAuthor(**data['author'])
        
        if 'permissions' in data and isinstance(data['permissions'], dict):
            data['permissions'] = PluginPermissions(**data['permissions'])
        
        if 'compatibility' in data and isinstance(data['compatibility'], dict):
            data['compatibility'] = PluginCompatibility(**data['compatibility'])
        
        if 'provides' in data and isinstance(data['provides'], dict):
            data['provides'] = PluginProvides(**data['provides'])
        
        # Convert dependencies
        if 'dependencies' in data and isinstance(data['dependencies'], list):
            dependencies = []
            for dep in data['dependencies']:
                if isinstance(dep, dict):
                    dependencies.append(PluginDependency(**dep))
                else:
                    dependencies.append(dep)
            data['dependencies'] = dependencies
        
        # Convert enums
        if 'plugin_type' in data and isinstance(data['plugin_type'], str):
            data['plugin_type'] = PluginType(data['plugin_type'])
        
        if 'trust_level' in data and isinstance(data['trust_level'], str):
            data['trust_level'] = TrustLevel(data['trust_level'])
        
        return cls(**data)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert PluginManifest to dictionary.
        
        Returns:
            Dictionary representation of manifest
        """
        result = asdict(self)
        
        # Convert enums to strings
        result['plugin_type'] = self.plugin_type.value
        result['trust_level'] = self.trust_level.value
        
        return result
    
    def to_json(self, indent: int = 2) -> str:
        """
        Convert PluginManifest to JSON string.
        
        Args:
            indent: JSON indentation
            
        Returns:
            JSON string representation
        """
        return json.dumps(self.to_dict(), indent=indent)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'PluginManifest':
        """
        Create PluginManifest from JSON string.
        
        Args:
            json_str: JSON string containing manifest data
            
        Returns:
            PluginManifest instance
        """
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def validate(self) -> List[str]:
        """
        Validate the plugin manifest for completeness and correctness.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Required fields validation
        if not self.plugin_id:
            errors.append("Plugin ID is required")
        
        if not self.name:
            errors.append("Plugin name is required")
        
        if not self.version:
            errors.append("Plugin version is required")
        
        if not self.description:
            errors.append("Plugin description is required")
        
        if not self.main_module:
            errors.append("Main module is required")
        
        # Author validation
        if not self.author.name:
            errors.append("Author name is required")
        
        if not self.author.email:
            errors.append("Author email is required")
        
        # Provides validation
        total_provides = (
            len(self.provides.nodes) + 
            len(self.provides.triggers) + 
            len(self.provides.tools) + 
            len(self.provides.apis)
        )
        
        if total_provides == 0:
            errors.append("Plugin must provide at least one node, trigger, tool, or API")
        
        # Plugin type consistency
        if self.plugin_type == PluginType.NODE and not self.provides.nodes:
            errors.append("Node plugin must provide at least one node")
        
        if self.plugin_type == PluginType.TRIGGER and not self.provides.triggers:
            errors.append("Trigger plugin must provide at least one trigger")
        
        if self.plugin_type == PluginType.TOOL and not self.provides.tools:
            errors.append("Tool plugin must provide at least one tool")
        
        # Permission validation
        if self.permissions.network_access and not self.permissions.external_apis:
            # Network access without specific APIs might be suspicious
            pass  # Warning, not error
        
        # Dependency validation
        for dep in self.dependencies:
            if not dep.name or not dep.version:
                errors.append(f"Invalid dependency: {dep}")
        
        # Compatibility validation
        if not self.compatibility.min_platform_version:
            errors.append("Minimum platform version is required")
        
        return errors
    
    def get_required_permissions(self) -> List[str]:
        """
        Get list of human-readable permission descriptions.
        
        Returns:
            List of permission descriptions
        """
        permissions = []
        
        if self.permissions.network_access:
            permissions.append("Access external networks and APIs")
        
        if self.permissions.file_system_access:
            permissions.append("Read and write files on the system")
        
        if self.permissions.database_access:
            permissions.append("Access workflow and user databases")
        
        if self.permissions.external_apis:
            api_list = ", ".join(self.permissions.external_apis)
            permissions.append(f"Access external APIs: {api_list}")
        
        if self.permissions.allowed_imports:
            import_list = ", ".join(self.permissions.allowed_imports)
            permissions.append(f"Import Python modules: {import_list}")
        
        if self.permissions.custom_permissions:
            for perm in self.permissions.custom_permissions:
                permissions.append(f"Custom permission: {perm}")
        
        return permissions
    
    def is_compatible_with_platform(self, platform_version: str) -> bool:
        """
        Check if plugin is compatible with given platform version.
        
        Args:
            platform_version: Platform version to check against
            
        Returns:
            True if compatible
        """
        # Simple version comparison (would use proper semver in production)
        min_version = self.compatibility.min_platform_version
        max_version = self.compatibility.max_platform_version
        
        if self._version_compare(platform_version, min_version) < 0:
            return False
        
        if max_version and self._version_compare(platform_version, max_version) > 0:
            return False
        
        return True
    
    def _is_valid_plugin_id(self, plugin_id: str) -> bool:
        """
        Validate plugin ID format.
        
        Args:
            plugin_id: Plugin ID to validate
            
        Returns:
            True if valid format
        """
        # Plugin ID should be lowercase, alphanumeric with hyphens/underscores
        import re
        pattern = r'^[a-z0-9][a-z0-9_-]*[a-z0-9]$'
        return bool(re.match(pattern, plugin_id)) and len(plugin_id) >= 3
    
    def _is_valid_version(self, version: str) -> bool:
        """
        Validate version format (semantic versioning).
        
        Args:
            version: Version string to validate
            
        Returns:
            True if valid format
        """
        import re
        # Basic semver pattern
        pattern = r'^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$'
        return bool(re.match(pattern, version))
    
    def _version_compare(self, version1: str, version2: str) -> int:
        """
        Compare two version strings.
        
        Args:
            version1: First version
            version2: Second version
            
        Returns:
            -1 if version1 < version2, 0 if equal, 1 if version1 > version2
        """
        # Simple version comparison (would use proper semver in production)
        v1_parts = [int(x) for x in version1.split('.')]
        v2_parts = [int(x) for x in version2.split('.')]
        
        # Pad shorter version with zeros
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts.extend([0] * (max_len - len(v1_parts)))
        v2_parts.extend([0] * (max_len - len(v2_parts)))
        
        for v1, v2 in zip(v1_parts, v2_parts):
            if v1 < v2:
                return -1
            elif v1 > v2:
                return 1
        
        return 0


def create_sample_manifest() -> PluginManifest:
    """
    Create a sample plugin manifest for reference.
    
    Returns:
        Sample PluginManifest
    """
    return PluginManifest(
        plugin_id="sample-http-node",
        name="Enhanced HTTP Request Node",
        version="1.0.0",
        description="An enhanced HTTP request node with advanced features like retry logic, authentication, and response validation.",
        author=PluginAuthor(
            name="John Developer",
            email="john@example.com",
            website="https://johndeveloper.com",
            organization="Example Corp"
        ),
        plugin_type=PluginType.NODE,
        main_module="main.py",
        provides=PluginProvides(
            nodes=["EnhancedHttpNode"],
            tools=["http_request_tool"]
        ),
        permissions=PluginPermissions(
            network_access=True,
            external_apis=["*"],  # Allow all external APIs
            allowed_imports=["requests", "urllib3", "json", "time"],
            resource_limits={
                "max_memory_mb": 100,
                "max_execution_time_seconds": 30,
                "max_network_requests_per_minute": 60
            }
        ),
        trust_level=TrustLevel.COMMUNITY,
        requires_signature=True,
        compatibility=PluginCompatibility(
            min_platform_version="1.0.0",
            max_platform_version="2.0.0",
            python_version=">=3.8",
            required_features=["http_nodes", "network_access"]
        ),
        dependencies=[
            PluginDependency(
                name="requests",
                version=">=2.25.0",
                source="pypi"
            )
        ],
        homepage="https://github.com/example/enhanced-http-node",
        repository="https://github.com/example/enhanced-http-node",
        documentation="https://docs.example.com/enhanced-http-node",
        license="MIT",
        keywords=["http", "api", "request", "network"],
        category="network",
        config_schema={
            "type": "object",
            "properties": {
                "default_timeout": {
                    "type": "integer",
                    "default": 30,
                    "minimum": 1,
                    "maximum": 300
                },
                "retry_attempts": {
                    "type": "integer",
                    "default": 3,
                    "minimum": 0,
                    "maximum": 10
                }
            }
        },
        default_config={
            "default_timeout": 30,
            "retry_attempts": 3
        }
    )