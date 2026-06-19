"""
Chat Response Handler

This module handles workflow execution completion for chat-triggered workflows.
It updates chat messages with workflow results and manages the conversation flow.
"""

import logging
import requests
from typing import Optional
from django.conf import settings
from django.utils import timezone

from .models import WorkflowExecution, ChatMessage

logger = logging.getLogger(__name__)


class ChatResponseHandler:
    """Handles workflow execution completion for chat-triggered workflows."""
    
    def __init__(self):
        self.base_url = getattr(settings, 'CHAT_API_BASE_URL', 'http://localhost:8000')
    
    def handle_workflow_completion(self, execution: WorkflowExecution) -> bool:
        """
        Handle workflow execution completion for chat-triggered workflows.
        
        Args:
            execution: The completed WorkflowExecution instance
            
        Returns:
            bool: True if handled successfully, False otherwise
        """
        try:
            # Only handle chat-triggered executions
            if execution.triggered_by != 'chat':
                return False
            
            logger.info(f"Handling chat workflow completion for execution {execution.id}")
            
            # Find associated chat message
            chat_message = self._find_chat_message(execution)
            if not chat_message:
                logger.warning(f"No chat message found for execution {execution.id}")
                return False
            
            # Update chat message with workflow result
            success = self._update_chat_message(chat_message, execution)
            
            if success:
                logger.info(f"Successfully updated chat message {chat_message.id}")
            else:
                logger.error(f"Failed to update chat message {chat_message.id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error handling chat workflow completion: {e}", exc_info=True)
            return False
    
    def _find_chat_message(self, execution: WorkflowExecution) -> Optional[ChatMessage]:
        """Find the chat message associated with the workflow execution."""
        try:
            return ChatMessage.objects.filter(
                workflow_execution=execution,
                message_type='assistant'
            ).first()
        except Exception as e:
            logger.error(f"Error finding chat message: {e}")
            return None
    
    def _update_chat_message(self, chat_message: ChatMessage, execution: WorkflowExecution) -> bool:
        """Update chat message with workflow execution result."""
        try:
            if execution.status in ['success', 'completed']:
                # Extract response from workflow output
                response_content = self._extract_workflow_response(execution)
                
                chat_message.content = response_content
                chat_message.metadata.update({
                    'status': 'completed',
                    'execution_status': execution.status,
                    'completed_at': timezone.now().isoformat()
                })
                
            elif execution.status == 'failed':
                error_message = self._format_error_message(execution)
                
                chat_message.content = error_message
                chat_message.message_type = 'error'
                chat_message.metadata.update({
                    'status': 'failed',
                    'execution_status': execution.status,
                    'error_message': execution.error_message,
                    'completed_at': timezone.now().isoformat()
                })
            
            else:
                # Execution still running or in unknown state
                logger.warning(f"Unexpected execution status: {execution.status}")
                return False
            
            chat_message.save(update_fields=['content', 'message_type', 'metadata'])
            return True
            
        except Exception as e:
            logger.error(f"Error updating chat message: {e}", exc_info=True)
            return False
    
    def _extract_workflow_response(self, execution: WorkflowExecution) -> str:
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
                        if 'result' in result:
                            return f"Task completed. Result: {result['result']}"
            
            # Default success message
            return 'Task completed successfully.'
            
        except Exception as e:
            logger.error(f"Error extracting workflow response: {e}")
            return 'Task completed, but response formatting failed.'
    
    def _format_error_message(self, execution: WorkflowExecution) -> str:
        """Format a user-friendly error message."""
        try:
            if execution.error_message:
                # Try to make error message more user-friendly
                error_msg = execution.error_message.lower()
                
                if 'timeout' in error_msg:
                    return 'The task took too long to complete. Please try again.'
                elif 'connection' in error_msg or 'network' in error_msg:
                    return 'There was a network connection issue. Please try again.'
                elif 'permission' in error_msg or 'unauthorized' in error_msg:
                    return 'Permission denied. Please check your credentials.'
                elif 'not found' in error_msg:
                    return 'Required resource not found. Please check your configuration.'
                else:
                    return f'An error occurred: {execution.error_message[:100]}...'
            else:
                return 'An unknown error occurred. Please try again.'
                
        except Exception as e:
            logger.error(f"Error formatting error message: {e}")
            return 'An error occurred while processing your request.'
    
    def notify_via_webhook(self, execution: WorkflowExecution) -> bool:
        """
        Notify chat system via webhook about workflow completion.
        
        This is an alternative to direct database updates.
        """
        try:
            webhook_url = f"{self.base_url}/api/chat/workflow-response/"
            
            payload = {
                'execution_id': str(execution.id),
                'status': execution.status,
                'triggered_by': execution.triggered_by
            }
            
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully notified chat system about execution {execution.id}")
                return True
            else:
                logger.error(f"Chat webhook returned status {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending chat webhook: {e}")
            return False


# Global instance
chat_response_handler = ChatResponseHandler()


def handle_chat_workflow_completion(execution: WorkflowExecution) -> bool:
    """
    Convenience function to handle chat workflow completion.
    
    This can be called from Celery tasks or Django signals.
    """
    return chat_response_handler.handle_workflow_completion(execution)