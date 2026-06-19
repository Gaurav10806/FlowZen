"""
WebSocket Consumers for Real-time Collaboration
Handles real-time communication between clients
"""

import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from .models import CollaborationSession, CollaborationParticipant, WorkflowOperation, WorkflowComment
from .operational_transform import OperationalTransform
from ..models import Workflow

class CollaborationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time workflow collaboration"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = None
        self.participant_id = None
        self.workflow_id = None
        self.room_group_name = None
        self.operational_transform = OperationalTransform()
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.workflow_id = self.scope['url_route']['kwargs']['workflow_id']
        self.room_group_name = f'collaboration_{self.session_id}'
        
        # Verify session and permissions
        session_valid = await self.verify_session()
        if not session_valid:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        # Create or update participant
        await self.create_participant()
        
        # Accept connection
        await self.accept()
        
        # Send initial state
        await self.send_initial_state()
        
        # Notify others of new participant
        await self.broadcast_participant_joined()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if self.room_group_name:
            # Update participant status
            await self.update_participant_status(False)
            
            # Notify others of participant leaving
            await self.broadcast_participant_left()
            
            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'operation':
                await self.handle_operation(data)
            elif message_type == 'cursor_update':
                await self.handle_cursor_update(data)
            elif message_type == 'comment':
                await self.handle_comment(data)
            elif message_type == 'selection_update':
                await self.handle_selection_update(data)
            elif message_type == 'heartbeat':
                await self.handle_heartbeat(data)
            else:
                await self.send_error(f'Unknown message type: {message_type}')
                
        except json.JSONDecodeError:
            await self.send_error('Invalid JSON format')
        except Exception as e:
            await self.send_error(f'Error processing message: {str(e)}')
    
    async def handle_operation(self, data):
        """Handle workflow operation (add/edit/delete nodes/edges)"""
        try:
            operation_data = data.get('operation', {})
            
            # Create operation record
            operation = await self.create_operation(operation_data)
            
            # Apply operational transform
            transformed_operation = await self.operational_transform.transform_operation(
                operation, self.session_id
            )
            
            # Broadcast to other participants
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'operation_broadcast',
                    'operation': transformed_operation,
                    'participant_id': str(self.participant_id),
                    'timestamp': timezone.now().isoformat()
                }
            )
            
            # Send acknowledgment
            await self.send(text_data=json.dumps({
                'type': 'operation_ack',
                'operation_id': str(operation.id),
                'success': True
            }))
            
        except Exception as e:
            await self.send_error(f'Operation failed: {str(e)}')
    
    async def handle_cursor_update(self, data):
        """Handle cursor position updates"""
        cursor_data = data.get('cursor', {})
        
        # Update participant cursor
        await self.update_participant_cursor(cursor_data)
        
        # Broadcast to others
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'cursor_broadcast',
                'participant_id': str(self.participant_id),
                'cursor': cursor_data,
                'timestamp': timezone.now().isoformat()
            }
        )
    
    async def handle_comment(self, data):
        """Handle comment creation/editing"""
        comment_data = data.get('comment', {})
        
        # Create comment
        comment = await self.create_comment(comment_data)
        
        # Broadcast to others
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'comment_broadcast',
                'comment': {
                    'id': str(comment.id),
                    'content': comment.content,
                    'target_type': comment.target_type,
                    'target_id': comment.target_id,
                    'position': comment.position,
                    'participant_id': str(self.participant_id),
                    'created_at': comment.created_at.isoformat()
                }
            }
        )
    
    async def handle_selection_update(self, data):
        """Handle selection updates"""
        selection_data = data.get('selection', {})
        
        # Update participant selection
        await self.update_participant_selection(selection_data)
        
        # Broadcast to others
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'selection_broadcast',
                'participant_id': str(self.participant_id),
                'selection': selection_data
            }
        )
    
    async def handle_heartbeat(self, data):
        """Handle heartbeat to keep connection alive"""
        await self.update_participant_last_seen()
        
        await self.send(text_data=json.dumps({
            'type': 'heartbeat_ack',
            'timestamp': timezone.now().isoformat()
        }))
    
    # Broadcast handlers
    async def operation_broadcast(self, event):
        """Send operation to WebSocket"""
        if event['participant_id'] != str(self.participant_id):
            await self.send(text_data=json.dumps({
                'type': 'operation',
                'operation': event['operation'],
                'participant_id': event['participant_id'],
                'timestamp': event['timestamp']
            }))
    
    async def cursor_broadcast(self, event):
        """Send cursor update to WebSocket"""
        if event['participant_id'] != str(self.participant_id):
            await self.send(text_data=json.dumps({
                'type': 'cursor_update',
                'participant_id': event['participant_id'],
                'cursor': event['cursor'],
                'timestamp': event['timestamp']
            }))
    
    async def comment_broadcast(self, event):
        """Send comment to WebSocket"""
        await self.send(text_data=json.dumps({
            'type': 'comment',
            'comment': event['comment']
        }))
    
    async def selection_broadcast(self, event):
        """Send selection update to WebSocket"""
        if event['participant_id'] != str(self.participant_id):
            await self.send(text_data=json.dumps({
                'type': 'selection_update',
                'participant_id': event['participant_id'],
                'selection': event['selection']
            }))
    
    async def participant_joined_broadcast(self, event):
        """Send participant joined notification"""
        await self.send(text_data=json.dumps({
            'type': 'participant_joined',
            'participant': event['participant']
        }))
    
    async def participant_left_broadcast(self, event):
        """Send participant left notification"""
        await self.send(text_data=json.dumps({
            'type': 'participant_left',
            'participant_id': event['participant_id']
        }))
    
    # Database operations
    @database_sync_to_async
    def verify_session(self):
        """Verify collaboration session exists and is valid"""
        try:
            session = CollaborationSession.objects.get(
                id=self.session_id,
                workflow_id=self.workflow_id,
                is_active=True,
                expires_at__gt=timezone.now()
            )
            return True
        except CollaborationSession.DoesNotExist:
            return False
    
    @database_sync_to_async
    def create_participant(self):
        """Create or update participant record"""
        user = self.scope.get('user')
        
        participant, created = CollaborationParticipant.objects.get_or_create(
            session_id=self.session_id,
            user=user if user.is_authenticated else None,
            defaults={
                'anonymous_id': self.channel_name if not user.is_authenticated else None,
                'is_active': True,
                'can_edit': True,
                'can_comment': True
            }
        )
        
        if not created:
            participant.is_active = True
            participant.last_seen = timezone.now()
            participant.save()
        
        self.participant_id = participant.id
        return participant
    
    @database_sync_to_async
    def create_operation(self, operation_data):
        """Create workflow operation record"""
        participant = CollaborationParticipant.objects.get(id=self.participant_id)
        
        operation = WorkflowOperation.objects.create(
            session_id=self.session_id,
            participant=participant,
            operation_type=operation_data.get('type'),
            target_id=operation_data.get('target_id'),
            operation_data=operation_data.get('data', {}),
            vector_clock=operation_data.get('vector_clock', {})
        )
        
        return operation
    
    @database_sync_to_async
    def create_comment(self, comment_data):
        """Create workflow comment"""
        participant = CollaborationParticipant.objects.get(id=self.participant_id)
        
        comment = WorkflowComment.objects.create(
            session_id=self.session_id,
            participant=participant,
            target_type=comment_data.get('target_type'),
            target_id=comment_data.get('target_id'),
            content=comment_data.get('content'),
            position=comment_data.get('position', {})
        )
        
        return comment
    
    @database_sync_to_async
    def update_participant_cursor(self, cursor_data):
        """Update participant cursor position"""
        CollaborationParticipant.objects.filter(id=self.participant_id).update(
            cursor_position=cursor_data,
            last_seen=timezone.now()
        )
    
    @database_sync_to_async
    def update_participant_selection(self, selection_data):
        """Update participant selection"""
        CollaborationParticipant.objects.filter(id=self.participant_id).update(
            current_selection=selection_data,
            last_seen=timezone.now()
        )
    
    @database_sync_to_async
    def update_participant_status(self, is_active):
        """Update participant active status"""
        CollaborationParticipant.objects.filter(id=self.participant_id).update(
            is_active=is_active,
            last_seen=timezone.now()
        )
    
    @database_sync_to_async
    def update_participant_last_seen(self):
        """Update participant last seen timestamp"""
        CollaborationParticipant.objects.filter(id=self.participant_id).update(
            last_seen=timezone.now()
        )
    
    @database_sync_to_async
    def get_session_state(self):
        """Get current session state"""
        session = CollaborationSession.objects.get(id=self.session_id)
        participants = list(session.participants.filter(is_active=True).values(
            'id', 'user__username', 'anonymous_id', 'cursor_position', 
            'current_selection', 'can_edit', 'can_comment'
        ))
        
        recent_operations = list(session.operations.order_by('-timestamp')[:50].values())
        comments = list(session.comments.filter(is_resolved=False).values())
        
        return {
            'session': {
                'id': str(session.id),
                'workflow_id': str(session.workflow_id),
                'created_at': session.created_at.isoformat(),
                'max_participants': session.max_participants
            },
            'participants': participants,
            'recent_operations': recent_operations,
            'comments': comments
        }
    
    async def send_initial_state(self):
        """Send initial collaboration state to new participant"""
        state = await self.get_session_state()
        
        await self.send(text_data=json.dumps({
            'type': 'initial_state',
            'state': state
        }))
    
    async def broadcast_participant_joined(self):
        """Broadcast participant joined to all others"""
        participant = await database_sync_to_async(
            CollaborationParticipant.objects.get
        )(id=self.participant_id)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'participant_joined_broadcast',
                'participant': {
                    'id': str(participant.id),
                    'username': participant.user.username if participant.user else 'Anonymous',
                    'can_edit': participant.can_edit,
                    'can_comment': participant.can_comment
                }
            }
        )
    
    async def broadcast_participant_left(self):
        """Broadcast participant left to all others"""
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'participant_left_broadcast',
                'participant_id': str(self.participant_id)
            }
        )
    
    async def send_error(self, message):
        """Send error message to client"""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': message,
            'timestamp': timezone.now().isoformat()
        }))