"""
Security and RBAC API Views
Role management, permissions, and audit logging
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
import logging

from .rbac import rbac_manager, Permission, Role, OrganizationUser, SecurityAuditLog
from .serializers import (
    RoleSerializer, OrganizationUserSerializer, SecurityAuditLogSerializer
)

logger = logging.getLogger(__name__)

class SecurityPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def rbac_permissions(request):
    """
    Get available permissions and user's current permissions
    """
    try:
        # Check if user can view permissions
        if not rbac_manager.check_permission(
            request.user, 
            request.tenant, 
            Permission.ORG_MANAGE_USERS
        ):
            return Response(
                {'error': 'Insufficient permissions to view RBAC information'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get all available permissions
        all_permissions = [
            {
                'value': perm.value,
                'label': perm.label,
                'category': perm.value.split('.')[0]
            }
            for perm in Permission
        ]
        
        # Group permissions by category
        permissions_by_category = {}
        for perm in all_permissions:
            category = perm['category']
            if category not in permissions_by_category:
                permissions_by_category[category] = []
            permissions_by_category[category].append(perm)
        
        # Get user's current permissions
        user_permissions = []
        try:
            org_user = OrganizationUser.objects.get(
                user=request.user,
                organization=request.tenant,
                is_active=True
            )
            user_permissions = list(org_user.get_permissions())
        except OrganizationUser.DoesNotExist:
            pass
        
        return Response({
            'success': True,
            'permissions': {
                'all': all_permissions,
                'by_category': permissions_by_category,
                'user_permissions': user_permissions
            }
        })
        
    except Exception as e:
        logger.error(f"RBAC permissions error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_roles(request):
    """
    Get user roles in organization
    """
    try:
        # Check permissions
        if not rbac_manager.check_permission(
            request.user, 
            request.tenant, 
            Permission.ORG_MANAGE_USERS
        ):
            return Response(
                {'error': 'Insufficient permissions to view user roles'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get organization users with roles
        org_users = OrganizationUser.objects.filter(
            organization=request.tenant,
            is_active=True
        ).select_related('user').prefetch_related('roles')
        
        # Get available roles
        available_roles = Role.objects.all().order_by('name')
        
        # Serialize data
        users_data = []
        for org_user in org_users:
            user_data = {
                'user_id': org_user.user.id,
                'username': org_user.user.username,
                'email': org_user.user.email,
                'full_name': org_user.user.get_full_name(),
                'roles': RoleSerializer(org_user.roles.all(), many=True).data,
                'joined_at': org_user.joined_at,
                'last_active': org_user.last_active
            }
            users_data.append(user_data)
        
        return Response({
            'success': True,
            'users': users_data,
            'available_roles': RoleSerializer(available_roles, many=True).data
        })
        
    except Exception as e:
        logger.error(f"User roles error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_role(request):
    """
    Assign or remove role from user
    """
    try:
        # Check permissions
        if not rbac_manager.check_permission(
            request.user, 
            request.tenant, 
            Permission.ORG_MANAGE_USERS
        ):
            return Response(
                {'error': 'Insufficient permissions to manage user roles'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate input
        user_id = request.data.get('user_id')
        role_id = request.data.get('role_id')
        action = request.data.get('action')  # 'assign' or 'remove'
        
        if not all([user_id, role_id, action]):
            return Response(
                {'error': 'user_id, role_id, and action are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if action not in ['assign', 'remove']:
            return Response(
                {'error': 'action must be "assign" or "remove"'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get user and role
        try:
            user = User.objects.get(id=user_id)
            role = Role.objects.get(id=role_id)
        except (User.DoesNotExist, Role.DoesNotExist):
            return Response(
                {'error': 'User or role not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Perform action
        if action == 'assign':
            rbac_manager.assign_role(user, request.tenant, role, request.user)
            message = f'Role "{role.display_name}" assigned to {user.username}'
        else:
            rbac_manager.remove_role(user, request.tenant, role, request.user)
            message = f'Role "{role.display_name}" removed from {user.username}'
        
        return Response({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        logger.error(f"Assign role error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def security_audit_log(request):
    """
    Get security audit log entries
    """
    try:
        # Check permissions
        if not rbac_manager.check_permission(
            request.user, 
            request.tenant, 
            Permission.ORG_VIEW_ANALYTICS
        ):
            return Response(
                {'error': 'Insufficient permissions to view audit log'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get query parameters
        action = request.GET.get('action')
        user_id = request.GET.get('user_id')
        resource_type = request.GET.get('resource_type')
        success = request.GET.get('success')
        
        # Build query
        queryset = SecurityAuditLog.objects.filter(
            organization=request.tenant
        ).select_related('user').order_by('-timestamp')
        
        if action:
            queryset = queryset.filter(action__icontains=action)
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        if resource_type:
            queryset = queryset.filter(resource_type=resource_type)
        
        if success is not None:
            queryset = queryset.filter(success=success.lower() == 'true')
        
        # Paginate results
        paginator = SecurityPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        if page is not None:
            serializer = SecurityAuditLogSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = SecurityAuditLogSerializer(queryset, many=True)
        return Response({
            'success': True,
            'audit_log': serializer.data
        })
        
    except Exception as e:
        logger.error(f"Security audit log error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_role(request):
    """
    Create a custom role
    """
    try:
        # Check permissions
        if not rbac_manager.check_permission(
            request.user, 
            request.tenant, 
            Permission.ORG_ADMIN
        ):
            return Response(
                {'error': 'Insufficient permissions to create roles'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Validate input
        name = request.data.get('name', '').strip()
        display_name = request.data.get('display_name', '').strip()
        description = request.data.get('description', '').strip()
        permissions = request.data.get('permissions', [])
        
        if not all([name, display_name]):
            return Response(
                {'error': 'name and display_name are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate permissions
        valid_permissions = [perm.value for perm in Permission]
        invalid_permissions = [p for p in permissions if p not in valid_permissions]
        
        if invalid_permissions:
            return Response(
                {'error': f'Invalid permissions: {invalid_permissions}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create role
        role = Role.objects.create(
            name=name,
            display_name=display_name,
            description=description,
            permissions=permissions,
            is_system_role=False
        )
        
        # Log the creation
        rbac_manager.log_security_action(
            user=request.user,
            organization=request.tenant,
            action='create_role',
            success=True,
            details={
                'role_name': role.name,
                'permissions_count': len(permissions)
            },
            ip_address=request.META.get('REMOTE_ADDR', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return Response({
            'success': True,
            'role': RoleSerializer(role).data,
            'message': f'Role "{display_name}" created successfully'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Create role error: {e}")
        return Response(
            {'error': 'Internal server error'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )