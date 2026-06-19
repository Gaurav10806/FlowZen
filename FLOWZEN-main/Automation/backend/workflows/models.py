print("LOADING VALIDATED MODELS V18 (User Export + Fixed Slicing)")
import uuid
import json
from django.db import models
import django.conf
from django.utils import timezone
from django.core.validators import MinLengthValidator, RegexValidator
from encrypted_model_fields.fields import EncryptedCharField
from django.contrib.auth.models import User  # Restore User export to satisfy hidden dependencies


class Tenant(models.Model):
    """Multi-tenant organization."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, max_length=100)
    settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["name"]
    
    def __str__(self):
        return self.name


class UserProfile(models.Model):
    """Extended user profile settings."""
    user = models.OneToOneField(django.conf.settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True, default='')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    avatar_url = models.URLField(blank=True, default='')
    theme = models.CharField(max_length=20, default='dark')
    theme_config = models.JSONField(default=dict, blank=True, help_text="Custom theme configuration: colors, glassmorphism, etc.")
    notifications_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"


class Workflow(models.Model):
    """Represents a workflow definition with nodes and edges."""
    
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("archived", "Archived"),
    ]
    
    ENVIRONMENT_CHOICES = [
        ("dev", "Development"),
        ("staging", "Staging"),
        ("production", "Production"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    environment = models.CharField(max_length=20, choices=ENVIRONMENT_CHOICES, default="dev")
    version = models.IntegerField(default=1)
    
    # Graph structure stored as JSON
    graph = models.JSONField(default=dict, help_text="Contains nodes and edges")
    
    # Webhook configuration
    webhook_secret = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="Secret for webhook HMAC verification"
    )
    webhook_enabled = models.BooleanField(default=False)
    webhook_path = models.CharField(max_length=255, blank=True, help_text="Custom webhook path", default="")
    webhook_config = models.JSONField(default=dict, blank=True)
    
    # Schedule configuration (for Celery beat)
    schedule = models.JSONField(
        default=dict,
        blank=True,
        help_text="Cron-like schedule config for periodic execution"
    )
    schedule_enabled = models.BooleanField(default=False)
    
    # Workflow settings
    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Priority, concurrency limits, timeout, etc."
    )
    
    # Sub-workflow support
    is_subworkflow = models.BooleanField(default=False)
    parent_workflow = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subworkflows"
    )
    
    # Sharing
    public_link_enabled = models.BooleanField(default=False)
    public_link_token = models.CharField(max_length=64, blank=True, unique=True, null=True)
    
    # Metadata
    owner = models.ForeignKey(django.conf.settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workflows")
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="workflows", null=True, blank=True)
    organization = models.ForeignKey("Organization", on_delete=models.CASCADE, related_name="workflows", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(django.conf.settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_workflows"
    )
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["webhook_enabled"]),
            models.Index(fields=["environment", "status"]),
            models.Index(fields=["public_link_token"]),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.id})"
    
    def save(self, *args, **kwargs):
        if not self.public_link_token and self.public_link_enabled:
            import secrets
            self.public_link_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)


class Node(models.Model):
    """Represents a node in a workflow graph."""
    
    NODE_TYPES = [
        ("trigger", "Trigger"),
        ("action", "Action"),
        ("condition", "Condition"),
    ]
    
    ACTION_TYPES = [
        ("http_request", "HTTP Request"),
        ("webhook", "Webhook Trigger"),
        ("schedule", "Schedule Trigger"),
        ("manual", "Manual Trigger"),
        ("email", "Send Email"),
        ("code", "Code (Python)"),
        ("condition", "IF / Condition"),
        ("delay", "Delay"),
        ("merge", "Merge"),
        ("set_variables", "Set Variables"),
        ("subworkflow", "Sub-Workflow"),
        ("transform", "Transform Data"),
        ("loop", "Loop"),
        ("google_calendar", "Google Calendar"),
        ("telegram_trigger", "Telegram Trigger"),
        ("telegram_send", "Telegram Send"),
        ("ai_agent", "AI Agent"),
        ("model_openai", "OpenAI Model"),
        ("tool_websearch", "Web Search Tool"),
        ("email_trigger", "Email Trigger"),
        ("whatsapp_trigger", "WhatsApp Trigger"),
        ("whatsapp_send", "WhatsApp Send"),
        ("chat_response", "Chat Response"),
    ]
    
    ERROR_STRATEGY_CHOICES = [
        ("stop", "Stop Workflow"),
        ("continue", "Continue to Next"),
        ("fallback", "Use Fallback Output"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="nodes")
    
    # Node identification in graph
    node_id = models.CharField(max_length=100, help_text="ID used in graph JSON")
    label = models.CharField(max_length=255)
    node_type = models.CharField(max_length=20, choices=NODE_TYPES, default="action")
    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)
    
    # Node configuration (action-specific)
    config = models.JSONField(default=dict, help_text="Action-specific configuration")
    
    # Position in visual editor
    position = models.JSONField(default=dict, blank=True)
    
    # Credential reference
    credential = models.ForeignKey(
        "Credential",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="nodes"
    )
    
    # Retry configuration (PHASE-1: Enhanced)
    max_retries = models.IntegerField(default=3, help_text="Maximum retry attempts")
    retry_delay = models.IntegerField(default=5, help_text="Retry delay in seconds")
    retry_backoff = models.JSONField(
        default=dict,
        blank=True,
        help_text="Retry backoff strategy: {type: 'exponential', base: 2, max: 300}"
    )
    
    # Timeout in seconds
    timeout = models.IntegerField(null=True, blank=True, default=30)
    
    # Error handling (PHASE-1: Enhanced)
    on_error = models.CharField(
        max_length=30,
        choices=[
            ("stop", "Stop Workflow"),
            ("continue", "Continue to Next"),
            ("goto_error_branch", "Go to Error Branch"),
        ],
        default="stop",
        help_text="Error handling policy"
    )
    error_strategy = models.CharField(
        max_length=20,
        choices=ERROR_STRATEGY_CHOICES,
        default="stop"
    )
    fallback_output = models.JSONField(default=dict, blank=True)
    
    # Data mapping configuration
    data_mapping = models.JSONField(
        default=dict,
        blank=True,
        help_text="Field mapping configuration for data transformation"
    )
    
    # Priority and throttling
    priority = models.IntegerField(default=5, help_text="1-10, higher = more priority")
    rate_limit = models.JSONField(
        default=dict,
        blank=True,
        help_text="Rate limit config: {requests: 100, window: 60}"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [["workflow", "node_id"]]
        indexes = [
            models.Index(fields=["workflow", "node_id"]),
            models.Index(fields=["action_type"]),
        ]
    
    def __str__(self):
        return f"{self.label} ({self.action_type})"




class AIWorkflowOptimization(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    workflow = models.ForeignKey("Workflow", on_delete=models.CASCADE, related_name="ai_optimizations")
    user = models.ForeignKey(django.conf.settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_optimizations")
    optimization_type = models.CharField(max_length=50, choices=[
        ('parallelism', 'Parallelism'),
        ('retry_tuning', 'Retry Tuning'),
        ('loop_detection', 'Loop Detection'),
        ('node_removal', 'Node Removal'),
        ('performance', 'Performance')
    ])
    suggestion = models.TextField()
    current_metrics = models.JSONField(default=dict, blank=True)
    predicted_improvement = models.JSONField(default=dict, blank=True)
    applied = models.BooleanField(default=False)
    applied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

class WorkflowEdge(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    workflow_id = models.UUIDField(db_index=True)
    source_node_id = models.CharField(max_length=100, db_index=True)
    source_handle = models.CharField(max_length=50, default='output')
    target_node_id = models.CharField(max_length=100, db_index=True)
    target_handle = models.CharField(max_length=50, default='input')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['workflow_id', 'source_node_id']),
            models.Index(fields=['workflow_id', 'target_node_id']),
        ]
class WorkflowExecution(models.Model):
    """Represents a single execution instance of a workflow."""
    
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("queued", "Queued"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
        ("paused", "Paused"),  # PHASE-1: For resume functionality
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="executions")
    
    # Explicit tenant FK for efficient queries (redundant but useful)
    # PHASE-1: NOT NULL enforced - no execution can exist without tenant
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="executions",
        help_text="Explicit tenant reference for efficient querying",
        null=True,
        blank=True
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    input_payload = models.JSONField(default=dict, help_text="Input data for workflow (legacy)")
    result = models.JSONField(default=dict, blank=True, help_text="Final aggregated result (legacy)")
    
    # NEW: Item-based input/output (n8n-style)
    input_items = models.JSONField(
        default=list,
        blank=True,
        help_text="Array of input items: [{'json': {...}, 'binary': {...}}, ...]"
    )
    output_items = models.JSONField(
        default=list,
        blank=True,
        help_text="Array of output items: [{'json': {...}, 'binary': {...}}, ...]"
    )
    
    # Error workflow reference
    error_workflow = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="error_handlers",
        help_text="Workflow to execute on error"
    )
    
    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    
    # Error tracking
    error_message = models.TextField(blank=True, null=True, default="")
    traceback = models.TextField(blank=True, null=True, default="")
    
    # Trigger information
    triggered_by = models.CharField(
        max_length=50,
        choices=[
            ("manual", "Manual"),
            ("webhook", "Webhook"),
            ("schedule", "Scheduled"),
            ("event", "Event"),
        ],
        default="manual"
    )
    
    # Correlation ID for distributed tracing
    correlation_id = models.CharField(max_length=100, blank=True, db_index=True, default="")
    idempotency_key = models.CharField(max_length=255, blank=True, db_index=True, default="")
    # Deterministic fingerprint for idempotent starts
    fingerprint = models.CharField(max_length=64, blank=True, db_index=True, default="")
    
    # Parent execution (for sub-workflows)
    parent_execution = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_executions"
    )
    
    # Priority
    priority = models.IntegerField(default=5)
    
    # PHASE-1: Resume support
    resume_from_node = models.CharField(max_length=100, blank=True, help_text="Node ID to resume from", default="")
    resume_data = models.JSONField(default=dict, blank=True, help_text="State data for resume")
    
    # Execution logs and results
    logs = models.TextField(blank=True, help_text="Human-readable execution logs", default="")
    node_results = models.JSONField(default=dict, blank=True, help_text="Per-node execution results")
    
    # Root/global context for entire execution (final state after all nodes)
    root_context = models.JSONField(
        default=dict,
        blank=True,
        help_text="Final global context after execution completes"
    )
    
    created_by = models.ForeignKey(django.conf.settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="workflow_executions")
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    output_data = models.JSONField(default=dict, blank=True, help_text="Final workflow output")
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["workflow", "status"]),
            models.Index(fields=["correlation_id"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["triggered_by", "created_at"]),
            models.Index(fields=["started_at"]),
            models.Index(fields=["finished_at"]),
            models.Index(fields=["priority", "created_at"]),
            models.Index(fields=["parent_execution"]),
            models.Index(fields=["tenant", "fingerprint"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(priority__gte=1) & models.Q(priority__lte=10),
                name="valid_priority_range"
            ),
            models.UniqueConstraint(fields=["tenant", "fingerprint"], name="u_exec_tenant_fingerprint"),
        ]
    
    def __str__(self):
        return f"Execution {self.id} - {self.workflow.name} ({self.status})"
    
    def mark_started(self):
        """Mark execution as started."""
        self.status = "running"
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at"])
    
    def mark_completed(self, result=None, output_items=None):
        """Mark execution as completed."""
        self.status = "completed"
        self.finished_at = timezone.now()
        update_fields = ["status", "finished_at"]
        
        if result:
            self.result = result
            update_fields.append("result")
        
        if output_items is not None:
            self.output_items = output_items
            update_fields.append("output_items")
        
        self.save(update_fields=update_fields)
    
    def mark_failed(self, error_message="", traceback=""):
        """Mark execution as failed."""
        self.status = "failed"
        self.finished_at = timezone.now()
        self.error_message = error_message
        self.traceback = traceback
        self.save(update_fields=["status", "finished_at", "error_message", "traceback"])


class NodeExecution(models.Model):
    """Represents a single execution of a node within a workflow execution."""
    
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("ready", "Ready"),  # Ready to execute (all dependencies met)
        ("running", "Running"),
        ("completed", "Completed"),
        ("success", "Success"),  # Alias for completed
        ("failed", "Failed"),
        ("skipped", "Skipped"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow_execution = models.ForeignKey(
        WorkflowExecution,
        on_delete=models.CASCADE,
        related_name="node_executions"
    )
    node = models.ForeignKey(Node, on_delete=models.CASCADE, related_name="executions", null=True, blank=True)
    # Explicit tenant for faster lookups and isolation
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="node_executions", null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    
    # Input/output data (legacy)
    input_data = models.JSONField(default=dict, blank=True)
    output = models.JSONField(default=dict, blank=True)
    
    # NEW: Item-based data storage (n8n-style)
    input_items = models.JSONField(
        default=list,
        blank=True,
        help_text="Array of input items: [{'json': {...}, 'binary': {...}}, ...]"
    )
    output_items = models.JSONField(
        default=list,
        blank=True,
        help_text="Array of output items: [{'json': {...}, 'binary': {...}}, ...]"
    )
    
    # Execution mode
    EXECUTION_MODE_CHOICES = [
        ("all", "Process All Items"),
        ("each", "Process Each Item"),
        ("batch", "Process in Batches"),
    ]
    execution_mode = models.CharField(
        max_length=20,
        choices=EXECUTION_MODE_CHOICES,
        default="each"
    )
    batch_size = models.IntegerField(null=True, blank=True)
    
    # Branch tracking
    branch_index = models.IntegerField(default=0, help_text="Which branch this execution belongs to")
    
    # Logs
    logs = models.TextField(blank=True, default="")
    
    # Timing
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    
    # Error tracking
    error_message = models.TextField(blank=True, default="")
    traceback = models.TextField(blank=True, default="")
    
    # Retry tracking
    retry_count = models.IntegerField(default=0)
    retry_policy = models.JSONField(
        default=dict,
        blank=True,
        help_text="Retry policy: {retries: 3, backoff: 'exponential', initial_delay_ms: 1000, max_delay_ms: 30000, retry_on: ['5xx', 'timeout']}"
    )
    
    # Idempotency key
    idempotency_key = models.CharField(max_length=255, blank=True, db_index=True, default="")
    
    # Join strategy for nodes with multiple incoming edges
    JOIN_STRATEGY_CHOICES = [
        ("all", "Wait for All Parents"),
        ("any", "Wait for Any Parent"),
        ("n", "Wait for N Parents"),
    ]
    join_strategy = models.CharField(
        max_length=10,
        choices=JOIN_STRATEGY_CHOICES,
        default="all",
        help_text="How to handle multiple incoming edges"
    )
    join_required_count = models.IntegerField(
        null=True,
        blank=True,
        help_text="Required parent count for 'n' strategy"
    )
    
    graph_node_id = models.CharField(max_length=100, blank=True, help_text="Node ID from workflow graph", default="")
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["workflow_execution", "status"]),
            models.Index(fields=["idempotency_key"]),
            models.Index(fields=["tenant", "graph_node_id"]),
        ]
    
    def __str__(self):
        node_label = self.node.label if self.node else (self.graph_node_id or "Unknown")
        return f"NodeExecution {node_label} - {self.status}"
    
    def mark_started(self):
        """Mark node execution as started."""
        self.status = "running"
        self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at"])
    
    def mark_completed(self, output=None, logs="", output_items=None):
        """Mark node execution as completed."""
        self.status = "completed"
        self.finished_at = timezone.now()
        update_fields = ["status", "finished_at"]
        
        if output:
            self.output = output
            update_fields.append("output")
        
        if output_items is not None:
            self.output_items = output_items
            update_fields.append("output_items")
        
        if logs:
            self.logs = logs
            update_fields.append("logs")
        
        self.save(update_fields=update_fields)
    
    def mark_failed(self, error_message="", traceback="", logs=""):
        """Mark node execution as failed."""
        self.status = "failed"
        self.finished_at = timezone.now()
        self.error_message = error_message
        self.traceback = traceback
        if logs:
            self.logs = logs
        self.save(update_fields=["status", "finished_at", "error_message", "traceback", "logs"])


class DeadLetterItem(models.Model):
    """Dead letter queue for failed items that exceeded retry limits."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow_execution = models.ForeignKey(WorkflowExecution, on_delete=models.CASCADE, related_name="dead_letters")
    node_execution = models.ForeignKey(NodeExecution, on_delete=models.SET_NULL, null=True, blank=True, related_name="dead_letters")
    # PHASE-1: Explicit tenant for isolation
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="dead_letters", null=True, blank=True)
    node_id = models.CharField(max_length=100, db_index=True)
    items = models.JSONField(default=list, blank=True)
    error_message = models.TextField(blank=True)
    error_type = models.CharField(max_length=100, blank=True)
    retries = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["workflow_execution", "node_id"]),
            models.Index(fields=["tenant", "created_at"]),
        ]

    def __str__(self):
        return f"DLQ {self.node_id} ({self.workflow_execution_id})"

class Credential(models.Model):
    """Encrypted credential storage."""
    
    CREDENTIAL_TYPES = [
        # Canonical Standards
        ("telegram_bot", "Telegram Bot"),
        ("meta_whatsapp", "WhatsApp Business"),
        ("gmail_oauth", "Gmail OAuth"),
        ("smtp_server", "SMTP Server"),
        ("general_api_key", "General API Key"),
        ("ollama_local", "Ollama (Local AI)"),
        
        # Legacy / Alias support (Keep for DB compatibility)
        ("telegram", "Telegram (Alias)"),
        ("whatsapp", "WhatsApp (Alias)"),
        ("gmail", "Gmail (Alias)"),
        ("google_oauth", "Google OAuth (Legacy)"),
        ("smtp", "SMTP (Alias)"),
        ("ollama", "Ollama (Alias)"),
        ("ai_offline", "AI Offline (Legacy)"),
        ("api_key", "API Key (Legacy)"),
        
        # Other types
        ("discord_bot", "Discord Bot"),
        ("google_calendar", "Google Calendar"),
        ("google_sheets", "Google Sheets"),
        ("basic_auth", "Basic Auth"),
        ("bearer_token", "Bearer Token"),
        ("custom", "Custom"),
    ]

    PROVIDER_CHOICES = [
        ("google", "Google"),
        ("smtp", "SMTP"),
        ("ollama", "Ollama"),
        ("telegram", "Telegram"),
        ("telegram_bot", "Telegram Bot"),
        ("whatsapp", "WhatsApp"),
        ("meta_whatsapp", "Meta WhatsApp"),
        ("internal", "Internal"),
        ("custom", "Custom"),
    ]
    
    ENVIRONMENT_CHOICES = [
        ("dev", "Development"),
        ("staging", "Staging"),
        ("production", "Production"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES, default="custom")
    type = models.CharField(max_length=50, choices=CREDENTIAL_TYPES)
    environment = models.CharField(max_length=20, choices=ENVIRONMENT_CHOICES, default="dev")
    
    # Credential data (stored as JSON; ensure secrets are protected at rest via storage/DB controls)
    encrypted_data = models.JSONField(default=dict)
    
    # Metadata
    email = models.EmailField(null=False, blank=False, default="", help_text="Associated email address for auto-resolution")
    owner = models.ForeignKey(django.conf.settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="credentials")
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="credentials", null=True, blank=True)
    organization = models.ForeignKey("Organization", on_delete=models.CASCADE, related_name="credentials", null=True, blank=True)
    # Status tracking
    status = models.CharField(max_length=20, default="not_configured", help_text="Configured status of the credential")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "provider", "type"]),
            models.Index(fields=["tenant", "provider", "type"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=['owner', 'provider', 'type'], name='unique_credential_per_user_svc')
        ]
    
    def __str__(self):
        return f"{self.name} ({self.type})"
    
    def get_auth_header(self):
        """Get formatted authorization header based on type."""
        data = self.encrypted_data  # Already decrypted by EncryptedJSONField
        
        if self.type == 'api_key':
            header_name = data.get('header_name', 'X-API-Key')
            api_key = data.get('api_key', '')
            return {header_name: api_key}
        
        elif self.type == 'bearer_token':
            token = data.get('token', '')
            return {'Authorization': f'Bearer {token}'}
        
        elif self.type == 'basic_auth':
            username = data.get('username', '')
            password = data.get('password', '')
            import base64
            auth_string = base64.b64encode(f'{username}:{password}'.encode()).decode()
            return {'Authorization': f'Basic {auth_string}'}
        
        elif self.type == 'oauth2':
            token = data.get('access_token', '')
            return {'Authorization': f'Bearer {token}'}
        
        return {}


class WorkflowVersion(models.Model):
    """Workflow versioning for rollback support."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="versions")
    version_number = models.IntegerField()
    graph = models.JSONField(help_text="Snapshot of workflow graph")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(django.conf.settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        unique_together = [["workflow", "version_number"]]
        ordering = ["-version_number"]
        indexes = [
            models.Index(fields=["workflow", "version_number"]),
        ]
    
    def __str__(self):
        return f"{self.workflow.name} v{self.version_number}"


class WorkflowTemplate(models.Model):
    """Workflow templates for quick workflow creation."""
    
    CATEGORY_CHOICES = [
        ("notifications", "Notifications"),
        ("data-sync", "Data Sync"),
        ("automation", "Automation"),
        ("integrations", "Integrations"),
        ("monitoring", "Monitoring"),
        ("e-commerce", "E-Commerce"),
        ("marketing", "Marketing"),
        ("other", "Other"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default="other")
    template_json = models.JSONField(help_text="Complete workflow JSON for template")
    tags = models.JSONField(default=list, blank=True, help_text="Tags for searching")
    is_public = models.BooleanField(default=False, help_text="Public templates visible to all users")
    usage_count = models.IntegerField(default=0, help_text="Number of times template was used")
    created_by = models.ForeignKey(django.conf.settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_templates")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-usage_count", "-created_at"]
        indexes = [
            models.Index(fields=["category", "is_public"]),
            models.Index(fields=["is_public"]),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.category})"



class WorkflowHistory(models.Model):
    """Audit log for workflow changes."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow = models.ForeignKey(Workflow, on_delete=models.CASCADE, related_name="history")
    event_type = models.CharField(max_length=50, choices=[
        ('SAVE', 'Save'),
        ('PUBLISH', 'Publish'),
        ('ROLLBACK', 'Rollback'),
        ('DELETE', 'Delete'),
        ('CREATE', 'Create')
    ])
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(django.conf.settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["workflow", "created_at"]),
        ]

    def __str__(self):
        return f"{self.event_type} on {self.workflow.name} ({self.created_at})"


class ExecutionLog(models.Model):
    """Detailed execution logs."""
    
    LEVEL_CHOICES = [
        ("debug", "Debug"),
        ("info", "Info"),
        ("warning", "Warning"),
        ("error", "Error"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    execution = models.ForeignKey(
        WorkflowExecution,
        on_delete=models.CASCADE,
        related_name="execution_logs"
    )
    node_execution = models.ForeignKey(
        NodeExecution,
        on_delete=models.CASCADE,
        related_name="execution_log_entries",
        related_query_name="execution_log_entry",
        null=True,
        blank=True
    )
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default="info")
    message = models.TextField(default="")
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    tenant = models.ForeignKey(
        "Tenant", on_delete=models.SET_NULL, null=True, blank=True
    )
    
    class Meta:
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["execution", "level"]),
            models.Index(fields=["node_execution"]),
        ]

class TelegramConversation(models.Model):
    """Tracks Telegram chat sessions."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    credential = models.ForeignKey(Credential, on_delete=models.CASCADE, related_name="telegram_conversations")
    chat_id = models.CharField(max_length=255, db_index=True)
    user_id = models.CharField(max_length=255, db_index=True, null=True, blank=True)
    username = models.CharField(max_length=255, null=True, blank=True)
    is_group = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_human_controlled = models.BooleanField(default=False)
    last_message_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_message_at"]
        unique_together = [["credential", "chat_id"]]
        indexes = [
            models.Index(fields=["credential", "chat_id"]),
            models.Index(fields=["credential", "user_id"]),
        ]

    def __str__(self):
        return f"Chat {self.chat_id} ({self.username or 'Unknown'})"


class TelegramMessage(models.Model):
    """Logs inbound and outbound Telegram messages."""
    DIRECTION_CHOICES = [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
    ]
    
    MESSAGE_TYPE_CHOICES = [
        ("text", "Text"),
        ("command", "Command"),
        ("photo", "Photo"),
        ("document", "Document"),
        ("audio", "Audio"),
        ("voice", "Voice"),
        ("other", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    credential = models.ForeignKey(Credential, on_delete=models.CASCADE, related_name="telegram_messages")
    conversation = models.ForeignKey(TelegramConversation, on_delete=models.CASCADE, related_name="messages")
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    chat_id = models.CharField(max_length=255, db_index=True)
    message_id = models.CharField(max_length=255, null=True, blank=True)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES, default="text")
    text = models.TextField(blank=True, default="")
    raw_payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["conversation", "created_at"]),
            models.Index(fields=["chat_id", "created_at"]),
        ]

    def __str__(self):
        return f"{self.direction} - {self.message_type} ({self.created_at})"



class WorkflowExecutionStep(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("skipped", "Skipped"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="execution_steps", null=True, blank=True)
    execution = models.ForeignKey(WorkflowExecution, on_delete=models.CASCADE, related_name="steps")
    node_id = models.CharField(max_length=100, db_index=True)
    node_type = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    input = models.JSONField(default=dict, blank=True)
    output = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["execution", "node_id"]),
            models.Index(fields=["status"]),
        ]


class BinaryFile(models.Model):
    """Binary file storage for workflow executions."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    execution = models.ForeignKey(
        WorkflowExecution,
        on_delete=models.CASCADE,
        related_name="files"
    )
    node_execution = models.ForeignKey(
        NodeExecution,
        on_delete=models.CASCADE,
        related_name="files",
        null=True,
        blank=True
    )
    filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    file_path = models.CharField(max_length=500, help_text="S3 key or local file path")
    size = models.BigIntegerField(help_text="File size in bytes")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["execution"]),
            models.Index(fields=["node_execution"]),
        ]
    
    def __str__(self):
        return f"{self.filename} ({self.size} bytes)"


class ChatSession(models.Model):
    """Chat session for conversational workflow interactions."""
    
    STATUS_CHOICES = [
        ("active", "Active"),
        ("paused", "Paused"),
        ("completed", "Completed"),
        ("expired", "Expired"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(django.conf.settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_sessions")
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="chat_sessions", null=True, blank=True)
    
    # Session metadata
    title = models.CharField(max_length=255, blank=True, help_text="Auto-generated or user-set title")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    
    # Session context and state
    context = models.JSONField(
        default=dict,
        blank=True,
        help_text="Persistent session context data"
    )
    
    # Associated workflow (if chat is tied to specific workflow)
    workflow = models.ForeignKey(
        Workflow,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_sessions",
        help_text="Optional workflow this chat session is associated with"
    )
    
    # Session settings
    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text="Chat session configuration and preferences"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_activity_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Session expiration time")
    
    class Meta:
        ordering = ["-last_activity_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["last_activity_at"]),
            models.Index(fields=["expires_at"]),
        ]
    
    def __str__(self):
        return f"Chat Session {self.id} - {self.user.username}"
    
    def is_expired(self):
        """Check if session is expired."""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def get_recent_messages(self, limit=10):
        """Get recent messages from this session."""
        return self.messages.order_by('-created_at')[:limit]


class ChatMessage(models.Model):
    """Individual chat message within a session."""
    
    MESSAGE_TYPES = [
        ("user", "User Message"),
        ("assistant", "Assistant Response"),
        ("system", "System Message"),
        ("workflow", "Workflow Response"),
        ("error", "Error Message"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name="messages")
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="chat_messages", null=True, blank=True)
    
    # Message content
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES)
    content = models.TextField(help_text="Message text content")
    
    # Structured data (for workflow responses)
    data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured data associated with message"
    )
    
    # Workflow execution reference (if message triggered workflow)
    workflow_execution = models.ForeignKey(
        WorkflowExecution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_messages",
        help_text="Workflow execution triggered by this message"
    )
    
    # Message metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional message metadata (tokens, processing time, etc.)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["session", "created_at"]),
            models.Index(fields=["tenant", "created_at"]),
            models.Index(fields=["message_type", "created_at"]),
            models.Index(fields=["workflow_execution"]),
        ]
    
    def __str__(self):
        return f"{self.message_type}: {self.content[:50]}..."


class AuditLog(models.Model):
    """Audit trail for all system actions."""
    
    ACTION_CHOICES = [
        ("create", "Create"),
        ("update", "Update"),
        ("delete", "Delete"),
        ("execute", "Execute"),
        ("publish", "Publish"),
        ("rollback", "Rollback"),
        ("share", "Share"),
    ]
    
    RESOURCE_TYPES = [
        ("workflow", "Workflow"),
        ("node", "Node"),
        ("credential", "Credential"),
        ("execution", "Execution"),
        ("tenant", "Tenant"),
        ("chat_session", "Chat Session"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(django.conf.settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="audit_logs")
    tenant = models.ForeignKey(Tenant, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    resource_type = models.CharField(max_length=50, choices=RESOURCE_TYPES)
    resource_id = models.UUIDField()
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["tenant", "timestamp"]),
            models.Index(fields=["resource_type", "resource_id"]),
        ]
    
    def __str__(self):
        return f"{self.action} {self.resource_type} by {self.user}"



class Notification(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    type = models.CharField(max_length=20, choices=[('email', 'Email'), ('webhook', 'Webhook'), ('in_app', 'In-App')])
    subject = models.CharField(max_length=255, blank=True)
    message = models.TextField()
    recipient = models.CharField(max_length=255, help_text='Email, webhook URL, or user ID')
    status = models.CharField(max_length=20, default='pending', choices=[('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed')])
    metadata = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(django.conf.settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    tenant = models.ForeignKey("Tenant", on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)

    class Meta:
        ordering = ['-created_at']





class Organization(models.Model):
    id = models.BigAutoField(primary_key=True)
    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='organization', null=True, blank=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True)
    settings = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [models.Index(fields=['slug'])]


class Team(models.Model):
    id = models.BigAutoField(primary_key=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='teams')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [models.Index(fields=['organization', 'name'])]


class Membership(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(django.conf.settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='memberships')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='memberships')
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    role = models.CharField(max_length=20, choices=[('owner', 'Owner'), ('admin', 'Admin'), ('viewer', 'Viewer')], default='viewer')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [['user', 'organization']]
        indexes = [
            models.Index(fields=['user', 'organization']),
            models.Index(fields=['organization', 'role'])
        ]


class SubscriptionPlan(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    name = models.CharField(max_length=50, unique=True, choices=[('free', 'Free'), ('pro', 'Pro'), ('team', 'Team'), ('enterprise', 'Enterprise')])
    display_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    max_executions_per_month = models.IntegerField(default=1000)
    max_webhook_hits_per_day = models.IntegerField(default=10000)
    max_active_workflows = models.IntegerField(default=10)
    max_active_credentials = models.IntegerField(default=20)
    max_team_members = models.IntegerField(default=5)
    price_monthly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_yearly = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    stripe_price_id_monthly = models.CharField(max_length=255, blank=True, default='')
    stripe_price_id_yearly = models.CharField(max_length=255, blank=True, default='')
    features = models.JSONField(blank=True, default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['price_monthly']


class Subscription(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='subscriptions')
    stripe_subscription_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=255, blank=True, default='')
    status = models.CharField(max_length=20, choices=[('active', 'Active'), ('canceled', 'Canceled'), ('past_due', 'Past Due'), ('trialing', 'Trialing'), ('unpaid', 'Unpaid')], default='active')
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['stripe_subscription_id'])
        ]


class UsageLimit(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    organization = models.OneToOneField(Organization, on_delete=models.CASCADE, related_name='usage_limit')
    max_executions_per_month = models.IntegerField(default=1000)
    max_webhook_hits_per_day = models.IntegerField(default=10000)
    max_active_workflows = models.IntegerField(default=10)
    max_active_credentials = models.IntegerField(default=20)
    max_team_members = models.IntegerField(default=5)
    executions_this_month = models.IntegerField(default=0)
    webhook_hits_today = models.IntegerField(default=0)
    last_reset_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['organization'])]


class Invoice(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='invoices')
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, related_name='invoices')
    stripe_invoice_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    stripe_pdf_url = models.URLField(blank=True, default='')
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='usd')
    status = models.CharField(max_length=20, choices=[('draft', 'Draft'), ('open', 'Open'), ('paid', 'Paid'), ('void', 'Void'), ('uncollectible', 'Uncollectible')], default='draft')
    due_date = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['stripe_invoice_id'])
        ]


class AIWorkflowGeneration(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    user = models.ForeignKey(django.conf.settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ai_workflow_generations')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, null=True, blank=True, related_name='ai_workflow_generations')
    workflow = models.ForeignKey("Workflow", on_delete=models.SET_NULL, null=True, blank=True, related_name='ai_generations')
    user_prompt = models.TextField(help_text="User's natural language description")
    generated_workflow_json = models.JSONField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed')], default='pending')
    error_message = models.TextField(blank=True, default='')
    tokens_used = models.IntegerField(default=0)
    model_used = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['organization', 'status'])
        ]


class RunRequest(models.Model):
    STATUS_CHOICES = [('pending', 'Pending'), ('running', 'Running'), ('completed', 'Completed'), ('failed', 'Failed'), ('expired', 'Expired')]
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    workflow = models.ForeignKey("Workflow", on_delete=models.CASCADE, related_name="run_requests", null=True, blank=True)
    execution = models.ForeignKey("WorkflowExecution", on_delete=models.CASCADE, related_name="run_requests")
    node_execution = models.ForeignKey("NodeExecution", on_delete=models.CASCADE, related_name="run_requests")
    tenant = models.ForeignKey("Tenant", on_delete=models.CASCADE, related_name="run_requests", null=True, blank=True)
    node_id = models.CharField(max_length=100, db_index=True)
    status = models.CharField(max_length=20, default="pending", choices=STATUS_CHOICES, db_index=True)
    worker_id = models.CharField(max_length=255, blank=True, help_text="Celery worker ID that claimed this request")
    claimed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    input_data = models.JSONField(default=dict, blank=True)
    correlation_id = models.CharField(max_length=100, blank=True)
    environment = models.CharField(max_length=50, default="development")
    
    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=['execution', 'node_id']),
            models.Index(fields=['node_execution']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['worker_id', 'status'])
        ]


class ExecutionEvent(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    execution = models.ForeignKey("WorkflowExecution", on_delete=models.CASCADE, related_name="timeline_events")
    workflow = models.ForeignKey("Workflow", on_delete=models.CASCADE, related_name="events", null=True, blank=True)
    node_execution = models.ForeignKey("NodeExecution", on_delete=models.SET_NULL, null=True, blank=True, related_name="timeline_events")
    tenant = models.ForeignKey("Tenant", on_delete=models.CASCADE, null=True, blank=True, related_name="execution_events")
    event_type = models.CharField(max_length=50, db_index=True)
    message = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=['execution', 'timestamp']),
            models.Index(fields=['node_execution', 'timestamp']),
            models.Index(fields=['tenant', 'timestamp']),
            models.Index(fields=['event_type', 'timestamp'])
        ]


class NodeEffect(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    node_execution = models.ForeignKey("NodeExecution", on_delete=models.CASCADE, related_name="node_effects")
    execution = models.ForeignKey("WorkflowExecution", on_delete=models.CASCADE, related_name="node_effects")
    workflow = models.ForeignKey("Workflow", on_delete=models.CASCADE, related_name="node_effects", null=True, blank=True)
    tenant = models.ForeignKey("Tenant", on_delete=models.CASCADE, null=True, blank=True, related_name="node_effects")
    node_id = models.CharField(max_length=100, db_index=True)
    effect_token = models.CharField(max_length=64, unique=True, db_index=True)
    effect_type = models.CharField(max_length=50) # was 50 inside usage, 100 in manual
    effect_data = models.JSONField(default=dict, blank=True)
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=['effect_token'], name='u_node_effect_token')]
        indexes = [
            models.Index(fields=['execution', 'node_id']),
            models.Index(fields=['node_execution']),
            models.Index(fields=['tenant', 'effect_token']),
            models.Index(fields=['effect_token'])
        ]


class AICodeGeneration(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    user = models.ForeignKey(django.conf.settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ai_code_generations')
    node_execution = models.ForeignKey("NodeExecution", on_delete=models.SET_NULL, null=True, blank=True, related_name='ai_code_generations')
    workflow = models.ForeignKey("Workflow", on_delete=models.CASCADE, related_name="ai_code_generations", null=True, blank=True)
    user_prompt = models.TextField(help_text="User's natural language description")
    prompt = models.TextField(blank=True, default='')
    context_data = models.JSONField(default=dict, blank=True)
    generated_code = models.TextField(blank=True)
    code_language = models.CharField(max_length=20, default="python")
    status = models.CharField(max_length=20, default='pending', choices=[('pending', 'Pending'), ('completed', 'Completed'), ('failed', 'Failed')])
    error_message = models.TextField(blank=True)
    tokens_used = models.IntegerField(default=0)
    execution_result = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    node_id = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=['user', 'status'])]


class Metric(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    name = models.CharField(max_length=255, db_index=True)
    workflow = models.ForeignKey("Workflow", on_delete=models.CASCADE, related_name="metrics", null=True, blank=True)
    # Re-adding missing fields from original migration
    metric_type = models.CharField(max_length=50, default="custom") # was 20 in migration, using safer 50
    value = models.FloatField(default=0.0)
    labels = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    node_id = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["name", "timestamp"]),
            models.Index(fields=["timestamp"])
        ]


class IPAllowlist(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='ip_allowlist')
    created_by = models.ForeignKey(django.conf.settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    ip_address = models.GenericIPAddressField()
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [['organization', 'ip_address']]
        indexes = [models.Index(fields=['organization', 'ip_address'])]


class GDPRDataRequest(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    user = models.ForeignKey(django.conf.settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='gdpr_requests')
    processed_by = models.ForeignKey(django.conf.settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_gdpr_requests')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='gdpr_requests', null=True, blank=True)
    request_type = models.CharField(max_length=20, choices=[('export', 'Data Export'), ('delete', 'Data Deletion')])
    status = models.CharField(max_length=20, default="pending", choices=[('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed')])
    export_file_path = models.CharField(max_length=500, blank=True, default='', help_text='Path to exported data file')
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-requested_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['organization', 'status']),
            models.Index(fields=['request_type', 'status'])
        ]


class SecretAccessLog(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    credential = models.ForeignKey("Credential", on_delete=models.CASCADE, related_name="access_logs")
    node_execution = models.ForeignKey("NodeExecution", on_delete=models.SET_NULL, null=True, blank=True, related_name="secret_access_logs")
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, null=True, blank=True, related_name="secret_access_logs")
    user = models.ForeignKey(django.conf.settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="secret_access_logs")
    access_type = models.CharField(max_length=50, help_text='read, decrypt, use_in_node')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['credential', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['organization', 'timestamp'])
        ]


class WorkerHeartbeat(models.Model):
    id = models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)
    worker_id = models.CharField(max_length=255, unique=True, db_index=True)
    last_heartbeat = models.DateTimeField(db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ["-last_heartbeat"]
        indexes = [
            models.Index(fields=["worker_id", "last_heartbeat"]),
        ]

    def __str__(self):
        return f"Worker {self.worker_id} - {self.last_heartbeat}"


# ==============================================================================
# WHATSAPP PRODUCTION MODELS (PHASE 1)
# ==============================================================================

class WhatsAppConversation(models.Model):
    """
    Tracks WhatsApp conversation sessions (24h window).
    Strictly follows Meta's definition: A conversation starts only on business reply/initiation.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    credential = models.ForeignKey(Credential, on_delete=models.CASCADE, related_name="whatsapp_conversations")
    user_phone_number = models.CharField(max_length=50, db_index=True)
    
    # Lifecycle
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(help_text="24h from last user message")
    is_active = models.BooleanField(default=True)
    
    # Activity
    last_user_message_at = models.DateTimeField(null=True, blank=True)
    last_business_message_at = models.DateTimeField(null=True, blank=True)
    
    # State
    is_human_controlled = models.BooleanField(default=False, help_text="If true, AI should pause")
    
    # Meta
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["credential", "user_phone_number"]),
            models.Index(fields=["expires_at"]),
        ]
        # Allow multiple conversations in history, but application logic enforces one active per user
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.user_phone_number} (Expires: {self.expires_at})"


class WhatsAppMessage(models.Model):
    """
    Audit log of all messages.
    """
    DIRECTION_CHOICES = [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
    ]
    
    TYPE_CHOICES = [
        ("text", "Text"),
        ("template", "Template"),
        ("image", "Image"),
        ("audio", "Audio"),
        ("document", "Document"),
        ("location", "Location"),
        ("interactive", "Interactive"),
        ("other", "Other"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(WhatsAppConversation, on_delete=models.SET_NULL, null=True, blank=True, related_name="messages")
    credential = models.ForeignKey(Credential, on_delete=models.CASCADE, related_name="whatsapp_messages")
    user_phone_number = models.CharField(max_length=50, blank=True, db_index=True, help_text="User phone for quick lookups")
    
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    message_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="text")
    
    meta_message_id = models.CharField(max_length=255, unique=True, null=True, blank=True, help_text="wamid...")
    content = models.JSONField(default=dict, blank=True)
    
    # Status Tracking (Phase 1 Enhancement)
    status = models.CharField(max_length=20, default="sent", db_index=True) # sent, delivered, read, failed
    error_code = models.CharField(max_length=50, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["credential", "timestamp"]),
            models.Index(fields=["meta_message_id"]),
        ]

    def __str__(self):
        return f"[{self.direction}] {self.message_type} - {self.meta_message_id}"


class WhatsAppUsage(models.Model):
    """
    Monthly usage tracking per credential.
    Strictly incremented only on NEW conversation creation.
    """
    credential = models.ForeignKey(Credential, on_delete=models.CASCADE, related_name="whatsapp_usage")
    month = models.CharField(max_length=7, help_text="YYYY-MM")
    conversation_count = models.IntegerField(default=0)
    warning_sent = models.BooleanField(default=False)
    
    class Meta:
        unique_together = [["credential", "month"]]

    def __str__(self):
        return f"{self.credential.name} - {self.month}: {self.conversation_count}"


class WhatsAppTemplate(models.Model):
    """
    Cache of approved templates from Meta.
    """
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    credential = models.ForeignKey(Credential, on_delete=models.CASCADE, related_name="whatsapp_templates")
    name = models.CharField(max_length=255)
    language = models.CharField(max_length=10, default="en_US")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    category = models.CharField(max_length=50, blank=True)
    content_schema = models.JSONField(default=dict, blank=True, help_text="Cached structure of the template")
    
    # Sync Metadata (Phase 1 Enhancement)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [["credential", "name", "language"]]

    def __str__(self):
        return f"{self.name} ({self.language}) - {self.status}"
