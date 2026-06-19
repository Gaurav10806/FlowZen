"""
Workflow Export/Import Core Logic

This module provides the core functionality for exporting and importing workflows
in a safe, portable, and version-aware manner.
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from copy import deepcopy

from django.conf import settings
from django.contrib.auth.models import User

from ..models import Workflow, Credential
from ..nodes import node_registry


logger = logging.getLogger(__name__)

# Export format version
EXPORT_FORMAT_VERSION = "1.0.0"
EXPORT_FORMAT_NAME = "n8n-automation-workflow"

# Supported export format versions (for import compatibility)
SUPPORTED_EXPORT_VERSIONS = ["1.0.0"]


@dataclass
class ExportMetadata:
    """Metadata for exported workflows."""
    export_version: str
    export_format: str
    exported_at: str
    exported_by: str
    compatibility: Dict[str, Any]


@dataclass
class DependencyInfo:
    """Information about workflow dependencies."""
    credentials: List[Dict[str, Any]]
    node_types: List[Dict[str, Any]]


@dataclass
class ImportResult:
    """Result of workflow import operation."""
    success: bool
    workflow_id: Optional[str] = None
    warnings: List[str] = None
    errors: List[str] = None
    import_summary: Dict[str, Any] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.errors is None:
            self.errors = []
        if self.import_summary is None:
            self.import_summary = {}


class WorkflowExporter:
    """
    Handles workflow export operations.
    
    Exports workflows in a portable format that can be imported
    into other instances of the platform.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
    
    def export_workflow(self, workflow: Workflow, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Export a workflow to portable format.
        
        Args:
            workflow: Workflow instance to export
            options: Export options (sanitize_credentials, include_metadata, etc.)
            
        Returns:
            Dict containing the exported workflow data
            
        Raises:
            ValueError: If workflow cannot be exported
        """
        if options is None:
            options = {}
        
        self.logger.info(f"Exporting workflow: {workflow.name} ({workflow.id})")
        
        try:
            # Extract workflow data
            workflow_data = self._extract_workflow_data(workflow)
            
            # Sanitize sensitive data
            if options.get('sanitize_credentials', True):
                workflow_data = self._sanitize_credentials(workflow_data)
            
            # Generate dependencies
            dependencies = self._extract_dependencies(workflow_data)
            
            # Create export metadata
            metadata = self._create_export_metadata(workflow, dependencies)
            
            # Build final export structure
            export_data = {
                "export_version": metadata.export_version,
                "export_format": metadata.export_format,
                "exported_at": metadata.exported_at,
                "exported_by": metadata.exported_by,
                "compatibility": metadata.compatibility,
                "workflow": workflow_data,
                "dependencies": asdict(dependencies),
                "import_notes": self._generate_import_notes(workflow, dependencies)
            }
            
            # Validate export data
            self._validate_export_data(export_data)
            
            self.logger.info(f"Successfully exported workflow: {workflow.name}")
            return export_data
            
        except Exception as e:
            self.logger.error(f"Failed to export workflow {workflow.name}: {e}")
            raise ValueError(f"Export failed: {str(e)}")
    
    def _extract_workflow_data(self, workflow: Workflow) -> Dict[str, Any]:
        """Extract workflow data in portable format."""
        # Get the workflow graph
        graph = workflow.graph or {}
        
        # Create portable workflow structure
        workflow_data = {
            "meta": {
                "name": workflow.name,
                "description": workflow.description,
                "version": workflow.version,
                "category": "automation",  # Default category
                "tags": []  # Could be extracted from settings
            },
            "trigger": graph.get("trigger", {}),
            "nodes": graph.get("nodes", {}),
            "connections": graph.get("connections", {})
        }
        
        # Remove database IDs and replace with portable IDs
        workflow_data = self._sanitize_ids(workflow_data)
        
        return workflow_data
    
    def _sanitize_ids(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove database IDs and replace with portable identifiers."""
        # Deep copy to avoid modifying original
        sanitized = deepcopy(data)
        
        # The workflow graph should already use portable node IDs
        # No additional ID sanitization needed for current structure
        
        return sanitized
    
    def _sanitize_credentials(self, workflow_data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove credential values and replace with placeholders."""
        sanitized = deepcopy(workflow_data)
        credential_counter = 1
        credential_mapping = {}
        
        def sanitize_node_params(params: Dict[str, Any]) -> Dict[str, Any]:
            nonlocal credential_counter, credential_mapping
            
            sanitized_params = deepcopy(params)
            
            # Look for credential references
            for key, value in params.items():
                if key.lower() in ['credential', 'credentials', 'auth', 'authentication']:
                    if isinstance(value, str) and value:
                        # Replace with placeholder
                        if value not in credential_mapping:
                            placeholder = f"CREDENTIAL_{credential_counter}"
                            credential_mapping[value] = placeholder
                            credential_counter += 1
                        sanitized_params[key] = credential_mapping[value]
                elif isinstance(value, dict):
                    sanitized_params[key] = sanitize_node_params(value)
            
            return sanitized_params
        
        # Sanitize trigger params
        if 'trigger' in sanitized and 'params' in sanitized['trigger']:
            sanitized['trigger']['params'] = sanitize_node_params(sanitized['trigger']['params'])
        
        # Sanitize node params
        if 'nodes' in sanitized:
            for node_id, node_data in sanitized['nodes'].items():
                if 'params' in node_data:
                    sanitized['nodes'][node_id]['params'] = sanitize_node_params(node_data['params'])
        
        return sanitized
    
    def _extract_dependencies(self, workflow_data: Dict[str, Any]) -> DependencyInfo:
        """Extract dependency information from workflow."""
        credentials = []
        node_types = []
        
        # Extract credential dependencies
        credential_placeholders = set()
        
        def extract_from_params(params: Dict[str, Any]):
            for key, value in params.items():
                if key.lower() in ['credential', 'credentials', 'auth', 'authentication']:
                    if isinstance(value, str) and value.startswith('CREDENTIAL_'):
                        credential_placeholders.add(value)
                elif isinstance(value, dict):
                    extract_from_params(value)
        
        # Check trigger
        if 'trigger' in workflow_data and 'params' in workflow_data['trigger']:
            extract_from_params(workflow_data['trigger']['params'])
        
        # Check nodes
        if 'nodes' in workflow_data:
            for node_data in workflow_data['nodes'].values():
                if 'params' in node_data:
                    extract_from_params(node_data['params'])
        
        # Create credential dependency info
        for placeholder in credential_placeholders:
            credentials.append({
                "placeholder": placeholder,
                "type": "unknown",  # Would need to infer from usage
                "description": f"Credential required for workflow operation",
                "required": True
            })
        
        # Extract node type dependencies
        node_type_set = set()
        
        # Add trigger type
        if 'trigger' in workflow_data and 'type' in workflow_data['trigger']:
            node_type_set.add(workflow_data['trigger']['type'])
        
        # Add node types
        if 'nodes' in workflow_data:
            for node_data in workflow_data['nodes'].values():
                if 'type' in node_data:
                    node_type_set.add(node_data['type'])
        
        # Create node type dependency info
        for node_type in node_type_set:
            node_types.append({
                "type": node_type,
                "version": ">=1.0.0",  # Default version requirement
                "required": True
            })
        
        return DependencyInfo(credentials=credentials, node_types=node_types)
    
    def _create_export_metadata(self, workflow: Workflow, dependencies: DependencyInfo) -> ExportMetadata:
        """Create export metadata."""
        # Get required node types
        required_node_types = [dep["type"] for dep in dependencies.node_types]
        
        # Determine required features
        required_features = []
        if any(nt in ["webhook_trigger"] for nt in required_node_types):
            required_features.append("webhooks")
        if any(nt in ["schedule_trigger"] for nt in required_node_types):
            required_features.append("scheduling")
        
        compatibility = {
            "min_platform_version": "1.0.0",
            "required_node_types": required_node_types,
            "required_features": required_features
        }
        
        return ExportMetadata(
            export_version=EXPORT_FORMAT_VERSION,
            export_format=EXPORT_FORMAT_NAME,
            exported_at=datetime.now(timezone.utc).isoformat(),
            exported_by="system",  # Could be user-specific
            compatibility=compatibility
        )
    
    def _generate_import_notes(self, workflow: Workflow, dependencies: DependencyInfo) -> Dict[str, str]:
        """Generate helpful import notes."""
        notes = {}
        
        if dependencies.credentials:
            notes["credential_mapping"] = f"You will need to configure {len(dependencies.credentials)} credential(s) before activating this workflow"
        
        if any(dep["type"] == "webhook_trigger" for dep in dependencies.node_types):
            notes["webhook_setup"] = "A new webhook URL will be generated upon import"
        
        if any(dep["type"] == "schedule_trigger" for dep in dependencies.node_types):
            notes["schedule_setup"] = "Schedule configuration will need to be reconfigured after import"
        
        return notes
    
    def _validate_export_data(self, export_data: Dict[str, Any]) -> None:
        """Validate export data structure."""
        required_fields = ["export_version", "export_format", "workflow", "dependencies"]
        
        for field in required_fields:
            if field not in export_data:
                raise ValueError(f"Missing required field: {field}")
        
        # Validate workflow structure
        workflow = export_data["workflow"]
        if "meta" not in workflow:
            raise ValueError("Workflow missing meta information")
        
        if "name" not in workflow["meta"]:
            raise ValueError("Workflow missing name")


class WorkflowImporter:
    """
    Handles workflow import operations.
    
    Imports workflows from portable format with validation
    and conflict resolution.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
    
    def validate_import(self, import_data: Dict[str, Any]) -> ImportResult:
        """
        Validate import data without actually importing.
        
        Args:
            import_data: Exported workflow data to validate
            
        Returns:
            ImportResult with validation results
        """
        self.logger.info("Validating workflow import data")
        
        try:
            # Validate format
            format_validation = self._validate_format(import_data)
            if not format_validation.success:
                return format_validation
            
            # Validate compatibility
            compatibility_validation = self._validate_compatibility(import_data)
            if not compatibility_validation.success:
                return compatibility_validation
            
            # Validate dependencies
            dependency_validation = self._validate_dependencies(import_data)
            if not dependency_validation.success:
                return dependency_validation
            
            # Validate workflow structure
            workflow_validation = self._validate_workflow_structure(import_data)
            if not workflow_validation.success:
                return workflow_validation
            
            self.logger.info("Import validation successful")
            return ImportResult(success=True)
            
        except Exception as e:
            self.logger.error(f"Import validation failed: {e}")
            return ImportResult(success=False, errors=[str(e)])
    
    def import_workflow(self, import_data: Dict[str, Any], user: User, 
                       options: Dict[str, Any] = None) -> ImportResult:
        """
        Import a workflow from portable format.
        
        Args:
            import_data: Exported workflow data
            user: User importing the workflow
            options: Import options (conflict_resolution, credential_mapping, etc.)
            
        Returns:
            ImportResult with import results
        """
        if options is None:
            options = {}
        
        self.logger.info(f"Importing workflow for user: {user.username}")
        
        try:
            # Validate import data first
            validation_result = self.validate_import(import_data)
            if not validation_result.success:
                return validation_result
            
            # Extract workflow data
            workflow_data = import_data["workflow"]
            
            # Handle naming conflicts
            final_name = self._resolve_naming_conflict(
                workflow_data["meta"]["name"], 
                user, 
                options.get("conflict_resolution", "rename")
            )
            
            # Apply credential mapping
            mapped_workflow_data = self._apply_credential_mapping(
                workflow_data, 
                options.get("credential_mapping", {})
            )
            
            # Create new workflow
            workflow = self._create_workflow(mapped_workflow_data, user, final_name)
            
            # Generate import summary
            import_summary = self._generate_import_summary(workflow_data, import_data.get("dependencies", {}))
            
            # Collect warnings
            warnings = []
            if final_name != workflow_data["meta"]["name"]:
                warnings.append(f"Workflow renamed from '{workflow_data['meta']['name']}' to '{final_name}' due to naming conflict")
            
            # Check for unmapped credentials
            unmapped_creds = self._check_unmapped_credentials(mapped_workflow_data)
            if unmapped_creds:
                warnings.extend([f"Credential '{cred}' needs to be configured" for cred in unmapped_creds])
            
            self.logger.info(f"Successfully imported workflow: {workflow.name} ({workflow.id})")
            
            return ImportResult(
                success=True,
                workflow_id=str(workflow.id),
                warnings=warnings,
                import_summary=import_summary
            )
            
        except Exception as e:
            self.logger.error(f"Failed to import workflow: {e}")
            return ImportResult(success=False, errors=[str(e)])
    
    def _validate_format(self, import_data: Dict[str, Any]) -> ImportResult:
        """Validate import data format."""
        # Check required top-level fields
        required_fields = ["export_version", "export_format", "workflow"]
        for field in required_fields:
            if field not in import_data:
                return ImportResult(success=False, errors=[f"Missing required field: {field}"])
        
        # Check export version compatibility
        export_version = import_data["export_version"]
        if export_version not in SUPPORTED_EXPORT_VERSIONS:
            return ImportResult(
                success=False, 
                errors=[f"Unsupported export version: {export_version}. Supported versions: {SUPPORTED_EXPORT_VERSIONS}"]
            )
        
        # Check export format
        export_format = import_data["export_format"]
        if export_format != EXPORT_FORMAT_NAME:
            return ImportResult(
                success=False,
                errors=[f"Unsupported export format: {export_format}. Expected: {EXPORT_FORMAT_NAME}"]
            )
        
        return ImportResult(success=True)
    
    def _validate_compatibility(self, import_data: Dict[str, Any]) -> ImportResult:
        """Validate platform compatibility."""
        compatibility = import_data.get("compatibility", {})
        
        # Check minimum platform version
        min_version = compatibility.get("min_platform_version", "1.0.0")
        current_version = getattr(settings, 'PLATFORM_VERSION', '1.0.0')
        
        # Simple version comparison (would need proper semver in production)
        if min_version > current_version:
            return ImportResult(
                success=False,
                errors=[f"Workflow requires platform version {min_version} or higher. Current version: {current_version}"]
            )
        
        return ImportResult(success=True)
    
    def _validate_dependencies(self, import_data: Dict[str, Any]) -> ImportResult:
        """Validate workflow dependencies."""
        dependencies = import_data.get("dependencies", {})
        errors = []
        warnings = []
        
        # Check node type availability
        required_node_types = dependencies.get("node_types", [])
        for node_type_info in required_node_types:
            node_type = node_type_info["type"]
            if not node_registry.has_node_type(node_type):
                if node_type_info.get("required", True):
                    errors.append(f"Required node type '{node_type}' is not available")
                else:
                    warnings.append(f"Optional node type '{node_type}' is not available")
        
        # Check required features
        compatibility = import_data.get("compatibility", {})
        required_features = compatibility.get("required_features", [])
        
        # Feature availability check (simplified)
        available_features = ["webhooks", "scheduling"]  # Would be dynamic in production
        for feature in required_features:
            if feature not in available_features:
                errors.append(f"Required feature '{feature}' is not available")
        
        if errors:
            return ImportResult(success=False, errors=errors, warnings=warnings)
        
        return ImportResult(success=True, warnings=warnings)
    
    def _validate_workflow_structure(self, import_data: Dict[str, Any]) -> ImportResult:
        """Validate workflow structure."""
        workflow = import_data["workflow"]
        errors = []
        
        # Check required workflow fields
        if "meta" not in workflow:
            errors.append("Workflow missing meta information")
        elif "name" not in workflow["meta"]:
            errors.append("Workflow missing name")
        
        # Check workflow graph structure
        if "trigger" not in workflow:
            errors.append("Workflow missing trigger")
        
        if "nodes" not in workflow:
            errors.append("Workflow missing nodes")
        
        if "connections" not in workflow:
            errors.append("Workflow missing connections")
        
        # Validate node references in connections
        if "nodes" in workflow and "connections" in workflow:
            node_ids = set(workflow["nodes"].keys())
            
            # Add trigger ID if present
            if "trigger" in workflow and "id" in workflow["trigger"]:
                node_ids.add(workflow["trigger"]["id"])
            
            connections = workflow["connections"]
            for source_id, targets in connections.items():
                if source_id not in node_ids:
                    errors.append(f"Connection references unknown node: {source_id}")
                
                if isinstance(targets, list):
                    for target_id in targets:
                        if target_id not in node_ids:
                            errors.append(f"Connection references unknown target node: {target_id}")
                elif isinstance(targets, dict):
                    for condition, target_list in targets.items():
                        if isinstance(target_list, list):
                            for target_id in target_list:
                                if target_id not in node_ids:
                                    errors.append(f"Connection references unknown target node: {target_id}")
        
        if errors:
            return ImportResult(success=False, errors=errors)
        
        return ImportResult(success=True)
    
    def _resolve_naming_conflict(self, desired_name: str, user: User, resolution: str) -> str:
        """Resolve workflow naming conflicts."""
        # Check if name already exists for user
        existing_workflows = Workflow.objects.filter(owner=user, name=desired_name)
        
        if not existing_workflows.exists():
            return desired_name
        
        if resolution == "fail":
            raise ValueError(f"Workflow with name '{desired_name}' already exists")
        elif resolution == "overwrite":
            # Would need additional confirmation in real implementation
            return desired_name
        else:  # resolution == "rename"
            # Find available name with suffix
            counter = 1
            while True:
                new_name = f"{desired_name} ({counter})"
                if not Workflow.objects.filter(owner=user, name=new_name).exists():
                    return new_name
                counter += 1
    
    def _apply_credential_mapping(self, workflow_data: Dict[str, Any], 
                                 credential_mapping: Dict[str, str]) -> Dict[str, Any]:
        """Apply credential mapping to workflow data."""
        mapped_data = deepcopy(workflow_data)
        
        def map_params(params: Dict[str, Any]) -> Dict[str, Any]:
            mapped_params = deepcopy(params)
            
            for key, value in params.items():
                if isinstance(value, str) and value.startswith('CREDENTIAL_'):
                    if value in credential_mapping:
                        mapped_params[key] = credential_mapping[value]
                    # If not mapped, leave as placeholder for later configuration
                elif isinstance(value, dict):
                    mapped_params[key] = map_params(value)
            
            return mapped_params
        
        # Map trigger params
        if 'trigger' in mapped_data and 'params' in mapped_data['trigger']:
            mapped_data['trigger']['params'] = map_params(mapped_data['trigger']['params'])
        
        # Map node params
        if 'nodes' in mapped_data:
            for node_id, node_data in mapped_data['nodes'].items():
                if 'params' in node_data:
                    mapped_data['nodes'][node_id]['params'] = map_params(node_data['params'])
        
        return mapped_data
    
    def _create_workflow(self, workflow_data: Dict[str, Any], user: User, name: str) -> Workflow:
        """Create new workflow from imported data."""
        # Get user's tenant (simplified - would need proper tenant resolution)
        from ..models import Tenant
        tenant = Tenant.objects.filter(name="default").first()
        if not tenant:
            tenant = Tenant.objects.create(name="default", slug="default")
        
        # Create workflow
        workflow = Workflow.objects.create(
            name=name,
            description=workflow_data["meta"].get("description", ""),
            version=workflow_data["meta"].get("version", 1),
            graph=workflow_data,  # Store the complete graph structure
            status="draft",  # Always import as draft
            owner=user,
            tenant=tenant,
            created_by=user
        )
        
        return workflow
    
    def _generate_import_summary(self, workflow_data: Dict[str, Any], 
                                dependencies: Dict[str, Any]) -> Dict[str, Any]:
        """Generate import summary."""
        node_count = len(workflow_data.get("nodes", {}))
        credential_count = len(dependencies.get("credentials", []))
        
        return {
            "nodes_imported": node_count,
            "credentials_required": credential_count,
            "conflicts_resolved": 0,  # Would track actual conflicts
            "status": "imported_as_draft"
        }
    
    def _check_unmapped_credentials(self, workflow_data: Dict[str, Any]) -> List[str]:
        """Check for unmapped credential placeholders."""
        unmapped = set()
        
        def check_params(params: Dict[str, Any]):
            for key, value in params.items():
                if isinstance(value, str) and value.startswith('CREDENTIAL_'):
                    unmapped.add(value)
                elif isinstance(value, dict):
                    check_params(value)
        
        # Check trigger
        if 'trigger' in workflow_data and 'params' in workflow_data['trigger']:
            check_params(workflow_data['trigger']['params'])
        
        # Check nodes
        if 'nodes' in workflow_data:
            for node_data in workflow_data['nodes'].values():
                if 'params' in node_data:
                    check_params(node_data['params'])
        
        return list(unmapped)


# Convenience functions
def export_workflow(workflow: Workflow, options: Dict[str, Any] = None) -> Dict[str, Any]:
    """Export a workflow to portable format."""
    exporter = WorkflowExporter()
    return exporter.export_workflow(workflow, options)


def import_workflow(import_data: Dict[str, Any], user: User, 
                   options: Dict[str, Any] = None) -> ImportResult:
    """Import a workflow from portable format."""
    importer = WorkflowImporter()
    return importer.import_workflow(import_data, user, options)


def validate_import(import_data: Dict[str, Any]) -> ImportResult:
    """Validate import data without importing."""
    importer = WorkflowImporter()
    return importer.validate_import(import_data)