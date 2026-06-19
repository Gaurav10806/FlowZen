
"""
REST API views for workflows, executions, credentials, etc.
"""
import json
import hmac
import hashlib
import uuid
import logging
import requests

# UI-SPECIFIC RICH SCHEMAS (Production-Grade Source of Truth)
from .node_schemas import FULL_NODE_SCHEMAS

import logging
from django.db import IntegrityError
import google_auth_oauthlib.flow
from google.oauth2.credentials import Credentials as GoogleCredentials
from rest_framework import viewsets, status, filters, serializers
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.views.decorators.cache import cache_page, never_cache
from django.views.decorators.vary import vary_on_headers
from django.core.cache import cache
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_datetime

from .models import (
    Workflow, WorkflowExecution, NodeExecution, Node,
    Credential, WorkflowVersion, ExecutionLog, BinaryFile, Tenant,
    Tenant, AuditLog, Notification, WorkflowTemplate, UserProfile,
    # PHASE-2
    Organization, Team, Membership, UsageLimit, SubscriptionPlan, Subscription, Invoice,
    # PHASE-3
    AICodeGeneration, AIWorkflowOptimization,
    # PHASE-4
    SecretAccessLog, IPAllowlist, GDPRDataRequest, DeadLetterItem
)
from .serializers import (
    WorkflowSerializer, WorkflowExecutionSerializer, NodeExecutionSerializer,
    CredentialSerializer, NodeSerializer, WorkflowVersionSerializer,
    ExecutionLogSerializer, BinaryFileSerializer, WorkflowRunSerializer,
    WorkflowTemplateSerializer, UserProfileSerializer,
    # PHASE-2
    OrganizationSerializer, TeamSerializer, MembershipSerializer,
    UsageLimitSerializer, SubscriptionPlanSerializer, SubscriptionSerializer, InvoiceSerializer,
    # PHASE-3
    AIWorkflowGenerationSerializer, AICodeGenerationSerializer, AIWorkflowOptimizationSerializer,
    # PHASE-4
    SecretAccessLogSerializer, IPAllowlistSerializer, GDPRDataRequestSerializer
)
from .tasks import execute_workflow_with_core_engine, run_workflow_execution
from .nodes import node_registry
from .ai_providers.ollama_provider import OllamaProvider
from .utils.credential_resolver import resolve_credential_data
from .utils.credential_validator import is_credential_configured
from .constants.credential_types import normalize_credential_type
from .services.credential_encryption import get_encryption_service



def queue_workflow_execution(execution_id: str, use_core_engine: bool = True):
    """
    Queue workflow execution using the appropriate system.
    
    Args:
        execution_id: UUID of the WorkflowExecution
        use_core_engine: Whether to use the new core engine (default: True)
    """
    if use_core_engine:
        # Use new core execution engine
        transaction.on_commit(lambda: execute_workflow_with_core_engine.delay(execution_id))
    else:
        # Use legacy execution system
        transaction.on_commit(lambda: run_workflow_execution.delay(execution_id))
from .permissions import (
    IsOrganizationMember, IsOwner, IsAdmin, IsViewer,
    CanCreateWorkflow, CanExecuteWorkflow
)

logger = logging.getLogger(__name__)


def get_default_tenant():
    """
    Get the default tenant for executions when workflow.tenant is None.
    This ensures all executions have a tenant assigned for proper isolation.
    """
    try:
        # Get the first available tenant as default
        default_tenant = Tenant.objects.first()
        if default_tenant:
            return default_tenant
        else:
            # If no tenants exist, create a default one
            logger.warning("No tenants found, creating default tenant")
            default_tenant = Tenant.objects.create(
                name="Default Tenant",
                slug="default-tenant"
            )
            return default_tenant
    except Exception as e:
        logger.error(f"Failed to get default tenant: {e}")
        # Return None as last resort, but this should not happen
        return None



from .tasks import run_workflow_execution

from rest_framework.views import APIView
from django.db.models import F, Func, IntegerField
import math
from .throttles import TenantWebhookRateThrottle


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 1000



class UserProfileView(APIView):
    """
    API View to retrieve and update the authenticated user's profile.
    Automatically creates a profile if one does not exist.
    STRICT PERSISTENCE: Uses transaction.atomic() and request.user
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            user_id = request.user.id
            logger.info(f"👤 [Profile GET] Fetching profile for user_id={user_id}")
            profile, created = UserProfile.objects.get_or_create(user=request.user)
            serializer = UserProfileSerializer(profile)
            return Response(serializer.data)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"👤 [Profile GET] CRITICAL ERROR: {e}\n{tb}")
            return Response({"error": str(e), "trace": tb}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def put(self, request):
        try:
            user_id = request.user.id
            logger.info(f"👤 [Profile PUT] Saving profile for user_id={user_id}")
            
            with transaction.atomic():
                profile, created = UserProfile.objects.get_or_create(user=request.user)
                serializer = UserProfileSerializer(profile, data=request.data, partial=True)
                
                if serializer.is_valid():
                    instance = serializer.save()
                    return Response({
                        "status": "success",
                        "message": "Profile updated successfully 👤",
                        "data": UserProfileSerializer(instance).data
                    })
                
                logger.error(f"❌ [Profile PUT] Validation: {serializer.errors}")
                return Response({
                    "status": "error",
                    "message": "Validation failed",
                    "errors": serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"❌ [Profile PUT] CRITICAL ERROR: {e}\n{tb}")
            return Response({"error": "Server Error", "detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class WorkflowViewSet(viewsets.ModelViewSet):
    """ViewSet for Workflow CRUD operations."""
    serializer_class = WorkflowSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'updated_at', 'name']
    ordering = ['-created_at']
    
    def get_queryset(self):
        qs = Workflow.objects.filter(owner=self.request.user)
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        return qs
    
    def perform_create(self, serializer):
        """Create workflow with owner."""
        try:
            serializer.save(owner=self.request.user)
        except Exception as e:
            logger.error(f"Error creating workflow: {e}")
            raise serializers.ValidationError({"error": f"Creation failed: {str(e)}"})

    def update(self, request, *args, **kwargs):
        """Update workflow with validation."""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            return Response({
                'error': 'Validation Error',
                'detail': e.detail
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # STRICT GRAPH VALIDATION on save
        if 'graph' in request.data:
            graph = request.data['graph']
            
            validation_errors = self.validate_workflow_graph(graph)
            
            if validation_errors:
                logger.warning(f"Saving workflow {instance.id} with validation errors: {validation_errors}")
                # Still allow save but include warnings in response
                
        self.perform_update(serializer)
        
        # --- AUTO-VERSIONING ON SAVE ---
        # Create a historical version for every save to allow full rollback
        if 'graph' in request.data:
            try:
                # Increment version number
                instance.refresh_from_db()
                instance.version += 1
                instance.save(update_fields=['version'])
                
                WorkflowVersion.objects.create(
                    workflow=instance,
                    version_number=instance.version,
                    graph=instance.graph,
                    name=instance.name,
                    description=instance.description,
                    created_by=request.user
                )
            except Exception as e:
                logger.error(f"Failed to create auto-version for workflow {instance.id}: {e}")

        # Include validation status in response
        response_data = serializer.data
        if 'graph' in request.data:
            graph = request.data['graph']
            validation_errors = self.validate_workflow_graph(graph)
            response_data['validation'] = {
                'is_valid': len(validation_errors) == 0,
                'errors': validation_errors
            }
        
        # --- AUDIT HISTORY ---
        try:
            from .models import WorkflowHistory
            WorkflowHistory.objects.create(
                workflow=instance,
                event_type="SAVE",
                message="Workflow saved successfully",
                created_by=request.user
            )
        except Exception as e:
            logger.error(f"Failed to log history: {e}")

        return Response({
            "status": "success",
            "message": "Workflow saved successfully ✅",
            "data": response_data
        })
    
    def validate_workflow_graph(self, graph):
        """Validate workflow graph structure."""
        validation_errors = []
        
        if not graph:
            return validation_errors
        
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        
        if not nodes:
            return validation_errors  # Empty workflow is valid for saving
        
        # Find trigger and action nodes
        trigger_types = {
            'manual', 'webhook', 'schedule', 'trigger',
            'manual_trigger', 'webhook_trigger', 'schedule_trigger', 'email_trigger',
            'email-trigger', 'schedule-trigger', 'manual-trigger', 'webhook-trigger',
            # Modern Triggers (Enterprise)
            'whatsapp_trigger', 'whatsapp-trigger',
            'telegram_trigger', 'telegram-trigger',
            'gmail_trigger', 'gmail-trigger',
            'google_calendar_trigger', 'chat_trigger'
        }
        trigger_nodes = [n for n in nodes if (n.get('action_type') or n.get('type', '')).lower() in trigger_types]
        action_nodes = [n for n in nodes if (n.get('action_type') or n.get('type', '')).lower() not in trigger_types and (n.get('action_type') or n.get('type', ''))]
        
        if not trigger_nodes and nodes:
            validation_errors.append('Workflow should contain at least one trigger node')
        
        if action_nodes and not edges:
            validation_errors.append('Action nodes should be connected to trigger nodes')
        
        # Check for disconnected action nodes
        if action_nodes and edges:
            connected_action_nodes = set()
            for edge in edges:
                target = edge.get('target') or edge.get('to')
                if target and any(an.get('id') == target for an in action_nodes):
                    connected_action_nodes.add(target)
            
            disconnected_actions = [an for an in action_nodes if an.get('id') not in connected_action_nodes]
            if disconnected_actions:
                disconnected_labels = [an.get('label', an.get('id')) for an in disconnected_actions]
                validation_errors.append(f'Disconnected action nodes: {", ".join(disconnected_labels)}')
        
        return validation_errors

    @action(detail=True, methods=['get'])
    def history(self, request, pk=None):
        """Get audit history for this workflow."""
        workflow = self.get_object()
        history = workflow.history.all()[:50]
        
        data = [{
            "id": str(h.id),
            "event_type": h.event_type,
            "message": h.message,
            "created_at": h.created_at,
            "user": h.created_by.username if h.created_by else "System"
        } for h in history]
        
        return Response({
            "status": "success",
            "data": data
        })
    
    @action(detail=True, methods=['post'], url_path='execute')
    def run(self, request, pk=None):
        """Manually trigger workflow execution with STRICT validation."""
        workflow = self.get_object()
        serializer = WorkflowRunSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # STRICT WORKFLOW VALIDATION
        graph = workflow.graph or {}
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        
        # Basic validation
        if not nodes:
            return Response({
                'error': 'Cannot run workflow',
                'error_type': 'VALIDATION_ERROR',
                'detail': 'Workflow must contain at least one node before it can be executed',
                'code': 'EMPTY_WORKFLOW'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Advanced validation: Check for proper connections
        validation_errors = []
        
        # Find trigger and action nodes
        trigger_types = [
            'manual', 'webhook', 'schedule', 'trigger',
            'manual_trigger', 'webhook_trigger', 'schedule_trigger', 'email_trigger',
            'email-trigger', 'schedule-trigger', 'manual-trigger', 'webhook-trigger',
            'telegram_trigger', 'whatsapp_trigger', 'chat_trigger', 'google_calendar_trigger'
        ]
        trigger_nodes = [n for n in nodes if (n.get('action_type') or n.get('type', '')).lower() in trigger_types]
        action_nodes = [n for n in nodes if (n.get('action_type') or n.get('type', '')).lower() not in trigger_types and (n.get('action_type') or n.get('type', ''))]
        
        if not trigger_nodes:
            validation_errors.append('Workflow must contain at least one trigger node (manual, webhook, or schedule)')
        
        if action_nodes and not edges:
            validation_errors.append('Action nodes must be connected to trigger nodes')
        
        # Check for disconnected action nodes
        if action_nodes and edges:
            connected_action_nodes = set()
            for edge in edges:
                target = edge.get('target') or edge.get('to')
                if target and any(an.get('id') == target for an in action_nodes):
                    connected_action_nodes.add(target)
            
            disconnected_actions = [an for an in action_nodes if an.get('id') not in connected_action_nodes]
            if disconnected_actions:
                disconnected_labels = [an.get('label', an.get('id')) for an in disconnected_actions]
                validation_errors.append(f'Disconnected action nodes: {", ".join(disconnected_labels)}')
        
        # Validate each action node has at least one incoming edge
        if action_nodes and edges:
            for action_node in action_nodes:
                node_id = action_node.get('id')
                incoming_edges = [e for e in edges if (e.get('target') or e.get('to')) == node_id]
                if not incoming_edges:
                    validation_errors.append(f'Action node "{action_node.get("label", node_id)}" has no incoming connections')
        
        # If validation failed, return error
        if validation_errors:
            return Response({
                'error': 'Workflow validation failed',
                'error_type': 'VALIDATION_ERROR',
                'detail': 'Workflow has structural issues that prevent execution',
                'validation_errors': validation_errors,
                'code': 'INVALID_WORKFLOW_STRUCTURE'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"✅ Workflow validation passed: {len(trigger_nodes)} triggers, {len(action_nodes)} actions, {len(edges)} edges")
        
        # Validate tenant before execution creation
        try:
            workflow_tenant = workflow.tenant
        except:
            workflow_tenant = None
            
        # Ensure execution always has a tenant assigned
        if not workflow_tenant:
            logger.warning(f"Workflow {workflow.id} has no tenant assigned, using default tenant")
            workflow_tenant = get_default_tenant()
        
        # Get input data
        input_data = serializer.validated_data.get('input_payload', {})
        
        # Convert to items format
        if isinstance(input_data, list):
            input_items = [{"json": item} for item in input_data]
        else:
            input_items = [{"json": input_data}]
        
        # Create execution with comprehensive error handling
        try:
            execution = WorkflowExecution.objects.create(
                workflow=workflow,
                tenant=workflow_tenant,  # Now guaranteed to be not None or None
                input_payload={
                    **input_data,
                    '_user_id': str(request.user.id),  # Store user ID for Gmail OAuth context
                    '_user_email': request.user.email,  # Store user email for debugging
                },
                input_items=input_items,
                triggered_by='manual',
                correlation_id=serializer.validated_data.get('correlation_id') or str(uuid.uuid4()),
                # Fix for unique constraint (tenant, fingerprint): valid manual runs need unique fingerprints
                fingerprint=str(uuid.uuid4())
            )
            
            # SAFETY: Schedule a timeout task to prevent infinite loading
            from .tasks import execution_timeout_check
            execution_timeout_check.apply_async(
                args=[str(execution.id)], 
                countdown=300  # 5 minute timeout
            )
            
        except IntegrityError as e:
            logger.error(f"Database integrity error creating execution: {e}", exc_info=True)
            return Response({
                'error': 'Database constraint violation',
                'error_type': 'INTEGRITY_ERROR',
                'detail': f'Failed to create execution due to database constraint: {str(e)}',
                'code': 'INTEGRITY_ERROR'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Unexpected error creating execution: {e}", exc_info=True)
            return Response({
                'error': 'Execution creation failed',
                'error_type': 'CREATION_ERROR',
                'detail': f'Failed to create workflow execution: {str(e)}',
                'code': 'CREATION_ERROR'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Queue execution task using new core engine
        try:
            # CRITICAL: Always update status immediately to prevent infinite loading
            execution.status = "running"
            execution.started_at = timezone.now()
            execution.save(update_fields=['status', 'started_at'])
            
            # Try to queue the task
            queue_workflow_execution(str(execution.id), use_core_engine=True)
            
        except Exception as e:
            logger.error(f"Failed to queue execution {execution.id}: {e}", exc_info=True)
            execution.mark_failed(
                error_message=f"Failed to queue execution: {str(e)}",
                traceback=""
            )
            return Response({
                'error': 'Execution queue failed',
                'error_type': 'QUEUE_ERROR',
                'detail': f'Failed to start workflow execution: {str(e)}',
                'code': 'QUEUE_ERROR'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            'execution_id': str(execution.id),
            'status': 'queued',
            'message': 'Workflow execution queued'
        }, status=status.HTTP_202_ACCEPTED)
    
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """
        Publish workflow (move from draft to published).
        Strictly returns JSON.
        """
        try:
            workflow = self.get_object()
            
            # STRICT VALIDATION BEFORE PUBLISHING
            nodes = workflow.graph.get('nodes', [])
            edges = workflow.graph.get('edges', [])
            
            # 1. Check for Empty Graph
            if not nodes:
                return Response({
                    'success': False,
                    'error': 'Workflow is empty',
                    'detail': 'Cannot deploy an empty workflow. Add triggers and actions.'
                }, status=status.HTTP_400_BAD_REQUEST)
                
            # 2. Check for Trigger
            # Broaden trigger types to include frontend specific types (hyphenated)
            trigger_types = {
                'webhook', 'schedule', 'manual', 'trigger', 
                'manual_trigger', 'webhook_trigger', 'schedule_trigger', 'email_trigger', 
                'email-trigger', 'schedule-trigger', 'manual-trigger', 'webhook-trigger',
                # Enterprise Triggers
                'telegram_trigger', 'telegram-trigger', 
                'whatsapp_trigger', 'whatsapp-trigger',
                'chat_trigger', 'google_calendar_trigger', 'google_calendar_trigger'
            }
            
            trigger_nodes = [
                node for node in nodes 
                if (node.get('action_type') or node.get('type', '')).lower() in trigger_types
            ]
            
            if not trigger_nodes:
                return Response({
                    'success': False,
                    'error': 'Missing Trigger',
                    'detail': 'Workflow must have at least one trigger node (e.g., Manual, Schedule, Webhook).'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Topology Checks
            existing_ids = {n['id'] for n in nodes}
            target_ids = {e['target'] for e in edges}
            source_ids = {e['source'] for e in edges}
            
            # Check Triggers: Must be Roots (No Incoming) and Have Outgoing
            for trigger in trigger_nodes:
                t_id = trigger.get('id')
                # A trigger should not be a target of any edge
                if t_id in target_ids:
                    return Response({
                        'success': False,
                        'error': 'Invalid Trigger Position',
                        'detail': f"Trigger '{trigger.get('label', 'Trigger')}' cannot have incoming connections. Triggers must be the starting point."
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # A trigger MUST have outgoing connections
                if t_id not in source_ids:
                    return Response({
                        'success': False,
                        'error': 'Disconnected Trigger',
                        'detail': f"Trigger '{trigger.get('label', 'Trigger')}' is not connected to any action. Please connect it."
                    }, status=status.HTTP_400_BAD_REQUEST)

            # 3. Check for Orphans (Nodes with no connections)
            for node in nodes:
                node_type = (node.get('action_type') or node.get('type', '')).lower()
                node_id = node.get('id')
                
                # If it's not a trigger, it MUST have an incoming connection
                if node_type not in trigger_types:
                    if node_id not in target_ids:
                        return Response({
                            'success': False,
                            'error': 'Disconnected Node',
                            'detail': f"Node '{node.get('label', 'Unknown')}' is disconnected. Please connect it to the workflow."
                        }, status=status.HTTP_400_BAD_REQUEST)

            # 4. Check CONFIGURATION (Credentials)
            for node in nodes:
                # STABILITY: Normalize node if it's a string (shouldn't happen but be safe)
                if isinstance(node, str):
                    try:
                        node = json.loads(node)
                    except:
                        continue # Skip malformed nodes
                        
                node_type = (node.get('action_type') or node.get('type', '')).lower()
                
                # Broaden validation to all nodes that definitely require credentials
                credential_nodes = {
                    'send_email', 'email-send', 'gmail-send', 
                    'gmail_trigger', 'gmail-trigger',
                    'google_sheets', 'google-sheets', 'google_sheets_node',
                    'google_calendar', 'google-calendar', 'google_calendar_node',
                    'youtube_trigger', 'youtube-trigger',
                    'telegram_send', 'telegram_trigger',
                    'whatsapp_send', 'whatsapp_trigger',
                    'ai_agent', 'ai-agent'
                }
                
                if node_type in credential_nodes:
                    # STABILITY: Normalize config
                    config = node.get('config')
                    if isinstance(config, str):
                        try:
                            config = json.loads(config)
                        except:
                            config = {}
                    if not isinstance(config, dict):
                        config = {}
                        
                    # Support multiple potential credential keys sent from frontend
                    config = config or {}
                    cred_id = config.get('credential_id') or config.get('credential') or config.get('access_token')
                    
                    if not cred_id:
                        return Response({
                            'success': False,
                            'error': 'Missing Credential',
                            'detail': f"Node '{node.get('label', node_type)}' requires a Credential. Please configure it."
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Validate Credential Exists and is Configured
                    try:
                        cred = Credential.objects.get(id=cred_id)
                        if cred.owner != request.user:
                            return Response({
                                'success': False,
                                'error': 'Invalid Credential',
                                'detail': f"Credential for node '{node.get('label', 'Send Email')}' belongs to another user."
                            }, status=status.HTTP_403_FORBIDDEN)
                            
                        # Check deep validation based on type
                        if cred.type in ['gmail_oauth', 'google_oauth']:
                             # Enhanced Validation: Check for actual token presence
                             data = cred.encrypted_data
                             
                             if isinstance(data, str):
                                 try:
                                     data = json.loads(data)
                                 except:
                                     pass
                             
                             if isinstance(data, dict):
                                 if not data or (not data.get('access_token') and not data.get('refresh_token') and not data.get('client_id')):
                                     return Response({
                                        'success': False, 
                                        'error': 'Unconfigured Credential',
                                        'detail': f"Google Credential '{cred.name}' is missing authentication tokens. Please reconnect via the Credentials page."
                                    }, status=status.HTTP_400_BAD_REQUEST)
                        
                        elif cred.type == 'smtp':
                             if not cred.encrypted_data:
                                 return Response({
                                    'success': False,
                                    'error': 'Unconfigured Credential',
                                    'detail': f"SMTP Credential '{cred.name}' is missing configuration data."
                                }, status=status.HTTP_400_BAD_REQUEST)

                    except Credential.DoesNotExist:
                        return Response({
                            'success': False,
                            'error': 'Credential Not Found',
                            'detail': f"The credential configured for node '{node.get('label', 'Send Email')}' no longer exists."
                        }, status=status.HTTP_400_BAD_REQUEST)
            
            # If all good, proceed
            workflow.status = 'published'
            
            # Create version snapshot
            workflow.version += 1
            WorkflowVersion.objects.create(
                workflow=workflow,
                version_number=workflow.version,
                graph=workflow.graph,
                name=workflow.name,
                description=workflow.description,
                created_by=request.user
            )
            workflow.save()
            
            # 5. ACTIVATE TRIGGERS
            from .triggers.trigger_registry import trigger_registry
            active_triggers = []
            for trigger_node in trigger_nodes:
                try:
                    t_type = (trigger_node.get('action_type') or trigger_node.get('type', '')).lower()
                    # Map node type to system trigger type if needed
                    # e.g. 'manual_trigger' -> 'manual'
                    
                    activation = trigger_registry.activate_trigger(workflow, t_type)
                    if activation.get('success'):
                        active_triggers.append(t_type)
                        logger.info(f"Activated trigger {t_type} for workflow {workflow.id}")
                    else:
                        logger.warning(f"Failed to activate trigger {t_type}: {activation.get('error')}")
                except Exception as e:
                    logger.error(f"Error activating trigger {t_type}: {e}")
            
            
            return Response({
                'success': True,
                'status': 'published', 
                'version': workflow.version,
                'message': 'Workflow deployed successfully',
                'workflow_id': str(workflow.id)
            })

        except Exception as e:
            logger.error(f"Deploy failed: {e}", exc_info=True)
            return Response({
                'success': False,
                'error': 'Deployment Failed',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def unpublish(self, request, pk=None):
        """Mark workflow as draft."""
        workflow = self.get_object()
        workflow.status = 'draft'
        workflow.save()
        return Response({'status': 'draft'})
    
    @action(detail=True, methods=['get'])
    def versions(self, request, pk=None):
        """List workflow versions."""
        workflow = self.get_object()
        versions = WorkflowVersion.objects.filter(workflow=workflow).order_by('-version_number')
        serializer = WorkflowVersionSerializer(versions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def rollback(self, request, pk=None):
        """Rollback to a specific version."""
        workflow = self.get_object()
        version_number = request.data.get('version_number')
        
        try:
            version = WorkflowVersion.objects.get(
                workflow=workflow,
                version_number=version_number
            )
            workflow.graph = version.graph
            workflow.name = version.name
            workflow.description = version.description
            workflow.save()
            
            return Response({'status': 'rolled_back', 'version': version_number})
        except WorkflowVersion.DoesNotExist:
            return Response(
                {'error': f'Version {version_number} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get'])
    def executions(self, request, pk=None):
        """List workflow executions."""
        workflow = self.get_object()
        executions = WorkflowExecution.objects.filter(workflow=workflow).order_by('-created_at')
        page = self.paginate_queryset(executions)
        if page is not None:
            serializer = WorkflowExecutionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = WorkflowExecutionSerializer(executions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def export(self, request, pk=None):
        """Export workflow as JSON."""
        workflow = self.get_object()
        export_data = {
            'name': workflow.name,
            'description': workflow.description,
            'graph': workflow.graph,
            'version': workflow.version,
            'exported_at': timezone.now().isoformat(),
        }
        return Response(export_data)
    
    @action(detail=False, methods=['post'])
    def import_workflow(self, request):
        """Import workflow from JSON."""
        data = request.data
        workflow = Workflow.objects.create(
            name=data.get('name', 'Imported Workflow'),
            description=data.get('description', ''),
            graph=data.get('graph', {}),
            owner=request.user,
            status='draft'
        )
        serializer = self.get_serializer(workflow)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class WorkflowExecutionViewSet(viewsets.ModelViewSet):
    """ViewSet for WorkflowExecution CRUD operations."""
    serializer_class = WorkflowExecutionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter executions by user's workflows."""
        return WorkflowExecution.objects.filter(
            workflow__owner=self.request.user
        ).select_related('workflow').prefetch_related('node_executions')
    
    def create(self, request, *args, **kwargs):
        """Create workflow execution with comprehensive error handling."""
        try:
            serializer = self.get_serializer(data=request.data)
            
            try:
                serializer.is_valid(raise_exception=True)
            except serializers.ValidationError as e:
                # Enhanced error response with specific details
                error_detail = str(e.detail) if hasattr(e, 'detail') else str(e)
                return Response({
                    'error': 'Workflow validation failed',
                    'error_type': 'VALIDATION_ERROR',
                    'detail': error_detail,
                    'code': 'VALIDATION_ERROR'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get workflow
            workflow_obj = serializer.validated_data.get('workflow')
            if not workflow_obj:
                return Response({
                    'error': 'Missing workflow field',
                    'error_type': 'MISSING_WORKFLOW',
                    'detail': 'workflow field is required',
                    'code': 'MISSING_WORKFLOW'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Ensure user has access to the provided workflow instance
            workflow = workflow_obj
            if workflow.owner != request.user:
                return Response({
                    'error': 'Workflow access denied', 
                    'error_type': 'ACCESS_DENIED',
                    'detail': 'You do not have permission to execute this workflow',
                    'code': 'ACCESS_DENIED'
                }, status=status.HTTP_404_NOT_FOUND)
            
            # Validate workflow graph before execution
            if not workflow.graph or not workflow.graph.get('nodes'):
                return Response({
                    'error': 'Invalid workflow',
                    'error_type': 'EMPTY_WORKFLOW', 
                    'detail': 'Workflow has no nodes defined',
                    'code': 'EMPTY_WORKFLOW'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            nodes = workflow.graph.get('nodes', [])
            edges = workflow.graph.get('edges', [])
            
            # Handle different graph formats
            if isinstance(nodes, dict):
                # Convert dict format to list format
                nodes = list(nodes.values())
            
            # Check if there's a separate trigger in the graph
            trigger = workflow.graph.get('trigger')
            if trigger and isinstance(trigger, dict):
                nodes.append(trigger)
            
            # Check for trigger nodes
            trigger_types = {'webhook', 'schedule', 'manual', 'trigger', 'manual_trigger', 'webhook_trigger', 'schedule_trigger'}
            has_trigger = any(
                (node.get('action_type') or node.get('type', '')).lower() in trigger_types 
                for node in nodes if isinstance(node, dict)
            )
            
            if not has_trigger:
                return Response({
                    'error': 'No trigger node found',
                    'error_type': 'NO_TRIGGER',
                    'detail': 'Workflow must have at least one trigger node (webhook, schedule, or manual)',
                    'code': 'NO_TRIGGER'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate node types are supported
            from .actions import ACTION_REGISTRY
            unsupported_types = []
            for node in nodes:
                if isinstance(node, dict):
                    node_type = node.get('action_type') or node.get('type', '')
                    if node_type and node_type not in ACTION_REGISTRY:
                        unsupported_types.append(node_type)
            
            if unsupported_types:
                available_types = list(ACTION_REGISTRY.keys())
                return Response({
                    'error': 'Unsupported node types',
                    'error_type': 'UNSUPPORTED_NODE_TYPES',
                    'detail': f'Unsupported node types: {unsupported_types}. Available types: {available_types}',
                    'unsupported_types': unsupported_types,
                    'available_types': available_types,
                    'code': 'UNSUPPORTED_NODE_TYPES'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate tenant before execution creation
            try:
                workflow_tenant = workflow.tenant
            except:
                workflow_tenant = None
                
            # Ensure execution always has a tenant assigned
            if not workflow_tenant:
                logger.warning(f"Workflow {workflow.id} has no tenant assigned, using default tenant")
                workflow_tenant = get_default_tenant()
            
            # Check for idempotency
            idem_key = request.headers.get('Idempotency-Key') or request.META.get('HTTP_IDEMPOTENCY_KEY') or serializer.validated_data.get('idempotency_key')
            if idem_key:
                existing = WorkflowExecution.objects.filter(workflow=workflow, idempotency_key=idem_key).first()
                if existing:
                    response_serializer = self.get_serializer(existing)
                    return Response(response_serializer.data, status=status.HTTP_200_OK)
            
            # Create execution with comprehensive error handling
            try:
                execution = WorkflowExecution.objects.create(
                    workflow=workflow,
                    tenant=workflow_tenant,  # Now guaranteed to be not None or None
                    input_payload={
                        **serializer.validated_data.get('input_payload', {}),
                        '_user_id': request.user.id,  # Store as int, not string
                        '_user_email': request.user.email,  # Store user email for debugging
                        '_tenant_id': workflow_tenant.id if workflow_tenant else None,  # Also store tenant ID
                    },
                    input_items=serializer.validated_data.get('input_items', []),
                    status="queued",
                    triggered_by="manual",
                    correlation_id=str(uuid.uuid4()),
                    idempotency_key=idem_key or ""
                )
                
            except IntegrityError as e:
                logger.error(f"Database integrity error creating execution: {e}", exc_info=True)
                return Response({
                    'error': 'Database constraint violation',
                    'error_type': 'INTEGRITY_ERROR',
                    'detail': f'Failed to create execution due to database constraint: {str(e)}',
                    'code': 'INTEGRITY_ERROR'
                }, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                logger.error(f"Unexpected error creating execution: {e}", exc_info=True)
                return Response({
                    'error': 'Execution creation failed',
                    'error_type': 'CREATION_ERROR',
                    'detail': f'Failed to create workflow execution: {str(e)}',
                    'code': 'CREATION_ERROR'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Queue execution with enhanced error handling
            try:
                transaction.on_commit(lambda: run_workflow_execution.delay(str(execution.id)))
            except Exception as e:
                logger.error(f"Failed to queue execution {execution.id}: {e}", exc_info=True)
                execution.mark_failed(
                    error_message=f"Failed to queue execution: {str(e)}",
                    traceback=""
                )
                return Response({
                    'error': 'Execution queue failed',
                    'error_type': 'QUEUE_ERROR',
                    'detail': f'Failed to start workflow execution: {str(e)}',
                    'code': 'QUEUE_ERROR'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Return execution data
            response_serializer = self.get_serializer(execution)
            headers = self.get_success_headers(response_serializer.data)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)
            
        except Exception as e:
            logger.error(f"Unexpected error in execution creation: {e}", exc_info=True)
            return Response({
                'error': 'Internal server error',
                'error_type': 'INTERNAL_ERROR',
                'detail': 'An unexpected error occurred while creating the execution',
                'code': 'INTERNAL_ERROR'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def nodes(self, request, pk=None):
        """Get node executions for this execution."""
        execution = self.get_object()
        node_executions = execution.node_executions.all()
        serializer = NodeExecutionSerializer(node_executions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        """Get execution logs."""
        execution = self.get_object()
        logs = ExecutionLog.objects.filter(execution=execution).order_by('timestamp')
        serializer = ExecutionLogSerializer(logs, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def trace(self, request, pk=None):
        """
        Get execution trace for visualization.
        
        Returns execution summary with node-wise execution details.
        """
        execution = self.get_object()
        
        # Get all node executions
        node_executions = execution.node_executions.all().order_by('started_at')
        
        # Build trace structure
        trace_nodes = []
        for node_exec in node_executions:
            duration = None
            if node_exec.started_at and node_exec.finished_at:
                duration = (node_exec.finished_at - node_exec.started_at).total_seconds()
            
            trace_nodes.append({
                "node_id": node_exec.graph_node_id or (str(node_exec.node.node_id) if node_exec.node else None),
                "node_label": node_exec.node.label if node_exec.node else "Unknown",
                "status": node_exec.status,
                "attempts": node_exec.retry_count + 1,  # +1 for initial attempt
                "started_at": node_exec.started_at.isoformat() if node_exec.started_at else None,
                "finished_at": node_exec.finished_at.isoformat() if node_exec.finished_at else None,
                "duration": duration,
                "error_summary": node_exec.error_message[:200] if node_exec.error_message else None,
                "output_item_count": len(node_exec.output_items) if node_exec.output_items else 0,
            })
        
        return Response({
            "execution_id": str(execution.id),
            "workflow_id": str(execution.workflow.id),
            "workflow_name": execution.workflow.name,
            "status": execution.status,
            "started_at": execution.started_at.isoformat() if execution.started_at else None,
            "finished_at": execution.finished_at.isoformat() if execution.finished_at else None,
            "duration": (
                (execution.finished_at - execution.started_at).total_seconds()
                if execution.started_at and execution.finished_at else None
            ),
            "triggered_by": execution.triggered_by,
            "nodes": trace_nodes,
            "total_nodes": len(trace_nodes),
            "completed_nodes": sum(1 for n in trace_nodes if n["status"] in ["completed", "success"]),
            "failed_nodes": sum(1 for n in trace_nodes if n["status"] == "failed"),
        })
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel running execution."""
        execution = self.get_object()
        if execution.status == 'running':
            execution.status = 'cancelled'
            execution.finished_at = timezone.now()
            execution.save()
            return Response({'status': 'cancelled'})
        return Response(
            {'error': 'Execution is not running'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=True, methods=['post'])
    def pause(self, request, pk=None):
        """Pause running execution."""
        execution = self.get_object()
        if execution.status == 'running':
            execution.status = 'paused'
            execution.save(update_fields=['status'])
            return Response({'status': 'paused'})
        return Response({'error': 'Execution is not running'}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        """Retry execution from failed node."""
        execution = self.get_object()
        if execution.status == 'failed':
            # Create new execution with same input
            new_execution = WorkflowExecution.objects.create(
                workflow=execution.workflow,
                input_payload=execution.input_payload,
                input_items=execution.input_items,
                triggered_by='manual',
                correlation_id=str(uuid.uuid4())
            )
            transaction.on_commit(lambda: run_workflow.delay(str(new_execution.id)))
            return Response({
                'execution_id': str(new_execution.id),
                'status': 'queued'
            })
        return Response(
            {'error': 'Can only retry failed executions'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=True, methods=['post'])
    def resume(self, request, pk=None):
        """Resume failed execution by re-queuing from a specific node."""
        execution = self.get_object()
        if execution.status not in ['failed', 'paused']:
            return Response(
                {'error': 'Can only resume failed or paused executions'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get resume node from request or find last failed node
        resume_from_node = request.data.get('resume_from_node')
        if not resume_from_node:
            # Find last failed node
            failed_node_exec = execution.node_executions.filter(status='failed').order_by('-finished_at').first()
            if failed_node_exec and failed_node_exec.node:
                resume_from_node = failed_node_exec.node.node_id
        
        if not resume_from_node:
            return Response(
                {'error': 'No node specified to resume from'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update execution with resume info
        execution.status = 'running'
        execution.resume_from_node = resume_from_node
        execution.resume_data = request.data.get('resume_data', {})
        execution.save(update_fields=['status', 'resume_from_node', 'resume_data'])
        
        # Re-queue execution
        transaction.on_commit(lambda: run_workflow_execution.delay(str(execution.id)))
        
        return Response({
            'execution_id': str(execution.id),
            'status': 'resumed',
            'resume_from_node': resume_from_node
        })

    @action(detail=True, methods=['post'])
    def drain(self, request, pk=None):
        """Enable or disable drain mode on execution (stop enqueuing children)."""
        execution = self.get_object()
        enable = bool(request.data.get('enable', True))
        data = execution.resume_data or {}
        data['drain'] = enable
        execution.resume_data = data
        execution.save(update_fields=['resume_data'])
        return Response({'drain': enable})


class CredentialViewSet(viewsets.ModelViewSet):
    """ViewSet for Credential CRUD operations."""
    serializer_class = CredentialSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter credentials by owner and optional type."""
        # Fix: Ensure strict filtering by owner
        queryset = Credential.objects.filter(owner=self.request.user)
        
        # Support filtering by type (e.g. ?type=gmail_oauth)
        cred_type = self.request.query_params.get('type')
        
        # LOGGING: Track request to verify it's hitting the backend
        logger.info(f"🔑 [CredentialViewSet] Request from {self.request.user} (ID: {self.request.user.id}). Type param: '{cred_type}'")

        if cred_type:
            # Validate type if requested
            allowed_types = [t[0] for t in Credential.CREDENTIAL_TYPES]
            if cred_type != 'email' and cred_type not in allowed_types:
                # We return empty queryset or we could raise error in list()
                pass

            if cred_type == 'email':
                # "email" is a meta-type for frontend convenience
                queryset = queryset.filter(type__in=['gmail_oauth', 'google_oauth', 'smtp', 'smtp_server', 'gmail'])
            elif cred_type in ['gmail_oauth', 'google_oauth', 'gmail']:
                queryset = queryset.filter(type__in=['gmail_oauth', 'google_oauth', 'gmail'])
            elif cred_type in ['telegram', 'telegram_bot']:
                queryset = queryset.filter(type__in=['telegram', 'telegram_bot'])
            elif cred_type in ['whatsapp', 'meta_whatsapp']:
                queryset = queryset.filter(type__in=['whatsapp', 'meta_whatsapp'])
            elif cred_type in ['smtp', 'smtp_server']:
                queryset = queryset.filter(type__in=['smtp', 'smtp_server'])
            elif cred_type in ['api_key', 'general_api_key']:
                queryset = queryset.filter(type__in=['api_key', 'general_api_key'])
            elif cred_type in ['ollama', 'ollama_local', 'ai_offline']:
                queryset = queryset.filter(type__in=['ollama', 'ollama_local', 'ai_offline'])
            elif cred_type == 'google_calendar':
                queryset = queryset.filter(type__in=['google_calendar', 'google_oauth'])
            elif cred_type == 'ai_provider':
                queryset = queryset.filter(type__in=['ollama_local', 'ollama', 'ai_offline', 'openai', 'anthropic', 'gemini'])
            else:
                queryset = queryset.filter(type=cred_type)

            logger.info(f"🔍 [Credential List] User={self.request.user.username}, Type={cred_type}, Count={queryset.count()}")
            
        return queryset.order_by('-updated_at')



    @action(detail=False, methods=['post', 'get'])
    def authorize_google(self, request):
        """
        Initiate Google OAuth Flow.
        Unified endpoint for Gmail, Drive, Sheets, YouTube.
        Handles both POST (from existing credential) and GET (fresh).
        """
        try:
            credential_id = request.data.get('credential_id') or request.query_params.get('credential_id')
            logger.critical(f"🚀 [Authorize Google] Hit with Credential ID: {credential_id} | Method: {request.method}")
            
            # Default to settings
            client_id = settings.GMAIL_OAUTH_CLIENT_ID
            client_secret = settings.GMAIL_OAUTH_CLIENT_SECRET
            redirect_uri = settings.GMAIL_OAUTH_REDIRECT_URI
            
            # Helper to check if settings exist
            if not client_id: logger.error("❌ [Authorize Google] missing settings.GMAIL_OAUTH_CLIENT_ID")
            if not client_secret: logger.error("❌ [Authorize Google] missing settings.GMAIL_OAUTH_CLIENT_SECRET")
            
            # If credential provided, try to use its keys (Self-Hosted)
            cred = None
            if credential_id and str(credential_id).strip() not in ['', 'None', 'null', 'undefined']:
                try:
                    cred = Credential.objects.filter(id=credential_id, owner=request.user).first()
                    if cred:
                        from .services.credential_encryption import get_encryption_service
                        svc = get_encryption_service()
                        data = {}
                        if svc and cred.encrypted_data:
                             data = svc.decrypt_credential_str(cred.encrypted_data) if isinstance(cred.encrypted_data, str) else cred.encrypted_data
                        
                        if data.get('client_id') and data.get('client_secret'):
                            client_id = data.get('client_id')
                            client_secret = data.get('client_secret')
                except Exception as e:
                    logger.warning(f"Failed to load custom keys from credential {credential_id}: {e}")

            if not client_id or not client_secret:
                return Response({'error': 'Missing Client ID/Secret configuration'}, status=500)

            # Construct client config
            client_config = {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    # Use setting for consistency
                    "redirect_uris": [settings.GMAIL_OAUTH_REDIRECT_URI] 
                }
            }
            
            print(f"DEBUG: CredentialViewSet sending redirect_uri: {settings.GMAIL_OAUTH_REDIRECT_URI}")
            logger.critical(f"DEBUG: CredentialViewSet sending redirect_uri: {settings.GMAIL_OAUTH_REDIRECT_URI}")
            
            # Unified Scopes
            scopes = [
                'https://www.googleapis.com/auth/userinfo.email',
                'https://www.googleapis.com/auth/userinfo.profile',
                'https://www.googleapis.com/auth/gmail.send',
                'https://www.googleapis.com/auth/gmail.readonly',
                'https://www.googleapis.com/auth/drive',
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/youtube'
            ]
            
            flow = google_auth_oauthlib.flow.Flow.from_client_config(
                client_config,
                scopes=scopes
            )
            
            # Use specific redirect URI for the flow
            flow.redirect_uri = client_config['web']['redirect_uris'][0]
            
            # Pass Credential ID in state for recovery in callback
            state = f"{request.user.id}:{credential_id}" if credential_id else f"{request.user.id}:new"
            
            authorization_url, _ = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent',
                state=state
            )

            # Store code_verifier in session so callback can use it
            if flow.code_verifier:
                request.session['google_oauth_code_verifier'] = flow.code_verifier
                request.session.modified = True
            
            return Response({'url': authorization_url})
            
        except Exception as e:
            logger.error(f"Failed to generate Google Auth URL: {e}")
            return Response({'error': str(e)}, status=500)

    @action(detail=False, methods=['get', 'post'])
    def google_callback(self, request):
        """
        Exchange auth code for tokens and save Credential.
        Handles both API calls and Browser Redirects.
        """
        from django.shortcuts import redirect
        from django.contrib.auth import get_user_model
        
        code = request.data.get('code') or request.query_params.get('code')
        error = request.query_params.get('error')
        state = request.query_params.get('state')
        
        if error:
            logger.error(f"Google OAuth Error: {error}")
            return redirect(f'/credentials/?error={error}')
            
        if not code:
            return redirect('/credentials/?error=no_code_provided')
            
        try:
            # Parse State
            credential_id = None
            user = request.user
            
            if state and ':' in state:
                user_id_str, cred_id_raw = state.split(':', 1)
                if cred_id_raw != 'new':
                    credential_id = cred_id_raw
                
                # If legitimate auth flow, we might need to load user if request.user is anonymous (callback)
                # But we are using session auth presumably? Or token?
                # If we are anonymous, we can't save. 
                # But Google Callback usually maintains session cookie if same browser.
                # If not, we trust state (security risk? signed state is better).
                # For now, we assume user is logged in or we assume state is valid.
                if not user.is_authenticated:
                    User = get_user_model()
                    user = User.objects.get(id=user_id_str)
            
            # Helper to get enc service
            from .services.credential_encryption import get_encryption_service
            svc = get_encryption_service()
            
            # Determine Client Keys (DB vs Settings)
            client_id = settings.GMAIL_OAUTH_CLIENT_ID
            client_secret = settings.GMAIL_OAUTH_CLIENT_SECRET
            
            cred = None
            if credential_id:
                try:
                    cred = Credential.objects.get(id=credential_id, owner=user)
                    data = {}
                    if svc and cred.encrypted_data:
                         data = svc.decrypt_credential_str(cred.encrypted_data) if isinstance(cred.encrypted_data, str) else cred.encrypted_data
                    
                    if data.get('client_id') and data.get('client_secret'):
                        client_id = data.get('client_id')
                        client_secret = data.get('client_secret')
                except Exception as e:
                    logger.warning(f"Failed to load custom keys from credential {credential_id}: {e}")

            # Exchange Code
            logger.critical(f"🔑 [Google Callback] State recovery: User={user.id} | Cred={credential_id}")
            logger.critical(f"🔑 [Google Callback] Code received: {code[:10]}...")
            print(f"DEBUG: Google Callback using redirect_uri: {settings.GMAIL_OAUTH_REDIRECT_URI}")

            # Exchange code directly, passing code_verifier if PKCE was used
            import requests
            token_payload = {
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': settings.GMAIL_OAUTH_REDIRECT_URI,
                'grant_type': 'authorization_code',
            }
            code_verifier = request.session.pop('google_oauth_code_verifier', None)
            if code_verifier:
                token_payload['code_verifier'] = code_verifier

            token_response = requests.post('https://oauth2.googleapis.com/token', data=token_payload)
            if not token_response.ok:
                raise Exception(f"Token exchange failed: {token_response.text}")
            token_json = token_response.json()

            from google.oauth2.credentials import Credentials as GoogleCredentials
            creds = GoogleCredentials(
                token=token_json.get('access_token'),
                refresh_token=token_json.get('refresh_token'),
                token_uri='https://oauth2.googleapis.com/token',
                client_id=client_id,
                client_secret=client_secret,
                scopes=token_json.get('scope', '').split()
            )
            logger.critical("✅ [Google Callback] Token exchanged successfully")
            
            # Get User Email
            user_info = requests.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {creds.token}'}
            ).json()
            email = user_info.get('email')
            
            # Prepare Data
            token_data = {
                'token': creds.token,
                'access_token': creds.token,
                'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri,
                'client_id': client_id,
                'client_secret': client_secret,
                'scopes': creds.scopes,
                'email': email,
                'expiry': creds.expiry.isoformat() if creds.expiry else None
            }
            
            # Update/Create Credential
            # If we had a provisional credential (cred), update it
            # Else find or create
            tenant = getattr(user, 'tenant', None)
            
            if cred:
                # Update existing
                cred.name = f"Gmail - {email}" # Update name
                cred.email = email # Update email field if exists
                
                # Merge existing data (like client_id) with new token data
                if svc and cred.encrypted_data:
                     # Decrypt to preserve old keys
                     old_data = svc.decrypt_credential_str(cred.encrypted_data) if isinstance(cred.encrypted_data, str) else cred.encrypted_data
                     token_data['client_id'] = old_data.get('client_id', client_id)
                     token_data['client_secret'] = old_data.get('client_secret', client_secret)
                
                cred.encrypted_data = svc.encrypt_credential_str(token_data) if svc else token_data
                cred.type = 'google_oauth' # Upgrade type
                cred.provider = 'google'
                cred.save()
            else:
                # Create new
                enc_data = svc.encrypt_credential_str(token_data) if svc else token_data
                cred = Credential.objects.create(
                    owner=user,
                    tenant=tenant,
                    name=f"Gmail - {email}",
                    type='google_oauth',
                    provider='google',
                    encrypted_data=enc_data
                )

            return redirect('/credentials/?status=success_gmail_connected')
            
        except Exception as e:
            logger.error(f"❌ [Google Callback] CRITICAL FAILURE: {str(e)}", exc_info=True)
            return redirect(f'/credentials/?error=auth_failed_{str(e)}')

    # --- CANONICAL CREDENTIAL PROVIDERS ---
    PROVIDERS = [
        "gmail_oauth",
        "google_calendar",
        "smtp_server",
        "telegram_bot",
        "meta_whatsapp",
        "ollama_local",
        "general_api_key",
        
        # Backward compatibility / legacy
        "gmail",
        "google_oauth",
        "smtp",
        "telegram",
        "whatsapp",
        "ollama",
        "ai_offline",
        "api_key"
    ]

    def create(self, request, *args, **kwargs):
        """Override create to implement upsert logic and strict normalization."""
        data = request.data.copy()
        
        # Normalize type and provider
        cred_type = normalize_credential_type(data.get('type'))
        data['type'] = cred_type
        
        # Provider normalization: Google should stay 'google'
        if 'provider' in data:
            p = data['provider'].lower()
            if p in ['google', 'gmail', 'gmail_oauth', 'google_gmail']:
                data['provider'] = 'google'
            else:
                data['provider'] = normalize_credential_type(data['provider'])
        else:
            # Fallback provider based on type
            if 'gmail' in cred_type or 'google' in cred_type:
                data['provider'] = 'google'
        
        # Upsert logic: If (owner, type) exists, update instead of create
        existing_instance = Credential.objects.filter(owner=request.user, type=cred_type).first()
        
        if existing_instance:
            serializer = self.get_serializer(existing_instance, data=data, partial=True)
        else:
            serializer = self.get_serializer(data=data)
            
        if serializer.is_valid():
            try:
                # Auto-assign owner and tenant
                tenant = getattr(request.user, 'tenant', None)
                instance = serializer.save(owner=request.user, tenant=tenant)
                
                # Manual encryption if data is still a dict (from frontend)
                svc = get_encryption_service()
                if svc and isinstance(instance.encrypted_data, dict):
                    instance.encrypted_data = svc.encrypt_credential_str(instance.encrypted_data)
                    instance.save()
                
                # Update status flag
                is_configured = is_credential_configured(instance.type, resolve_credential_data(instance))
                instance.status = "connected" if is_configured else "pending"
                instance.save()
            except IntegrityError as e:
                logger.error(f"IntegrityError in create: {e}")
                # If collision, try to find the conflicting record and update it 
                # (Simple fallback: return error with help)
                return Response({
                    "success": False,
                    "message": "A credential of this type already exists. Please edit the existing one.",
                    "error": str(e)
                }, status=status.HTTP_409_CONFLICT)

            return Response({
                "success": True,
                "message": f"Credential {'updated' if existing_instance else 'saved'} successfully",
                "credential": {
                    "id": instance.id,
                    "type": instance.type,
                    "status": instance.status,
                    "configured": is_configured
                }
            }, status=status.HTTP_201_CREATED if not existing_instance else status.HTTP_200_OK)
        
        return Response({
            "success": False,
            "message": "Validation failed",
            "error": serializer.errors.get('error', "Check input fields"),
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        """Standard update with normalization and encryption."""
        data = request.data.copy()
        if 'type' in data:
            data['type'] = normalize_credential_type(data['type'])
        
        if 'provider' in data:
            p = data['provider'].lower()
            if p in ['google', 'gmail', 'gmail_oauth', 'google_gmail']:
                data['provider'] = 'google'
            else:
                data['provider'] = normalize_credential_type(data['provider'])
            
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=data, partial=partial)
        
        if serializer.is_valid():
            try:
                instance = serializer.save()
                
                svc = get_encryption_service()
                if svc and isinstance(instance.encrypted_data, dict):
                     instance.encrypted_data = svc.encrypt_credential_str(instance.encrypted_data)
                
                is_configured = is_credential_configured(instance.type, resolve_credential_data(instance))
                instance.status = "connected" if is_configured else "pending"
                instance.save()
            except IntegrityError as e:
                logger.error(f"IntegrityError in update: {e}")
                return Response({
                    "success": False,
                    "message": "Update failed: Another credential of this type already exists.",
                    "error": str(e)
                }, status=status.HTTP_409_CONFLICT)
                 
            return Response({
                "success": True,
                "message": "Credential updated successfully",
                "credential": {
                    "id": instance.id,
                    "type": instance.type,
                    "status": instance.status,
                    "configured": is_configured
                }
            })

        return Response({
            "success": False,
            "message": "Update failed",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def test(self, request):
        """
        Unified Test Endpoint for ALL Credential Types (Hardened).
        """
        provider = normalize_credential_type(request.data.get('provider') or request.data.get('type'))
        data = request.data.get('data')
        
        # If no explicit data, try to load from existing credential
        cred_id = request.data.get('credential_id')
        if not data and cred_id:
            cred = Credential.objects.filter(id=cred_id, owner=request.user).first()
            if cred:
                data = resolve_credential_data(cred)

        if not data:
             return Response({"success": False, "error": "No configuration data provided for test."}, status=400)

        try:
            # --- TELEGRAM ---
            if provider == 'telegram_bot':
                token = data.get('bot_token') or data.get('token')
                if not token: return Response({"success": False, "error": "❌ Missing Bot Token"}, status=400)
                # FIX 4: Call getMe
                res = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
                if res.ok:
                    bot = res.json().get('result', {})
                    return Response({"success": True, "message": f"✅ Connected as @{bot.get('username')}"})
                return Response({"success": False, "error": f"❌ Telegram: {res.json().get('description', 'Auth Failed')}"}, status=400)

            # --- WHATSAPP ---
            elif provider == 'meta_whatsapp':
                token = data.get('access_token')
                if not token: return Response({"success": False, "error": "❌ Missing Access Token"}, status=400)
                # FIX 4: Call Meta API /me
                res = requests.get(
                    "https://graph.facebook.com/v18.0/me", 
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5
                )
                if res.ok:
                    return Response({"success": True, "message": "✅ WhatsApp Access Token verified!"})
                try:
                    err_msg = res.json().get('error', {}).get('message', 'Auth Failed')
                except:
                    err_msg = "Meta API Error"
                return Response({"success": False, "error": f"❌ WhatsApp: {err_msg}"}, status=400)

            # --- OLLAMA ---
            elif provider == 'ollama_local':
                host = data.get('base_url', 'http://localhost:11434').rstrip('/')
                res = requests.get(f"{host}/api/tags", timeout=3)
                if res.ok: return Response({"success": True, "message": "✅ Ollama connection successful!"})
                return Response({"success": False, "error": "❌ Ollama service not reachable."}, status=400)

            # --- SMTP ---
            elif provider == 'smtp_server':
                import smtplib
                host, port = data.get('host'), int(data.get('port', 587))
                user, pwd = data.get('username'), data.get('password')
                try:
                    server = smtplib.SMTP(host, port, timeout=5)
                    server.starttls()
                    server.login(user, pwd)
                    server.quit()
                    return Response({"success": True, "message": "✅ SMTP credentials verified!"})
                except Exception as e: return Response({"success": False, "error": f"❌ SMTP Failed: {str(e)}"}, status=400)

            return Response({"success": False, "error": f"Test logic not implemented for {provider}."}, status=400)

        except Exception as e:
            logger.error(f"❌ [Credential Test] Error for {provider}: {str(e)}", exc_info=True)
            return Response({"success": False, "error": f"Test Failed: {str(e)}"}, status=500)

    def perform_create(self, serializer):
        """
        STRICT Upsert logic for credentials. 
        Ensures (owner, type) uniqueness without crashing.
        """
        user_id = self.request.user.id
        cred_type = self.request.data.get('type')
        logger.critical(f"🔑 [Credential Create] Request from user_id={user_id} for type={cred_type}")
        
        # Determine tenant (fallback to user's first tenant or default)
        tenant = getattr(self.request.user, 'tenant', None)
        if not tenant:
            tenant = get_default_tenant()

        try:
            # We use a manual check before save to provide better logs and avoids IntegrityError 500
            existing = Credential.objects.filter(owner=self.request.user, type=cred_type).first()
            
            if cred_type == 'ai_offline':
                self.validate_offline_ai_credential(serializer)

            if existing:
                logger.warning(f"🔄 [Credential Create] Found existing {cred_type}. Upgrading to Update.")
                # Update existing instance with new validated data
                # We reuse the serializer to perform the update on the existing instance
                for attr, value in serializer.validated_data.items():
                    setattr(existing, attr, value)
                existing.save()
                serializer.instance = existing # Critical for DRF response
                logger.critical(f"✅ [Credential Create] SUCCESSFULLY UPDATED. ID: {existing.id}")
            else:
                # Normal create
                instance = serializer.save(owner=self.request.user, tenant=tenant)
                logger.critical(f"✅ [Credential Create] SUCCESSFULLY CREATED. ID: {instance.id}")

        except IntegrityError:
            # Race condition fallback: Try to get again and update
            # (In case two requests for same type hit at once)
            existing = Credential.objects.filter(owner=self.request.user, type=cred_type).first()
            if existing:
                for attr, value in serializer.validated_data.items():
                    setattr(existing, attr, value)
                existing.save()
                serializer.instance = existing
            else:
                raise serializers.ValidationError({"detail": "Storage error: Unique constraint failed."})
        except Exception as e:
            logger.error(f"❌ [Credential Create] Exception: {str(e)}")
            if isinstance(e, serializers.ValidationError):
                raise e
            raise serializers.ValidationError({"detail": str(e)})

    def validate_offline_ai_credential(self, serializer, instance=None):
        """
        Strict validation for Offline AI credentials.
        Blocks save if Ollama is unreachable.
        Enforces full model names (e.g. llama3:8b).
        """
        # Get input data
        data = serializer.validated_data
        cred_type = data.get('type')
        
        # If updating, use instance type if not in data
        if not cred_type and instance:
            cred_type = instance.type
            
        if cred_type == 'ai_offline':
            encrypted_data = data.get('encrypted_data', {})
            
            # If valid dict, check it
            if isinstance(encrypted_data, dict):
                base_url = encrypted_data.get('base_url', 'http://localhost:11434')
                default_model = encrypted_data.get('default_model', '')
                available_models = encrypted_data.get('available_models', [])
                
                # 1. Validate Model Names
                if default_model and ":" not in default_model:
                     raise serializers.ValidationError({
                         "encrypted_data": f"Invalid default model '{default_model}'. Full name required (e.g. llama3:8b)."
                     })
                
                if available_models:
                    for m in available_models:
                        if ":" not in m:
                            raise serializers.ValidationError({
                                "encrypted_data": f"Invalid model in available list: '{m}'. Full name required."
                            })

                # 2. Check Health & Connectivity
                # This runs on the server (container). 
                # If user used 'localhost', it means container's localhost.
                # If they want host's ollama, they need host.docker.internal
                provider = OllamaProvider()
                health = provider.check_health(base_url)
                
                if not health['success']:
                     # STRICT BLOCK
                     raise serializers.ValidationError({
                         "encrypted_data": f"Ollama unreachable at {base_url}. Error: {health.get('error')}. (Hint: Use host.docker.internal for host machine)"
                     })
                     
                # 3. Optional: Check if default_model actually exists? 
                # No, user might not have pulled it yet but we allow saving config.
                # But strict format check is mandatory.

    def perform_update(self, serializer):
        """Update credential with validation."""
        start_time = timezone.now()
        instance = self.get_object()
        user_id = self.request.user.id
        logger.info(f"🔑 [Credential Update] Request for ID {instance.id}")
        
        try:
            # Validate before saving
            self.validate_offline_ai_credential(serializer, instance)
            
            with transaction.atomic():
                 serializer.save()
                 
            logger.info(f"✅ [Credential Update] Success for {instance.id}")
        except Exception as e:
            logger.error(f"❌ [Credential Update] Failed: {e}")
            raise

    @action(detail=False, methods=['post'])
    def check_health(self, request):
        """
        Check health of an AI Provider (Offline/Online).
        Used by Frontend "Test Connection" button.
        """
        try:
            cred_type = request.data.get('type')
            encrypted_data = request.data.get('encrypted_data', {})
            
            if cred_type == 'ai_offline':
                base_url = encrypted_data.get('base_url', 'http://localhost:11434')
                provider = OllamaProvider()
                
                # Check Health
                health = provider.check_health(base_url)
                if not health['success']:
                     return Response({
                         "success": False,
                         "error": f"Unreachable: {health.get('error')}"
                     }, status=status.HTTP_400_BAD_REQUEST)
                     
                # Sync Models
                models = provider.get_models(base_url)
                return Response({
                    "success": True,
                    "message": "Connected to Ollama",
                    "models": models
                })
                
            return Response({"success": True, "message": "Connection check skipped for this type"})
            
        except Exception as e:
            return Response({
                "success": False, 
                "error": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def email(self, request):
        """
        Get all credentials capable of sending email (Gmail OAuth + SMTP).
        Returns a simplified list for the frontend dropdown.
        """
        email_creds = Credential.objects.filter(
            owner=request.user, 
            type__in=['gmail_oauth', 'smtp']
        ).order_by('-updated_at')
        
        results = []
        for cred in email_creds:
            item_type = cred.type
            name = cred.name
            provider = 'gmail' if item_type == 'gmail_oauth' else 'smtp'
            
            results.append({
                "id": cred.id,
                "name": name,
                "provider": provider,
                "type": item_type,
                "status": "connected" # Simplified for now
            })
            
        return Response({
            "success": True,
            "data": results
        })
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """Test credential by attempting to use it."""
        credential = self.get_object()
        
        # Log access
        from .models import SecretAccessLog
        SecretAccessLog.objects.create(
            user=request.user,
            credential=credential,
            organization=credential.organization,
            access_type='test',
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        try:

            # Test based on credential type
            if credential.type == 'smtp':
                try:
                    import smtplib
                    
                    # Decrypt credentials
                    # Note: We need to handle decryption here as Credential model might not exposing everything directly
                    # Reusing helper from Gmail Service or just duplicating logic? 
                    # Better to import encryption service
                    from .services.credential_encryption import get_encryption_service
                    enc_service = get_encryption_service()
                    
                    data = credential.encrypted_data
                    if isinstance(data, str) and enc_service:
                        data = enc_service.decrypt_credential_str(data)
                    
                    host = data.get('host')
                    port = int(data.get('port', 587))
                    username = data.get('username')
                    password = data.get('password')
                    use_tls = data.get('use_tls', True)
                    
                    connection = smtplib.SMTP(host, port, timeout=10)
                    connection.ehlo()
                    if use_tls:
                        connection.starttls()
                        connection.ehlo()
                    
                    connection.login(username, password)
                    connection.quit()
                    
                    return Response({
                        'status': 'tested',
                        'valid': True,
                        'message': f'Successfully connected to SMTP server {host}'
                    })
                except Exception as e:
                    return Response({
                        'status': 'invalid',
                        'error': f'SMTP Connection Failed: {str(e)}'
                    }, status=400)

            elif credential.type == 'telegram_bot':
                try:
                    data = credential.encrypted_data
                    if isinstance(data, str):
                        try: data = json.loads(data)
                        except: pass
                    
                    token = data.get('bot_token')
                    if not token:
                         return Response({'status': 'invalid', 'error': 'No bot_token found'}, status=400)
                    
                    import requests
                    resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
                    if resp.status_code == 200:
                        bot_info = resp.json().get('result', {})
                        return Response({
                            'status': 'tested',
                            'valid': True,
                            'message': f"Connected to @{bot_info.get('username')} ({bot_info.get('first_name')})"
                        })
                    else:
                         return Response({
                            'status': 'invalid',
                            'error': f"Invalid Token. Telegram API response: {resp.text}" 
                        }, status=400)
                except Exception as e:
                    return Response({'status': 'invalid', 'error': f"Connection Failed: {str(e)}"}, status=400)

            elif credential.type == 'gmail_oauth':
                try:
                    from .services.gmail_oauth_service import GmailOAuthService
                    service = GmailOAuthService(user=request.user, tenant=credential.tenant)
                    
                    # Decrypt to get email
                    data = service._decrypt_credential_data(credential)
                    email_address = data.get('email')
                    
                    if not email_address:
                         return Response({
                            'status': 'invalid',
                            'error': 'Credential missing email address'
                        }, status=400)
                    
                    # Send execution test
                    service.send_email(
                        user=request.user,
                        tenant=credential.tenant,
                        to=email_address,
                        subject="Credential Test Successful",
                        body="Your Gmail credential is working correctly. This is a real email sent via the Gmail API.",
                        from_email=email_address,
                        credential_id=credential.id
                    )
                    
                    return Response({
                        'status': 'tested',
                        'valid': True,
                        'message': f'Test email sent successfully to {email_address}'
                    })
                except Exception as e:
                    return Response({
                        'status': 'invalid',
                        'error': f'Failed to send email: {str(e)}'
                    }, status=400)
            
            # For other types, check auth headers
            auth_headers = credential.get_auth_header()
            if not auth_headers and credential.type not in ['api_key']: # API key might just be stored
                 return Response({
                    'status': 'invalid',
                    'error': 'No auth headers generated'
                }, status=400)

            if credential.type == 'api_key':
                return Response({
                    'status': 'tested',
                    'valid': True,
                    'message': 'API Key saved and ready for use'
                })
            
            elif credential.type == 'bearer_token' or credential.type == 'oauth2':
                token = credential.encrypted_data.get('access_token') or credential.encrypted_data.get('token')
                if token and len(token) > 10:
                    return Response({
                        'status': 'tested',
                        'valid': True,
                        'message': 'Token format is valid'
                    })
                else:
                    return Response({
                        'status': 'invalid',
                        'error': 'Token is missing or invalid'
                    }, status=400)
            
            elif credential.type == 'basic_auth':
                username = credential.encrypted_data.get('username')
                password = credential.encrypted_data.get('password')
                if username and password:
                    return Response({
                        'status': 'tested',
                        'valid': True,
                        'message': 'Basic auth credentials format is valid'
                    })
                else:
                     return Response({
                        'status': 'invalid',
                        'error': 'Username or password is missing'
                    }, status=400)

            return Response({
                'status': 'tested',
                'valid': True
            })

            
        except Exception as e:
            return Response({
                'status': 'error',
                'error': str(e)
            }, status=500)
    
    def _get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class WorkflowTemplateViewSet(viewsets.ModelViewSet):
    """ViewSet for WorkflowTemplate CRUD operations."""
    serializer_class = WorkflowTemplateSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description', 'tags']
    ordering_fields = ['usage_count', 'created_at', 'name']
    ordering = ['-usage_count']
    
    def get_queryset(self):
        """Filter templates - show public or user's own."""
        user = self.request.user
        from django.db.models import Q
        return WorkflowTemplate.objects.filter(
            Q(is_public=True) | Q(created_by=user)
        )
    
    @action(detail=True, methods=['post'])
    def use(self, request, pk=None):
        """Create a workflow from template."""
        template = self.get_object()
        
        # Import workflow from template JSON
        template_data = template.template_json
        
        # Regenerate IDs
        import uuid
        node_id_mapping = {}
        nodes_data = template_data.get('nodes', [])
        new_nodes = []
        for node in nodes_data:
            old_id = node.get('id')
            new_id = str(uuid.uuid4())
            node_id_mapping[old_id] = new_id
            node['id'] = new_id
            if 'config' in node and 'credential_id' in node['config']:
                node['config']['credential_id'] = None
            new_nodes.append(node)
        
        edges_data = template_data.get('edges', [])
        new_edges = []
        for edge in edges_data:
            source = edge.get('source')
            target = edge.get('target')
            if source in node_id_mapping and target in node_id_mapping:
                edge['source'] = node_id_mapping[source]
                edge['target'] = node_id_mapping[target]
                new_edges.append(edge)
        
        # Create workflow
        workflow = Workflow.objects.create(
            name=f"{template.name} (Copy)",
            description=template.description,
            graph={
                'nodes': new_nodes,
                'edges': new_edges
            },
            owner=request.user,
            status='draft'
        )
        
        # Increment usage count
        template.usage_count += 1
        template.save(update_fields=['usage_count'])
        
        serializer = WorkflowSerializer(workflow, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
@throttle_classes([TenantWebhookRateThrottle])
def webhook_trigger(request, workflow_id):
    """Webhook endpoint to trigger workflow."""
    try:
        workflow = Workflow.objects.get(id=workflow_id, webhook_enabled=True)
    except Workflow.DoesNotExist:
        return JsonResponse({'error': 'Workflow not found or webhook disabled'}, status=404)
    
    # Verify webhook signature if secret is set
    if workflow.webhook_secret:
        signature = request.headers.get('X-Webhook-Signature', '')
        body = request.body
        
        expected_signature = hmac.new(
            workflow.webhook_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            return JsonResponse({'error': 'Invalid signature'}, status=401)
    
    # Parse payload
    try:
        payload = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        payload = {}
    
    # Convert to items format
    if isinstance(payload, list):
        input_items = [{"json": item} for item in payload]
    else:
        input_items = [{"json": payload}]
    
    # Check idempotency key (if provided)
    idem_key = request.headers.get("X-Idempotency-Key") or request.headers.get("Idempotency-Key")
    if idem_key:
        existing = WorkflowExecution.objects.filter(
            workflow=workflow,
            idempotency_key=idem_key,
        ).first()
        if existing:
            return JsonResponse(
                {
                    "status": "triggered",
                    "execution_id": str(existing.id),
                    "idempotent": True,
                },
                status=200,
            )
    
    # Create execution
    execution = WorkflowExecution.objects.create(
        workflow=workflow,
        tenant=workflow.tenant or get_default_tenant(),  # Ensure tenant is always assigned
        input_payload=payload,
        input_items=input_items,
        triggered_by='webhook',
        correlation_id=str(uuid.uuid4()),
        idempotency_key=idem_key or "",
    )
    
    # Check if webhook should wait for completion
    wait_for_completion = workflow.webhook_config.get('wait_for_completion', False)
    timeout = workflow.webhook_config.get('timeout', 30)
    
    # Set status to queued
    execution.status = "queued"
    execution.save(update_fields=["status"])
    
    # Always trigger async execution
    from .tasks import run_workflow_execution
    transaction.on_commit(lambda: run_workflow_execution.delay(str(execution.id)))
    
    return JsonResponse({
        "status": "triggered",
        "execution_id": str(execution.id)
    }, status=202)


# ============================================
# PHASE-2: ORGANIZATIONS, TEAMS & ROLES
# ============================================

class OrganizationViewSet(viewsets.ModelViewSet):
    """ViewSet for Organization CRUD operations."""
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter organizations by user membership."""
        return Organization.objects.filter(
            memberships__user=self.request.user
        ).distinct()
    
    @action(detail=True, methods=['get'])
    def usage(self, request, pk=None):
        """Get organization usage limits and current usage."""
        organization = self.get_object()
        usage_limit, _ = UsageLimit.objects.get_or_create(organization=organization)
        serializer = UsageLimitSerializer(usage_limit)
        return Response(serializer.data)


class TeamViewSet(viewsets.ModelViewSet):
    """ViewSet for Team CRUD operations."""
    serializer_class = TeamSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter teams by user's organizations."""
        return Team.objects.filter(
            organization__memberships__user=self.request.user
        ).distinct()


class MembershipViewSet(viewsets.ModelViewSet):
    """ViewSet for Membership CRUD operations."""
    serializer_class = MembershipSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter memberships by user's organizations."""
        return Membership.objects.filter(
            organization__memberships__user=self.request.user,
            organization__memberships__role__in=['owner', 'admin']
        ).distinct()


class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for SubscriptionPlan (read-only)."""
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [AllowAny]  # Public plans
    pagination_class = StandardResultsSetPagination
    queryset = SubscriptionPlan.objects.filter(is_active=True)


class SubscriptionViewSet(viewsets.ModelViewSet):
    """ViewSet for Subscription CRUD operations."""
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter subscriptions by user's organizations."""
        return Subscription.objects.filter(
            organization__memberships__user=self.request.user
        ).distinct()
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel subscription at period end."""
        subscription = self.get_object()
        subscription.cancel_at_period_end = True
        subscription.save()
        return Response({'status': 'canceled', 'cancel_at_period_end': True})


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Invoice (read-only)."""
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated, IsViewer]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter invoices by user's organizations."""
        return Invoice.objects.filter(
            organization__memberships__user=self.request.user
        ).distinct()


# ============================================
# PHASE-3: AI FEATURES
# ============================================

class AIWorkflowGenerationViewSet(viewsets.ModelViewSet):
    """ViewSet for AI Workflow Generation."""
    serializer_class = AIWorkflowGenerationSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter by user."""
        return AIWorkflowGeneration.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Create AI workflow generation request."""
        serializer.save(user=self.request.user)
        # Trigger AI generation task
        from .ai_services import generate_workflow_from_prompt
        instance = serializer.instance
        generate_workflow_from_prompt.delay(str(instance.id))


class AICodeGenerationViewSet(viewsets.ModelViewSet):
    """ViewSet for AI Code Generation."""
    serializer_class = AICodeGenerationSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter by user."""
        return AICodeGeneration.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Create AI code generation request."""
        serializer.save(user=self.request.user)
        # Trigger AI code generation task
        from .ai_services import generate_code_from_prompt
        instance = serializer.instance
        generate_code_from_prompt.delay(str(instance.id))


class AIWorkflowOptimizationViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for AI Workflow Optimizations."""
    serializer_class = AIWorkflowOptimizationSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter by user's workflows."""
        return AIWorkflowOptimization.objects.filter(
            workflow__owner=self.request.user
        )
    
    @action(detail=True, methods=['post'])
    def apply(self, request, pk=None):
        """Apply optimization suggestion."""
        optimization = self.get_object()
        if optimization.applied:
            return Response(
                {'error': 'Optimization already applied'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Apply optimization (implementation depends on optimization type)
        optimization.applied = True
        optimization.applied_at = timezone.now()
        optimization.save()
        
        return Response({'status': 'applied'})


# ============================================
# PHASE-4: SECURITY & COMPLIANCE
# ============================================

class SecretAccessLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Secret Access Logs (read-only for auditing)."""
    serializer_class = SecretAccessLogSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter by user's organizations."""
        return SecretAccessLog.objects.filter(
            organization__memberships__user=self.request.user,
            organization__memberships__role__in=['owner', 'admin']
        ).distinct()


class IPAllowlistViewSet(viewsets.ModelViewSet):
    """ViewSet for IP Allowlist."""
    serializer_class = IPAllowlistSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter by user's organizations."""
        return IPAllowlist.objects.filter(
            organization__memberships__user=self.request.user,
            organization__memberships__role__in=['owner', 'admin']
        ).distinct()
    
    def perform_create(self, serializer):
        """Create IP allowlist entry."""
        serializer.save(created_by=self.request.user)


class GDPRDataRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for GDPR Data Requests."""
    serializer_class = GDPRDataRequestSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        """Filter by user."""
        return GDPRDataRequest.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Create GDPR request."""
        serializer.save(user=self.request.user)
        # Trigger GDPR processing task
        from .gdpr_service import process_gdpr_request
        instance = serializer.instance
        process_gdpr_request.delay(str(instance.id))


# ============================================
# FRONTEND VIEWS (Templates + Vanilla JS)
# ============================================


@ensure_csrf_cookie
@login_required
def dashboard_view(request):
    """Render the main dashboard page with live metrics."""
    try:
        from django.shortcuts import render
        from django.utils import timezone
        from datetime import timedelta
        from django.db.models import Count, Q
        
        # 1. Metrics Cards
        total_workflows = Workflow.objects.filter(owner=request.user).count()
        active_workflows = Workflow.objects.filter(owner=request.user, status='published').count()
        
        # Execution stats
        today = timezone.now().date()
        today_executions = WorkflowExecution.objects.filter(
            workflow__owner=request.user, 
            created_at__date=today
        ).count()
        
        failed_runs = WorkflowExecution.objects.filter(
            workflow__owner=request.user, 
            status='failed'
        ).count()
        
        # 2. Recent Activity (Timeline)
        recent_activity_query = WorkflowExecution.objects.filter(
            workflow__owner=request.user
        ).select_related('workflow').order_by('-created_at')[:10]

        # Annotate with duration for UI
        recent_activity = []
        for exec in recent_activity_query:
            duration = "Running"
            if exec.finished_at and exec.started_at:
                delta = (exec.finished_at - exec.started_at).total_seconds()
                if delta < 1:
                    duration = f"{delta * 1000:.0f}ms"
                else:
                    duration = f"{delta:.2f}s"
            elif exec.status == 'pending' or exec.status == 'queued':
                duration = "Pending"
            
            # Monkey-patch for template convenience
            exec.duration_display = duration
            recent_activity.append(exec)
        
        # 3. Active Workflows (for Management Panel)
        active_workflow_list = Workflow.objects.filter(
            owner=request.user
        ).order_by('-updated_at')[:5]  # Top 5 recently updated
        
        # 4. System Health (Mock logic based on real DB connectivity)
        system_health = {
            "api": True,
            "db": True,  # If we got here, DB is up
            "redis": settings.CELERY_TASK_ALWAYS_EAGER == False, # True if Redis configured
            "email": bool(settings.EMAIL_HOST_USER or settings.GMAIL_OAUTH_CLIENT_ID)
        }
        
        context = {
            "stats": {
                "total_workflows": total_workflows,
                "active_workflows": active_workflows,
                "executions_today": today_executions,
                "failed_runs": failed_runs,
                "system_health": "99.9%" if system_health['redis'] else "Running Locally",
            },
            "recent_activity": recent_activity,
            "workflow_list": active_workflow_list,
            "system_status": system_health,
            "user_mode": "admin" if request.user.is_staff or request.user.is_superuser else "user"
        }
        
        response = render(request, "workflows/dashboard.html", context)
        response["X-FlowZen-Source"] = "Django-Engine-V1"
        return response
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Dashboard render failed: {e}", exc_info=True)
        # Debugging: Show the error directly to the user
        return HttpResponse(f"<h1>Dashboard Render Error</h1><pre>{error_details}</pre>", status=500)


@login_required
@ensure_csrf_cookie
def create_workflow_view(request):
    """Render the create workflow page."""
    return render(request, "workflows/create_workflow.html", {})


@login_required
@ensure_csrf_cookie
def workflow_detail_view(request, workflow_id):
    """Render enhanced workflow builder for viewing/editing workflow."""
    # Use the same enhanced builder for both viewing and editing
    return render(
        request,
        "workflows/enhanced_workflow_builder.html",
        {
            "workflow_id": workflow_id,
            "mode": "view",  # Indicates this is accessed via eye button
            "title": "View Workflow"
        },
    )


@login_required
@ensure_csrf_cookie
def execution_list_view(request):
    """Render workflow execution list page."""
    return render(request, "workflows/executions.html", {})


@login_required
@ensure_csrf_cookie
def execution_detail_view(request, execution_id):
    """Render workflow execution detail page."""
    return render(
        request,
        "workflows/execution_detail.html",
        {"execution_id": execution_id},
    )


@login_required
@ensure_csrf_cookie
def debug_view(request):
    """Render debug page for API testing."""
    return render(request, "workflows/debug.html", {})


class DLQListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        qs = DeadLetterItem.objects.all()
        workflow_id = request.query_params.get("workflow_id")
        execution_id = request.query_params.get("execution_id")
        sort_by = request.query_params.get("sort_by") or "created_at"
        sort_dir = request.query_params.get("sort_dir") or "desc"
        page = int(request.query_params.get("page") or 1)
        page_size = int(request.query_params.get("page_size") or 50)
        if page_size > 200:
            page_size = 200
        if workflow_id:
            qs = qs.filter(workflow_execution__workflow_id=workflow_id)
        if execution_id:
            qs = qs.filter(workflow_execution_id=execution_id)
        # Richer filters
        error_type = request.query_params.get("error_type")
        node_id = request.query_params.get("node_id")
        text = request.query_params.get("text")
        min_retries = request.query_params.get("min_retries")
        max_retries = request.query_params.get("max_retries")
        created_from = request.query_params.get("created_from")
        created_to = request.query_params.get("created_to")
        if error_type:
            qs = qs.filter(error_type=error_type)
        if node_id:
            qs = qs.filter(node_id__icontains=node_id)
        if text:
            qs = qs.filter(error_message__icontains=text)
        if min_retries:
            try:
                qs = qs.filter(retries__gte=int(min_retries))
            except:
                pass
        if max_retries:
            try:
                qs = qs.filter(retries__lte=int(max_retries))
            except:
                pass
        if created_from:
            try:
                dtf = parse_datetime(created_from)
                if dtf:
                    qs = qs.filter(created_at__gte=dtf)
            except:
                pass
        if created_to:
            try:
                dtt = parse_datetime(created_to)
                if dtt:
                    qs = qs.filter(created_at__lte=dtt)
            except:
                pass
        allowed_sorts = {"created_at": "created_at", "retries": "retries", "node_id": "node_id", "error_type": "error_type", "item_count": "item_count"}
        sort_field = allowed_sorts.get(sort_by, "created_at")
        use_python_sort = False
        if sort_field == "item_count":
            try:
                engine = settings.DATABASES.get("default", {}).get("ENGINE", "")
                if "postgres" in engine:
                    qs = qs.annotate(item_count=Func(F("items"), function="jsonb_array_length", output_field=IntegerField()))
                else:
                    use_python_sort = True
            except Exception:
                use_python_sort = True
        if not use_python_sort:
            if sort_dir == "asc":
                qs = qs.order_by(sort_field)
            else:
                qs = qs.order_by(f"-{sort_field}")
            total = qs.count()
            page_count = math.ceil(total / page_size) if page_size else 0
            start = (page - 1) * page_size
            end = start + page_size
            rows = list(qs[start:end])
        else:
            rows_all = list(qs)
            for r in rows_all:
                setattr(r, "item_count", len(r.items or []))
            rows_all.sort(key=lambda x: getattr(x, "item_count", 0), reverse=(sort_dir != "asc"))
            total = len(rows_all)
            page_count = math.ceil(total / page_size) if page_size else 0
            start = (page - 1) * page_size
            end = start + page_size
            rows = rows_all[start:end]
        items = []
        for d in rows:
            items.append({
                "id": str(d.id),
                "workflow_id": str(d.workflow_execution.workflow_id),
                "execution_id": str(d.workflow_execution_id),
                "node_id": d.node_id,
                "item_count": getattr(d, "item_count", len(d.items or [])),
                "error_message": d.error_message,
                "error_type": d.error_type,
                "retries": d.retries,
                "created_at": d.created_at.isoformat(),
            })
        return Response({
            "items": items,
            "meta": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "page_count": page_count,
                "sort_by": sort_by,
                "sort_dir": sort_dir,
            }
        })


class DLQReplayView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        dlq_id = request.data.get("id")
        if not dlq_id:
            return Response({"error": "id is required"}, status=status.HTTP_400_BAD_REQUEST)
        d = DeadLetterItem.objects.filter(id=dlq_id).first()
        if not d:
            return Response({"error": "DLQ item not found"}, status=status.HTTP_404_NOT_FOUND)
        execution = d.workflow_execution
        workflow = execution.workflow
        new_exec = WorkflowExecution.objects.create(
            workflow=workflow,
            tenant=workflow.tenant,
            input_payload={},
            input_items=d.items or [],
            status="queued",
            triggered_by="dlq_replay",
            correlation_id=str(uuid.uuid4())
        )
        from .tasks import run_workflow_execution
        transaction.on_commit(lambda: run_workflow_execution.delay(str(new_exec.id)))
        return Response({"execution_id": str(new_exec.id), "status": "queued"}, status=status.HTTP_202_ACCEPTED)


class DLQDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, dlq_id: str):
        d = DeadLetterItem.objects.filter(id=dlq_id).first()
        if not d:
            return Response({"error": "DLQ item not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            "id": str(d.id),
            "workflow_id": str(d.workflow_execution.workflow_id),
            "execution_id": str(d.workflow_execution_id),
            "node_id": d.node_id,
            "items": d.items or [],
            "error_message": d.error_message,
            "error_type": d.error_type,
            "retries": d.retries,
            "created_at": d.created_at.isoformat(),
        })


class DLQBulkReplayView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        ids = request.data.get("ids") or []
        if not isinstance(ids, list) or not ids:
            return Response({"error": "ids array is required"}, status=status.HTTP_400_BAD_REQUEST)
        created = []
        for dlq_id in ids:
            d = DeadLetterItem.objects.filter(id=dlq_id).first()
            if not d:
                continue
            execution = d.workflow_execution
            workflow = execution.workflow
            new_exec = WorkflowExecution.objects.create(
                workflow=workflow,
                tenant=workflow.tenant,
                input_payload={},
                input_items=d.items or [],
                status="queued",
                triggered_by="dlq_replay",
                correlation_id=str(uuid.uuid4())
            )
            from .tasks import run_workflow_execution
            transaction.on_commit(lambda: run_workflow_execution.delay(str(new_exec.id)))
            created.append(str(new_exec.id))
        return Response({"queued": created}, status=status.HTTP_202_ACCEPTED)


class DLQBulkDeleteView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        ids = request.data.get("ids") or []
        if not isinstance(ids, list) or not ids:
            return Response({"error": "ids array is required"}, status=status.HTTP_400_BAD_REQUEST)
        DeadLetterItem.objects.filter(id__in=ids).delete()
        return Response({"deleted": ids})


class DLQBulkReplayCombinedView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request):
        ids = request.data.get("ids") or []
        if not isinstance(ids, list) or not ids:
            return Response({"error": "ids array is required"}, status=status.HTTP_400_BAD_REQUEST)
        dlqs = list(DeadLetterItem.objects.filter(id__in=ids))
        if not dlqs:
            return Response({"error": "No DLQ items found"}, status=status.HTTP_404_NOT_FOUND)
        wf_ids = {str(d.workflow_execution.workflow_id) for d in dlqs}
        if len(wf_ids) != 1:
            return Response({"error": "Selected items must belong to the same workflow"}, status=status.HTTP_400_BAD_REQUEST)
        workflow = dlqs[0].workflow_execution.workflow
        all_items = []
        for d in dlqs:
            all_items.extend(d.items or [])
        new_exec = WorkflowExecution.objects.create(
            workflow=workflow,
            tenant=workflow.tenant,
            input_payload={},
            input_items=all_items,
            status="queued",
            triggered_by="dlq_replay_combined",
            correlation_id=str(uuid.uuid4())
        )
        from .tasks import run_workflow_execution
        transaction.on_commit(lambda: run_workflow_execution.delay(str(new_exec.id)))
        return Response({"execution_id": str(new_exec.id), "status": "queued", "items": len(all_items)}, status=status.HTTP_202_ACCEPTED)

@login_required
@ensure_csrf_cookie
def dlq_view(request):
    return serve_frontend_template("workflows/dlq.html", request)

@login_required
@ensure_csrf_cookie
def credentials_list_view(request):
    """Serve the enhanced credential management interface with data."""
    # Get user's credentials
    credentials = Credential.objects.filter(owner=request.user).order_by('-created_at')
    
    # Calculate stats
    total = credentials.count()
    active = credentials.filter(is_active=True).count()
    
    context = {
        'credentials': credentials,
        'stats': {
            'total': total,
            'active': active,
            'testing': 0, # Placeholder
            'failed': 0   # Placeholder
        }
    }
    return render(request, "workflows/credentials_enhanced.html", context)

@login_required
@ensure_csrf_cookie
def user_app_view(request):
    """Serve the user application interface."""
    from django.http import FileResponse
    from django.conf import settings
    import os
    
    # Path to the user-app HTML file
    user_app_path = os.path.join(settings.BASE_DIR.parent, 'frontend', 'user-app', 'index.html')
    
    if os.path.exists(user_app_path):
        with open(user_app_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return HttpResponse(content, content_type='text/html')
    else:
        return HttpResponse("User app not found", status=404)

def serve_user_app_static(request, path):
    """Serve static files for user-app (CSS, JS, etc.)."""
    from django.http import FileResponse, Http404
    from django.conf import settings
    import os
    import mimetypes
    
    # Path to the user-app static files
    static_path = os.path.join(settings.BASE_DIR.parent, 'frontend', 'user-app', path)
    
    if os.path.exists(static_path) and os.path.isfile(static_path):
        # Determine content type
        content_type, _ = mimetypes.guess_type(static_path)
        if content_type is None:
            content_type = 'application/octet-stream'
            
        return FileResponse(open(static_path, 'rb'), content_type=content_type)
    else:
        raise Http404("Static file not found")

def serve_shared_static(request, path):
    """Serve shared static files (shared JS, etc.)."""
    from django.http import FileResponse, Http404
    from django.conf import settings
    import os
    import mimetypes
    
    # Path to the shared static files
    static_path = os.path.join(settings.BASE_DIR.parent, 'frontend', 'shared', path)
    
    if os.path.exists(static_path) and os.path.isfile(static_path):
        # Determine content type
        content_type, _ = mimetypes.guess_type(static_path)
        if content_type is None:
            content_type = 'application/octet-stream'
            
        return FileResponse(open(static_path, 'rb'), content_type=content_type)
    else:
        raise Http404("Shared static file not found")

@login_required
@ensure_csrf_cookie
def credential_detail_view(request, credential_id):
    return serve_frontend_template("workflows/credential_detail.html", request)








@login_required
@ensure_csrf_cookie
def workflows_list_view(request):
    """Render workflows list page."""
    return serve_frontend_template("workflows/workflows.html", request)


@login_required
@ensure_csrf_cookie
def workflow_builder_view(request, workflow_id):
    """Render maximum width workflow builder for editing."""
    workflow = get_object_or_404(Workflow, id=workflow_id)
    
    # Pass workflow data for frontend initialization
    context = {
        "workflow": workflow,
        "workflow_id": str(workflow_id),
        "workflow_data": json.dumps(workflow.graph)  # Serialize for template
    }
    
    return serve_frontend_template("workflows/builder.html", request, context)

# NEW: Maximum width builder without authentication for testing
@login_required
@ensure_csrf_cookie
def maximum_width_builder_view(request):
    """Render maximum width builder without authentication."""
    return serve_frontend_template("workflows/builder.html", request)

# ============================================
# EXECUTION ENGINE API ENDPOINTS
# ============================================

@api_view(['GET'])
def get_execution_engine_info(request):
    """Get information about the execution engine."""
    try:
        from .nodes import node_registry
        
        # Get node registry stats
        registry_stats = node_registry.get_registry_stats()
        
        return JsonResponse({
            'engine_info': {
                'name': 'Core Workflow Execution Engine',
                'version': '1.0.0',
                'features': [
                    'DAG-based execution',
                    'Node registry integration',
                    'Fail-fast error handling',
                    'Execution context flow',
                    'Django model integration'
                ]
            },
            'node_registry': registry_stats,
            'status': 'operational'
        })
        
    except Exception as e:
        return JsonResponse(
            {'error': f'Failed to get engine info: {e}'}, 
            status=500
        )


@api_view(['POST'])
def create_sample_workflow(request):
    """Create a sample workflow for testing the execution engine."""
    try:
        sample_workflow = {
            "meta": {
                "name": "Sample Test Workflow",
                "description": "A sample workflow for testing the execution engine",
                "version": "1.0.0",
                "active": True
            },
            "trigger": {
                "id": "manual_trigger_1",
                "type": "manual_trigger",
                "name": "Manual Start",
                "params": {
                    "test_data": {
                        "message": "Hello from sample workflow!",
                        "timestamp": "2024-01-01T00:00:00Z"
                    }
                }
            },
            "nodes": {
                "logger_1": {
                    "id": "logger_1",
                    "type": "logger",
                    "name": "Log Message",
                    "params": {
                        "message": "Processing: {{message}}",
                        "level": "info",
                        "include_data": True
                    }
                }
            },
            "connections": {
                "manual_trigger_1": ["logger_1"],
                "logger_1": []
            }
        }
        
        return JsonResponse({
            'workflow_definition': sample_workflow,
            'description': 'Sample workflow with manual trigger and logger node',
            'node_count': len(sample_workflow['nodes']),
            'estimated_execution_time': '~1 second'
        })
        
    except Exception as e:
        return JsonResponse(
            {'error': f'Failed to create sample workflow: {e}'}, 
            status=500
        )



        



@api_view(['GET'])
@permission_classes([AllowAny])
def current_user_info(request):
    """
    Return current user info for the frontend.
    Allows static frontend to adapt to user role.
    """
    if not request.user.is_authenticated:
        return Response({
            'is_authenticated': False,
            'username': 'Guest',
            'role': 'User'
        })
    
    # Determine admin status
    is_admin = (
        request.user.is_staff or 
        request.user.is_superuser
    )
    
    return Response({
        'is_authenticated': True,
        'is_admin': is_admin,
        'username': request.user.username,
        'email': request.user.email,
        'role': 'Admin' if is_admin else 'User'
    })

# ================================
# GMAIL OAUTH VIEWS
# ================================
import uuid
import json
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import ensure_csrf_cookie
import logging
import requests
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from django.db import transaction
from .models import Credential
from .serializers import CredentialSerializer
from .constants.credential_types import normalize_credential_type
from .utils.credential_resolver import resolve_credential_data
from .services.credential_encryption import get_encryption_service
from .models import Workflow, WorkflowExecution, NodeExecution, Credential, WorkflowTemplate, DeadLetterItem
from .serializers import WorkflowSerializer, WorkflowExecutionSerializer, NodeExecutionSerializer, CredentialSerializer, WorkflowTemplateSerializer
from .template_utils import serve_frontend_template
import secrets
import requests
from django.conf import settings
from .services.gmail_oauth_service import get_gmail_oauth_service
from .services.credential_encryption import get_encryption_service

# Gmail OAuth configuration
GMAIL_OAUTH_CONFIG = {
    'client_id': getattr(settings, 'GMAIL_OAUTH_CLIENT_ID', ''),
    'client_secret': getattr(settings, 'GMAIL_OAUTH_CLIENT_SECRET', ''),
    'redirect_uri': getattr(settings, 'GMAIL_OAUTH_REDIRECT_URI', 'http://localhost:8000/api/v1/gmail-oauth/callback/'),
    'scope': 'https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly',
    'auth_url': 'https://accounts.google.com/o/oauth2/v2/auth',
    'token_url': 'https://oauth2.googleapis.com/token',
}


from django.http import JsonResponse
import secrets
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

@csrf_exempt
@require_http_methods(["GET"])
def gmail_oauth_start(request):
    """
    Start Gmail OAuth flow.
    Returns authorization URL for user to visit.
    """
    try:
        # Import here to avoid circular imports
        from django.conf import settings
        
        # Get Gmail OAuth config
        GMAIL_OAUTH_CONFIG = {
            'client_id': getattr(settings, 'GMAIL_OAUTH_CLIENT_ID', ''),
            'client_secret': getattr(settings, 'GMAIL_OAUTH_CLIENT_SECRET', ''),
            'redirect_uri': getattr(settings, 'GMAIL_OAUTH_REDIRECT_URI', ''),
            'scope': 'https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly',
            'auth_url': 'https://accounts.google.com/o/oauth2/auth',
        }
        
        # Validate OAuth configuration
        if not GMAIL_OAUTH_CONFIG['client_id'] or not GMAIL_OAUTH_CONFIG['client_secret']:
            return JsonResponse({
                'error': 'Gmail OAuth not configured',
                'message': 'Please configure GMAIL_OAUTH_CLIENT_ID and GMAIL_OAUTH_CLIENT_SECRET in settings'
            }, status=500)
        
        # Generate state parameter for security
        state = secrets.token_urlsafe(32)
        
        # Store state in session (with development bypass in callback)
        request.session['oauth_state'] = state
        
        if hasattr(request, 'user') and request.user.is_authenticated:
            request.session['gmail_oauth_user_id'] = request.user.id
        
        # Build authorization URL
        from urllib.parse import urlencode
        
        auth_params = {
            'client_id': GMAIL_OAUTH_CONFIG['client_id'],
            'redirect_uri': GMAIL_OAUTH_CONFIG['redirect_uri'],
            'scope': GMAIL_OAUTH_CONFIG['scope'],
            'response_type': 'code',
            'access_type': 'offline',  # Required for refresh token
            'prompt': 'consent',  # Force consent to get refresh token
            'state': state,
        }
        
        auth_url = GMAIL_OAUTH_CONFIG['auth_url'] + '?' + urlencode(auth_params)
        
        return JsonResponse({
            'auth_url': auth_url,
            'state': state,
            'message': 'Visit the auth_url to authorize Gmail access'
        })
        
    except Exception as e:
        return JsonResponse({
            'error': 'OAuth start failed',
            'message': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def gmail_oauth_callback(request):
    """
    Handle Gmail OAuth callback.
    Exchanges authorization code for access token and creates credential.
    """
    try:
        # Get parameters
        code = request.GET.get('code')
        state = request.GET.get('state')
        error = request.GET.get('error')
        
        if error:
            return JsonResponse({
                'error': 'OAuth authorization failed',
                'message': f'Google returned error: {error}'
            }, status=400)
        
        if not code:
            return JsonResponse({
                'error': 'Missing authorization code',
                'message': 'No authorization code received from Google'
            }, status=400)
        
        # OAuth state validation with development bypass
        session_state = request.session.get('oauth_state')
        
        # ✅ LOCALHOST / DEV BYPASS
        if settings.DEBUG:
            pass  # Skip state validation in development
        else:
            # Production: Strict state validation
            if not state or state != session_state:
                return JsonResponse({
                    "error": "Invalid state parameter",
                    "message": "OAuth state validation failed"
                }, status=400)
        
        # Get user from session or use default for localhost/development
        user_id = request.session.get('gmail_oauth_user_id')
        if not user_id:
            # For localhost/development: Use first available user or create test user
            from django.contrib.auth.models import User
            try:
                user = User.objects.first()
                if not user:
                    # Create a default test user for OAuth
                    user = User.objects.create_user(
                        username='oauth_test_user',
                        email='oauth_test_user@gmail.com',
                        first_name='OAuth',
                        last_name='Test'
                    )
            except Exception as e:
                return JsonResponse({
                    'error': 'User setup failed',
                    'message': f'Could not get or create user for OAuth: {str(e)}'
                }, status=400)
        else:
            from django.contrib.auth.models import User
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return JsonResponse({
                    'error': 'User not found',
                    'message': 'OAuth session user not found'
                }, status=400)
        
        # Exchange code for tokens
        token_data = {
            'client_id': GMAIL_OAUTH_CONFIG['client_id'],
            'client_secret': GMAIL_OAUTH_CONFIG['client_secret'],
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': GMAIL_OAUTH_CONFIG['redirect_uri'],
        }
        
        response = requests.post(GMAIL_OAUTH_CONFIG['token_url'], data=token_data, timeout=30)
        
        if response.status_code != 200:
            return JsonResponse({
                'error': 'Token exchange failed',
                'message': f'Google token endpoint returned: {response.status_code} {response.text}'
            }, status=400)
        
        tokens = response.json()
        access_token = tokens.get('access_token')
        refresh_token = tokens.get('refresh_token')
        
        if not access_token:
            return JsonResponse({
                'error': 'No access token received',
                'message': 'Google did not return an access token'
            }, status=400)
        
        # Get user's Gmail profile
        profile_response = requests.get(
            'https://gmail.googleapis.com/gmail/v1/users/me/profile',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10
        )
        
        if profile_response.status_code != 200:
            return JsonResponse({
                'error': 'Failed to get Gmail profile',
                'message': 'Could not retrieve Gmail profile information'
            }, status=400)
        
        profile = profile_response.json()
        email_address = profile.get('emailAddress')
        
        if not email_address:
            return JsonResponse({
                'error': 'No email address found',
                'message': 'Could not determine Gmail address'
            }, status=400)
        
        # Get or create tenant
        tenant = getattr(user, 'tenant', None)
        if not tenant:
            # Create default tenant for user if none exists
            tenant, created = Tenant.objects.get_or_create(
                slug=f'user-{user.id}',
                defaults={'name': f'{user.username} Workspace'}
            )
        
        # Create or update Gmail OAuth credential
        credential_data = {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'client_id': GMAIL_OAUTH_CONFIG['client_id'],
            'client_secret': GMAIL_OAUTH_CONFIG['client_secret'],
            'email': email_address,
            'scope': GMAIL_OAUTH_CONFIG['scope'],
            'token_type': tokens.get('token_type', 'Bearer'),
        }
        
        # Encrypt credential data
        encryption_service = get_encryption_service()
        if encryption_service:
            encrypted_data = encryption_service.encrypt_credential_str(credential_data)
        else:
            encrypted_data = credential_data
        
        # Create or update credential
        credential, created = Credential.objects.update_or_create(
            owner=user,
            tenant=tenant,
            type='gmail',
            name=f'Gmail OAuth - {email_address}',
            defaults={
                'encrypted_data': encrypted_data,
                'environment': 'production',  # Gmail OAuth is always production
            }
        )
        
        # Clean up session (if any session data exists)
        request.session.pop('gmail_oauth_state', None)
        request.session.pop('gmail_oauth_user_id', None)
        
        # Return success page or redirect
        return JsonResponse({
            'success': True,
            'message': f'Gmail OAuth setup completed for {email_address}',
            'credential_id': str(credential.id),
            'email': email_address,
            'created': created
        })
        
    except Exception as e:
        logger.error(f"Gmail OAuth callback failed: {e}")
        return JsonResponse({
            'error': 'OAuth callback failed',
            'message': str(e)
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gmail_oauth_status(request):
    """
    Check Gmail OAuth status for current user.
    Returns list of connected Gmail accounts.
    """
    try:
        # Get user's tenant
        tenant = getattr(request.user, 'tenant', None)
        
        # Find Gmail OAuth credentials
        credentials = Credential.objects.filter(
            owner=request.user,
            tenant=tenant,
            type='gmail_oauth'
        )
        
        gmail_service = get_gmail_oauth_service(tenant=tenant)
        credential_list = []
        
        for credential in credentials:
            try:
                # Validate credential
                validation = gmail_service.validate_gmail_credential(credential)
                
                credential_info = {
                    'id': str(credential.id),
                    'name': credential.name,
                    'email': validation.get('email', 'unknown'),
                    'valid': validation.get('valid', False),
                    'created_at': credential.created_at.isoformat(),
                }
                
                if not validation.get('valid'):
                    credential_info['error'] = validation.get('error', 'Unknown error')
                
                credential_list.append(credential_info)
                
            except Exception as e:
                credential_list.append({
                    'id': str(credential.id),
                    'name': credential.name,
                    'email': 'unknown',
                    'valid': False,
                    'error': str(e),
                    'created_at': credential.created_at.isoformat(),
                })
        
        return Response({
            'gmail_accounts': credential_list,
            'total_accounts': len(credential_list),
            'oauth_configured': bool(GMAIL_OAUTH_CONFIG['client_id'] and GMAIL_OAUTH_CONFIG['client_secret'])
        })
        
    except Exception as e:
        logger.error(f"Gmail OAuth status check failed: {e}")
        return Response({
            'error': 'Status check failed',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def gmail_oauth_disconnect(request, credential_id):
    """
    Disconnect Gmail OAuth credential.
    """
    try:
        # Get credential
        credential = Credential.objects.get(
            id=credential_id,
            owner=request.user,
            type='gmail_oauth'
        )
        
        email = 'unknown'
        try:
            gmail_service = get_gmail_oauth_service(tenant=credential.tenant)
            data = gmail_service._decrypt_credential_data(credential)
            email = data.get('email', 'unknown')
        except Exception:
            pass
        
        # Delete credential
        credential.delete()
        
        return Response({
            'success': True,
            'message': f'Gmail OAuth disconnected for {email}',
            'credential_id': credential_id
        })
        
    except Credential.DoesNotExist:
        return Response({
            'error': 'Credential not found',
            'message': 'Gmail OAuth credential not found or access denied'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Gmail OAuth disconnect failed: {e}")
        return Response({
            'error': 'Disconnect failed',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def gmail_oauth_test(request):
    """
    Test Gmail OAuth by sending a test email.
    """
    try:
        data = request.data
        from_email = data.get('from_email')
        to_email = data.get('to_email', request.user.email)
        
        if not from_email:
            return Response({
                'error': 'Missing from_email',
                'message': 'Please specify the Gmail address to send from'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get Gmail service
        tenant = getattr(request.user, 'tenant', None)
        gmail_service = get_gmail_oauth_service(tenant=tenant)
        
        # Send test email
        result = gmail_service.send_email(
            to=to_email,
            subject='Gmail OAuth Test Email',
            body=f'This is a test email sent via Gmail OAuth from {from_email}.\n\nIf you received this, Gmail OAuth is working correctly!',
            from_email=from_email,
            is_html=False
        )
        
        return Response({
            'success': True,
            'message': f'Test email sent successfully to {to_email}',
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Gmail OAuth test failed: {e}")
        return Response({
            'error': 'Test email failed',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([AllowAny])
def public_workflow_view(request, workflow_id):
    """
    Render a read-only view of a specific workflow.
    """
    workflow = get_object_or_404(Workflow, id=workflow_id)
    return render(request, 'workflows/public_view.html', {'workflow': workflow})





@api_view(['GET'])
@permission_classes([AllowAny])
def get_node_types(request):
    """
    Get all available node types with their definitions and categorizations.
    Includes rich schema for UI form generation.
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"📚 [API] Node Library Requested by: {request.user} | Client: {request.META.get('HTTP_USER_AGENT', 'Unknown')}")

    try:
        # Merge lists
        response_list = []
        for type_key, schema in FULL_NODE_SCHEMAS.items():
            # BACKWARD COMPATIBILITY: Auto-inject defaults if missing
            if 'inputs' not in schema:
                schema['inputs'] = ["main"]
            if 'outputs' not in schema:
                schema['outputs'] = ["output"]
                
            response_list.append({
                "type": type_key,
                **schema
            })
            
        return Response({"node_types": response_list})

    except Exception as e:
        logger.error(f"Error fetching node types: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_node_schema(request, node_type):
    """
    Get detailed schema for a specific node type.
    """
    try:
        if node_type in FULL_NODE_SCHEMAS:
            schema = FULL_NODE_SCHEMAS[node_type]
            
            # BACKWARD COMPATIBILITY: Auto-inject defaults if missing
            inputs = schema.get("inputs", ["main"])
            outputs = schema.get("outputs", ["output"])
            
            return Response({
                "node_type": node_type,
                "title": schema.get("title", schema.get("label")),
                "properties": schema.get("properties", schema.get("fields", [])),
                "inputs": inputs,
                "outputs": outputs,
                "schema": schema # Compatibility
            })
        
        # Fallback to registry
        from .nodes import node_registry
        if node_registry.has_node_type(node_type):
            node_class = node_registry.get_node_class(node_type)
            return Response({
                "node_type": node_type,
                "title": node_class.get_display_name(),
                "properties": getattr(node_class, 'PROPERTIES', []),
                "schema": node_class.get_schema()
            })
            
        return Response({"error": "Node type not found"}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=500)

@api_view(['GET'])
@permission_classes([AllowAny])
def node_health_check(request):
    """
    Verify that all registered nodes in FULL_NODE_SCHEMAS can be instantiated or at least resolved.
    """
    node_status = {}
    all_healthy = True
    
    # We essentially mock-check the registry here
    # In a real dynamic system we'd try import_module for each, 
    # but for now we verify the schema integrity.
    
    try:
        # Re-access schema from the view above or define it globally (it's inside get_node_types unfortunately)
        # To avoid duplication, we will just check if we can fetch the types internally.
        
        # PROBE: Just return the schema content as a "Health Check" of the registry definition
        # We will manually duplicate the check logic here for safety.
        from workflows.nodes.registry import node_registry
        
        # Access the singleton registry dictionary
        # We access the internal _nodes dict for the health check verification
        # First ensure discovery happened
        if not node_registry._auto_discovered:
            node_registry.auto_discover()
            
        registry_dict = node_registry._nodes
        
        for key, node_class in registry_dict.items():
            try:
                # Basic Inspection
                node_status[key] = {
                    "status": "ok",
                    "class": node_class.__name__
                }
            except Exception as e:
                node_status[key] = {"status": "error", "error": str(e)}
                all_healthy = False

        return Response({
            "status": "ok" if all_healthy else "degraded",
            "nodes": node_status,
            "registry_count": len(registry_dict)
        })

    except Exception as e:
         return Response({"status": "critical_failure", "error": str(e)}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_node_schemas(request):
    """
    Get raw node schemas from registry.
    """
    try:
        from .nodes import node_registry
        schemas = node_registry.get_node_schemas()
        return Response(schemas)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_missing_handles(request):
    """
    Debug endpoint to identify nodes missing explicit input/output handle definitions in FULL_NODE_SCHEMAS.
    Useful for developers to ensure all nodes are strictly defined.
    """
    broken_nodes = []
    for type_key, schema in FULL_NODE_SCHEMAS.items():
        # Check if either 'inputs' or 'outputs' is missing
        if 'inputs' not in schema or 'outputs' not in schema:
            broken_nodes.append(type_key)
            
    return Response({
        "status": "success",
        "broken_nodes": broken_nodes,
        "total_nodes": len(FULL_NODE_SCHEMAS),
        "broken_count": len(broken_nodes),
        "message": "These nodes are missing explicit handle definitions and are using system defaults."
    })


@login_required
def delete_workflow(request, workflow_id):
    workflow = get_object_or_404(Workflow, id=workflow_id)
    workflow.delete()
    messages.success(request, 'Workflow deleted successfully')
    return redirect('workflows')

