"""
Test Router Node Implementation

This management command tests the router node functionality
with various scenarios and edge cases.
"""

from django.core.management.base import BaseCommand
from workflows.nodes.router_node import RouterNode
from workflows.services.conditional_engine_extension import ConditionalEngineExtension
import json


class Command(BaseCommand):
    help = 'Test router node implementation with various scenarios'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--scenario',
            type=str,
            choices=['basic', 'chat_intent', 'priority', 'edge_cases', 'all'],
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
        
        self.stdout.write(self.style.SUCCESS('🔀 Testing Router Node Implementation'))
        self.stdout.write('=' * 60)
        
        if scenario == 'all':
            self.test_basic_routing()
            self.test_chat_intent_routing()
            self.test_priority_routing()
            self.test_edge_cases()
        elif scenario == 'basic':
            self.test_basic_routing()
        elif scenario == 'chat_intent':
            self.test_chat_intent_routing()
        elif scenario == 'priority':
            self.test_priority_routing()
        elif scenario == 'edge_cases':
            self.test_edge_cases()
        
        self.stdout.write(self.style.SUCCESS('\n✅ All router node tests completed!'))
    
    def test_basic_routing(self):
        """Test basic router functionality."""
        self.stdout.write('\n📋 Testing Basic Router Functionality')
        self.stdout.write('-' * 40)
        
        router = RouterNode()
        
        # Test simple string matching
        input_data = {"message": "I need help with billing"}
        params = {
            "rules": [
                {
                    "name": "billing",
                    "left_operand": "{{message}}",
                    "operator": "contains",
                    "right_operand": "billing"
                },
                {
                    "name": "support",
                    "left_operand": "{{message}}",
                    "operator": "contains",
                    "right_operand": "support"
                }
            ],
            "default_path": "general"
        }
        
        result = router.run(input_data, params, {})
        router_result = result['router_result']
        
        assert router_result['selected_path'] == 'billing', f"Expected 'billing', got {router_result['selected_path']}"
        assert len(router_result['matched_paths']) == 1, f"Expected 1 match, got {len(router_result['matched_paths'])}"
        
        self.stdout.write(self.style.SUCCESS('✓ Basic string matching works'))
        
        if self.verbose:
            self.stdout.write(f"  Selected path: {router_result['selected_path']}")
            self.stdout.write(f"  Matched paths: {router_result['matched_paths']}")
    
    def test_chat_intent_routing(self):
        """Test chat intent routing scenario."""
        self.stdout.write('\n💬 Testing Chat Intent Routing')
        self.stdout.write('-' * 40)
        
        router = RouterNode()
        
        test_cases = [
            {
                "input": {"text": "I want a refund for my purchase"},
                "expected": "billing"
            },
            {
                "input": {"text": "There's a bug in your app"},
                "expected": "support"
            },
            {
                "input": {"text": "Can I see pricing for premium?"},
                "expected": "sales"
            },
            {
                "input": {"text": "Hello, how are you?"},
                "expected": "general"
            }
        ]
        
        params = {
            "rules": [
                {
                    "name": "billing",
                    "left_operand": "{{text}}",
                    "operator": "contains",
                    "right_operand": "refund"
                },
                {
                    "name": "billing",
                    "left_operand": "{{text}}",
                    "operator": "contains",
                    "right_operand": "payment"
                },
                {
                    "name": "support",
                    "left_operand": "{{text}}",
                    "operator": "contains",
                    "right_operand": "bug"
                },
                {
                    "name": "support",
                    "left_operand": "{{text}}",
                    "operator": "contains",
                    "right_operand": "error"
                },
                {
                    "name": "sales",
                    "left_operand": "{{text}}",
                    "operator": "contains",
                    "right_operand": "pricing"
                },
                {
                    "name": "sales",
                    "left_operand": "{{text}}",
                    "operator": "contains",
                    "right_operand": "demo"
                }
            ],
            "default_path": "general",
            "case_sensitive": False
        }
        
        for i, test_case in enumerate(test_cases):
            result = router.run(test_case["input"], params, {})
            router_result = result['router_result']
            selected_path = router_result['selected_path']
            
            assert selected_path == test_case["expected"], \
                f"Test {i+1}: Expected '{test_case['expected']}', got '{selected_path}'"
            
            if self.verbose:
                self.stdout.write(f"  Test {i+1}: '{test_case['input']['text'][:30]}...' -> {selected_path}")
        
        self.stdout.write(self.style.SUCCESS('✓ Chat intent routing works'))
    
    def test_priority_routing(self):
        """Test priority-based routing."""
        self.stdout.write('\n⚡ Testing Priority Routing')
        self.stdout.write('-' * 40)
        
        router = RouterNode()
        
        test_cases = [
            {
                "input": {"priority": "critical", "batch_size": 50},
                "expected": "critical"
            },
            {
                "input": {"priority": "normal", "batch_size": 150},
                "expected": "high_volume"
            },
            {
                "input": {"priority": "urgent", "batch_size": 10},
                "expected": "urgent"
            },
            {
                "input": {"priority": "low", "batch_size": 5},
                "expected": "standard"
            }
        ]
        
        params = {
            "rules": [
                {
                    "name": "critical",
                    "left_operand": "{{priority}}",
                    "operator": "equals",
                    "right_operand": "critical"
                },
                {
                    "name": "urgent",
                    "left_operand": "{{priority}}",
                    "operator": "equals",
                    "right_operand": "urgent"
                },
                {
                    "name": "high_volume",
                    "left_operand": "{{batch_size}}",
                    "operator": "greater_than",
                    "right_operand": "100"
                }
            ],
            "default_path": "standard",
            "evaluation_strategy": "first_match"
        }
        
        for i, test_case in enumerate(test_cases):
            result = router.run(test_case["input"], params, {})
            router_result = result['router_result']
            selected_path = router_result['selected_path']
            
            assert selected_path == test_case["expected"], \
                f"Test {i+1}: Expected '{test_case['expected']}', got '{selected_path}'"
            
            if self.verbose:
                self.stdout.write(f"  Test {i+1}: priority={test_case['input']['priority']}, batch_size={test_case['input']['batch_size']} -> {selected_path}")
        
        self.stdout.write(self.style.SUCCESS('✓ Priority routing works'))
    
    def test_edge_cases(self):
        """Test edge cases and error conditions."""
        self.stdout.write('\n🔍 Testing Edge Cases')
        self.stdout.write('-' * 40)
        
        router = RouterNode()
        
        # Test empty rules with default path
        result = router.run(
            {"data": "test"},
            {"rules": [], "default_path": "fallback"},
            {}
        )
        assert result['router_result']['selected_path'] == 'fallback'
        self.stdout.write(self.style.SUCCESS('✓ Empty rules with default path'))
        
        # Test no matching rules
        result = router.run(
            {"message": "hello world"},
            {
                "rules": [
                    {
                        "name": "billing",
                        "left_operand": "{{message}}",
                        "operator": "contains",
                        "right_operand": "refund"
                    }
                ],
                "default_path": "general"
            },
            {}
        )
        assert result['router_result']['selected_path'] == 'general'
        self.stdout.write(self.style.SUCCESS('✓ No matching rules uses default'))
        
        # Test case sensitivity
        result = router.run(
            {"text": "BILLING ISSUE"},
            {
                "rules": [
                    {
                        "name": "billing",
                        "left_operand": "{{text}}",
                        "operator": "contains",
                        "right_operand": "billing"
                    }
                ],
                "default_path": "general",
                "case_sensitive": True
            },
            {}
        )
        assert result['router_result']['selected_path'] == 'general'  # Should not match due to case
        
        result = router.run(
            {"text": "BILLING ISSUE"},
            {
                "rules": [
                    {
                        "name": "billing",
                        "left_operand": "{{text}}",
                        "operator": "contains",
                        "right_operand": "billing"
                    }
                ],
                "default_path": "general",
                "case_sensitive": False
            },
            {}
        )
        assert result['router_result']['selected_path'] == 'billing'  # Should match case-insensitive
        self.stdout.write(self.style.SUCCESS('✓ Case sensitivity works'))
        
        # Test numeric comparisons
        result = router.run(
            {"score": 85},
            {
                "rules": [
                    {
                        "name": "high_score",
                        "left_operand": "{{score}}",
                        "operator": "greater_than",
                        "right_operand": "80"
                    }
                ],
                "default_path": "low_score"
            },
            {}
        )
        assert result['router_result']['selected_path'] == 'high_score'
        self.stdout.write(self.style.SUCCESS('✓ Numeric comparisons work'))
        
        # Test regex matching
        result = router.run(
            {"email": "user@example.com"},
            {
                "rules": [
                    {
                        "name": "valid_email",
                        "left_operand": "{{email}}",
                        "operator": "regex_match",
                        "right_operand": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
                    }
                ],
                "default_path": "invalid_email"
            },
            {}
        )
        assert result['router_result']['selected_path'] == 'valid_email'
        self.stdout.write(self.style.SUCCESS('✓ Regex matching works'))
        
        # Test list operations
        result = router.run(
            {"category": "electronics"},
            {
                "rules": [
                    {
                        "name": "allowed_category",
                        "left_operand": "{{category}}",
                        "operator": "in_list",
                        "right_operand": '["electronics", "books", "clothing"]'
                    }
                ],
                "default_path": "restricted"
            },
            {}
        )
        assert result['router_result']['selected_path'] == 'allowed_category'
        self.stdout.write(self.style.SUCCESS('✓ List operations work'))
    
    def test_engine_integration(self):
        """Test integration with conditional engine extension."""
        self.stdout.write('\n🔧 Testing Engine Integration')
        self.stdout.write('-' * 40)
        
        # Test router node detection
        router_config = {"type": "router", "params": {}}
        assert ConditionalEngineExtension.is_conditional_node(router_config)
        
        # Test path processing
        router_output = {
            "router_result": {
                "selected_path": "billing",
                "matched_paths": ["billing"]
            }
        }
        
        edges = [
            {"from": "router_1", "to": "billing_node", "condition": "billing"},
            {"from": "router_1", "to": "support_node", "condition": "support"},
            {"from": "router_1", "to": "default_node", "condition": "general"}
        ]
        
        next_nodes = ConditionalEngineExtension.process_conditional_result(
            router_output, edges, "router_1"
        )
        
        assert next_nodes == ["billing_node"], f"Expected ['billing_node'], got {next_nodes}"
        
        self.stdout.write(self.style.SUCCESS('✓ Engine integration works'))
        
        if self.verbose:
            self.stdout.write(f"  Next nodes: {next_nodes}")