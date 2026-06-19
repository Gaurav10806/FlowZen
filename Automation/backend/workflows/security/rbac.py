"""
Role-Based Access Control (RBAC) System
Enterprise-grade security with granular permissions
"""

from enum import Enum
from typing import Dict, List, Set, Optional
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.cache import cache
from django.utils import timezone
import json
import logging

logger = logging.getLogger(__name__)

class Permission(models.TextChoices):
    """System permissions"""
    # Workflow permissions
    WORKFLOW_CREATE = 'workflow.create', 'Create Workflows'
    WORKFLOW_READ = 'workflow.read', 'Read Workflows'
    WORKFLOW_UPDATE = 'workflow.update', 'Update Workflows'
    WORKFLOW_DELETE = 'workflow.delete', 'Delete Workflows'
    WORKFLOW_EXECUTE = 'workflow.execute', 'Execute Workflows'
    WORKFLOW_PUBLISH = 'workflow.publish', 'Publish Workflows'
    
    # Execution permissions
    EXECUTION_READ = 'execution.read', 'Read Executions'
    EXECUTION_RETRY = 'execution.retry', 'Retry Executions'
    EXECUTION_CANCEL = 'execution.cancel', 'Cancel Executions'
    EXECUTION_DELETE = 'execution.delete', 'Delete Executions'
    
    # Node permissions
    NODE_CREATE = 'node.create', 'Create Nodes'
    NODE_READ = 'node.read', 'Read Nodes'
    NODE_UPDATE = 'node.update', 'Update Nodes'
    NODE_DELETE = 'node.delete', 'Delete Nodes'
    
    # Credential permissions
    CREDENTIAL_CREATE = 'credential.create', 'Create Credentials'
    CREDENTIAL_READ = 'credential.read', 'Read Credentials'
    CREDENTIAL_UPDATE = 'credential.update', 'Update Credentials'
    CREDENTIAL_DELETE = 'credential.delete', 'Delete Credentials'
    CREDENTIAL_USE = 'credential.use', 'Use Credentials'
    
    # Organization permissions
    ORG_ADMIN = 'org.admin', 'Organization Admin'
    ORG_MANAGE_USERS = 'org.manage_users', 'Manage Organization Users'
    ORG_MANAGE_BILLING = 'org.manage_billing', 'Manage Billing'
    ORG_VIEW_ANALYTICS = 'org.view_analytics', 'View Analytics'
    
    # System permissions
    SYSTEM_ADMIN = 'system.admin', 'System Administrator'
    SYSTEM_MONITOR = 'system.monitor', 'System Monitoring'
    SYSTEM_BACKUP = 'system.backup', 'System Backup'
    
    # AI permissions
    AI_USE_BASIC = 'ai.use_basic', 'Use Basic AI Features'
    AI_USE_ADVANCED = 'ai.use_advanced', 'Use Advanced AI Features'
    AI_MANAGE_MODELS = 'ai.manage_models', 'Manage AI Models'

class Role(models.Model):
    """Role definition with permissions"""
    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    permissions = models.JSONField(default=list)
    is_system_role = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'workflow_roles'
    
    def __str__(self):
        return self.display_name
    
    def has_permission(self, permission: str) -> bool:
        """Check if role has specific permission"""
        return permission in self.permissions
    
    def add_permission(self, permission: str):
        """Add permission to role"""
        if permission not in self.permissions:
            self.permissions.append(permission)
            self.save()
    
    def remove_permission(self, permission: str):
        """Remove permission from role"""
        if permission in self.permissions:
            self.permissions.remove(permission)
            self.save()

class OrganizationUser(models.Model):
    """User membership in organization with roles"""
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    organization = models.ForeignKey('workflows.Organization', on_delete=models.CASCADE)
    roles = models.ManyToManyField(Role, blank=True)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'workflow_organization_users'
        unique_together = ['user', 'organization']
    
    def get_permissions(self) -> Set[str]:
        """Get all permissions for this user in the organization"""
        permissions = set()
        for role in self.roles.all():
            permissions.update(role.permissions)
        return permissions
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission in organization"""
        return permission in self.get_permissions()

class ResourcePermission(models.Model):
    """Resource-level permissions for fine-grained access control"""
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    organization = models.ForeignKey('workflows.Organization', on_delete=models.CASCADE)
    resource_type = models.CharField(max_length=50)  # workflow, execution, credential, etc.
    resource_id = models.CharField(max_length=100)
    permissions = models.JSONField(default=list)
    granted_by = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='granted_permissions')
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'workflow_resource_permissions'
        unique_together = ['user', 'organization', 'resource_type', 'resource_id']

class SecurityAuditLog(models.Model):
    """Security audit log for compliance"""
    user = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True)
    organization = models.ForeignKey('workflows.Organization', on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=50)
    resource_id = models.CharField(max_length=100, blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    success = models.BooleanField()
    details = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'workflow_security_audit_log'
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['organization', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]

class RBACManager:
    """Role-Based Access Control Manager"""
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
    
    def create_default_roles(self):
        """Create default system roles"""
        default_roles = [
            {
                'name': 'viewer',
                'display_name': 'Viewer',
                'description': 'Can view workflows and executions',
                'permissions': [
                    Permission.WORKFLOW_READ,
                    Permission.EXECUTION_READ,
                    Permission.NODE_READ,
                ]
            },
            {
                'name': 'editor',
                'display_name': 'Editor',
                'description': 'Can create and edit workflows',
                'permissions': [
                    Permission.WORKFLOW_CREATE,
                    Permission.WORKFLOW_READ,
                    Permission.WORKFLOW_UPDATE,
                    Permission.WORKFLOW_EXECUTE,
                    Permission.EXECUTION_READ,
                    Permission.EXECUTION_RETRY,
                    Permission.NODE_CREATE,
                    Permission.NODE_READ,
                    Permission.NODE_UPDATE,
                    Permission.CREDENTIAL_READ,
                    Permission.CREDENTIAL_USE,
                ]
            },
            {
                'name': 'admin',
                'display_name': 'Administrator',
                'description': 'Full access to organization resources',
                'permissions': [
                    Permission.WORKFLOW_CREATE,
                    Permission.WORKFLOW_READ,
                    Permission.WORKFLOW_UPDATE,
                    Permission.WORKFLOW_DELETE,
                    Permission.WORKFLOW_EXECUTE,
                    Permission.WORKFLOW_PUBLISH,
                    Permission.EXECUTION_READ,
                    Permission.EXECUTION_RETRY,
                    Permission.EXECUTION_CANCEL,
                    Permission.EXECUTION_DELETE,
                    Permission.NODE_CREATE,
                    Permission.NODE_READ,
                    Permission.NODE_UPDATE,
                    Permission.NODE_DELETE,
                    Permission.CREDENTIAL_CREATE,
                    Permission.CREDENTIAL_READ,
                    Permission.CREDENTIAL_UPDATE,
                    Permission.CREDENTIAL_DELETE,
                    Permission.CREDENTIAL_USE,
                    Permission.ORG_MANAGE_USERS,
                    Permission.ORG_VIEW_ANALYTICS,
                    Permission.AI_USE_BASIC,
                    Permission.AI_USE_ADVANCED,
                ]
            },
            {
                'name': 'owner',
                'display_name': 'Owner',
                'description': 'Organization owner with full permissions',
                'permissions': [perm.value for perm in Permission if not perm.value.startswith('system.')],
                'is_system_role': True
            },
            {
                'name': 'system_admin',
                'display_name': 'System Administrator',
                'description': 'System-wide administrator',
                'permissions': [perm.value for perm in Permission],
                'is_system_role': True
            }
        ]
        
        for role_data in default_roles:
            role, created = Role.objects.get_or_create(
                name=role_data['name'],
                defaults=role_data
            )
            if created:
                logger.info(f"Created default role: {role.name}")
    
    def check_permission(self, user, organization, permission: str, resource_type: str = None, resource_id: str = None) -> bool:
        """Check if user has permission for resource"""
        try:
            # Cache key for user permissions
            cache_key = f"user_permissions:{user.id}:{organization.id}"
            user_permissions = cache.get(cache_key)
            
            if user_permissions is None:
                # Get user's organization membership
                try:
                    org_user = OrganizationUser.objects.get(
                        user=user,
                        organization=organization,
                        is_active=True
                    )
                    user_permissions = org_user.get_permissions()
                    cache.set(cache_key, user_permissions, self.cache_timeout)
                except OrganizationUser.DoesNotExist:
                    return False
            
            # Check role-based permission
            if permission in user_permissions:
                return True
            
            # Check resource-level permission
            if resource_type and resource_id:
                try:
                    resource_perm = ResourcePermission.objects.get(
                        user=user,
                        organization=organization,
                        resource_type=resource_type,
                        resource_id=resource_id
                    )
                    
                    # Check if permission is not expired
                    if resource_perm.expires_at and resource_perm.expires_at < timezone.now():
                        return False
                    
                    return permission in resource_perm.permissions
                except ResourcePermission.DoesNotExist:
                    pass
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking permission: {e}")
            return False
    
    def grant_resource_permission(self, user, organization, resource_type: str, resource_id: str, 
                                permissions: List[str], granted_by, expires_at=None):
        """Grant resource-level permissions"""
        try:
            resource_perm, created = ResourcePermission.objects.get_or_create(
                user=user,
                organization=organization,
                resource_type=resource_type,
                resource_id=resource_id,
                defaults={
                    'permissions': permissions,
                    'granted_by': granted_by,
                    'expires_at': expires_at
                }
            )
            
            if not created:
                # Update existing permissions
                resource_perm.permissions = list(set(resource_perm.permissions + permissions))
                resource_perm.granted_by = granted_by
                resource_perm.expires_at = expires_at
                resource_perm.save()
            
            # Clear user permissions cache
            cache_key = f"user_permissions:{user.id}:{organization.id}"
            cache.delete(cache_key)
            
            # Log the action
            self.log_security_action(
                user=granted_by,
                organization=organization,
                action='grant_resource_permission',
                resource_type=resource_type,
                resource_id=resource_id,
                success=True,
                details={
                    'target_user': user.username,
                    'permissions': permissions,
                    'expires_at': expires_at.isoformat() if expires_at else None
                }
            )
            
        except Exception as e:
            logger.error(f"Error granting resource permission: {e}")
            raise
    
    def revoke_resource_permission(self, user, organization, resource_type: str, resource_id: str, 
                                 permissions: List[str], revoked_by):
        """Revoke resource-level permissions"""
        try:
            resource_perm = ResourcePermission.objects.get(
                user=user,
                organization=organization,
                resource_type=resource_type,
                resource_id=resource_id
            )
            
            # Remove specified permissions
            for perm in permissions:
                if perm in resource_perm.permissions:
                    resource_perm.permissions.remove(perm)
            
            if not resource_perm.permissions:
                # Delete if no permissions left
                resource_perm.delete()
            else:
                resource_perm.save()
            
            # Clear user permissions cache
            cache_key = f"user_permissions:{user.id}:{organization.id}"
            cache.delete(cache_key)
            
            # Log the action
            self.log_security_action(
                user=revoked_by,
                organization=organization,
                action='revoke_resource_permission',
                resource_type=resource_type,
                resource_id=resource_id,
                success=True,
                details={
                    'target_user': user.username,
                    'permissions': permissions
                }
            )
            
        except ResourcePermission.DoesNotExist:
            pass  # Permission doesn't exist, nothing to revoke
        except Exception as e:
            logger.error(f"Error revoking resource permission: {e}")
            raise
    
    def log_security_action(self, user, organization, action: str, resource_type: str = '', 
                          resource_id: str = '', success: bool = True, details: Dict = None,
                          ip_address: str = '', user_agent: str = ''):
        """Log security action for audit"""
        try:
            SecurityAuditLog.objects.create(
                user=user,
                organization=organization,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=ip_address or '127.0.0.1',
                user_agent=user_agent or '',
                success=success,
                details=details or {}
            )
        except Exception as e:
            logger.error(f"Error logging security action: {e}")
    
    def get_user_roles(self, user, organization) -> List[Role]:
        """Get user's roles in organization"""
        try:
            org_user = OrganizationUser.objects.get(
                user=user,
                organization=organization,
                is_active=True
            )
            return list(org_user.roles.all())
        except OrganizationUser.DoesNotExist:
            return []
    
    def assign_role(self, user, organization, role: Role, assigned_by):
        """Assign role to user in organization"""
        try:
            org_user, created = OrganizationUser.objects.get_or_create(
                user=user,
                organization=organization,
                defaults={'is_active': True}
            )
            
            org_user.roles.add(role)
            
            # Clear user permissions cache
            cache_key = f"user_permissions:{user.id}:{organization.id}"
            cache.delete(cache_key)
            
            # Log the action
            self.log_security_action(
                user=assigned_by,
                organization=organization,
                action='assign_role',
                success=True,
                details={
                    'target_user': user.username,
                    'role': role.name
                }
            )
            
        except Exception as e:
            logger.error(f"Error assigning role: {e}")
            raise
    
    def remove_role(self, user, organization, role: Role, removed_by):
        """Remove role from user in organization"""
        try:
            org_user = OrganizationUser.objects.get(
                user=user,
                organization=organization
            )
            
            org_user.roles.remove(role)
            
            # Clear user permissions cache
            cache_key = f"user_permissions:{user.id}:{organization.id}"
            cache.delete(cache_key)
            
            # Log the action
            self.log_security_action(
                user=removed_by,
                organization=organization,
                action='remove_role',
                success=True,
                details={
                    'target_user': user.username,
                    'role': role.name
                }
            )
            
        except OrganizationUser.DoesNotExist:
            pass  # User not in organization
        except Exception as e:
            logger.error(f"Error removing role: {e}")
            raise

# Global RBAC manager instance
rbac_manager = RBACManager()