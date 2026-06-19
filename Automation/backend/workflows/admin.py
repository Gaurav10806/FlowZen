"""
Django admin configuration for all models.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    # PHASE-1 - Core models that definitely exist
    Workflow, Node, WorkflowExecution, NodeExecution,
    Credential, WorkflowVersion, ExecutionLog, BinaryFile,
    Tenant, Notification, WorkflowTemplate, DeadLetterItem,
    WorkflowExecutionStep, ChatSession, ChatMessage,
    # PHASE-2 - Organization models
    Organization, Team, Membership, UsageLimit, SubscriptionPlan, Subscription, Invoice,
    # PHASE-3 - AI models
    AIWorkflowGeneration, AICodeGeneration, AIWorkflowOptimization,
    # PHASE-4 - Security and observability models
    Metric, SecretAccessLog, GDPRDataRequest, AuditLog, IPAllowlist
)


# ============================================
# PHASE-1: CORE MODELS
# ============================================

@admin.register(Workflow)
class WorkflowAdmin(admin.ModelAdmin):
    list_display = ['name', 'status', 'owner', 'safe_organization', 'created_at']
    list_filter = ['status', 'environment', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    def safe_organization(self, obj):
        """Safely display organization name."""
        try:
            return obj.organization.name if obj.organization else "No Organization"
        except Exception:
            return "Error"
    safe_organization.short_description = 'Organization'


@admin.register(Node)
class NodeAdmin(admin.ModelAdmin):
    list_display = ['label', 'action_type', 'workflow', 'safe_max_retries', 'safe_on_error']
    list_filter = ['action_type', 'created_at']
    search_fields = ['label', 'node_id']
    
    def safe_max_retries(self, obj):
        """Safely display max_retries."""
        try:
            return getattr(obj, 'max_retries', 'N/A')
        except Exception:
            return 'Error'
    safe_max_retries.short_description = 'Max Retries'
    
    def safe_on_error(self, obj):
        """Safely display on_error."""
        try:
            return getattr(obj, 'on_error', 'N/A')
        except Exception:
            return 'Error'
    safe_on_error.short_description = 'On Error'


@admin.register(WorkflowExecution)
class WorkflowExecutionAdmin(admin.ModelAdmin):
    list_display = ['id', 'workflow', 'status', 'triggered_by', 'started_at', 'finished_at']
    list_filter = ['status', 'triggered_by', 'created_at']
    search_fields = ['workflow__name', 'correlation_id']
    readonly_fields = ['id', 'created_at']


@admin.register(NodeExecution)
class NodeExecutionAdmin(admin.ModelAdmin):
    list_display = ['node', 'status', 'retry_count', 'started_at', 'finished_at']
    list_filter = ['status', 'created_at']
    search_fields = ['node__label']


@admin.register(Credential)
class CredentialAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'environment', 'owner', 'safe_organization', 'created_at']
    list_filter = ['type', 'environment', 'created_at']
    search_fields = ['name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    def safe_organization(self, obj):
        """Safely display organization name."""
        try:
            return obj.organization.name if obj.organization else "No Organization"
        except Exception:
            return "Error"
    safe_organization.short_description = 'Organization'


@admin.register(WorkflowTemplate)
class WorkflowTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'safe_category', 'is_public', 'usage_count', 'created_at']
    list_filter = ['is_public', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    def safe_category(self, obj):
        """Safely display category."""
        try:
            return getattr(obj, 'category', 'No Category')
        except Exception:
            return 'Error'
    safe_category.short_description = 'Category'


@admin.register(ExecutionLog)
class ExecutionLogAdmin(admin.ModelAdmin):
    list_display = ['safe_execution', 'level', 'safe_message', 'timestamp']
    list_filter = ['level', 'timestamp']
    search_fields = ['message']
    readonly_fields = ['id', 'timestamp']
    
    def safe_execution(self, obj):
        """Safely display execution."""
        try:
            return str(obj.execution) if obj.execution else "No Execution"
        except Exception:
            return "Error"
    safe_execution.short_description = 'Execution'
    
    def safe_message(self, obj):
        """Safely display message."""
        try:
            message = getattr(obj, 'message', '')
            return message[:50] + '...' if len(message) > 50 else message
        except Exception:
            return 'Error'
    safe_message.short_description = 'Message'


@admin.register(BinaryFile)
class BinaryFileAdmin(admin.ModelAdmin):
    list_display = ['filename', 'safe_execution', 'content_type', 'size', 'created_at']
    list_filter = ['content_type', 'created_at']
    search_fields = ['filename']
    readonly_fields = ['id', 'created_at']
    
    def safe_execution(self, obj):
        """Safely display execution."""
        try:
            return str(obj.execution) if obj.execution else "No Execution"
        except Exception:
            return "Error"
    safe_execution.short_description = 'Execution'


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ['safe_user', 'title', 'status', 'safe_workflow', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['title', 'user__username']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    def safe_user(self, obj):
        """Safely display user."""
        try:
            return obj.user.username if obj.user else "No User"
        except Exception:
            return "Error"
    safe_user.short_description = 'User'
    
    def safe_workflow(self, obj):
        """Safely display workflow."""
        try:
            return obj.workflow.name if obj.workflow else "No Workflow"
        except Exception:
            return "Error"
    safe_workflow.short_description = 'Workflow'


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['safe_session', 'message_type', 'safe_content', 'created_at']
    list_filter = ['message_type', 'created_at']
    search_fields = ['content']
    readonly_fields = ['id', 'created_at']
    
    def safe_session(self, obj):
        """Safely display session."""
        try:
            return str(obj.session) if obj.session else "No Session"
        except Exception:
            return "Error"
    safe_session.short_description = 'Session'
    
    def safe_content(self, obj):
        """Safely display content."""
        try:
            content = getattr(obj, 'content', '')
            return content[:50] + '...' if len(content) > 50 else content
        except Exception:
            return 'Error'
    safe_content.short_description = 'Content'


# ============================================
# PHASE-2: ORGANIZATIONS & BILLING
# ============================================

@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_at']
    search_fields = ['name', 'slug']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ['name', 'organization', 'created_at']
    list_filter = ['organization', 'created_at']
    search_fields = ['name']


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'organization', 'role', 'team', 'created_at']
    list_filter = ['role', 'organization', 'created_at']
    search_fields = ['user__username', 'organization__name']


@admin.register(UsageLimit)
class UsageLimitAdmin(admin.ModelAdmin):
    list_display = ['organization', 'executions_this_month', 'max_executions_per_month', 'last_reset_at']
    list_filter = ['created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'name', 'price_monthly', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'display_name']


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['organization', 'plan', 'status', 'current_period_end', 'cancel_at_period_end']
    list_filter = ['status', 'plan', 'created_at']
    search_fields = ['organization__name', 'stripe_subscription_id']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['organization', 'amount_due', 'status', 'paid_at', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['organization__name', 'stripe_invoice_id']
    readonly_fields = ['id', 'created_at', 'updated_at']


# ============================================
# PHASE-3: AI FEATURES
# ============================================

@admin.register(AIWorkflowGeneration)
class AIWorkflowGenerationAdmin(admin.ModelAdmin):
    list_display = ['user', 'status', 'tokens_used', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'user_prompt']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(AICodeGeneration)
class AICodeGenerationAdmin(admin.ModelAdmin):
    list_display = ['user', 'status', 'code_language', 'tokens_used', 'created_at']
    list_filter = ['status', 'code_language', 'created_at']
    search_fields = ['user__username', 'user_prompt']


@admin.register(AIWorkflowOptimization)
class AIWorkflowOptimizationAdmin(admin.ModelAdmin):
    list_display = ['workflow', 'optimization_type', 'applied', 'created_at']
    list_filter = ['optimization_type', 'applied', 'created_at']
    search_fields = ['workflow__name', 'suggestion']


# ============================================
# PHASE-4: SECURITY & OBSERVABILITY
# ============================================

@admin.register(SecretAccessLog)
class SecretAccessLogAdmin(admin.ModelAdmin):
    list_display = ['credential', 'user', 'access_type', 'timestamp']
    list_filter = ['access_type', 'timestamp']
    search_fields = ['credential__name', 'user__username']
    readonly_fields = ['id', 'timestamp']


@admin.register(IPAllowlist)
class IPAllowlistAdmin(admin.ModelAdmin):
    list_display = ['organization', 'ip_address', 'description', 'created_at']
    list_filter = ['created_at']
    search_fields = ['organization__name', 'ip_address', 'description']


@admin.register(GDPRDataRequest)
class GDPRDataRequestAdmin(admin.ModelAdmin):
    list_display = ['user', 'request_type', 'status', 'requested_at', 'completed_at']
    list_filter = ['request_type', 'status', 'requested_at']
    search_fields = ['user__username']
    readonly_fields = ['id', 'requested_at']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'resource_type', 'timestamp']
    list_filter = ['action', 'resource_type', 'timestamp']
    search_fields = ['user__username']
    readonly_fields = ['id', 'timestamp']


@admin.register(Metric)
class MetricAdmin(admin.ModelAdmin):
    list_display = ['name', 'metric_type', 'value', 'timestamp']
    list_filter = ['metric_type', 'timestamp']
    search_fields = ['name']
    readonly_fields = ['id', 'timestamp']


# ============================================
# ADDITIONAL MISSING ADMIN CLASSES
# ============================================

@admin.register(WorkflowVersion)
class WorkflowVersionAdmin(admin.ModelAdmin):
    list_display = ['safe_workflow', 'version_number', 'name', 'safe_created_by', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'workflow__name']
    readonly_fields = ['id', 'created_at']
    
    def safe_workflow(self, obj):
        """Safely display workflow."""
        try:
            return obj.workflow.name if obj.workflow else "No Workflow"
        except Exception:
            return "Error"
    safe_workflow.short_description = 'Workflow'
    
    def safe_created_by(self, obj):
        """Safely display created by."""
        try:
            return obj.created_by.username if obj.created_by else "System"
        except Exception:
            return "Error"
    safe_created_by.short_description = 'Created By'


@admin.register(DeadLetterItem)
class DeadLetterItemAdmin(admin.ModelAdmin):
    list_display = ['safe_workflow_execution', 'node_id', 'error_type', 'retries', 'created_at']
    list_filter = ['error_type', 'created_at']
    search_fields = ['node_id', 'error_message']
    readonly_fields = ['id', 'created_at']
    
    def safe_workflow_execution(self, obj):
        """Safely display workflow execution."""
        try:
            return str(obj.workflow_execution) if obj.workflow_execution else "No Execution"
        except Exception:
            return "Error"
    safe_workflow_execution.short_description = 'Workflow Execution'


@admin.register(WorkflowExecutionStep)
class WorkflowExecutionStepAdmin(admin.ModelAdmin):
    list_display = ['safe_execution', 'node_id', 'node_type', 'status', 'created_at']
    list_filter = ['status', 'node_type', 'created_at']
    search_fields = ['node_id']
    readonly_fields = ['id', 'created_at']
    
    def safe_execution(self, obj):
        """Safely display execution."""
        try:
            return str(obj.execution) if obj.execution else "No Execution"
        except Exception:
            return "Error"
    safe_execution.short_description = 'Execution'
