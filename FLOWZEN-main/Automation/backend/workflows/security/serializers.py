"""
Security and RBAC Serializers
"""

from rest_framework import serializers
from .rbac import Role, OrganizationUser, SecurityAuditLog

class RoleSerializer(serializers.ModelSerializer):
    permission_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Role
        fields = [
            'id', 'name', 'display_name', 'description', 'permissions',
            'is_system_role', 'permission_count', 'created_at', 'updated_at'
        ]
    
    def get_permission_count(self, obj):
        return len(obj.permissions)

class OrganizationUserSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    roles = RoleSerializer(many=True, read_only=True)
    
    class Meta:
        model = OrganizationUser
        fields = [
            'user', 'username', 'email', 'full_name', 'roles',
            'is_active', 'joined_at', 'last_active'
        ]

class SecurityAuditLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    user_full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = SecurityAuditLog
        fields = [
            'id', 'username', 'user_full_name', 'action', 'resource_type',
            'resource_id', 'ip_address', 'success', 'details', 'timestamp'
        ]