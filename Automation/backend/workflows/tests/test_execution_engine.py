"""
Tests for the Core Execution Engine

This module tests the workflow execution engine functionality.
"""

import unittest
from datetime import datetime
from django.test import TestCase

from ..execution.core_engine import (
    WorkflowExecutionEngine, ExecutionContext, NodeExecutionResult,
    WorkflowExecutionResult, execute_workflow
)
from ..nodes import node_registry


class TestExecutionContext(TestCase):
    """Test the ExecutionContext class."""
    
    def test_context_creation(self):
        """Test creating execution context."""
        context = ExecutionContext(
            workflow_id="workflow_123",
            execution_id="execution_456",
            user_id="user_789"
        )
        
        self.assertEqual(context.workflow_id, "workflow_123")
        self.assertEqual(context.execution_id, "execution_456")
        self.assertEqual(context.user_id, "user_789")
        self.assertIsInstance(context.variables, dict)
        self.assertIsInstance(context.secrets, dict)
        self.assertIsInstance(context.started_at, datetime)
    
    def test_context_to_dict(self):
        """Test converting context to dictionary."""
        context = ExecutionContext(
            workflow_id="workflow_123",
            execution_id="execution_456"
        )
        
        context_dict = context.to_dict()
        
        self.assertIn('workflow_id', context_dict)
        self.assertIn('execution_id', context_dict)
        self.assertIn('variables', context_dict)
        self.assertIn('secrets', context_dict)
        self.assertEqual(context_dict['workflow_id'], "workflow_123")


class TestWorkflowExecutionEngine(TestCase):
    """Test the core workflow execution engine."""
    
    def setUp(self):
        """Set up test data."""
        self.engine = WorkflowExecutionEngine()
        
        # Ensure node registry is initialized
        node_registry.auto_discover()
        
        # Simple test workflow
        self.simple_workflow = {
            "meta": {
                "name": "Simple Test Workflow",
                "version": "1.0.0",
                "active": True
            },
            "trigger": {
                "id": "trigger_1",
                "type": "manual_trigger",
                "params": {
                    "test_data": {"message": "Hello World"}
                }
            },
            "nodes": {
                "delay_1": {
                    "id": "delay_1",
                    "type": "delay",
                    "params": {
                        "type": "seconds",
                        "value": 0.1
                    }
                },
                "logger_1": {
                    "id": "logger_1",
                    "type": "logger",
                    "params": {
                        "message": "Processing complete: {{message}}",
                        "level": "info"
                    }
                }
            },
            "connections": {
                "trigger_1": ["delay_1"],
                "delay_1": ["logger_1"],
                "logger_1": []
            }
        }
        
        # Complex workflow with branching
        self.complex_workflow = {
            "meta": {
                "name": "Complex Test Workflow",
                "version": "1.0.0",
                "active": True
            },
            "trigger": {
                "id": "webhook_1",
                "type": "webhook_trigger",
                "params": {
                    "path": "/test-webhook",
                    "method": "POST"
                }
            },
            "nodes": {
                "condition_1": {
                    "id": "condition_1",
                    "type": "conditional",
                    "params": {
                        "conditions": [
                            {
                                "type": "exists",
                                "field": "user.email",
                                "path": "has_email"
                            }
                        ],
                        "default_path": "no_email"
                    }
                },
                "transform_1": {
                    "id": "transform_1",
                    "type": "data_transform",
                    "params": {
                        "transformations": [
                            {
                                "type": "set_field",
                                "field": "processed",
                                "value": True
                            }
                        ]
                    }
                }
            },
            "connections": {
                "webhook_1": ["condition_1"],
                "condition_1": ["transform_1"],
                "transform_1": []
            }
        }
    
    def test_validate_workflow_structure(self):
        """Test workflow structure validation."""
        # Valid workflow should pass
        self.engine._validate_workflow_structure(self.simple_workflow)
        
        # Invalid workflow should fail
        invalid_workflow = {
            "meta": {"name": "Invalid"},
            # Missing trigger, nodes, connections
        }
        
        with self.assertRaises(ValueError) as cm:
            self.engine._validate_workflow_structure(invalid_workflow)
        
        self.assertIn("missing required key", str(cm.exception))
    
    def test_validate_dag_structure(self):
        """Test DAG structure validation."""
        nodes = self.simple_workflow["nodes"]
        connections = self.simple_workflow["connections"]
        
        # Valid DAG should pass
        self.engine._validate_dag_structure(nodes, connections)
        
        # Cyclic connections should fail
        cyclic_connections = {
            "node_a": ["node_b"],
            "node_b": ["node_c"],
            "node_c": ["node_a"]  # Creates cycle
        }
        
        cyclic_nodes = {
            "node_a": {"type": "delay"},
            "node_b": {"type": "delay"},
            "node_c": {"type": "delay"}
        }
        
        with self.assertRaises(ValueError) as cm:
            self.engine._validate_dag_structure(cyclic_nodes, cyclic_connections)
        
        self.assertIn("cycle", str(cm.exception))
    
    def test_resolve_execution_order(self):
        """Test execution order resolution."""
        nodes = self.simple_workflow["nodes"]
        connections = self.simple_workflow["connections"]
        trigger_id = "trigger_1"
        
        order = self.engine._resolve_execution_order(nodes, connections, trigger_id)
        
        # Should return nodes in correct order
        self.assertEqual(len(order), 2)
        self.assertIn("delay_1", order)
        self.assertIn("logger_1", order)
        
        # delay_1 should come before logger_1
        delay_index = order.index("delay_1")
        logger_index = order.index("logger_1")
        self.assertLess(delay_index, logger_index)
    
    def test_execute_trigger(self):
        """Test trigger execution."""
        trigger = self.simple_workflow["trigger"]
        trigger_input = {"test": True}
        
        context = ExecutionContext(
            workflow_id="test_workflow",
            execution_id="test_execution"
        )
        
        result = self.engine._execute_trigger(trigger, trigger_input, context)
        
        self.assertIsInstance(result, NodeExecutionResult)
        self.assertTrue(result.success)
        self.assertEqual(result.node_id, "trigger_1")
        self.assertEqual(result.node_type, "manual_trigger")
        self.assertIn("message", result.output_data)
    
    def test_execute_node(self):
        """Test individual node execution."""
        node_id = "delay_1"
        node_def = self.simple_workflow["nodes"][node_id]
        input_data = {"message": "test"}
        
        context = ExecutionContext(
            workflow_id="test_workflow",
            execution_id="test_execution"
        )
        
        result = self.engine._execute_node(node_id, node_def, input_data, context)
        
        self.assertIsInstance(result, NodeExecutionResult)
        self.assertTrue(result.success)
        self.assertEqual(result.node_id, "delay_1")
        self.assertEqual(result.node_type, "delay")
        self.assertIn("delay_info", result.output_data)
    
    def test_simple_workflow_execution(self):
        """Test complete simple workflow execution."""
        trigger_input = {"user_data": {"test": True}}
        
        context = ExecutionContext(
            workflow_id="test_workflow",
            execution_id="test_execution"
        )
        
        result = self.engine.run(self.simple_workflow, trigger_input, context)
        
        self.assertIsInstance(result, WorkflowExecutionResult)
        self.assertTrue(result.success)
        self.assertEqual(len(result.node_results), 3)  # trigger + 2 nodes
        
        # Check that data flowed through nodes
        final_output = result.final_output
        self.assertIn("message", final_output)  # From trigger
        self.assertIn("delay_info", final_output)  # From delay node
        self.assertIn("log_info", final_output)  # From logger node
    
    def test_complex_workflow_execution(self):
        """Test complex workflow with conditional logic."""
        trigger_input = {
            "body": {"user": {"email": "test@example.com", "name": "Test User"}},
            "headers": {"content-type": "application/json"},
            "method": "POST"
        }
        
        context = ExecutionContext(
            workflow_id="test_workflow",
            execution_id="test_execution"
        )
        
        result = self.engine.run(self.complex_workflow, trigger_input, context)
        
        self.assertIsInstance(result, WorkflowExecutionResult)
        self.assertTrue(result.success)
        
        # Check conditional result
        final_output = result.final_output
        self.assertIn("condition_result", final_output)
        self.assertTrue(final_output["condition_result"]["matched"])
        
        # Check transformation result
        self.assertIn("processed", final_output)
        self.assertTrue(final_output["processed"])
    
    def test_workflow_execution_with_node_failure(self):
        """Test workflow execution when a node fails."""
        # Create workflow with invalid node parameters
        failing_workflow = {
            "meta": {"name": "Failing Workflow", "version": "1.0.0"},
            "trigger": {
                "id": "trigger_1",
                "type": "manual_trigger",
                "params": {"test_data": {"message": "test"}}
            },
            "nodes": {
                "delay_1": {
                    "id": "delay_1",
                    "type": "delay",
                    "params": {
                        "type": "invalid_type",  # This will cause failure
                        "value": 1
                    }
                }
            },
            "connections": {
                "trigger_1": ["delay_1"],
                "delay_1": []
            }
        }
        
        context = ExecutionContext(
            workflow_id="test_workflow",
            execution_id="test_execution"
        )
        
        result = self.engine.run(failing_workflow, {}, context)
        
        self.assertIsInstance(result, WorkflowExecutionResult)
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error_message)
        self.assertIn("delay_1", result.error_message)
    
    def test_workflow_execution_with_missing_node_type(self):
        """Test workflow execution with unknown node type."""
        invalid_workflow = {
            "meta": {"name": "Invalid Workflow", "version": "1.0.0"},
            "trigger": {
                "id": "trigger_1",
                "type": "manual_trigger",
                "params": {"test_data": {"message": "test"}}
            },
            "nodes": {
                "unknown_1": {
                    "id": "unknown_1",
                    "type": "unknown_node_type",  # This doesn't exist
                    "params": {}
                }
            },
            "connections": {
                "trigger_1": ["unknown_1"],
                "unknown_1": []
            }
        }
        
        context = ExecutionContext(
            workflow_id="test_workflow",
            execution_id="test_execution"
        )
        
        result = self.engine.run(invalid_workflow, {}, context)
        
        self.assertFalse(result.success)
        self.assertIn("unknown_node_type", result.error_message)


class TestConvenienceFunction(TestCase):
    """Test the convenience execute_workflow function."""
    
    def setUp(self):
        """Set up test data."""
        node_registry.auto_discover()
        
        self.test_workflow = {
            "meta": {"name": "Test Workflow", "version": "1.0.0"},
            "trigger": {
                "id": "trigger_1",
                "type": "manual_trigger",
                "params": {"test_data": {"status": "ready"}}
            },
            "nodes": {
                "logger_1": {
                    "id": "logger_1",
                    "type": "logger",
                    "params": {
                        "message": "Status: {{status}}",
                        "level": "info"
                    }
                }
            },
            "connections": {
                "trigger_1": ["logger_1"],
                "logger_1": []
            }
        }
    
    def test_execute_workflow_convenience_function(self):
        """Test the convenience execute_workflow function."""
        result = execute_workflow(
            workflow_json=self.test_workflow,
            trigger_input={"user_data": {"custom": "data"}},
            user_id="test_user"
        )
        
        self.assertIsInstance(result, WorkflowExecutionResult)
        self.assertTrue(result.success)
        
        # Check that data flowed correctly
        final_output = result.final_output
        self.assertIn("status", final_output)
        self.assertEqual(final_output["status"], "ready")
    
    def test_execute_workflow_with_defaults(self):
        """Test convenience function with default parameters."""
        result = execute_workflow(self.test_workflow)
        
        self.assertTrue(result.success)
        self.assertIsNotNone(result.total_execution_time_ms)


if __name__ == '__main__':
    unittest.main()