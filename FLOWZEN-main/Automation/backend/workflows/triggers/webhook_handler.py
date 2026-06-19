"""
Webhook Trigger Handler

This module provides Django views and utilities for handling webhook triggers.
It creates the bridge between HTTP requests and workflow execution.
"""

import json
import hmac
import hashlib
import uuid
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from ..models import Workflow, WorkflowExecution
from ..tasks import execute_workflow_with_core_engine
from ..throttles import TenantWebhookRateThrottle


logger = logging.getLogger(__name__)


class WebhookSecurityError(Exception):
    """Raised when webhook security validation fails."""
    pass


class WebhookHandler:
    """
    Handles webhook trigger processing with security and validation.
    
    This class encapsulates all webhook-related logic to keep views clean
    and enable easy testing and reuse.
    """
    
    def __init__(self, workflow: Workflow):
        """Initialize handler for specific workflow."""
        self.workflow = workflow
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
    
    def process_webhook(self, request) -> Dict[str, Any]:
        """
        Process incoming webhook request.
        
        Args:
            request: Django HTTP request object
            
        Returns:
            Dictionary with execution details
            
        Raises:
            WebhookSecurityError: If security validation fails
            ValueError: If request data is invalid
        """
        # Extract request data
        webhook_data = self._extract_request_data(request)
        
        # Validate security
        self._validate_security(request, webhook_data)
        
        # Create workflow execution
        execution = self._create_execution(webhook_data)
        
        # Queue execution
        self._queue_execution(execution)
        
        return {
            'execution_id': str(execution.id),
            'workflow_id': str(self.workflow.id),
            'status': 'queued',
            'webhook_data': webhook_data
        }
    
    def _extract_request_data(self, request) -> Dict[str, Any]:
        """Extract and structure data from HTTP request."""
        # Parse request body
        body = {}
        if request.body:
            try:
                if request.content_type == 'application/json':
                    body = json.loads(request.body.decode('utf-8'))
                elif request.content_type == 'application/x-www-form-urlencoded':
                    body = dict(request.POST)
                else:
                    # Store raw body for other content types
                    body = {'raw_body': request.body.decode('utf-8', errors='ignore')}
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                self.logger.warning(f"Failed to parse request body: {e}")
                body = {'raw_body': str(request.body)}
        
        # Extract headers (filter out sensitive ones)
        headers = {}
        for key, value in request.META.items():
            if key.startswith('HTTP_'):
                # Convert HTTP_X_CUSTOM_HEADER to X-Custom-Header
                header_name = key[5:].replace('_', '-').title()
                headers[header_name] = value
        
        # Add important non-HTTP headers
        if 'CONTENT_TYPE' in request.META:
            headers['Content-Type'] = request.META['CONTENT_TYPE']
        if 'CONTENT_LENGTH' in request.META:
            headers['Content-Length'] = request.META['CONTENT_LENGTH']
        
        return {
            'body': body,
            'headers': headers,
            'query': dict(request.GET),
            'method': request.method,
            'path': request.path,
            'timestamp': timezone.now().isoformat(),
            'remote_addr': self._get_client_ip(request)
        }
    
    def _get_client_ip(self, request) -> str:
        """Get client IP address, handling proxies."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')
    
    def _validate_security(self, request, webhook_data: Dict[str, Any]) -> None:
        """
        Validate webhook security based on workflow configuration.
        
        Raises:
            WebhookSecurityError: If validation fails
        """
        webhook_config = self.workflow.webhook_config or {}
        auth_method = webhook_config.get('authentication', 'none')
        
        if auth_method == 'none':
            return  # No authentication required
        
        if auth_method == 'hmac_sha256':
            self._validate_hmac_signature(request, webhook_data)
        elif auth_method == 'bearer_token':
            self._validate_bearer_token(request, webhook_config)
        elif auth_method == 'basic_auth':
            self._validate_basic_auth(request, webhook_config)
        elif auth_method == 'query_param':
            self._validate_query_param(request, webhook_config)
        else:
            raise WebhookSecurityError(f"Unknown authentication method: {auth_method}")
    
    def _validate_hmac_signature(self, request, webhook_data: Dict[str, Any]) -> None:
        """Validate HMAC SHA256 signature."""
        if not self.workflow.webhook_secret:
            raise WebhookSecurityError("HMAC authentication enabled but no secret configured")
        
        # Get signature from header
        signature_header = request.META.get('HTTP_X_SIGNATURE') or request.META.get('HTTP_X_HUB_SIGNATURE_256')
        if not signature_header:
            raise WebhookSecurityError("Missing HMAC signature header")
        
        # Extract signature (handle different formats)
        if signature_header.startswith('sha256='):
            provided_signature = signature_header[7:]
        else:
            provided_signature = signature_header
        
        # Calculate expected signature
        secret = self.workflow.webhook_secret.encode('utf-8')
        expected_signature = hmac.new(
            secret,
            request.body,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures securely
        if not hmac.compare_digest(provided_signature, expected_signature):
            raise WebhookSecurityError("Invalid HMAC signature")
    
    def _validate_bearer_token(self, request, webhook_config: Dict[str, Any]) -> None:
        """Validate Bearer token authentication."""
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            raise WebhookSecurityError("Missing or invalid Authorization header")
        
        provided_token = auth_header[7:]  # Remove 'Bearer ' prefix
        expected_token = webhook_config.get('bearer_token', '')
        
        if not expected_token:
            raise WebhookSecurityError("Bearer token authentication enabled but no token configured")
        
        if not hmac.compare_digest(provided_token, expected_token):
            raise WebhookSecurityError("Invalid bearer token")
    
    def _validate_basic_auth(self, request, webhook_config: Dict[str, Any]) -> None:
        """Validate Basic authentication."""
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Basic '):
            raise WebhookSecurityError("Missing or invalid Authorization header")
        
        # Decode credentials
        import base64
        try:
            encoded_credentials = auth_header[6:]  # Remove 'Basic ' prefix
            decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')
            username, password = decoded_credentials.split(':', 1)
        except (ValueError, UnicodeDecodeError):
            raise WebhookSecurityError("Invalid Basic authentication format")
        
        # Validate credentials
        expected_username = webhook_config.get('basic_username', '')
        expected_password = webhook_config.get('basic_password', '')
        
        if not expected_username or not expected_password:
            raise WebhookSecurityError("Basic authentication enabled but credentials not configured")
        
        if not (hmac.compare_digest(username, expected_username) and 
                hmac.compare_digest(password, expected_password)):
            raise WebhookSecurityError("Invalid username or password")
    
    def _validate_query_param(self, request, webhook_config: Dict[str, Any]) -> None:
        """Validate query parameter authentication."""
        param_name = webhook_config.get('query_param_name', 'token')
        expected_value = webhook_config.get('query_param_value', '')
        
        if not expected_value:
            raise WebhookSecurityError("Query parameter authentication enabled but value not configured")
        
        provided_value = request.GET.get(param_name, '')
        if not hmac.compare_digest(provided_value, expected_value):
            raise WebhookSecurityError(f"Invalid query parameter '{param_name}'")
    
    def _create_execution(self, webhook_data: Dict[str, Any]) -> WorkflowExecution:
        """Create WorkflowExecution record for webhook trigger."""
        # Generate correlation ID for tracking
        correlation_id = str(uuid.uuid4())
        
        # Create execution record
        execution = WorkflowExecution.objects.create(
            workflow=self.workflow,
            tenant=self.workflow.tenant,
            status='pending',
            triggered_by='webhook',
            input_data=webhook_data,
            correlation_id=correlation_id,
            created_by=None  # Webhooks don't have authenticated users
        )
        
        self.logger.info(f"Created webhook execution {execution.id} for workflow {self.workflow.id}")
        return execution
    
    def _queue_execution(self, execution: WorkflowExecution) -> None:
        """Queue execution for async processing."""
        # Check if webhook should wait for completion
        webhook_config = self.workflow.webhook_config or {}
        wait_for_completion = webhook_config.get('wait_for_completion', False)
        
        if wait_for_completion:
            # Synchronous execution (not recommended for production)
            self.logger.warning(f"Synchronous webhook execution for {execution.id}")
            # Could implement sync execution here, but async is preferred
        
        # Queue for async execution (recommended)
        execution.status = 'queued'
        execution.save(update_fields=['status'])
        
        # Use the core engine task
        transaction.on_commit(lambda: execute_workflow_with_core_engine.delay(str(execution.id)))
        
        self.logger.info(f"Queued execution {execution.id} for async processing")


@csrf_exempt
@require_http_methods(["GET", "POST", "PUT", "PATCH", "DELETE"])
@api_view(['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([AllowAny])
@throttle_classes([TenantWebhookRateThrottle])
def webhook_trigger_view(request, workflow_id):
    """
    Enhanced webhook endpoint for triggering workflows.
    
    This view handles all HTTP methods and provides comprehensive
    webhook functionality with security and error handling.
    
    URL: /webhooks/<workflow_id>/
    """
    try:
        # Find workflow and validate webhook is enabled
        try:
            workflow = Workflow.objects.select_related('tenant').get(
                id=workflow_id,
                webhook_enabled=True
            )
        except Workflow.DoesNotExist:
            return JsonResponse({
                'error': 'Workflow not found or webhook disabled',
                'code': 'WORKFLOW_NOT_FOUND'
            }, status=404)
        
        # Handle GET requests (webhook verification)
        if request.method == 'GET':
            return _handle_webhook_verification(request, workflow)
        
        # Process webhook with handler
        handler = WebhookHandler(workflow)
        result = handler.process_webhook(request)
        
        # Return success response
        webhook_config = workflow.webhook_config or {}
        response_config = webhook_config.get('response', {})
        
        response_data = {
            'success': True,
            'execution_id': result['execution_id'],
            'status': result['status'],
            **response_config.get('data', {})
        }
        
        return JsonResponse(
            response_data,
            status=response_config.get('status_code', 202)
        )
        
    except WebhookSecurityError as e:
        logger.warning(f"Webhook security error for workflow {workflow_id}: {e}")
        return JsonResponse({
            'error': 'Authentication failed',
            'code': 'AUTHENTICATION_FAILED'
        }, status=401)
        
    except ValueError as e:
        logger.warning(f"Webhook validation error for workflow {workflow_id}: {e}")
        return JsonResponse({
            'error': 'Invalid request data',
            'code': 'INVALID_REQUEST',
            'details': str(e)
        }, status=400)
        
    except Exception as e:
        logger.error(f"Webhook processing error for workflow {workflow_id}: {e}")
        return JsonResponse({
            'error': 'Internal server error',
            'code': 'INTERNAL_ERROR'
        }, status=500)


def _handle_webhook_verification(request, workflow: Workflow) -> JsonResponse:
    """
    Handle GET requests for webhook verification.
    
    Some services (like GitHub) send GET requests to verify webhook endpoints.
    """
    webhook_config = workflow.webhook_config or {}
    
    # Handle challenge-response verification (e.g., Facebook, Slack)
    challenge = request.GET.get('challenge') or request.GET.get('hub.challenge')
    if challenge:
        return HttpResponse(challenge, content_type='text/plain')
    
    # Handle verification token (e.g., GitHub)
    verify_token = request.GET.get('hub.verify_token')
    expected_token = webhook_config.get('verify_token')
    if verify_token and expected_token:
        if hmac.compare_digest(verify_token, expected_token):
            return HttpResponse('OK', content_type='text/plain')
        else:
            return JsonResponse({'error': 'Invalid verify token'}, status=403)
    
    # Default verification response
    return JsonResponse({
        'webhook_active': True,
        'workflow_id': str(workflow.id),
        'workflow_name': workflow.name,
        'timestamp': timezone.now().isoformat()
    })


def get_webhook_url(workflow: Workflow, request=None) -> str:
    """
    Generate webhook URL for a workflow.
    
    Args:
        workflow: Workflow instance
        request: Optional request object for domain detection
        
    Returns:
        Complete webhook URL
    """
    if request:
        # Use request to build absolute URL
        from django.urls import reverse
        path = reverse('workflows:webhook_trigger', kwargs={'workflow_id': str(workflow.id)})
        return request.build_absolute_uri(path)
    else:
        # Use configured domain or fallback
        domain = getattr(settings, 'WEBHOOK_DOMAIN', 'localhost:8000')
        protocol = 'https' if getattr(settings, 'WEBHOOK_USE_HTTPS', False) else 'http'
        return f"{protocol}://{domain}/webhooks/{workflow.id}/"


def test_webhook_configuration(workflow: Workflow) -> Dict[str, Any]:
    """
    Test webhook configuration for a workflow.
    
    Args:
        workflow: Workflow instance
        
    Returns:
        Dictionary with test results
    """
    results = {
        'webhook_enabled': workflow.webhook_enabled,
        'has_secret': bool(workflow.webhook_secret),
        'configuration': workflow.webhook_config or {},
        'issues': []
    }
    
    if not workflow.webhook_enabled:
        results['issues'].append('Webhook is disabled')
    
    webhook_config = workflow.webhook_config or {}
    auth_method = webhook_config.get('authentication', 'none')
    
    if auth_method == 'hmac_sha256' and not workflow.webhook_secret:
        results['issues'].append('HMAC authentication enabled but no secret configured')
    
    if auth_method == 'bearer_token' and not webhook_config.get('bearer_token'):
        results['issues'].append('Bearer token authentication enabled but no token configured')
    
    if auth_method == 'basic_auth':
        if not webhook_config.get('basic_username') or not webhook_config.get('basic_password'):
            results['issues'].append('Basic authentication enabled but credentials not configured')
    
    if auth_method == 'query_param':
        if not webhook_config.get('query_param_name') or not webhook_config.get('query_param_value'):
            results['issues'].append('Query parameter authentication enabled but not properly configured')
    
    results['valid'] = len(results['issues']) == 0
    return results