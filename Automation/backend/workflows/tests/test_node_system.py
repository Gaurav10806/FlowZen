"""
Tests for the Node System

This module tests the core node system functionality.
"""

import unittest
from django.test import TestCase
from django.contrib.auth.models import User

from ..nodes import (
    BaseNode, NodeExecutionError, node_registry, register_node,
    get_node_class, list_available_nodes
)
from ..nodes.trigger_nodes import WebhookTriggerNode, ManualTriggerNode
from ..nodes.action_nodes import HttpRequestNode, EmailSenderNode
from ..nodes.utility_nodes import DelayNode, ConditionalNode, DataTransformNode
from ..models import Workflow, WorkflowExecution, Tenant


class TestNodeRegistry(TestCase):
    """Test the node registry system."""
    
    def setUp(self):
        """Set up test data."""
        # Force registry auto-discovery
        node_registry.auto_discover()
    
    def test_registry_auto_discovery(self):
        """Test that auto-discovery finds and registers nodes."""
        # Check that nodes are registered
        node_types = node_registry.list_node_types()
        
        # Should have at least our core nodes
        expected_nodes = [
            'webhook_trigger',
            'manual_trigger',
            'http_request',
            'email_sender',
            'delay',
            'conditional',
            'data_transform'
        ]
        
        for expected_node in expected_nodes:
            self.assertIn(expected_node, node_types, f"Node {expected_node} not found in registry")
    
    def test_get_node_class(self):
        """Test getting node classes from registry."""
        # Test getting a known node
        node_class = node_registry.get_node_class('webhook_trigger')
        self.assertEqual(node_class, WebhookTriggerNode)
        
        # Test getting unknown node
        with self.assertRaises(KeyError):
            node_registry.get_node_class('unknown_node')
    
    def test_node_schemas(self):
        """Test that all nodes have valid schemas."""
        schemas = node_registry.get_node_schemas()
        
        for node_type, schema in schemas.items():
            # Check required schema fields
            self.assertIn('type', schema)
            self.assertIn('name', schema)
            self.assertIn('category', schema)
            self.assertIn('parameter_schema', schema)
            
            # Check parameter schema structure
            param_schema = schema['parameter_schema']
            self.assertIsInstance(param_schema, dict)
            self.assertEqual(param_schema.get('type'), 'object')
            self.assertIn('properties', param_schema)
    
    def test_validate_workflow_nodes(self):
        """Test workflow node validation."""
        # Valid workflow
        valid_workflow = {
            'meta': {'name': 'Test Workflow'},
            'trigger': {'type': 'webhook_trigger', 'params': {}},
            'nodes': {
                'node1': {'type': 'http_request', 'params': {}}
            },
            'connections': {}
        }
        
        errors = node_registry.validate_workflow_nodes(valid_workflow)
        self.assertEqual(len(errors), 0)
        
        # Invalid workflow with unknown node
        invalid_workflow = {
            'meta': {'name': 'Test Workflow'},
            'trigger': {'type': 'unknown_trigger', 'params': {}},
            'nodes': {},
            'connections': {}
        }
        
        errors = node_registry.validate_workflow_nodes(invalid_workflow)
        self.assertGreater(len(errors), 0)
        self.assertIn('unknown_trigger', errors[0])


class TestBaseNode(TestCase):
    """Test the BaseNode functionality."""
    
    def test_base_node_abstract(self):
        """Test that BaseNode cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            BaseNode()
    
    def test_node_type_generation(self):
        """Test automatic node type generation."""
        # Test with NODE_TYPE attribute
        self.assertEqual(WebhookTriggerNode.get_node_type(), 'webhook_trigger')
        
        # Test with class name fallback
        class TestActionNode(BaseNode):
            def run(self, input_data, params, context):
                return {}
        
        self.assertEqual(TestActionNode.get_node_type(), 'testaction')
    
    def test_template_resolution(self):
        """Test template variable resolution."""
        class TestNode(BaseNode):
            def run(self, input_data, params, context):
                return {}
        
        node = TestNode()
        
        # Test simple template
        input_data = {'user': {'name': 'John', 'email': 'john@example.com'}}
        context = {'env': {'API_KEY': 'secret123'}}
        
        result = node._resolve_template('Hello {{user.name}}!', input_data, context)
        self.assertEqual(result, 'Hello John!')
        
        # Test nested template
        result = node._resolve_template('Email: {{user.email}}', input_data, context)
        self.assertEqual(result, 'Email: john@example.com')
        
        # Test context template
        result = node._resolve_template('Key: {{env.API_KEY}}', input_data, context)
        self.assertEqual(result, 'Key: secret123')
        
        # Test missing variable
        result = node._resolve_template('Missing: {{missing.var}}', input_data, context)
        self.assertEqual(result, 'Missing: {{missing.var}}')


class TestTriggerNodes(TestCase):
    """Test trigger node implementations."""
    
    def test_webhook_trigger_node(self):
        """Test webhook trigger node."""
        node = WebhookTriggerNode()
        
        # Test basic webhook execution
        input_data = {
            'body': {'customer': {'name': 'John', 'email': 'john@example.com'}},
            'headers': {'content-type': 'application/json'},
            'method': 'POST'
        }
        params = {
            'path': '/webhook/customer-signup',
            'method': 'POST',
            'authentication': 'none'
        }
        context = {
            'execution_timestamp': '2024-01-01T00:00:00Z',
            'webhook_id': 'webhook_123'
        }
        
        result = node.run(input_data, params, context)
        
        # Check result structure
        self.assertIn('webhook', result)
        self.assertIn('trigger_data', result)
        self.assertIn('customer', result)  # Payload fields at root level
        
        # Check webhook data
        webhook_data = result['webhook']
        self.assertEqual(webhook_data['method'], 'POST')
        self.assertEqual(webhook_data['webhook_id'], 'webhook_123')
        
        # Check trigger data
        self.assertEqual(result['trigger_data'], input_data['body'])
    
    def test_manual_trigger_node(self):
        """Test manual trigger node."""
        node = ManualTriggerNode()
        
        input_data = {'user_data': {'test': True}}
        params = {
            'test_data': {'sample': 'data'},
            'description': 'Test execution'
        }
        context = {
            'execution_timestamp': '2024-01-01T00:00:00Z',
            'user_id': 'user_123'
        }
        
        result = node.run(input_data, params, context)
        
        # Check result structure
        self.assertIn('manual', result)
        self.assertIn('trigger_data', result)
        
        # Check merged data
        self.assertIn('test', result)  # From user_data
        self.assertIn('sample', result)  # From test_data


class TestActionNodes(TestCase):
    """Test action node implementations."""
    
    def test_delay_node(self):
        """Test delay node."""
        node = DelayNode()
        
        input_data = {'test': 'data'}
        params = {
            'type': 'seconds',
            'value': 0.1  # Very short delay for testing
        }
        context = {}
        
        import time
        start_time = time.time()
        result = node.run(input_data, params, context)
        end_time = time.time()
        
        # Check that delay occurred
        self.assertGreaterEqual(end_time - start_time, 0.1)
        
        # Check result structure
        self.assertIn('test', result)  # Input data passed through
        self.assertIn('delay_info', result)
        
        delay_info = result['delay_info']
        self.assertEqual(delay_info['delay_type'], 'seconds')
        self.assertEqual(delay_info['delay_value'], 0.1)
    
    def test_conditional_node(self):
        """Test conditional node."""
        node = ConditionalNode()
        
        input_data = {'user': {'age': 25, 'status': 'active'}}
        params = {
            'conditions': [
                {
                    'type': 'greater_than',
                    'field': 'user.age',
                    'value': 18,
                    'path': 'adult_path'
                },
                {
                    'type': 'equals',
                    'field': 'user.status',
                    'value': 'inactive',
                    'path': 'inactive_path'
                }
            ],
            'default_path': 'default_path'
        }
        context = {}
        
        result = node.run(input_data, params, context)
        
        # Should match first condition (age > 18)
        self.assertIn('condition_result', result)
        condition_result = result['condition_result']
        self.assertTrue(condition_result['matched'])
        self.assertEqual(condition_result['path'], 'adult_path')
        self.assertEqual(condition_result['condition_index'], 0)
    
    def test_data_transform_node(self):
        """Test data transform node."""
        node = DataTransformNode()
        
        input_data = {
            'user': {'first_name': 'John', 'last_name': 'Doe'},
            'metadata': {'source': 'api'}
        }
        params = {
            'transformations': [
                {
                    'type': 'set_field',
                    'field': 'user.full_name',
                    'value': '{{user.first_name}} {{user.last_name}}'
                },
                {
                    'type': 'copy_field',
                    'source': 'metadata.source',
                    'target': 'data_source'
                },
                {
                    'type': 'remove_field',
                    'field': 'user.last_name'
                }
            ]
        }
        context = {}
        
        result = node.run(input_data, params, context)
        
        # Check transformations applied
        self.assertEqual(result['user']['full_name'], 'John Doe')
        self.assertEqual(result['data_source'], 'api')
        self.assertNotIn('last_name', result['user'])
        
        # Check transform info
        self.assertIn('transform_info', result)
        self.assertEqual(result['transform_info']['transformations_applied'], 3)


class TestNodeExecution(TestCase):
    """Test complete node execution flow."""
    
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
        
        # Create a simple workflow with new JSON contract
        self.workflow_definition = {
            'meta': {
                'name': 'Test Workflow',
                'description': 'A test workflow',
                'version': '1.0.0',
                'active': True
            },
            'trigger': {
                'id': 'trigger_1',
                'type': 'manual_trigger',
                'name': 'Manual Trigger',
                'params': {
                    'test_data': {'message': 'Hello World'}
                }
            },
            'nodes': {
                'delay_1': {
                    'id': 'delay_1',
                    'type': 'delay',
                    'name': 'Short Delay',
                    'params': {
                        'type': 'seconds',
                        'value': 0.1
                    }
                },
                'transform_1': {
                    'id': 'transform_1',
                    'type': 'data_transform',
                    'name': 'Add Timestamp',
                    'params': {
                        'transformations': [
                            {
                                'type': 'set_field',
                                'field': 'processed_at',
                                'value': '2024-01-01T00:00:00Z'
                            }
                        ]
                    }
                }
            },
            'connections': {
                'trigger_1': ['delay_1'],
                'delay_1': ['transform_1'],
                'transform_1': []
            }
        }
        
        self.workflow = Workflow.objects.create(
            name='Test Workflow',
            definition=self.workflow_definition,
            owner=self.user,
            tenant=self.tenant
        )
    
    def test_workflow_execution_with_nodes(self):
        """Test complete workflow execution using node system."""
        from ..execution.node_executor import NodeBasedExecutor
        
        # Create execution
        execution = WorkflowExecution.objects.create(
            workflow=self.workflow,
            status='pending',
            input_data={'test': True},
            created_by=self.user,
            tenant=self.tenant
        )
        
        # Execute workflow
        executor = NodeBasedExecutor(self.workflow, execution)
        result = executor.execute()
        
        # Check execution completed
        execution.refresh_from_db()
        self.assertEqual(execution.status, 'completed')
        
        # Check result contains expected data
        self.assertIn('message', result)  # From trigger
        self.assertIn('delay_info', result)  # From delay node
        self.assertIn('processed_at', result)  # From transform node
        self.assertEqual(result['message'], 'Hello World')
        self.assertEqual(result['processed_at'], '2024-01-01T00:00:00Z')


if __name__ == '__main__':
    unittest.main()