"""
Production Security Permissions
Enhanced permission classes for strict access control
"""
import logging
from rest_framework import permissions
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from .models import Organization, Membership, Workflow, WorkflowExecution

logger = logging.getLogger('security')


class StrictTenantIsolation(permissions.BasePermission):
    """
    CRITICAL: Enforce strict tenant isolation
    Prevents any cross-tenant data access
    """
    
    def has_permission(self, request, view):
        if isinstance(request.user, AnonymousUser):
            return False
        
        # Ensure user has tenant context
        if not hasattr(request, 'tenant'):
            logger.error(f"Request missing tenant context for user {request.user.id}")
            return False
        
        return True
    
    def has_object_permission(self, request, view, obj):
        if isinstance(request.user, AnonymousUser):
            return False
        
        # Get object's tenant
        obj_tenant = None
        if hasattr(obj, 'tenant'):
            obj_tenant = obj.tenant
        elif hasattr(obj, 'workflow') and hasattr(obj.workflow, 'tenant'):
            obj_tenant = obj.workflow.tenant
        elif hasattr(obj, 'organization') and hasattr(obj.organization, 'tenant'):
            obj_tenant = obj.organization.tenant
        
        # Verify tenant match
        if obj_tenant and hasattr(request, 'tenant'):
            if obj_tenant.id != request.tenant.id:
                logger.warning(
                    f"SECURITY: Tenant isolation violation - user {request.user.id} "
                    f"attempted access to tenant {obj_tenant.id} resource"
                )
                return False
        
        return True


class StrictWorkflowOwnership(permissions.BasePermission):
    """
    CRITICAL: Ensure users can only access workflows they own or have explicit access to
    """
    
    def has_object_permission(self, request, view, obj):
        if isinstance(request.user, AnonymousUser):
            return False
        
        # For workflow objects
        if isinstance(obj, Workflow):
            return self._check_workflow_access(request.user, obj)
        
        # For execution objects
        elif isinstance(obj, WorkflowExecution):
            return self._check_workflow_access(request.user, obj.workflow)
        
        # For objects with workflow relationship
        elif hasattr(obj, 'workflow'):
            return self._check_workflow_access(request.user, obj.workflow)
        
        return False
    
    def _check_workflow_access(self, user, workflow):
        """Check if user has access to workflow"""
        
        # Direct ownership
        if workflow.owner == user:
            return True
        
        # Organization membership
        if workflow.organization:
            membership = Membership.objects.filter(
                user=user,
                organization=workflow.organization
            ).first()
            
            if membership:
                # Check role-based access
                if membership.role in ['owner', 'admin']:
                    return True
                elif membership.role == 'viewer' and request.method in ['GET', 'HEAD', 'OPTIONS']:
                    return True
        
        logger.warning(
            f"SECURITY: Workflow access denied - user {user.id} "
            f"attempted access to workflow {workflow.id}"
        )
        return False


class ExecutionLimitsPermission(permissions.BasePermission):
    """
    CRITICAL: Enforce execution limits before allowing new executions
    """
    
    def has_permission(self, request, view):
        # Only check for execution creation
        if request.method != 'POST' or not request.path.endswith('/executions/'):
            return True
        
        if isinstance(request.user, AnonymousUser):
            return False
        
        # Check concurrent execution limit
        if not self._check_concurrent_limit(request):
            return False
        
        # Check daily execution limit
        if not self._check_daily_limit(request):
            return False
        
        return True
    
    def _check_concurrent_limit(self, request):
        """Check concurrent execution limit"""
        from django.utils import timezone
        
        # Count current running executions
        current_executions = WorkflowExecution.objects.filter(
            workflow__owner=request.user,
            workflow__tenant=request.tenant,
            status__in=['queued', 'running']
        ).count()
        
        # Get limit from tenant settings
        max_concurrent = getattr(request.tenant, 'settings', {}).get('max_concurrent_executions', 5)
        
        if current_executions >= max_concurrent:
            logger.warning(
                f"SECURITY: Concurrent execution limit exceeded - user {request.user.id} "
                f"has {current_executions}/{max_concurrent} executions"
            )
            return False
        
        return True
    
    def _check_daily_limit(self, request):
        """Check daily execution limit"""
        from django.utils import timezone
        
        today = timezone.now().date()
        daily_count = WorkflowExecution.objects.filter(
            workflow__owner=request.user,
            workflow__tenant=request.tenant,
            created_at__date=today
        ).count()
        
        # Get limit from tenant settings
        max_daily = getattr(request.tenant, 'settings', {}).get('max_daily_executions', 1000)
        
        if daily_count >= max_daily:
            logger.warning(
                f"SECURITY: Daily execution limit exceeded - user {request.user.id} "
                f"has {daily_count}/{max_daily} executions today"
            )
            return False
        
        return True


class CredentialAccessPermission(permissions.BasePermission):
    """
    CRITICAL: Control access to credentials with audit logging
    """
    
    def has_object_permission(self, request, view, obj):
        if isinstance(request.user, AnonymousUser):
            return False
        
        # Log credential access attempts
        logger.info(
            f"AUDIT: Credential access attempt - user {request.user.id} "
            f"credential {obj.id} method {request.method}"
        )
        
        # Check ownership
        if obj.owner != request.user:
            logger.warning(
                f"SECURITY: Unauthorized credential access - user {request.user.id} "
                f"attempted access to credential {obj.id} owned by {obj.owner.id}"
            )
            return False
        
        # Check tenant isolation
        if hasattr(request, 'tenant') and obj.tenant != request.tenant:
            logger.warning(
                f"SECURITY: Cross-tenant credential access - user {request.user.id} "
                f"attempted access to credential in different tenant"
            )
            return False
        
        return True


class WebhookSecurityPermission(permissions.BasePermission):
    """
    CRITICAL: Secure webhook access with validation
    """
    
    def has_permission(self, request, view):
        # Allow webhook triggers (they have their own security)
        if request.path.startswith('/webhook/'):
            return True
        
        # For webhook configuration endpoints, require authentication
        return request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        if isinstance(request.user, AnonymousUser):
            return False
        
        # Only workflow owners can configure webhooks
        if hasattr(obj, 'webhook_enabled') and obj.owner != request.user:
            logger.warning(
                f"SECURITY: Unauthorized webhook configuration - user {request.user.id} "
                f"attempted to configure webhook for workflow {obj.id}"
            )
            return False
        
        return True


class AdminOnlyPermission(permissions.BasePermission):
    """
    CRITICAL: Restrict admin-only operations
    """
    
    def has_permission(self, request, view):
        if isinstance(request.user, AnonymousUser):
            return False
        
        # Check if user has admin role in any organization
        admin_membership = Membership.objects.filter(
            user=request.user,
            role__in=['owner', 'admin']
        ).exists()
        
        if not admin_membership:
            logger.warning(
                f"SECURITY: Admin operation denied - user {request.user.id} "
                f"attempted admin operation without admin role"
            )
            return False
        
        return True