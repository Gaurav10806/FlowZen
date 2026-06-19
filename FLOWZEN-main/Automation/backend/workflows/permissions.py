"""
Permission classes for multi-tenant SaaS with role-based access control.
"""
from rest_framework import permissions
from django.contrib.auth.models import AnonymousUser
from .models import Organization, Membership


class IsOrganizationMember(permissions.BasePermission):
    """Check if user is a member of the organization."""
    
    def has_object_permission(self, request, view, obj):
        if isinstance(request.user, AnonymousUser):
            return False
        
        # Get organization from object
        organization = None
        if hasattr(obj, 'organization'):
            organization = obj.organization
        elif hasattr(obj, 'workflow') and hasattr(obj.workflow, 'organization'):
            organization = obj.workflow.organization
        elif hasattr(obj, 'workflow_execution') and hasattr(obj.workflow_execution.workflow, 'organization'):
            organization = obj.workflow_execution.workflow.organization
        
        if not organization:
            return False
        
        # Check membership
        return Membership.objects.filter(
            user=request.user,
            organization=organization
        ).exists()


class HasOrganizationRole(permissions.BasePermission):
    """Check if user has required role in organization."""
    
    required_roles = []
    
    def has_permission(self, request, view):
        if isinstance(request.user, AnonymousUser):
            return False
        
        # Get organization from request
        org_id = request.data.get('organization') or request.query_params.get('organization')
        if not org_id:
            return False
        
        try:
            organization = Organization.objects.get(id=org_id)
        except Organization.DoesNotExist:
            return False
        
        # Check membership and role
        membership = Membership.objects.filter(
            user=request.user,
            organization=organization
        ).first()
        
        if not membership:
            return False
        
        return membership.role in self.required_roles
    
    def has_object_permission(self, request, view, obj):
        if isinstance(request.user, AnonymousUser):
            return False
        
        # Get organization from object
        organization = None
        if hasattr(obj, 'organization'):
            organization = obj.organization
        elif hasattr(obj, 'workflow') and hasattr(obj.workflow, 'organization'):
            organization = obj.workflow.organization
        
        if not organization:
            return False
        
        # Check membership and role
        membership = Membership.objects.filter(
            user=request.user,
            organization=organization
        ).first()
        
        if not membership:
            return False
        
        return membership.role in self.required_roles


class IsOwner(HasOrganizationRole):
    """User must be Owner."""
    required_roles = ['owner']


class IsAdmin(HasOrganizationRole):
    """User must be Admin or Owner."""
    required_roles = ['owner', 'admin']


class IsViewer(HasOrganizationRole):
    """User must be Viewer, Admin, or Owner."""
    required_roles = ['owner', 'admin', 'viewer']


class CanCreateWorkflow(permissions.BasePermission):
    """Check if user can create workflows (Admin+)."""
    
    def has_permission(self, request, view):
        if request.method not in ['POST', 'PUT', 'PATCH']:
            return True
        
        if isinstance(request.user, AnonymousUser):
            return False
        
        org_id = request.data.get('organization')
        if not org_id:
            return True  # Allow if no org specified (legacy)
        
        try:
            organization = Organization.objects.get(id=org_id)
        except Organization.DoesNotExist:
            return False
        
        membership = Membership.objects.filter(
            user=request.user,
            organization=organization
        ).first()
        
        if not membership:
            return False
        
        return membership.role in ['owner', 'admin']


class CanExecuteWorkflow(permissions.BasePermission):
    """Check if user can execute workflows (Admin+)."""
    
    def has_object_permission(self, request, view, obj):
        if request.method not in ['POST']:  # Only for execute actions
            return True
        
        if isinstance(request.user, AnonymousUser):
            return False
        
        organization = None
        if hasattr(obj, 'organization'):
            organization = obj.organization
        elif hasattr(obj, 'workflow') and hasattr(obj.workflow, 'organization'):
            organization = obj.workflow.organization
        
        if not organization:
            return True  # Legacy workflows without org
        
        membership = Membership.objects.filter(
            user=request.user,
            organization=organization
        ).first()
        
        if not membership:
            return False
        
        return membership.role in ['owner', 'admin']


