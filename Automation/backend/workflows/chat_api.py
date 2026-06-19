"""
Chat API Controller

This module provides REST API endpoints for the chatbot system.
It handles chat sessions, messages, and workflow integration.
"""

import uuid
import logging
from typing import Dict, Any, Optional
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.http import JsonResponse

from .models import (
    ChatSession, ChatMessage, Workflow, WorkflowExecution, 
    Tenant, User
)
from .serializers import (
    ChatSessionSerializer, ChatMessageSerializer, 
    WorkflowExecutionSerializer
)
from .tasks import execute_workflow_with_core_engine

logger = logging.getLogger(__name__)


class ChatPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class ChatSessionViewSet(viewsets.ModelViewSet):
    """ViewSet for Chat Session CRUD operations."""
    
    serializer_class = ChatSessionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ChatPagination
    
    def get_queryset(self):
        """Filter chat sessions by user."""
        return ChatSession.objects.filter(
            user=self.request.user
        ).select_related('workflow', 'tenant')
    
    def perform_create(self, serializer):
        """Create chat session with user and tenant."""
        # Get user's default tenant (you may need to adjust this logic)
        tenant = getattr(self.request.user, 'tenant', None)
        if not tenant:
            # Fallback: get first tenant or create one
            tenant = Tenant.objects.filter(
                workflows__owner=self.request.user
            ).first()
            
        if not tenant:
            # Create a default tenant for the user
            tenant = Tenant.objects.create(
                name=f"{self.request.user.username}'s Workspace",
                slug=f"{self.request.user.username}-workspace"
            )
        
        serializer.save(
            user=self.request.user,
            tenant=tenant
        )
    
    @action(detail=True, methods=['get'])
    def messages(self, request, pk=None):
        """Get messages for a chat session."""
        session = self.get_object()
        messages = session.messages.all().order_by('created_at')
        
        page = self.paginate_queryset(messages)
        if page is not None:
            serializer = ChatMessageSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def send_message(self, request, pk=None):
        """Send a message in the chat session and trigger workflow if needed."""
        session = self.get_object()
        
        # Validate request data
        message_content = request.data.get('message', '').strip()
        if not message_content:
            return Response(
                {'error': 'Message content is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                # Create user message
                user_message = ChatMessage.objects.create(
                    session=session,
                    tenant=session.tenant,
                    message_type='user',
                    content=message_content,
                    metadata={
                        'timestamp': timezone.now().isoformat(),
                        'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                        'ip_address': self._get_client_ip(request)
                    }
                )
                
                # Update session activity
                session.last_activity_at = timezone.now()
                session.save(update_fields=['last_activity_at'])
                
                # Check if session has an associated workflow
                workflow_execution = None
                assistant_message = None
                
                if session.workflow:
                    # Trigger workflow with chat message
                    workflow_execution = self._trigger_chat_workflow(
                        session, user_message, message_content
                    )
                    
                    if workflow_execution:
                        user_message.workflow_execution = workflow_execution
                        user_message.save(update_fields=['workflow_execution'])
                        
                        # Create placeholder assistant message
                        assistant_message = ChatMessage.objects.create(
                            session=session,
                            tenant=session.tenant,
                            message_type='assistant',
                            content='Processing your request...',
                            workflow_execution=workflow_execution,
                            metadata={
                                'status': 'processing',
                                'workflow_id': str(session.workflow.id)
                            }
                        )
                else:
                    # No workflow associated - create a simple acknowledgment
                    assistant_message = ChatMessage.objects.create(
                        session=session,
                        tenant=session.tenant,
                        message_type='assistant',
                        content='I received your message. To enable workflow responses, please associate this chat with a workflow.',
                        metadata={'status': 'no_workflow'}
                    )
                
                # Prepare response
                response_data = {
                    'user_message': ChatMessageSerializer(user_message).data,
                    'assistant_message': ChatMessageSerializer(assistant_message).data if assistant_message else None,
                    'workflow_execution': WorkflowExecutionSerializer(workflow_execution).data if workflow_execution else None
                }
                
                return Response(response_data, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            logger.error(f"Error sending chat message: {e}", exc_info=True)
            return Response(
                {'error': 'Failed to send message'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _trigger_chat_workflow(self, session: ChatSession, user_message: ChatMessage, message_content: str) -> Optional[WorkflowExecution]:
        """Trigger workflow execution from chat message."""
        try:
            workflow = session.workflow
            if not workflow:
                return None
            
            # Build chat input data for workflow
            chat_input_data = {
                'message': message_content,
                'session_id': str(session.id),
                'user_id': str(session.user.id),
                'message_type': 'user',
                'timestamp': timezone.now().isoformat(),
                'session_context': {
                    'message_history': self._get_message_history(session),
                    'session_data': session.context
                }
            }
            
            # Convert to items format for workflow execution
            input_items = [{"json": chat_input_data}]
            
            # Create workflow execution
            execution = WorkflowExecution.objects.create(
                workflow=workflow,
                tenant=session.tenant,
                input_payload=chat_input_data,
                input_items=input_items,
                triggered_by='chat',
                correlation_id=str(uuid.uuid4())
            )
            
            # Queue execution using core engine
            transaction.on_commit(lambda: execute_workflow_with_core_engine.delay(str(execution.id)))
            
            logger.info(f"Triggered workflow {workflow.id} from chat message {user_message.id}")
            return execution
            
        except Exception as e:
            logger.error(f"Failed to trigger chat workflow: {e}", exc_info=True)
            return None
    
    def _get_message_history(self, session: ChatSession, limit: int = 10) -> list:
        """Get recent message history for context."""
        messages = session.messages.order_by('-created_at')[:limit]
        return [
            {
                'type': msg.message_type,
                'content': msg.content,
                'timestamp': msg.created_at.isoformat()
            }
            for msg in reversed(messages)
        ]
    
    def _get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @action(detail=True, methods=['post'])
    def associate_workflow(self, request, pk=None):
        """Associate a workflow with the chat session."""
        session = self.get_object()
        workflow_id = request.data.get('workflow_id')
        
        if not workflow_id:
            return Response(
                {'error': 'workflow_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            workflow = Workflow.objects.get(
                id=workflow_id,
                owner=request.user
            )
            
            session.workflow = workflow
            session.save(update_fields=['workflow'])
            
            # Create system message about association
            ChatMessage.objects.create(
                session=session,
                tenant=session.tenant,
                message_type='system',
                content=f'Chat session associated with workflow: {workflow.name}',
                metadata={'workflow_id': str(workflow.id)}
            )
            
            return Response({
                'message': 'Workflow associated successfully',
                'workflow': {
                    'id': str(workflow.id),
                    'name': workflow.name
                }
            })
            
        except Workflow.DoesNotExist:
            return Response(
                {'error': 'Workflow not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def clear_context(self, request, pk=None):
        """Clear session context."""
        session = self.get_object()
        session.context = {}
        session.save(update_fields=['context'])
        
        # Create system message
        ChatMessage.objects.create(
            session=session,
            tenant=session.tenant,
            message_type='system',
            content='Session context cleared',
            metadata={'action': 'context_cleared'}
        )
        
        return Response({'message': 'Context cleared successfully'})


class ChatMessageViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Chat Message read operations."""
    
    serializer_class = ChatMessageSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ChatPagination
    
    def get_queryset(self):
        """Filter chat messages by user's sessions."""
        return ChatMessage.objects.filter(
            session__user=self.request.user
        ).select_related('session', 'workflow_execution')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def handle_workflow_response(request):
    """
    Handle workflow execution completion and update chat message.
    
    This endpoint is called by the workflow execution system when
    a chat-triggered workflow completes.
    """
    try:
        execution_id = request.data.get('execution_id')
        if not execution_id:
            return JsonResponse(
                {'error': 'execution_id is required'},
                status=400
            )
        
        # Get workflow execution
        try:
            execution = WorkflowExecution.objects.get(
                id=execution_id,
                triggered_by='chat'
            )
        except WorkflowExecution.DoesNotExist:
            return JsonResponse(
                {'error': 'Workflow execution not found'},
                status=404
            )
        
        # Find associated chat message
        chat_message = ChatMessage.objects.filter(
            workflow_execution=execution,
            message_type='assistant'
        ).first()
        
        if not chat_message:
            logger.warning(f"No chat message found for execution {execution_id}")
            return JsonResponse({'message': 'No associated chat message'})
        
        # Update chat message with workflow result
        if execution.status == 'success' or execution.status == 'completed':
            # Extract response from workflow output
            response_content = _extract_workflow_response(execution)
            
            chat_message.content = response_content
            chat_message.metadata.update({
                'status': 'completed',
                'execution_status': execution.status,
                'completed_at': timezone.now().isoformat()
            })
            
        elif execution.status == 'failed':
            chat_message.content = 'Sorry, I encountered an error processing your request.'
            chat_message.message_type = 'error'
            chat_message.metadata.update({
                'status': 'failed',
                'execution_status': execution.status,
                'error_message': execution.error_message,
                'completed_at': timezone.now().isoformat()
            })
        
        chat_message.save(update_fields=['content', 'message_type', 'metadata'])
        
        return JsonResponse({
            'message': 'Chat message updated successfully',
            'message_id': str(chat_message.id)
        })
        
    except Exception as e:
        logger.error(f"Error handling workflow response: {e}", exc_info=True)
        return JsonResponse(
            {'error': 'Failed to handle workflow response'},
            status=500
        )


def _extract_workflow_response(execution: WorkflowExecution) -> str:
    """Extract human-readable response from workflow execution."""
    try:
        # Check if workflow has chat response node output
        if execution.output_items:
            for item in execution.output_items:
                json_data = item.get('json', {})
                
                # Look for chat_response field (from ChatResponseNode)
                if 'chat_response' in json_data:
                    return json_data['chat_response'].get('message', 'Task completed successfully.')
                
                # Look for message field
                if 'message' in json_data:
                    return json_data['message']
        
        # Fallback to node results
        if execution.node_results:
            # Look for the last successful node with output
            for node_id, result in reversed(execution.node_results.items()):
                if isinstance(result, dict):
                    if 'message' in result:
                        return result['message']
                    if 'chat_response' in result:
                        return result['chat_response'].get('message', 'Task completed.')
        
        # Default success message
        return 'Task completed successfully.'
        
    except Exception as e:
        logger.error(f"Error extracting workflow response: {e}")
        return 'Task completed, but response formatting failed.'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chat_health(request):
    """Health check endpoint for chat system."""
    return JsonResponse({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'features': {
            'chat_sessions': True,
            'workflow_integration': True,
            'message_history': True
        }
    })