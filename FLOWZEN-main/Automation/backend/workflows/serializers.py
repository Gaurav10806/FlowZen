from rest_framework import serializers
from django.contrib.auth.models import User
from .utils.credential_validator import is_credential_configured
import logging
from .models import (
    Workflow, Node, WorkflowExecution, NodeExecution,
    Workflow, Node, WorkflowExecution, NodeExecution, WorkflowEdge,
    Credential, WorkflowVersion, ExecutionLog, BinaryFile,
    Tenant, Notification, WorkflowTemplate, UserProfile,
    ChatSession, ChatMessage,  # Added chat models
    # PHASE-2
    Organization, Team, Membership, UsageLimit, SubscriptionPlan, Subscription, Invoice,
    # PHASE-3
    AIWorkflowGeneration, AICodeGeneration, AIWorkflowOptimization,
    # PHASE-4
    Metric, SecretAccessLog, IPAllowlist, GDPRDataRequest
)

logger = logging.getLogger(__name__)



class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile model."""
    username = serializers.CharField(source='user.username')  # Remove read_only=True
    email = serializers.EmailField(source='user.email')

    class Meta:
        model = UserProfile
        fields = ['username', 'email', 'bio', 'avatar', 'avatar_url', 'theme', 'theme_config', 'notifications_enabled', 'updated_at']
        read_only_fields = ['updated_at']

    def update(self, instance, validated_data):
        # Handle nested user fields manually
        user_data = validated_data.pop('user', {})
        email = user_data.get('email')
        username = user_data.get('username')
        
        if email:
             instance.user.email = email
        if username:
             # Check if username exists for OTHER user
             if User.objects.filter(username=username).exclude(pk=instance.user.pk).exists():
                 raise serializers.ValidationError({"username": "This username is already taken."})
             instance.user.username = username
             
        if email or username:
            instance.user.save()
            
        return super().update(instance, validated_data)


class NodeSerializer(serializers.ModelSerializer):
    """Serializer for Node model."""
    
    class Meta:
        model = Node
        fields = [
            "id", "node_id", "label", "action_type", "config",
            "position", "max_retries", "retry_delay", "retry_backoff",
            "timeout", "on_error", "error_strategy", "fallback_output",
            "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def to_representation(self, instance):
        """Inject default values for missing fields from current schema."""
        ret = super().to_representation(instance)
        
        try:
            # Get latest schema for this node type
            from .nodes.registry import NODE_REGISTRY
            node_class = NODE_REGISTRY.get(instance.action_type)
            
            if node_class:
                schema = node_class.get_schema()
                config = ret.get('config', {}) or {}
                
                # Check properties for defaults
                properties = schema.get('properties', {})
                for key, prop in properties.items():
                    if key not in config and 'default' in prop:
                        config[key] = prop['default']
                        
                ret['config'] = config
        except Exception:
            # Fail silently on schema lookup to prevent read breaking
            pass
            
        return ret


class WorkflowSerializer(serializers.ModelSerializer):
    """Serializer for Workflow model."""
    
    nodes = NodeSerializer(many=True, read_only=True)
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    is_published = serializers.SerializerMethodField()
    last_execution = serializers.SerializerMethodField()
    success_rate = serializers.SerializerMethodField()
    
    class Meta:
        model = Workflow
        fields = [
            "id", "name", "description", "status", "graph",
            "webhook_secret", "webhook_enabled", "schedule",
            "owner", "owner_username", "nodes",
            "created_at", "updated_at", "is_published",
            "last_execution", "success_rate"
        ]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]

    def get_is_published(self, obj):
        return obj.status == "published"

    def get_last_execution(self, obj):
        """Get timestamp of most recent execution."""
        try:
            # Optimize: Use index on created_at
            last_exec = obj.executions.order_by('-created_at').first()
            return last_exec.created_at if last_exec else None
        except Exception:
            return None

    def get_success_rate(self, obj):
        """Calculate success rate percentage."""
        try:
            # Optimize: Cache this on specific intervals if scale increases
            total = obj.executions.count()
            if total == 0:
                return 0
            
            # Count success/completed
            success_count = obj.executions.filter(
                status__in=['completed', 'success']
            ).count()
            
            return int((success_count / total) * 100)
        except Exception:
            return 0
    
    def create(self, validated_data):
        """Create workflow and nodes from graph with enhanced error handling."""
        try:
            graph = validated_data.get("graph", {})
            nodes_data = graph.get("nodes", [])
            # Skip strict node validation during creation (allow empty workflows)
            self._validate_graph(graph, skip_node_count_validation=True, skip_edge_validation=True)
            
            # Set owner from request user
            validated_data["owner"] = self.context["request"].user
            
            # Ensure tenant is set
            if not validated_data.get("tenant"):
                # Create or get default tenant
                from .models import Tenant
                default_tenant, created = Tenant.objects.get_or_create(
                    slug='default',
                    defaults={
                        'name': 'Default Tenant'
                    }
                )
                validated_data["tenant"] = default_tenant
            
            # Remove nodes from graph for now (we'll create Node objects separately)
            workflow = Workflow.objects.create(**validated_data)
            
            # Create Node objects from graph nodes with safe field access
            for node_data in nodes_data:
                if isinstance(node_data, dict):
                    # Remove any problematic fields
                    node_data.pop("retry_count", None)
                    
                    # Safe field extraction with defaults
                    node_id = node_data.get("id", "")
                    if not node_id:
                        continue  # Skip nodes without IDs
                    
                    label = node_data.get("label") or node_data.get("name", "Untitled Node")
                    action_type = node_data.get("type") or node_data.get("action_type", "")
                    
                    # Map action types safely
                    type_map = {
                        "http-request": "http_request",
                        "http_request": "http_request",
                        "webhook-trigger": "webhook",
                        "webhook": "webhook",
                        "manual-trigger": "manual",
                        "manual_trigger": "manual",
                        "manual": "manual",
                        "trigger": "manual",
                        "email-send": "email",
                        "email_send": "email",
                        "email": "email",
                        "function": "code",
                        "code": "code",
                        "condition": "condition",
                        "if-condition": "condition",
                        "merge": "merge",
                        "delay": "delay",
                        "set_variables": "set_variables",
                        "subworkflow": "subworkflow",
                        "transform": "transform",
                        "loop": "loop",
                        "slack-message": "slack_message",
                        "discord-message": "discord_message",
                        "whatsapp-message": "whatsapp_message",
                        "telegram-message": "telegram_send",
                        "ai-agent": "ai_agent",
                        "ai_agent": "ai_agent",
                        "openai-gpt": "model_openai",
                    }
                    mapped_action_type = type_map.get(action_type, action_type or "code")
                    
                    # Ensure action_type is valid
                    valid_choices = {
                        "http_request","webhook","schedule","manual","email","code",
                        "condition","delay","merge","set_variables","subworkflow",
                        "transform","loop",
                        "telegram_trigger", "telegram_send", "ai_agent", "model_openai", "tool_websearch", "email_trigger", "whatsapp_trigger",
                        "slack_message", "discord_message", "whatsapp_message"
                    }
                    if mapped_action_type not in valid_choices:
                        mapped_action_type = "code"
                    
                    # Safe position extraction
                    position = node_data.get("position", {})
                    if not isinstance(position, dict):
                        position = {"x": node_data.get("x", 0), "y": node_data.get("y", 0)}
                    
                    try:
                        Node.objects.create(
                            workflow=workflow,
                            node_id=node_id,
                            label=label,
                            action_type=mapped_action_type,
                            config=node_data.get("config", {}),
                            position=position,
                            retry_backoff=node_data.get("retry_backoff", {}),
                            timeout=node_data.get("timeout"),
                        )
                    except Exception as e:
                        # Log node creation error but continue
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to create node {node_id}: {e}")
            
                        logger.warning(f"Failed to create node {node_id}: {e}")
            
            # Sync Edges
            edges_data = graph.get("edges", [])
            if edges_data:
                new_edges = []
                for edge in edges_data:
                    if not isinstance(edge, dict): continue
                    
                    src = edge.get("source") or edge.get("from")
                    tgt = edge.get("target") or edge.get("to")
                    
                    if src and tgt:
                        new_edges.append(WorkflowEdge(
                            workflow_id=workflow.id,
                            source_node_id=src,
                            target_node_id=tgt,
                            source_handle=edge.get("sourceHandle", "output"),
                            target_handle=edge.get("targetHandle", "input")
                        ))
                
                if new_edges:
                    WorkflowEdge.objects.bulk_create(new_edges, ignore_conflicts=True)
            
            return workflow
            
        except Exception as e:
            # Enhanced error handling for workflow creation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Workflow creation failed: {e}", exc_info=True)
            raise serializers.ValidationError(f"Failed to create workflow: {str(e)}")
    
    def update(self, instance, validated_data):
        """Update workflow and sync nodes from graph with enhanced error handling."""
        try:
            graph = validated_data.get("graph")
            
            if graph:
                # Allow saving empty/partial workflows during update
                self._validate_graph(graph, skip_node_count_validation=True)
                nodes_data = graph.get("nodes", [])
                
                # Update or create nodes with safe field handling
                existing_node_ids = set()
                for node_data in nodes_data:
                    if not isinstance(node_data, dict):
                        continue
                        
                    # Remove problematic fields
                    node_data.pop("retry_count", None)
                    
                    node_id = node_data.get("id", "")
                    if not node_id:
                        continue  # Skip malformed nodes without ids
                    
                    # Safe field extraction
                    label = node_data.get("label") or node_data.get("name", "Untitled Node")
                    action_type = node_data.get("type") or node_data.get("action_type", "")
                    
                    # Map and validate action type
                    type_map = {
                        "http-request": "http_request",
                        "http_request": "http_request",
                        "webhook-trigger": "webhook",
                        "webhook": "webhook",
                        "manual-trigger": "manual",
                        "manual_trigger": "manual",
                        "manual": "manual",
                        "trigger": "manual",
                        "email-send": "email",
                        "email_send": "email",
                        "email": "email",
                        "function": "code",
                        "code": "code",
                        "condition": "condition",
                        "if-condition": "condition",
                        "merge": "merge",
                        "delay": "delay",
                        "set_variables": "set_variables",
                        "subworkflow": "subworkflow",
                        "transform": "transform",
                        "loop": "loop",
                        "slack-message": "slack_message",
                        "discord-message": "discord_message",
                        "whatsapp-message": "whatsapp_message",
                        "telegram-message": "telegram_send",
                        "ai-agent": "ai_agent",
                        "ai_agent": "ai_agent",
                        "openai-gpt": "model_openai",
                    }
                    mapped_action_type = type_map.get(action_type, action_type or "code")
                    
                    # Ensure action_type is a valid choice
                    valid_choices = {
                        "http_request","webhook","schedule","manual","email","code",
                        "condition","delay","merge","set_variables","subworkflow",
                        "transform","loop",
                        "telegram_trigger", "telegram_send", "ai_agent", "model_openai", "tool_websearch", "email_trigger", "whatsapp_trigger",
                        "slack_message", "discord_message", "whatsapp_message"
                    }
                    if mapped_action_type not in valid_choices:
                        mapped_action_type = "code"
                    
                    # Safe position extraction
                    position = node_data.get("position", {})
                    if not isinstance(position, dict):
                        position = {"x": node_data.get("x", 0), "y": node_data.get("y", 0)}
                    
                    try:
                        node, created = Node.objects.update_or_create(
                            workflow=instance,
                            node_id=node_id,
                            defaults={
                                "label": label,
                                "action_type": mapped_action_type,
                                "config": node_data.get("config", {}),
                                "position": position,
                                "retry_backoff": node_data.get("retry_backoff", {}),
                                "timeout": node_data.get("timeout"),
                            }
                        )
                        existing_node_ids.add(node_id)
                    except Exception as e:
                        # Log node update error but continue
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to update node {node_id}: {e}")
                
                # Delete nodes not in graph anymore (with error handling)
                try:
                    instance.nodes.exclude(node_id__in=existing_node_ids).delete()
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to delete orphaned nodes: {e}")
                
                # Persist full graph including edges
                # Persist full graph including edges
                instance.graph = graph
                
                # Sync Edges (Strict Relation Persistence)
                edges = graph.get("edges", [])
                # Always clear separate edge table to ensure sync with graph JSON
                WorkflowEdge.objects.filter(workflow_id=instance.id).delete()
                
                new_db_edges = []
                for edge in edges:
                    if not isinstance(edge, dict): continue
                    
                    src = edge.get("source") or edge.get("from")
                    tgt = edge.get("target") or edge.get("to")
                    
                    if src and tgt:
                        new_db_edges.append(WorkflowEdge(
                            workflow_id=instance.id,
                            source_node_id=src,
                            target_node_id=tgt,
                            source_handle=edge.get("sourceHandle", "output"),
                            target_handle=edge.get("targetHandle", "input")
                        ))
                
                if new_db_edges:
                    try:
                        WorkflowEdge.objects.bulk_create(new_db_edges, ignore_conflicts=True)
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to sync edges to strict table: {e}")
            
            # Update other fields safely
            for attr, value in validated_data.items():
                if attr != "graph":
                    try:
                        setattr(instance, attr, value)
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to set attribute {attr}: {e}")
            
            instance.save()
            return instance
            
        except Exception as e:
            # Enhanced error handling for workflow update
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Workflow update failed: {e}", exc_info=True)
            raise serializers.ValidationError(f"Failed to update workflow: {str(e)}")

    def _validate_graph(self, graph, skip_node_count_validation=False, skip_edge_validation=False):
        """Enhanced server-side validation for graph integrity with detailed error messages and safe field access."""
        try:
            if not isinstance(graph, dict):
                raise serializers.ValidationError("Graph must be a valid object")
            
            nodes = graph.get("nodes", []) or []
            edges = graph.get("edges", []) or []
            
            # Handle different node formats safely
            if isinstance(nodes, dict):
                # Convert dict format to list format
                nodes = list(nodes.values())
            elif not isinstance(nodes, list):
                nodes = []
            
            if not nodes and not skip_node_count_validation:
                raise serializers.ValidationError("Workflow must contain at least one node")
            
            # Collect node IDs and validate node structure
            node_ids = set()
            valid_nodes = []
            
            for i, node in enumerate(nodes):
                # Skip invalid nodes instead of failing completely
                if not isinstance(node, dict):
                    print(f"Warning: Skipping invalid node {i}: not a dictionary")
                    continue
                
                node_id = node.get("id")
                if not node_id:
                    print(f"Warning: Skipping node {i}: missing 'id' field")
                    continue
                
                if node_id in node_ids:
                    print(f"Warning: Skipping duplicate node ID: {node_id}")
                    continue
                
                node_ids.add(node_id)
                valid_nodes.append(node)
                
                # Validate action_type with safe field access
                action_type = node.get("action_type") or node.get("type")
                if not action_type:
                    print(f"Warning: Node '{node_id}' missing action_type, will use default")
            
            # Update the graph with valid nodes only
            if valid_nodes:
                graph["nodes"] = valid_nodes
            elif not skip_node_count_validation:
                # If no valid nodes and we're not skipping validation, create a default manual trigger node
                print("Warning: No valid nodes found, creating default trigger node")
                default_node = {
                    "id": "default_trigger",
                    "type": "manual",
                    "action_type": "manual",
                    "label": "Manual Trigger",
                    "position": {"x": 100, "y": 100}
                }
                graph["nodes"] = [default_node]
            else:
                # If we're skipping validation (creation), allow empty nodes
                graph["nodes"] = []
            
            # Handle different edge formats safely
            if isinstance(edges, dict):
                # Convert dict format to list format
                edges = list(edges.values())
            elif not isinstance(edges, list):
                edges = []
            
            # Validate edges with safe field access (skip during creation)
            if not skip_edge_validation:
                for i, edge in enumerate(edges):
                    if not isinstance(edge, dict):
                        raise serializers.ValidationError(f"Edge {i} is not a valid object")
                    
                    # Support both frontend (source/target) and backend (from/to) formats
                    source = edge.get("from") or edge.get("source")
                    target = edge.get("to") or edge.get("target")
                    
                    if not source:
                        raise serializers.ValidationError(f"Edge {i} is missing source/from field")
                    if not target:
                        raise serializers.ValidationError(f"Edge {i} is missing target/to field")
                    
                    if source not in node_ids:
                        print(f"Warning: Skipping edge {i} with unknown source: '{source}'")
                        continue
                    if target not in node_ids:
                        print(f"Warning: Skipping edge {i} with unknown target: '{target}'")
                        continue
                    if source == target:
                        raise serializers.ValidationError(f"Edge {i} creates a self-loop (source == target): '{source}'")
            
            # Check for trigger nodes with safe field access
            trigger_types = {'webhook', 'schedule', 'manual', 'trigger', 'telegram_trigger', 'email_trigger', 'form_trigger', 'chat_trigger', 'whatsapp_trigger'}
            trigger_nodes = []
            for node in nodes:
                if isinstance(node, dict):
                    action_type = (node.get("action_type") or node.get("type", "")).lower()
                    if action_type in trigger_types:
                        trigger_nodes.append(node)
            
            if not trigger_nodes:
                # Warning but not error - some workflows might be triggered differently
                import logging
                logger = logging.getLogger(__name__)
                logger.warning("Workflow has no trigger nodes - execution may require manual triggering")
            
            # Validate email nodes have required configuration with safe field access
            email_types = {'email', 'email_send'}
            for node in nodes:
                if isinstance(node, dict):
                    action_type = (node.get("action_type") or node.get("type", "")).lower()
                    if action_type in email_types:
                        config = node.get("config", {})
                        node_id = node.get("id", "unknown")
                        
                        if not isinstance(config, dict):
                            config = {}
                        
                        if not config.get("to"):
                            raise serializers.ValidationError(f"Email node '{node_id}' is missing required 'to' field in config")
                        if not config.get("subject"):
                            raise serializers.ValidationError(f"Email node '{node_id}' is missing required 'subject' field in config")
                        if not config.get("from") and not config.get("sender"):
                            raise serializers.ValidationError(f"Email node '{node_id}' is missing required 'from' field in config")
            
            # Simple cycle detection (DFS) with safe field access
            visited = set()
            stack = set()
            
            def dfs(node_id):
                if node_id in stack:
                    return True  # Cycle detected
                if node_id in visited:
                    return False
                
                visited.add(node_id)
                stack.add(node_id)
                
                # Find all outgoing edges from this node
                for edge in edges:
                    if isinstance(edge, dict):
                        next_node = edge.get("to") or edge.get("target")
                        current_node = edge.get("from") or edge.get("source")
                        
                        if current_node == node_id and next_node:
                            if dfs(next_node):
                                return True
                
                stack.remove(node_id)
                return False
            
            # Check for cycles starting from each unvisited node
            for node_id in node_ids:
                if node_id not in visited:
                    if dfs(node_id):
                        raise serializers.ValidationError(f"Graph contains a cycle involving node '{node_id}'")
            
        except serializers.ValidationError:
            raise
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Graph validation error: {e}", exc_info=True)
            raise serializers.ValidationError(f"Invalid graph structure: {str(e)}")


class ExecutionLogSerializer(serializers.ModelSerializer):
    """Serializer for ExecutionLog model."""
    
    class Meta:
        model = ExecutionLog
        fields = [
            "id", "execution", "node_execution", "level", "message",
            "metadata", "timestamp"
        ]
        read_only_fields = ["id", "timestamp"]


class NodeExecutionSerializer(serializers.ModelSerializer):
    """Serializer for NodeExecution model."""
    
    node_label = serializers.CharField(source="node.label", read_only=True)
    node_id = serializers.CharField(source="node.node_id", read_only=True)
    node_type = serializers.CharField(source="node.action_type", read_only=True)
    node_action_type = serializers.CharField(source="node.action_type", read_only=True) # Keeping for backward compat
    # Use nested execution logs for rich debugging
    execution_log_entries = ExecutionLogSerializer(many=True, read_only=True)
    duration_ms = serializers.SerializerMethodField()
    
    class Meta:
        model = NodeExecution
        fields = [
            "id", "node", "node_label", "node_id", "node_type", "node_action_type",
            "status", "input_data", "output", "logs", "execution_log_entries",
            "started_at", "finished_at", "duration_ms", "error_message",
            "retry_count", "created_at", "traceback"
        ]
        read_only_fields = [
            "id", "status", "started_at", "finished_at", "duration_ms",
            "error_message", "retry_count", "created_at", "execution_log_entries"
        ]

    def get_duration_ms(self, obj):
        if obj.started_at and obj.finished_at:
            delta = obj.finished_at - obj.started_at
            return int(delta.total_seconds() * 1000)
        return None

class WorkflowExecutionSerializer(serializers.ModelSerializer):
    """Serializer for WorkflowExecution model."""
    
    workflow_name = serializers.CharField(source="workflow.name", read_only=True)
    # Order by created_at explicitly to ensure timeline is correct
    node_executions = NodeExecutionSerializer(many=True, read_only=True)
    duration_ms = serializers.SerializerMethodField()
    
    class Meta:
        model = WorkflowExecution
        fields = [
            "id", "workflow", "tenant", "workflow_name", "status",
            "input_payload", "result", "started_at", "finished_at", "duration_ms",
            "error_message", "triggered_by", "correlation_id",
            "node_executions", "created_at", "logs", "node_results", "root_context"
        ]
        read_only_fields = [
            "id", "tenant", "status", "started_at", "finished_at", "duration_ms",
            "error_message", "triggered_by", "correlation_id", "created_at",
            "logs", "node_results", "root_context"
        ]
        
    def get_duration_ms(self, obj):
        if obj.started_at and obj.finished_at:
            delta = obj.finished_at - obj.started_at
            return int(delta.total_seconds() * 1000)
        elif obj.started_at and obj.status == 'running':
            # Live duration for running workflows
            from django.utils import timezone
            delta = timezone.now() - obj.started_at
            return int(delta.total_seconds() * 1000)
        return None
    
    def create(self, validated_data):
        """Create execution and set tenant from workflow with enhanced error handling."""
        try:
            workflow = validated_data.get('workflow')
            if workflow:
                # Try to get tenant from workflow, create default if none exists
                if hasattr(workflow, 'tenant') and workflow.tenant:
                    validated_data['tenant'] = workflow.tenant
                else:
                    # Create or get default tenant for workflows without tenant
                    from .models import Tenant
                    try:
                        default_tenant, created = Tenant.objects.get_or_create(
                            slug='default',
                            defaults={
                                'name': 'Default Tenant'
                            }
                        )
                        validated_data['tenant'] = default_tenant
                        # Also update the workflow to have this tenant
                        workflow.tenant = default_tenant
                        workflow.save(update_fields=['tenant'])
                    except Exception as e:
                        # If tenant creation fails, continue without tenant (for backwards compatibility)
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to create default tenant: {e}")
                        validated_data.pop('tenant', None)
            
            return super().create(validated_data)
            
        except Exception as e:
            # Enhanced error handling for execution creation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Execution creation failed: {e}", exc_info=True)
            raise serializers.ValidationError(f"Failed to create execution: {str(e)}")


class WorkflowRunSerializer(serializers.Serializer):
    """Serializer for manual workflow run request."""
    
    input_payload = serializers.JSONField(default=dict, required=False)
    correlation_id = serializers.CharField(max_length=100, required=False, allow_blank=True)


class CredentialSerializer(serializers.ModelSerializer):
    """Serializer for Credential model."""
    
    client_id = serializers.SerializerMethodField()
    client_secret = serializers.SerializerMethodField()
    encrypted_data = serializers.JSONField(default=dict)
    provider = serializers.CharField(required=False, default="custom", allow_blank=True)

    class Meta:
        model = Credential
        fields = [
            "id", "name", "provider", "type", "environment", "encrypted_data",
            "owner", "tenant", "email", "status", "created_at", "updated_at",
            "client_id", "client_secret", "configured"
        ]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]

        extra_kwargs = {
            "environment": {"required": False}
        }

    def to_representation(self, instance):
        """Decrypt encrypted_data for the owner."""
        ret = super().to_representation(instance)
        request = self.context.get('request')
        
        # Only expose secrets to the owner
        if request and hasattr(instance, 'owner') and instance.owner == request.user:
            try:
                from .services.credential_encryption import get_encryption_service
                svc = get_encryption_service()
                if svc and instance.encrypted_data:
                    if isinstance(instance.encrypted_data, str):
                         # It's an encrypted string
                         ret['encrypted_data'] = svc.decrypt_credential_str(instance.encrypted_data)
                    elif isinstance(instance.encrypted_data, dict):
                         # Already a dict (rare, but possible if encryption failed or pending)
                         ret['encrypted_data'] = instance.encrypted_data
            except Exception as e:
                # Fallback to empty or raw if decryption fails to avoid 500
                print(f"Decryption failed in serializer: {e}")
                pass
                
        return ret

    def validate_encrypted_data(self, data):
        """
        Normalize credential keys safely based on type.
        """
        if isinstance(data, str):
            import json
            try:
                data = json.loads(data)
            except Exception:
                return {}

        if isinstance(data, dict):
            # Only apply WhatsApp normalization for WhatsApp credentials
            cred_type = self.initial_data.get('type', '')
            if cred_type in ('meta_whatsapp', 'whatsapp'):
                if "phone_id" in data and "phone_number_id" not in data:
                    data["phone_number_id"] = data.pop("phone_id")
                if "token" in data and "access_token" not in data:
                    data["access_token"] = data.pop("token")
                data.setdefault("phone_number_id", "")
                data.setdefault("access_token", "")

        import logging
        logging.getLogger(__name__).info(f"Saving credential encrypted_data keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
        return data

        return data

    def validate(self, data):
        """Strict validation for credential fields with type normalization."""
        from .constants.credential_types import normalize_credential_type
        print(f">>> [CREDENTIAL VALIDATE] Incoming Data: {data}")
        
        # FIX 0: Normalize type and provider
        if 'type' in data:
            data['type'] = normalize_credential_type(data['type'])
        if 'provider' in data:
            data['provider'] = normalize_credential_type(data['provider'])
        
        cred_type = data.get('type')
        encrypted_data = data.get('encrypted_data', {})

        if not isinstance(encrypted_data, dict):
            # If it's a string, we assume it's already encrypted and skip deep validation
            return data

        # FIX 1: Enforce schema
        if not data.get('name'):
             raise serializers.ValidationError({"success": False, "error": "Name is required"})
        
        if not cred_type:
             raise serializers.ValidationError({"success": False, "error": "Type is required"})

        errors = {}

        # Capture specific field errors based on type
        if cred_type == 'telegram_bot':
            if not encrypted_data.get('bot_token') and not encrypted_data.get('token'):
                # Try to extract from top-level
                token = data.get('bot_token') or data.get('token')
                if token:
                    encrypted_data['bot_token'] = token
                else:
                    errors['bot_token'] = "Telegram Bot Token is required"

        elif cred_type in ['gmail_oauth', 'google_calendar']:
            if not encrypted_data.get('client_id'):
                errors['client_id'] = "Client ID is required"
            if not encrypted_data.get('client_secret'):
                errors['client_secret'] = "Client Secret is required"
        
        elif cred_type == 'meta_whatsapp':
            if not encrypted_data.get('access_token'):
                errors['access_token'] = "WhatsApp Access Token is required"
            # Support both for validation, but prefer phone_number_id
            if not encrypted_data.get('phone_number_id') and not encrypted_data.get('phone_id'):
                errors['phone_number_id'] = "WhatsApp Phone Number ID is required"
            if not encrypted_data.get('verify_token'):
                errors['verify_token'] = "WhatsApp Verify Token is required"
        
        elif cred_type == 'smtp_server':
            if not encrypted_data.get('host'): errors['host'] = "SMTP Host is required"
            if not encrypted_data.get('port'): errors['port'] = "SMTP Port is required"
            if not encrypted_data.get('username'): errors['username'] = "SMTP Username is required"
            if not encrypted_data.get('password'): errors['password'] = "SMTP Password is required"
        
        elif cred_type == 'general_api_key':
            if not encrypted_data.get('api_key'):
                errors['api_key'] = "API Key is required"
        
        elif cred_type == 'ollama_local':
            if not encrypted_data.get('base_url'):
                errors['base_url'] = "Ollama Base URL is required"

        if errors:
            print(f">>> [CREDENTIAL VALIDATE] FAILED: {errors}")
            # Ensure unified error format requested by user
            raise serializers.ValidationError({"success": False, "error": next(iter(errors.values())), "errors": errors})

        return data

    def get_client_id(self, obj):
        """Return decrypted client_id for owner."""
        if obj.type in ['gmail', 'google_calendar', 'google_oauth', 'gmail_oauth'] and self.context.get('request') and obj.owner == self.context['request'].user:
            try:
                from .services.credential_encryption import get_encryption_service
                svc = get_encryption_service()
                data = {}
                if isinstance(obj.encrypted_data, str) and svc:
                    data = svc.decrypt_credential_str(obj.encrypted_data)
                elif isinstance(obj.encrypted_data, dict):
                    data = obj.encrypted_data
                return data.get('client_id', '')
            except Exception:
                pass
        return None

    def get_client_secret(self, obj):
        """Return decrypted client_secret for owner."""
        if obj.type in ['gmail', 'google_calendar', 'google_oauth', 'gmail_oauth'] and self.context.get('request') and obj.owner == self.context['request'].user:
            try:
                from .services.credential_encryption import get_encryption_service
                svc = get_encryption_service()
                data = {}
                if isinstance(obj.encrypted_data, str) and svc:
                    data = svc.decrypt_credential_str(obj.encrypted_data)
                elif isinstance(obj.encrypted_data, dict):
                    data = obj.encrypted_data
                return data.get('client_secret', '')
            except Exception:
                pass
        return None

    configured = serializers.SerializerMethodField()

    def get_configured(self, obj):
        """Returns True if the credential has all required fields for its type."""
        from .utils.credential_resolver import resolve_credential_data
        data = resolve_credential_data(obj)
        return is_credential_configured(obj.type, data)


class WorkflowVersionSerializer(serializers.ModelSerializer):
    """Serializer for WorkflowVersion model."""
    
    class Meta:
        model = WorkflowVersion
        fields = [
            "id", "workflow", "version_number", "graph", "name",
            "description", "created_at", "created_by"
        ]
        read_only_fields = ["id", "created_at"]





class BinaryFileSerializer(serializers.ModelSerializer):
    """Serializer for BinaryFile model."""
    
    class Meta:
        model = BinaryFile
        fields = [
            "id", "execution", "node_execution", "filename",
            "content_type", "file_path", "size", "metadata", "created_at"
        ]
        read_only_fields = ["id", "created_at"]


class WorkflowTemplateSerializer(serializers.ModelSerializer):
    """Serializer for WorkflowTemplate model."""
    
    class Meta:
        model = WorkflowTemplate
        fields = [
            "id", "name", "description", "category", "template_json",
            "tags", "is_public", "usage_count", "created_by", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "usage_count", "created_at", "updated_at"]


# ============================================
# CHAT SYSTEM SERIALIZERS
# ============================================

class ChatSessionSerializer(serializers.ModelSerializer):
    """Serializer for ChatSession model."""
    
    user_username = serializers.CharField(source="user.username", read_only=True)
    workflow_name = serializers.CharField(source="workflow.name", read_only=True)
    message_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatSession
        fields = [
            "id", "user", "user_username", "tenant", "title", "status",
            "context", "workflow", "workflow_name", "settings",
            "message_count", "created_at", "updated_at", "last_activity_at", "expires_at"
        ]
        read_only_fields = ["id", "user", "tenant", "created_at", "updated_at", "last_activity_at"]
    
    def get_message_count(self, obj):
        """Get total message count for the session."""
        return obj.messages.count()


class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for ChatMessage model."""
    
    session_title = serializers.CharField(source="session.title", read_only=True)
    workflow_execution_status = serializers.CharField(source="workflow_execution.status", read_only=True)
    
    class Meta:
        model = ChatMessage
        fields = [
            "id", "session", "session_title", "tenant", "message_type", "content",
            "data", "workflow_execution", "workflow_execution_status", "metadata", "created_at"
        ]
        read_only_fields = ["id", "tenant", "created_at"]


class ChatMessageCreateSerializer(serializers.Serializer):
    """Serializer for creating chat messages."""
    
    message = serializers.CharField(max_length=10000, help_text="Message content")
    message_type = serializers.ChoiceField(
        choices=ChatMessage.MESSAGE_TYPES,
        default='user',
        help_text="Type of message"
    )
    data = serializers.JSONField(default=dict, required=False, help_text="Additional structured data")


# ============================================
# PHASE-2: ORGANIZATIONS, TEAMS & ROLES
# ============================================

class OrganizationSerializer(serializers.ModelSerializer):
    """Serializer for Organization model."""
    
    class Meta:
        model = Organization
        fields = [
            "id", "name", "slug", "settings", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class TeamSerializer(serializers.ModelSerializer):
    """Serializer for Team model."""
    
    class Meta:
        model = Team
        fields = [
            "id", "organization", "name", "description", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class MembershipSerializer(serializers.ModelSerializer):
    """Serializer for Membership model."""
    
    user_username = serializers.CharField(source="user.username", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    
    class Meta:
        model = Membership
        fields = [
            "id", "user", "user_username", "organization", "organization_name",
            "team", "role", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class UsageLimitSerializer(serializers.ModelSerializer):
    """Serializer for UsageLimit model."""
    
    class Meta:
        model = UsageLimit
        fields = [
            "id", "organization", "max_executions_per_month", "max_webhook_hits_per_day",
            "max_active_workflows", "max_active_credentials", "max_team_members",
            "executions_this_month", "webhook_hits_today", "last_reset_at",
            "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Serializer for SubscriptionPlan model."""
    
    class Meta:
        model = SubscriptionPlan
        fields = [
            "id", "name", "display_name", "description",
            "max_executions_per_month", "max_webhook_hits_per_day",
            "max_active_workflows", "max_active_credentials", "max_team_members",
            "price_monthly", "price_yearly", "stripe_price_id_monthly", "stripe_price_id_yearly",
            "features", "is_active", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for Subscription model."""
    
    plan_name = serializers.CharField(source="plan.display_name", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    
    class Meta:
        model = Subscription
        fields = [
            "id", "organization", "organization_name", "plan", "plan_name",
            "stripe_subscription_id", "stripe_customer_id", "status",
            "current_period_start", "current_period_end", "cancel_at_period_end",
            "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class InvoiceSerializer(serializers.ModelSerializer):
    """Serializer for Invoice model."""
    
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    
    class Meta:
        model = Invoice
        fields = [
            "id", "organization", "organization_name", "subscription",
            "stripe_invoice_id", "stripe_pdf_url", "amount_due", "amount_paid",
            "currency", "status", "due_date", "paid_at", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


# ============================================
# PHASE-3: AI FEATURES
# ============================================

class AIWorkflowGenerationSerializer(serializers.ModelSerializer):
    """Serializer for AIWorkflowGeneration model."""
    
    class Meta:
        model = AIWorkflowGeneration
        fields = [
            "id", "user", "organization", "user_prompt", "generated_workflow_json",
            "workflow", "status", "error_message", "tokens_used", "model_used",
            "created_at", "updated_at"
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]


class AICodeGenerationSerializer(serializers.ModelSerializer):
    """Serializer for AICodeGeneration model."""
    
    class Meta:
        model = AICodeGeneration
        fields = [
            "id", "user", "node_execution", "user_prompt", "context_data",
            "generated_code", "code_language", "status", "error_message",
            "tokens_used", "execution_result", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]


class AIWorkflowOptimizationSerializer(serializers.ModelSerializer):
    """Serializer for AIWorkflowOptimization model."""
    
    class Meta:
        model = AIWorkflowOptimization
        fields = [
            "id", "workflow", "user", "optimization_type", "suggestion",
            "current_metrics", "predicted_improvement", "applied", "applied_at",
            "created_at"
        ]
        read_only_fields = ["id", "created_at"]


# ============================================
# PHASE-4: OBSERVABILITY & SECURITY
# ============================================

class MetricSerializer(serializers.ModelSerializer):
    """Serializer for Metric model."""
    
    class Meta:
        model = Metric
        fields = [
            "id", "name", "metric_type", "value", "labels", "timestamp"
        ]
        read_only_fields = ["id", "timestamp"]


class SecretAccessLogSerializer(serializers.ModelSerializer):
    """Serializer for SecretAccessLog model."""
    
    credential_name = serializers.CharField(source="credential.name", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)
    
    class Meta:
        model = SecretAccessLog
        fields = [
            "id", "user", "user_username", "credential", "credential_name",
            "organization", "access_type", "node_execution", "ip_address",
            "user_agent", "timestamp"
        ]
        read_only_fields = ["id", "timestamp"]


class IPAllowlistSerializer(serializers.ModelSerializer):
    """Serializer for IPAllowlist model."""
    
    class Meta:
        model = IPAllowlist
        fields = [
            "id", "organization", "ip_address", "cidr", "description",
            "is_active", "created_at", "created_by"
        ]
        read_only_fields = ["id", "created_at"]


class GDPRDataRequestSerializer(serializers.ModelSerializer):
    """Serializer for GDPRDataRequest model."""
    
    class Meta:
        model = GDPRDataRequest
        fields = [
            "id", "user", "organization", "request_type", "status",
            "export_file_path", "requested_at", "completed_at", "processed_by"
        ]
        read_only_fields = ["id", "requested_at"]
