"""
Comprehensive test suite for workflow automation platform.
"""
import json
import time
from unittest.mock import patch, MagicMock
from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from .models import Workflow, WorkflowExecution
from .tasks import run_workflow_execution


class WorkflowModelTest(TestCase):
    """Test Workflow model."""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
    
    def test_create_workflow(self):
        """Test workflow creation."""
        workflow = Workflow.objects.create(
            name="Test Workflow",
            description="Test description",
            owner=self.user,
            graph={"nodes": [], "edges": []}
        )
        self.assertEqual(workflow.name, "Test Workflow")
        self.assertEqual(workflow.status, "draft")
        self.assertIsNotNone(workflow.id)


class WorkflowExecutionTest(TestCase):
    """Test WorkflowExecution model."""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.workflow = Workflow.objects.create(
            name="Test Workflow",
            owner=self.user,
            graph={
                "nodes": [
                    {"id": "node1", "type": "trigger", "config": {}},
                    {"id": "node2", "type": "http_request", "config": {"method": "GET", "url": "https://httpbin.org/get"}}
                ],
                "edges": [
                    {"from": "node1", "to": "node2"}
                ]
            }
        )
    
    def test_create_execution(self):
        """Test execution creation."""
        execution = WorkflowExecution.objects.create(
            workflow=self.workflow,
            status="queued",
            triggered_by="manual"
        )
        self.assertEqual(execution.status, "queued")
        self.assertEqual(execution.workflow, self.workflow)
        self.assertIsNotNone(execution.id)
    
    def test_execution_mark_started(self):
        """Test marking execution as started."""
        execution = WorkflowExecution.objects.create(
            workflow=self.workflow,
            status="queued"
        )
        execution.mark_started()
        self.assertEqual(execution.status, "running")
        self.assertIsNotNone(execution.started_at)
    
    def test_execution_mark_completed(self):
        """Test marking execution as completed."""
        execution = WorkflowExecution.objects.create(
            workflow=self.workflow,
            status="running"
        )
        execution.mark_completed()
        self.assertEqual(execution.status, "completed")
        self.assertIsNotNone(execution.finished_at)
    
    def test_execution_mark_failed(self):
        """Test marking execution as failed."""
        execution = WorkflowExecution.objects.create(
            workflow=self.workflow,
            status="running"
        )
        execution.mark_failed(error_message="Test error")
        self.assertEqual(execution.status, "failed")
        self.assertEqual(execution.error_message, "Test error")
        self.assertIsNotNone(execution.finished_at)


class WorkflowAPITest(TestCase):
    """Test Workflow API endpoints."""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_create_workflow(self):
        """Test creating workflow via API."""
        data = {
            "name": "API Test Workflow",
            "description": "Test",
            "graph": {"nodes": [], "edges": []}
        }
        response = self.client.post('/api/v1/workflows/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], "API Test Workflow")
    
    def test_get_workflow(self):
        """Test getting workflow via API."""
        workflow = Workflow.objects.create(
            name="Test Workflow",
            owner=self.user,
            graph={"nodes": [], "edges": []}
        )
        response = self.client.get(f'/api/v1/workflows/{workflow.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], "Test Workflow")
    
    def test_update_workflow_graph(self):
        """Test updating workflow graph via API."""
        workflow = Workflow.objects.create(
            name="Test Workflow",
            owner=self.user,
            graph={"nodes": [], "edges": []}
        )
        new_graph = {
            "nodes": [
                {"id": "node1", "type": "trigger", "config": {}}
            ],
            "edges": []
        }
        response = self.client.patch(
            f'/api/v1/workflows/{workflow.id}/',
            {"graph": new_graph},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        workflow.refresh_from_db()
        self.assertEqual(len(workflow.graph['nodes']), 1)


class WorkflowExecutionAPITest(TestCase):
    """Test WorkflowExecution API endpoints."""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.workflow = Workflow.objects.create(
            name="Test Workflow",
            owner=self.user,
            graph={
                "nodes": [
                    {"id": "node1", "type": "trigger", "config": {}}
                ],
                "edges": []
            }
        )
    
    @patch('workflows.tasks.run_workflow_execution.delay')
    def test_create_execution(self, mock_task):
        """Test creating execution via API."""
        data = {"workflow": str(self.workflow.id)}
        response = self.client.post('/api/v1/executions/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], "queued")
        mock_task.assert_called_once()
    
    def test_get_execution(self):
        """Test getting execution via API."""
        execution = WorkflowExecution.objects.create(
            workflow=self.workflow,
            status="queued"
        )
        response = self.client.get(f'/api/v1/executions/{execution.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], "queued")


class ExecutionEngineTest(TransactionTestCase):
    """Test execution engine with database transactions."""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.workflow = Workflow.objects.create(
            name="Test Workflow",
            owner=self.user,
            graph={
                "nodes": [
                    {"id": "node1", "type": "trigger", "config": {}},
                    {"id": "node2", "type": "delay", "config": {"amount": 1, "unit": "seconds"}}
                ],
                "edges": [
                    {"from": "node1", "to": "node2"}
                ]
            }
        )
    
    @patch('workflows.tasks.send_mail')
    def test_trigger_node_execution(self, mock_send_mail):
        """Test trigger node execution."""
        execution = WorkflowExecution.objects.create(
            workflow=self.workflow,
            status="queued"
        )
        
        # Execute workflow
        run_workflow_execution(str(execution.id))
        
        execution.refresh_from_db()
        self.assertIn("success", execution.status.lower())
        self.assertIn("node1", execution.node_results)
        self.assertEqual(execution.node_results["node1"]["message"], "trigger start")
    
    @patch('workflows.tasks.requests.request')
    def test_http_node_execution(self, mock_request):
        """Test HTTP node execution."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"success": true}'
        mock_response.headers = {"Content-Type": "application/json"}
        mock_request.return_value = mock_response
        
        workflow = Workflow.objects.create(
            name="HTTP Test",
            owner=self.user,
            graph={
                "nodes": [
                    {"id": "node1", "type": "trigger", "config": {}},
                    {"id": "node2", "type": "http_request", "config": {
                        "method": "GET",
                        "url": "https://httpbin.org/get"
                    }}
                ],
                "edges": [
                    {"from": "node1", "to": "node2"}
                ]
            }
        )
        
        execution = WorkflowExecution.objects.create(
            workflow=workflow,
            status="queued"
        )
        
        run_workflow_execution(str(execution.id))
        
        execution.refresh_from_db()
        self.assertIn("success", execution.status.lower())
        self.assertIn("node2", execution.node_results)
        self.assertEqual(execution.node_results["node2"]["status_code"], 200)
        mock_request.assert_called_once()
    
    def test_delay_node_execution(self):
        """Test delay node execution."""
        execution = WorkflowExecution.objects.create(
            workflow=self.workflow,
            status="queued"
        )
        
        start_time = time.time()
        run_workflow_execution(str(execution.id))
        elapsed = time.time() - start_time
        
        execution.refresh_from_db()
        self.assertIn("success", execution.status.lower())
        self.assertIn("node2", execution.node_results)
        # Delay should have taken at least 1 second
        self.assertGreaterEqual(elapsed, 1.0)
    
    @patch('workflows.tasks.send_mail')
    def test_email_node_execution(self, mock_send_mail):
        """Test email node execution."""
        workflow = Workflow.objects.create(
            name="Email Test",
            owner=self.user,
            graph={
                "nodes": [
                    {"id": "node1", "type": "trigger", "config": {}},
                    {"id": "node2", "type": "email_send", "config": {
                        "to": "test@example.com",
                        "subject": "Test",
                        "body": "Test body"
                    }}
                ],
                "edges": [
                    {"from": "node1", "to": "node2"}
                ]
            }
        )
        
        execution = WorkflowExecution.objects.create(
            workflow=workflow,
            status="queued"
        )
        
        run_workflow_execution(str(execution.id))
        
        execution.refresh_from_db()
        self.assertIn("success", execution.status.lower())
        self.assertIn("node2", execution.node_results)
        self.assertTrue(execution.node_results["node2"]["sent"])
        mock_send_mail.assert_called_once()
    
    def test_sequential_execution(self):
        """Test nodes execute in correct order."""
        workflow = Workflow.objects.create(
            name="Sequential Test",
            owner=self.user,
            graph={
                "nodes": [
                    {"id": "node1", "type": "trigger", "config": {}},
                    {"id": "node2", "type": "delay", "config": {"amount": 0.1, "unit": "seconds"}},
                    {"id": "node3", "type": "trigger", "config": {}}
                ],
                "edges": [
                    {"from": "node1", "to": "node2"},
                    {"from": "node2", "to": "node3"}
                ]
            }
        )
        
        execution = WorkflowExecution.objects.create(
            workflow=workflow,
            status="queued"
        )
        
        run_workflow_execution(str(execution.id))
        
        execution.refresh_from_db()
        self.assertIn("success", execution.status.lower())
        # All nodes should have results
        self.assertIn("node1", execution.node_results)
        self.assertIn("node2", execution.node_results)
        self.assertIn("node3", execution.node_results)
    
    def test_execution_logs(self):
        """Test execution logs are saved."""
        execution = WorkflowExecution.objects.create(
            workflow=self.workflow,
            status="queued"
        )
        
        run_workflow_execution(str(execution.id))
        
        execution.refresh_from_db()
        self.assertIsNotNone(execution.logs)
        self.assertGreater(len(execution.logs), 0)
        self.assertIn("Starting execution", execution.logs)
    
    def test_node_failure_stops_execution(self):
        """Test that node failure stops execution."""
        workflow = Workflow.objects.create(
            name="Failure Test",
            owner=self.user,
            graph={
                "nodes": [
                    {"id": "node1", "type": "trigger", "config": {}},
                    {"id": "node2", "type": "http_request", "config": {
                        "method": "GET",
                        "url": ""  # Invalid URL should fail
                    }}
                ],
                "edges": [
                    {"from": "node1", "to": "node2"}
                ]
            }
        )
        
        execution = WorkflowExecution.objects.create(
            workflow=workflow,
            status="queued"
        )
        
        run_workflow_execution(str(execution.id))
        
        execution.refresh_from_db()
        self.assertEqual(execution.status, "failed")
        self.assertIn("node2", execution.node_results)
        self.assertIn("error", execution.node_results["node2"])


class WebhookTriggerTest(TestCase):
    """Test webhook trigger functionality."""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.workflow = Workflow.objects.create(
            name="Webhook Test",
            owner=self.user,
            webhook_enabled=True,
            graph={
                "nodes": [
                    {"id": "node1", "type": "trigger", "config": {}}
                ],
                "edges": []
            }
        )
    
    @patch('workflows.tasks.run_workflow_execution.delay')
    def test_webhook_trigger(self, mock_task):
        """Test webhook triggers execution."""
        client = APIClient()
        response = client.post(
            f'/webhook/{self.workflow.id}/',
            {"test": "data"},
            format='json'
        )
        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertEqual(data['status'], 'triggered')
        self.assertIn('execution_id', data)
        mock_task.assert_called_once()


class EdgeConditionAggregatorTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='edgeuser', password='pass')
        self.workflow = Workflow.objects.create(
            name="Edge Condition Test",
            owner=self.user,
            graph={
                "nodes": [
                    {"id": "trigger", "type": "trigger", "config": {}},
                    {"id": "sumNode", "type": "noop", "config": {"aggregator": "reduce_sum", "reduce_field": "amount"}},
                ],
                "edges": [
                    {"from": "trigger", "to": "sumNode", "condition_expr": "$json.amount > 10"}
                ]
            }
        )
        self.exec = WorkflowExecution.objects.create(
            workflow=self.workflow,
            input_items=[
                {"json": {"amount": 5}},
                {"json": {"amount": 15}},
                {"json": {"amount": 30}},
            ],
            status="queued"
        )

    def test_edge_condition_and_reduce(self):
        from workflows.services.enhanced_execution_engine import EnhancedExecutionEngine
        engine = EnhancedExecutionEngine(self.exec)
        # Simulate trigger outputs equal to input
        engine.node_output_items["trigger"] = self.exec.input_items
        items = engine._get_node_input_items("sumNode")
        # Expect reduce_sum over items with amount > 10 => 15 + 30 = 45
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["json"].get("amount"), 45)


class ConcurrencyTimeoutTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='concuser', password='pass')
        self.workflow = Workflow.objects.create(
            name="Concurrency Test",
            owner=self.user,
            graph={
                "nodes": [
                    {"id": "trigger", "type": "trigger", "config": {}},
                    {"id": "worker", "type": "noop", "config": {"max_parallel": 0, "rate_limit_per_sec": 1, "timeout_ms": 1}},
                ],
                "edges": [
                    {"from": "trigger", "to": "worker"}
                ]
            }
        )
        self.exec = WorkflowExecution.objects.create(
            workflow=self.workflow,
            input_items=[{"json": {}}],
            status="queued"
        )

    def test_rate_limit_blocks_second_schedule(self):
        from workflows.services.node_execution_queue import NodeExecutionQueue
        from workflows.services.enhanced_execution_engine import EnhancedExecutionEngine
        engine = EnhancedExecutionEngine(self.exec)
        engine.node_output_items["trigger"] = self.exec.input_items
        # First check should allow
        allowed1 = NodeExecutionQueue.can_schedule_node(self.exec, "worker", {"rate_limit_per_sec": 1})
        # Second in same second should block
        allowed2 = NodeExecutionQueue.can_schedule_node(self.exec, "worker", {"rate_limit_per_sec": 1})
        self.assertTrue(allowed1)
        self.assertFalse(allowed2)


def test_workflow_chain(user=None, workflow_id=None):
    """
    Test mode function to automatically test: Trigger → HTTP → Delay → Email chain.
    
    Usage:
        from workflows.tests import test_workflow_chain
        result = test_workflow_chain()
    
    Returns:
        dict with test results and assertions
    """
    from django.contrib.auth.models import User
    from .models import Workflow, WorkflowExecution
    from .execution_engine import DAGExecutor
    from unittest.mock import patch
    
    if not user:
        user, _ = User.objects.get_or_create(username='test_user', defaults={'email': 'test@example.com'})
    
    # Create test workflow with chain: Trigger → HTTP → Delay → Email
    workflow_data = {
        "name": "Test Chain Workflow",
        "description": "Automated test workflow",
        "owner": user,
        "graph": {
            "nodes": [
                {
                    "id": "trigger1",
                    "type": "trigger",
                    "name": "Start",
                    "config": {},
                    "x": 100,
                    "y": 100
                },
                {
                    "id": "http1",
                    "type": "http_request",
                    "name": "HTTP Request",
                    "config": {
                        "method": "GET",
                        "url": "https://httpbin.org/get",
                        "headers": [],
                        "body": ""
                    },
                    "x": 300,
                    "y": 100
                },
                {
                    "id": "delay1",
                    "type": "delay",
                    "name": "Delay",
                    "config": {
                        "amount": 1,
                        "unit": "seconds"
                    },
                    "x": 500,
                    "y": 100
                },
                {
                    "id": "email1",
                    "type": "email_send",
                    "name": "Send Email",
                    "config": {
                        "from": "test@example.com",
                        "to": "recipient@example.com",
                        "subject": "Test Email",
                        "body": "Hello {{context.last_http.body.name}}"
                    },
                    "x": 700,
                    "y": 100
                }
            ],
            "edges": [
                {"from": "trigger1", "to": "http1"},
                {"from": "http1", "to": "delay1"},
                {"from": "delay1", "to": "email1"}
            ]
        }
    }
    
    if workflow_id:
        workflow = Workflow.objects.get(id=workflow_id)
        workflow.graph = workflow_data["graph"]
        workflow.save()
    else:
        workflow = Workflow.objects.create(**workflow_data)
    
    # Create execution
    execution = WorkflowExecution.objects.create(
        workflow=workflow,
        input_items=[{"json": {"name": "Test User", "value": 42}}],
        status="queued",
        triggered_by="test"
    )
    
    # Mock email sending
    with patch('workflows.actions.send_mail') as mock_send_mail:
        # Execute workflow
        executor = DAGExecutor(workflow, execution)
        result = executor.execute()
        
        # Refresh execution
        execution.refresh_from_db()
        
        # Assertions
        assertions = {
            "execution_completed": execution.status in ["completed", "success"],
            "all_nodes_executed": all(
                node_id in execution.node_results or 
                node_id in [ne.node_id for ne in execution.node_executions.all()]
                for node_id in ["trigger1", "http1", "delay1", "email1"]
            ),
            "context_passing": "http1" in executor.node_output_items,
            "email_sent": mock_send_mail.called if 'email1' in execution.node_results else False,
            "logs_present": bool(execution.logs) or execution.execution_logs.exists(),
        }
        
        return {
            "success": all(assertions.values()),
            "execution_id": str(execution.id),
            "workflow_id": str(workflow.id),
            "status": execution.status,
            "node_results": execution.node_results,
            "assertions": assertions,
            "logs": execution.logs[:500] if execution.logs else "No logs",
            "execution_logs_count": execution.execution_logs.count(),
        }
