"""
Chat Nodes for Conversational Workflow Integration

This module contains chat-specific nodes that enable conversational interfaces
to trigger and interact with workflows.
"""

from typing import Dict, Any, List
from .base_node import TriggerNode, ActionNode, NodeExecutionError
from .registry import register_node
import json


@register_node
class ChatTriggerNode(TriggerNode):
    """
    Chat trigger node - starts workflow execution from chat messages.
    
    This is the CORE integration point between chatbot and workflow engine.
    It receives user messages and converts them to structured workflow input.
    """
    
    NODE_TYPE = "chat_trigger"
    DISPLAY_NAME = "Chat Trigger"
    DESCRIPTION = "Triggers workflow when user sends a chat message"
    CATEGORY = "triggers"
    SUPPORTS_RETRY = False  # Triggers don't retry
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process incoming chat message and convert to workflow input.
        
        Args:
            input_data: Chat message data from ChatController
                {
                    'message': 'User message text',
                    'session_id': 'uuid',
                    'user_id': 'user_id',
                    'message_type': 'user',
                    'timestamp': 'iso_timestamp',
                    'session_context': {...}  # Previous conversation context
                }
            params: Chat trigger configuration
                {
                    'intent_extraction': True/False,
                    'context_window': 10,  # Number of previous messages to include
                    'required_entities': ['name', 'email'],  # Optional entity validation
                    'response_format': 'text'  # or 'structured'
                }
            context: Execution context with chat session info
        
        Returns:
            Structured data for workflow execution
        """
        self.logger.info(f"Chat trigger activated for session {input_data.get('session_id')}")
        
        # Extract message data
        user_message = input_data.get('message', '')
        session_id = input_data.get('session_id')
        user_id = input_data.get('user_id')
        session_context = input_data.get('session_context', {})
        
        if not user_message.strip():
            raise NodeExecutionError("Empty message received", self.NODE_TYPE)
        
        # Build structured output for workflow
        chat_data = {
            'user_message': user_message,
            'session_id': session_id,
            'user_id': user_id,
            'timestamp': input_data.get('timestamp'),
            'message_type': input_data.get('message_type', 'user'),
            'session_context': session_context
        }
        
        # Add conversation history if configured
        context_window = params.get('context_window', 5)
        if context_window > 0 and session_context.get('message_history'):
            recent_messages = session_context['message_history'][-context_window:]
            chat_data['conversation_history'] = recent_messages
        
        # Extract entities if configured (basic keyword extraction)
        if params.get('intent_extraction', False):
            chat_data['extracted_entities'] = self._extract_entities(user_message, params)
        
        # Validate required entities
        required_entities = params.get('required_entities', [])
        if required_entities:
            self._validate_required_entities(chat_data.get('extracted_entities', {}), required_entities)
        
        return {
            'chat': chat_data,
            'trigger_data': chat_data,
            # Make message available at root level for easy access in workflow
            'message': user_message,
            'user_id': user_id,
            'session_id': session_id,
            **chat_data.get('extracted_entities', {})
        }
    
    def _extract_entities(self, message: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Basic entity extraction from user message.
        
        This is a simple implementation - can be enhanced with NLP libraries.
        """
        entities = {}
        message_lower = message.lower()
        
        # Simple email extraction
        import re
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, message)
        if emails:
            entities['email'] = emails[0]
        
        # Simple phone number extraction
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        phones = re.findall(phone_pattern, message)
        if phones:
            entities['phone'] = phones[0]
        
        # Simple name extraction (words that are capitalized)
        name_pattern = r'\b[A-Z][a-z]+\b'
        names = re.findall(name_pattern, message)
        if names and len(names) >= 2:
            entities['name'] = ' '.join(names[:2])
        
        return entities
    
    def _validate_required_entities(self, entities: Dict[str, Any], required: List[str]) -> None:
        """Validate that required entities are present."""
        missing = [entity for entity in required if entity not in entities]
        if missing:
            raise NodeExecutionError(
                f"Required information missing: {', '.join(missing)}. "
                f"Please provide this information to continue.",
                self.NODE_TYPE
            )
    
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "intent_extraction": {
                    "type": "boolean",
                    "default": True,
                    "title": "Extract Entities",
                    "description": "Automatically extract entities like names, emails, phone numbers from messages"
                },
                "context_window": {
                    "type": "integer",
                    "default": 5,
                    "minimum": 0,
                    "maximum": 20,
                    "title": "Context Window",
                    "description": "Number of previous messages to include as context"
                },
                "required_entities": {
                    "type": "array",
                    "items": {"type": "string"},
                    "title": "Required Entities",
                    "description": "List of entities that must be extracted before workflow can proceed"
                },
                "response_format": {
                    "type": "string",
                    "enum": ["text", "structured"],
                    "default": "text",
                    "title": "Response Format",
                    "description": "Expected format of workflow response"
                }
            }
        }


@register_node
class ChatResponseNode(ActionNode):
    """
    Chat response node - formats workflow output as chat message.
    
    This node should be used at the end of chat-triggered workflows
    to format the response for the chatbot.
    """
    
    NODE_TYPE = "chat_response"
    DISPLAY_NAME = "Chat Response"
    DESCRIPTION = "Formats workflow output as chat message response"
    CATEGORY = "chat"
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format workflow data as chat response.
        
        Args:
            input_data: Data from previous workflow nodes
            params: Response formatting configuration
                {
                    'message_template': 'Hello {name}, your order {order_id} is confirmed!',
                    'response_type': 'text',  # or 'card', 'list'
                    'include_data': True,  # Include structured data in response
                    'error_message': 'Sorry, something went wrong. Please try again.'
                }
        """
        self.logger.info("Formatting chat response")
        
        # Get message template
        template = params.get('message_template', '')
        response_type = params.get('response_type', 'text')
        include_data = params.get('include_data', False)
        
        # Format message using template and input data
        try:
            if template:
                # Simple template substitution
                formatted_message = template.format(**input_data)
            else:
                # Default response based on input data
                formatted_message = self._generate_default_response(input_data)
        
        except (KeyError, ValueError) as e:
            # Template formatting failed, use error message
            error_msg = params.get('error_message', 'Sorry, I encountered an error processing your request.')
            formatted_message = error_msg
            self.logger.warning(f"Template formatting failed: {e}")
        
        # Build response structure
        response = {
            'message': formatted_message,
            'type': response_type,
            'timestamp': context.get('execution_timestamp')
        }
        
        # Include structured data if requested
        if include_data:
            response['data'] = input_data
        
        return {
            'chat_response': response,
            'message': formatted_message,
            'response_type': response_type
        }
    
    def _generate_default_response(self, data: Dict[str, Any]) -> str:
        """Generate a default response when no template is provided."""
        if 'error' in data:
            return f"I encountered an error: {data['error']}"
        elif 'result' in data:
            return f"Task completed successfully. Result: {data['result']}"
        elif 'status' in data:
            return f"Status: {data['status']}"
        else:
            return "Task completed successfully."
    
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "message_template": {
                    "type": "string",
                    "title": "Message Template",
                    "description": "Template for response message. Use {field_name} for variable substitution.",
                    "examples": [
                        "Hello {name}!",
                        "Your order {order_id} has been {status}",
                        "Found {count} results for {query}"
                    ]
                },
                "response_type": {
                    "type": "string",
                    "enum": ["text", "card", "list"],
                    "default": "text",
                    "title": "Response Type",
                    "description": "Type of response format"
                },
                "include_data": {
                    "type": "boolean",
                    "default": False,
                    "title": "Include Data",
                    "description": "Include structured data in response for debugging"
                },
                "error_message": {
                    "type": "string",
                    "default": "Sorry, I encountered an error processing your request.",
                    "title": "Error Message",
                    "description": "Message to show when template formatting fails"
                }
            }
        }