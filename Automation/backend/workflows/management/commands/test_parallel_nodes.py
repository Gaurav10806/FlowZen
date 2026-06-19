"""
Test Parallel Node Implementation

This management command tests the parallel fork and merge nodes
with various scenarios and edge cases.
"""

from django.core.management.base import BaseCommand
from workflows.nodes.parallel_nodes import ParallelForkNode, ParallelMergeNode
from workflows.services.conditional_engine_extension import ConditionalEngineExtension
import json


class Command(BaseCommand):
    help = 'Test parallel node implementation with various scenarios'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--scenario',
            type=str,
            choices=['basic', 'fork', 'merge', 'integration', 'edge_cases', 'all'],
            default='all',
            help='Which test scenario to run'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )
    
    def handle(self, *args, **options):
        self.verbose = options['verbose']
        scenario = options['scenario']
        
        self.stdout.write(self.style.SUCCESS('🔀 Testing Parallel Node Implementation'))
        self.stdout.write('=' * 60)
        
        if scenario == 'all':
            self.test_basic_parallel()
            self.test_fork_node()
            self.test_merge_node()
            self.test_integration()
            self.test_edge_cases()
        elif scenario == 'basic':
            self.test_basic_parallel()
        elif scenario == 'fork':
            self.test_fork_node()
        elif scenario == 'merge':
            self.test_merge_node()
        elif scenario == 'integration':
            self.test_integration()
        elif scenario == 'edge_cases':
            self.test_edge_cases()
        
        self.stdout.write(self.style.SUCCESS('\n✅ All parallel node tests completed!'))
    
    def test_basic_parallel(self):
        """Test basic parallel functionality."""
        self.stdout.write('\n📋 Testing Basic Parallel Functionality')
        self.stdout.write('-' * 40)
        
        # Test fork node
        fork = ParallelForkNode()
        input_data = {'message': 'Test data for parallel processing'}
        params = {
            'branch_count': 3,
            'branch_names': ['process_a', 'process_b', 'process_c'],
            'execution_mode': 'sync',
            'failure_strategy': 'continue_on_error'
        }
        context = {'execution_id': 'test-execution-123', 'node_id': 'fork_1'}
        
        result = fork.run(input_data, params, context)
        fork_result = result['fork_result']
        
        assert fork_result['total_branches'] == 3, f"Expected 3 branches, got {fork_result['total_branches']}"
        assert len(fork_result['branch_executions']) == 3, f"Expected 3 branch executions"
        
        self.stdout.write(self.style.SUCCESS('✓ Basic fork functionality works'))
        
        if self.verbose:
            self.stdout.write(f"  Fork result: {fork_result['fork_status']}")
            self.stdout.write(f"  Branches: {[b['branch_id'] for b in fork_result['branch_executions']]}")
    
    def test_fork_node(self):
        """Test fork node scenarios."""
        self.stdout.write('\n🔀 Testing Fork Node Scenarios')
        self.stdout.write('-' * 40)
        
        fork = ParallelForkNode()
        
        # Test 1: Default branch names
        result = fork.run(
            {'data': 'test'},
            {'branch_count': 2, 'execution_mode': 'sync'},
            {'execution_id': 'test-123'}
        )
        branch_names = [b['branch_id'] for b in result['fork_result']['branch_executions']]
        assert 'branch_1' in branch_names and 'branch_2' in branch_names
        self.stdout.write(self.style.SUCCESS('✓ Default branch names work'))
        
        # Test 2: Custom branch names
        result = fork.run(
            {'data': 'test'},
            {
                'branch_count': 3,
                'branch_names': ['email', 'sms', 'push'],
                'execution_mode': 'sync'
            },
            {'execution_id': 'test-123'}
        )
        branch_names = [b['branch_id'] for b in result['fork_result']['branch_executions']]
        assert branch_names == ['email', 'sms', 'push']
        self.stdout.write(self.style.SUCCESS('✓ Custom branch names work'))
        
        # Test 3: Async mode (simulated)
        result = fork.run(
            {'data': 'test'},
            {
                'branch_count': 2,
                'execution_mode': 'async',
                'timeout_ms': 5000
            },
            {'execution_id': 'test-123'}
        )
        assert result['fork_result']['execution_mode'] == 'async'
        assert result['fork_result']['fork_status'] == 'scheduled'
        self.stdout.write(self.style.SUCCESS('✓ Async mode works'))
        
        if self.verbose:
            for i, test in enumerate(['Default names', 'Custom names', 'Async mode'], 1):
                self.stdout.write(f"  Test {i}: {test} ✓")
    
    def test_merge_node(self):
        """Test merge node scenarios."""
        self.stdout.write('\n🔗 Testing Merge Node Scenarios')
        self.stdout.write('-' * 40)
        
        merge = ParallelMergeNode()
        
        # Test 1: Array merge mode
        input_data = {
            'fork_result': {
                'branch_executions': [
                    {
                        'branch_id': 'branch_a',
                        'execution_id': 'exec-1',
                        'status': 'completed',
                        'result': {'items': [{'id': 1, 'value': 'a'}]}
                    },
                    {
                        'branch_id': 'branch_b',
                        'execution_id': 'exec-2',
                        'status': 'completed',
                        'result': {'items': [{'id': 2, 'value': 'b'}]}
                    }
                ]
            }
        }
        
        result = merge.run(
            input_data,
            {
                'merge_strategy': 'all',
                'merge_mode': 'array',
                'failure_strategy': 'partial_success'
            },
            {'execution_id': 'test-123'}
        )
        
        merge_result = result['merge_result']
        assert merge_result['successful_branches'] == 2
        assert merge_result['total_branches'] == 2
        assert len(merge_result['merged_data']) == 2  # Two items in array
        
        self.stdout.write(self.style.SUCCESS('✓ Array merge mode works'))
        
        # Test 2: Object merge mode
        result = merge.run(
            input_data,
            {
                'merge_strategy': 'all',
                'merge_mode': 'object',
                'failure_strategy': 'partial_success'
            },
            {'execution_id': 'test-123'}
        )
        
        merged_data = result['merge_result']['merged_data']
        assert 'branch_a' in merged_data
        assert 'branch_b' in merged_data
        
        self.stdout.write(self.style.SUCCESS('✓ Object merge mode works'))
        
        # Test 3: First success strategy
        result = merge.run(
            input_data,
            {
                'merge_strategy': 'first_success',
                'merge_mode': 'first',
                'failure_strategy': 'partial_success'
            },
            {'execution_id': 'test-123'}
        )
        
        # Should return result from first successful branch
        assert result['merge_result']['successful_branches'] >= 1
        
        self.stdout.write(self.style.SUCCESS('✓ First success strategy works'))
        
        if self.verbose:
            self.stdout.write(f"  Array merge: {len(merge_result['merged_data'])} items")
            self.stdout.write(f"  Object merge: {list(merged_data.keys())}")
    
    def test_integration(self):
        """Test integration with engine extension."""
        self.stdout.write('\n🔧 Testing Engine Integration')
        self.stdout.write('-' * 40)
        
        # Test parallel node detection
        fork_config = {"type": "parallel_fork", "params": {}}
        merge_config = {"type": "parallel_merge", "params": {}}
        
        assert ConditionalEngineExtension.is_conditional_node(fork_config)
        assert ConditionalEngineExtension.is_conditional_node(merge_config)
        
        self.stdout.write(self.style.SUCCESS('✓ Parallel node detection works'))
        
        # Test fork result processing
        fork_output = {
            "fork_result": {
                "branch_executions": [
                    {"branch_id": "branch_a"},
                    {"branch_id": "branch_b"}
                ]
            }
        }
        
        edges = [
            {"from": "fork_1", "to": "node_a", "condition": "branch_a"},
            {"from": "fork_1", "to": "node_b", "condition": "branch_b"},
            {"from": "fork_1", "to": "node_c", "condition": "branch_c"}
        ]
        
        next_nodes = ConditionalEngineExtension.process_conditional_result(
            fork_output, edges, "fork_1"
        )
        
        assert "node_a" in next_nodes
        assert "node_b" in next_nodes
        assert "node_c" not in next_nodes  # No matching branch
        
        self.stdout.write(self.style.SUCCESS('✓ Fork result processing works'))
        
        # Test merge result processing
        merge_output = {
            "merge_result": {
                "successful_branches": 2,
                "total_branches": 2
            }
        }
        
        edges = [
            {"from": "merge_1", "to": "final_node"}
        ]
        
        next_nodes = ConditionalEngineExtension.process_conditional_result(
            merge_output, edges, "merge_1"
        )
        
        assert next_nodes == ["final_node"]
        
        self.stdout.write(self.style.SUCCESS('✓ Merge result processing works'))
        
        if self.verbose:
            self.stdout.write(f"  Fork next nodes: {next_nodes}")
    
    def test_edge_cases(self):
        """Test edge cases and error conditions."""
        self.stdout.write('\n🔍 Testing Edge Cases')
        self.stdout.write('-' * 40)
        
        fork = ParallelForkNode()
        merge = ParallelMergeNode()
        
        # Test invalid branch count
        try:
            fork.run(
                {"data": "test"},
                {"branch_count": 0},
                {"execution_id": "test"}
            )
            assert False, "Should have raised error for invalid branch count"
        except Exception as e:
            assert "Branch count must be between 1 and 10" in str(e)
        
        self.stdout.write(self.style.SUCCESS('✓ Invalid branch count validation works'))
        
        # Test invalid execution mode
        try:
            fork.run(
                {"data": "test"},
                {"branch_count": 2, "execution_mode": "invalid"},
                {"execution_id": "test"}
            )
            assert False, "Should have raised error for invalid execution mode"
        except Exception as e:
            assert "Invalid execution mode" in str(e)
        
        self.stdout.write(self.style.SUCCESS('✓ Invalid execution mode validation works'))
        
        # Test merge with no branch results
        try:
            merge.run(
                {"no_fork_result": True},
                {"merge_strategy": "all"},
                {"execution_id": "test"}
            )
            assert False, "Should have raised error for no branch results"
        except Exception as e:
            assert "No branch results found" in str(e)
        
        self.stdout.write(self.style.SUCCESS('✓ No branch results validation works'))
        
        # Test merge with partial failures
        input_data = {
            'fork_result': {
                'branch_executions': [
                    {
                        'branch_id': 'success_branch',
                        'status': 'completed',
                        'result': {'items': [{'success': True}]}
                    },
                    {
                        'branch_id': 'failed_branch',
                        'status': 'failed',
                        'error': 'Branch execution failed'
                    }
                ]
            }
        }
        
        result = merge.run(
            input_data,
            {
                'merge_strategy': 'all',
                'failure_strategy': 'partial_success'
            },
            {'execution_id': 'test'}
        )
        
        merge_result = result['merge_result']
        assert merge_result['successful_branches'] == 1
        assert merge_result['failed_branches'] == 1
        
        self.stdout.write(self.style.SUCCESS('✓ Partial failure handling works'))
        
        # Test workflow validation
        workflow_graph = {
            "nodes": [
                {"id": "fork_1", "type": "parallel_fork", "params": {"branch_count": 2, "branch_names": ["a", "b"]}}
            ],
            "edges": [
                {"from": "fork_1", "to": "node_a", "condition": "a"},
                {"from": "fork_1", "to": "node_c", "condition": "c"}  # Undefined branch
            ]
        }
        
        errors = ConditionalEngineExtension.validate_conditional_edges(workflow_graph)
        assert any("undefined branches" in error for error in errors)
        
        self.stdout.write(self.style.SUCCESS('✓ Workflow validation works'))
        
        if self.verbose:
            self.stdout.write(f"  Validation errors: {len(errors)}")
    
    def test_real_world_scenario(self):
        """Test a complete real-world scenario."""
        self.stdout.write('\n🌍 Testing Real-World Scenario')
        self.stdout.write('-' * 40)
        
        # Simulate multi-channel notification workflow
        fork = ParallelForkNode()
        merge = ParallelMergeNode()
        
        # Step 1: Fork for multiple notification channels
        notification_data = {
            'recipient': {'email': 'user@example.com', 'phone': '+1234567890'},
            'message': 'Your order has been shipped!',
            'subject': 'Order Update'
        }
        
        fork_result = fork.run(
            notification_data,
            {
                'branch_count': 3,
                'branch_names': ['email', 'sms', 'push'],
                'execution_mode': 'sync',
                'failure_strategy': 'continue_on_error'
            },
            {'execution_id': 'notification-123'}
        )
        
        # Simulate branch execution results
        simulated_results = {
            'fork_result': {
                'branch_executions': [
                    {
                        'branch_id': 'email',
                        'status': 'completed',
                        'result': {'delivery_status': 'sent', 'message_id': 'email-456'}
                    },
                    {
                        'branch_id': 'sms',
                        'status': 'completed',
                        'result': {'delivery_status': 'sent', 'message_id': 'sms-789'}
                    },
                    {
                        'branch_id': 'push',
                        'status': 'failed',
                        'error': 'Device not registered'
                    }
                ]
            }
        }
        
        # Step 2: Merge results
        merge_result = merge.run(
            simulated_results,
            {
                'merge_strategy': 'all',
                'merge_mode': 'object',
                'failure_strategy': 'partial_success'
            },
            {'execution_id': 'notification-123'}
        )
        
        final_result = merge_result['merge_result']
        
        # Verify results
        assert final_result['successful_branches'] == 2  # email and sms
        assert final_result['failed_branches'] == 1     # push
        assert 'email' in final_result['branch_results']
        assert 'sms' in final_result['branch_results']
        assert 'push' in final_result['branch_results']
        
        self.stdout.write(self.style.SUCCESS('✓ Real-world notification scenario works'))
        
        if self.verbose:
            self.stdout.write(f"  Successful deliveries: {final_result['successful_branches']}")
            self.stdout.write(f"  Failed deliveries: {final_result['failed_branches']}")
            self.stdout.write(f"  Channels: {list(final_result['branch_results'].keys())}")
        
        return final_result