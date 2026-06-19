"""
Tests for Enhanced Execution Logging and History System

This test suite verifies that the execution logging system works correctly:
- Non-intrusive hooks don't break execution logic
- Comprehensive logging is captured at all levels
- Database records are created correctly
- API endpoints return proper data
- Celery-safe operations work in background tasks
"""

import json
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

from ..models import (
    Workflow, WorkflowExecution, NodeExecution, ExecutionLog, Tenant
)
from ..execution.core_engine import (
    WorkflowExecutionEngine, ExecutionContext, ExecutionHooks
)
from ..execution.django_executor import (
    DjangoWorkflowExecutor, DjangoExecutionHooks, execute_django_workflow
)


class ExecutionHooksTest(TestCase):
    """Test the core execution hooks system."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant'
        )
        self.workflow = Workflow.objects.create(
            name='Test Workflow',
            owner=self.user,
            tenant=self.tenant,
            definition={
                'meta': {'name': 'Test Workflow', 'version': '1.0'},
                'trigger': {'id': 'trigger1', 'type': 'manual_trigger'},
                'nodes': {
                    'node1': {'type': 'delay_node', 'params': {'seconds': 1}}
                },
                'connections': {
                    'trigger1': ['node1'],
                    'node1': []
                }
            }
        )
    
    def test_hooks_are_called_during_execution(self):
        """Test that hooks are called at the right times during execution."""
        # Create mock hooks
        hooks = ExecutionHooks()
        
        # Mock hook methods
        hooks.on_execution_start = MagicMock()
        hooks.on_execution_complete = MagicMock()
        hooks.on_node_start = MagicMock()
        hooks.on_node_complete = MagicMock()
        
        # Create execution context
        context = ExecutionContext(
            workflow_id=str(self.workflow.id),
            execution_id=str(uuid.uuid4()),
            user_id=str(self.user.id)
        )
        
        # Execute workflow with hooks
        engine = WorkflowExecutionEngine(hooks=hooks)
        result = engine.run(self.workflow.definition, {}, context)
        
        # Verify hooks were called
        self.assertTrue(result.success)
        hooks.on_execution_start.assert_called_once()
        hooks.on_execution_complete.assert_called_once()
        hooks.on_node_start.assert_called()  # Called for trigger and node
        hooks.on_node_complete.assert_called()  # Called for trigger and node
        
        # Verify hook arguments
        execution_start_call = hooks.on_execution_start.call_args
        self.assertEqual(execution_start_call[0][0], context)  # First arg is context
        self.assertEqual(execution_start_call[0][1], self.workflow.definition)  # Second arg is workflow_json
    
    def test_hooks_handle_execution_failure(self):
        """Test that hooks are called correctly when execution fails."""
        # Create workflow with invalid node type
        invalid_workflow = {
            'meta': {'name': 'Invalid Workflow', 'version': '1.0'},
            'trigger': {'id': 'trigger1', 'type': 'manual_trigger'},
            'nodes': {
                'node1': {'type': 'nonexistent_node', 'params': {}}
            },
            'connections': {
                'trigger1': ['node1'],
                'node1': []
            }
        }
        
        # Create mock hooks
        hooks = ExecutionHooks()
        hooks.on_execution_start = MagicMock()
        hooks.on_execution_error = MagicMock()
        hooks.on_node_error = MagicMock()
        
        # Create execution context
        context = ExecutionContext(
            workflow_id=str(self.workflow.id),
            execution_id=str(uuid.uuid4())
        )
        
        # Execute workflow with hooks
        engine = WorkflowExecutionEngine(hooks=hooks)
        result = engine.run(invalid_workflow, {}, context)
        
        # Verify execution failed and hooks were called
        self.assertFalse(result.success)
        hooks.on_execution_start.assert_called_once()
        hooks.on_execution_error.assert_called_once()
        hooks.on_node_error.assert_called_once()
    
    def test_hook_exceptions_dont_break_execution(self):
        """Test that exceptions in hooks don't break the execution."""
        # Create hooks that raise exceptions
        hooks = ExecutionHooks()
        hooks.on_execution_start = MagicMock(side_effect=Exception("Hook failed"))
        hooks.on_node_start = MagicMock(side_effect=Exception("Hook failed"))
        
        # Create execution context
        context = ExecutionContext(
            workflow_id=str(self.workflow.id),
            execution_id=str(uuid.uuid4())
        )
        
        # Execute workflow - should still succeed despite hook failures
        engine = WorkflowExecutionEngine(hooks=hooks)
        result = engine.run(self.workflow.definition, {}, context)
        
        # Execution should still succeed
        self.assertTrue(result.success)
        
        # Hooks should have been called (and failed)
        hooks.on_execution_start.assert_called_once()
        hooks.on_node_start.assert_called()


class DjangoExecutionHooksTest(TransactionTestCase):
    """Test Django-specific execution hooks."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant'
        )
        self.workflow = Workflow.objects.create(
            name='Test Workflow',
            owner=self.user,
            tenant=self.tenant,
            definition={
                'meta': {'name': 'Test Workflow', 'version': '1.0'},
                'trigger': {'id': 'trigger1', 'type': 'manual_trigger'},
                'nodes': {
                    'node1': {'type': 'delay_node', 'params': {'seconds': 1}}
                },
                'connections': {
                    'trigger1': ['node1'],
                    'node1': []
                }
            }
        )
        self.execution = WorkflowExecution.objects.create(
            workflow=self.workflow,
            tenant=self.tenant,
            created_by=self.user,
            status='pending',
            input_data={}
        )
    
    def test_django_hooks_create_execution_logs(self):
        """Test that Django hooks create ExecutionLog entries."""
        # Execute workflow with Django executor
        executor = DjangoWorkflowExecutor()
        result = executor.execute_workflow_execution(self.execution)
        
        # Verify execution succeeded
        self.assertTrue(result.success)
        
        # Verify ExecutionLog entries were created
        logs = ExecutionLog.objects.filter(execution=self.execution)
        self.assertGreater(logs.count(), 0)
        
        # Verify we have start and completion logs
        start_logs = logs.filter(message__icontains='started')
        completion_logs = logs.filter(message__icontains='completed')
        
        self.assertGreater(start_logs.count(), 0)
        self.assertGreater(completion_logs.count(), 0)
        
        # Verify log structure
        first_log = logs.first()
        self.assertEqual(first_log.execution, self.execution)
        self.assertEqual(first_log.tenant, self.tenant)
        self.assertIn(first_log.level, ['info', 'error', 'warning', 'debug'])
        self.assertIsInstance(first_log.metadata, dict)
    
    def test_django_hooks_create_node_executions(self):
        """Test that Django hooks create NodeExecution entries."""
        # Execute workflow with Django executor
        executor = DjangoWorkflowExecutor()
        result = executor.execute_workflow_execution(self.execution)
        
        # Verify execution succeeded
        self.assertTrue(result.success)
        
        # Verify NodeExecution entries were created
        node_executions = NodeExecution.objects.filter(workflow_execution=self.execution)
        self.assertGreater(node_executions.count(), 0)
        
        # Verify node execution structure
        node_exec = node_executions.first()
        self.assertEqual(node_exec.workflow_execution, self.execution)
        self.assertEqual(node_exec.tenant, self.tenant)
        self.assertIn(node_exec.status, ['completed', 'failed', 'running', 'pending'])
        self.assertIsInstance(node_exec.output_data, dict)
    
    @patch('workflows.websocket_publisher.publish_execution_event')
    def test_django_hooks_publish_websocket_events(self, mock_publish):
        """Test that Django hooks publish WebSocket events."""
        # Execute workflow with Django executor
        executor = DjangoWorkflowExecutor()
        result = executor.execute_workflow_execution(self.execution)
        
        # Verify execution succeeded
        self.assertTrue(result.success)
        
        # Verify WebSocket events were published
        self.assertGreater(mock_publish.call_count, 0)
        
        # Check for specific event types
        call_args_list = [call[0] for call in mock_publish.call_args_list]
        event_types = [args[1] for args in call_args_list]
        
        self.assertIn('execution_started', event_types)
        self.assertIn('execution_completed', event_types)
        self.assertIn('node_started', event_types)
        self.assertIn('node_completed', event_types)


class ExecutionHistoryAPITest(APITestCase):
    """Test the execution history API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant'
        )
        self.workflow = Workflow.objects.create(
            name='Test Workflow',
            owner=self.user,
            tenant=self.tenant,
            definition={'meta': {'name': 'Test'}}
        )
        
        # Create test executions
        self.execution1 = WorkflowExecution.objects.create(
            workflow=self.workflow,
            tenant=self.tenant,
            created_by=self.user,
            status='completed',
            started_at=timezone.now() - timedelta(hours=2),
            finished_at=timezone.now() - timedelta(hours=1),
            input_data={'test': 'data1'}
        )
        self.execution2 = WorkflowExecution.objects.create(
            workflow=self.workflow,
            tenant=self.tenant,
            created_by=self.user,
            status='failed',
            started_at=timezone.now() - timedelta(hours=1),
            finished_at=timezone.now() - timedelta(minutes=30),
            input_data={'test': 'data2'},
            error_message='Test error'
        )
        
        # Create test logs
        ExecutionLog.objects.create(
            execution=self.execution1,
            tenant=self.tenant,
            level='info',
            message='Test log message',
            metadata={'test': 'metadata'}
        )
        
        # Authenticate user
        self.client.force_authenticate(user=self.user)
    
    def test_execution_history_endpoint(self):
        """Test the execution history endpoint."""
        url = reverse('workflows:execution_history')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check response structure
        data = response.json()
        self.assertIn('results', data)  # Paginated response
        self.assertIn('count', data)
        
        # Check execution data
        executions = data['results']
        self.assertEqual(len(executions), 2)
        
        # Verify execution data structure
        execution_data = executions[0]
        self.assertIn('id', execution_data)
        self.assertIn('workflow', execution_data)
        self.assertIn('status', execution_data)
        self.assertIn('duration_ms', execution_data)
        self.assertIn('node_summary', execution_data)
    
    def test_execution_history_filtering(self):
        """Test execution history filtering."""
        url = reverse('workflows:execution_history')
        
        # Filter by status
        response = self.client.get(url, {'status': 'completed'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        executions = data['results']
        self.assertEqual(len(executions), 1)
        self.assertEqual(executions[0]['status'], 'completed')
        
        # Filter by workflow
        response = self.client.get(url, {'workflow_id': str(self.workflow.id)})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertEqual(data['count'], 2)
    
    def test_execution_detail_endpoint(self):
        """Test the execution detail endpoint."""
        url = reverse('workflows:execution_detail', kwargs={'execution_id': self.execution1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check response structure
        data = response.json()
        self.assertEqual(data['id'], str(self.execution1.id))
        self.assertIn('workflow', data)
        self.assertIn('status', data)
        self.assertIn('duration_ms', data)
        self.assertIn('node_executions', data)
        self.assertIn('logs', data)
        self.assertIn('timeline', data)
        
        # Verify timeline structure
        timeline = data['timeline']
        self.assertIsInstance(timeline, list)
        if timeline:
            timeline_item = timeline[0]
            self.assertIn('timestamp', timeline_item)
            self.assertIn('type', timeline_item)
            self.assertIn('message', timeline_item)
    
    def test_execution_logs_endpoint(self):
        """Test the execution logs endpoint."""
        url = reverse('workflows:execution_logs', kwargs={'execution_id': self.execution1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check response structure
        data = response.json()
        self.assertIn('logs', data)
        self.assertIn('count', data)
        self.assertIn('has_more', data)
        
        # Verify log data
        logs = data['logs']
        self.assertGreater(len(logs), 0)
        
        log_item = logs[0]
        self.assertIn('id', log_item)
        self.assertIn('level', log_item)
        self.assertIn('message', log_item)
        self.assertIn('metadata', log_item)
        self.assertIn('timestamp', log_item)
    
    def test_execution_metrics_endpoint(self):
        """Test the execution metrics endpoint."""
        url = reverse('workflows:execution_metrics')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check response structure
        data = response.json()
        self.assertIn('period', data)
        self.assertIn('summary', data)
        self.assertIn('performance', data)
        self.assertIn('status_distribution', data)
        self.assertIn('trigger_distribution', data)
        self.assertIn('time_series', data)
        
        # Verify summary data
        summary = data['summary']
        self.assertEqual(summary['total_executions'], 2)
        self.assertEqual(summary['successful_executions'], 1)
        self.assertEqual(summary['failed_executions'], 1)
        self.assertEqual(summary['success_rate'], 50.0)
    
    def test_workflow_execution_summary_endpoint(self):
        """Test the workflow execution summary endpoint."""
        url = reverse('workflows:workflow_execution_summary', kwargs={'workflow_id': self.workflow.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check response structure
        data = response.json()
        self.assertIn('workflow', data)
        self.assertIn('summary', data)
        self.assertIn('last_execution', data)
        self.assertIn('recent_executions', data)
        
        # Verify workflow data
        workflow_data = data['workflow']
        self.assertEqual(workflow_data['id'], str(self.workflow.id))
        self.assertEqual(workflow_data['name'], self.workflow.name)
        
        # Verify summary data
        summary = data['summary']
        self.assertEqual(summary['total_executions'], 2)
        self.assertIn('success_rate', summary)
        self.assertIn('status_counts', summary)


class CeleryExecutionLoggingTest(TransactionTestCase):
    """Test execution logging in Celery context."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant'
        )
        self.workflow = Workflow.objects.create(
            name='Test Workflow',
            owner=self.user,
            tenant=self.tenant,
            definition={
                'meta': {'name': 'Test Workflow', 'version': '1.0'},
                'trigger': {'id': 'trigger1', 'type': 'manual_trigger'},
                'nodes': {
                    'node1': {'type': 'delay_node', 'params': {'seconds': 1}}
                },
                'connections': {
                    'trigger1': ['node1'],
                    'node1': []
                }
            }
        )
        self.execution = WorkflowExecution.objects.create(
            workflow=self.workflow,
            tenant=self.tenant,
            created_by=self.user,
            status='pending',
            input_data={}
        )
    
    def test_celery_safe_execution_logging(self):
        """Test that execution logging works in Celery context."""
        # Execute workflow using the Celery-compatible function
        result = execute_django_workflow(str(self.execution.id))
        
        # Verify execution succeeded
        self.assertTrue(result.success)
        
        # Verify database records were created
        self.execution.refresh_from_db()
        self.assertEqual(self.execution.status, 'completed')
        
        # Verify logs were created
        logs = ExecutionLog.objects.filter(execution=self.execution)
        self.assertGreater(logs.count(), 0)
        
        # Verify node executions were created
        node_executions = NodeExecution.objects.filter(workflow_execution=self.execution)
        self.assertGreater(node_executions.count(), 0)
    
    def test_database_transaction_safety(self):
        """Test that logging operations are transaction-safe."""
        # This test ensures that logging doesn't interfere with main execution transactions
        
        # Execute workflow
        result = execute_django_workflow(str(self.execution.id))
        
        # Verify execution completed
        self.assertTrue(result.success)
        
        # Verify all database records are consistent
        self.execution.refresh_from_db()
        self.assertIsNotNone(self.execution.started_at)
        self.assertIsNotNone(self.execution.completed_at)
        self.assertEqual(self.execution.status, 'completed')
        
        # Verify logs and node executions exist and are consistent
        logs = ExecutionLog.objects.filter(execution=self.execution)
        node_executions = NodeExecution.objects.filter(workflow_execution=self.execution)
        
        self.assertGreater(logs.count(), 0)
        self.assertGreater(node_executions.count(), 0)
        
        # All records should have the same tenant
        for log in logs:
            self.assertEqual(log.tenant, self.tenant)
        
        for node_exec in node_executions:
            self.assertEqual(node_exec.tenant, self.tenant)