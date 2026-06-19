"""
Test AI-Native Capabilities

Comprehensive test suite for AI agent nodes, tool registry, memory service,
prompt management, and safety controls.
"""

import json
import logging
from typing import Dict, Any, List
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone

from ...nodes.ai_agent_node import AIAgentNode
from ...nodes.ai_safety_nodes import AIValidationNode, AIGuardrailNode
from ...services.tool_registry import ToolRegistry, ToolDefinition, ToolPermissionLevel
from ...services.memory_service import MemoryService, MemoryType
from ...services.prompt_manager import PromptManager, PromptType, PromptStatus
from ...services.ai_services import AIService, AIProvider


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test AI-Native Capabilities implementation'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--scenario',
            type=str,
            default='all',
            help='Test scenario to run (all, agent, tools, memory, prompts, safety)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )
    
    def handle(self, *args, **options):
        scenario = options['scenario']
        verbose = options['verbose']
        
        if verbose:
            logging.basicConfig(level=logging.INFO)
        
        self.stdout.write("🤖 Testing AI-Native Capabilities Implementation")
        self.stdout.write("=" * 60)
        
        test_results = {}
        
        if scenario in ['all', 'agent']:
            test_results['agent'] = self.test_ai_agent_node()
        
        if scenario in ['all', 'tools']:
            test_results['tools'] = self.test_tool_registry()
        
        if scenario in ['all', 'memory']:
            test_results['memory'] = self.test_memory_service()
        
        if scenario in ['all', 'prompts']:
            test_results['prompts'] = self.test_prompt_manager()
        
        if scenario in ['all', 'safety']:
            test_results['safety'] = self.test_safety_controls()
        
        if scenario in ['all', 'integration']:
            test_results['integration'] = self.test_integration_scenarios()
        
        # Print summary
        self.print_test_summary(test_results)
    
    def test_ai_agent_node(self) -> Dict[str, Any]:
        """Test AI Agent Node functionality."""
        self.stdout.write("📋 Testing AI Agent Node")
        results = {'passed': 0, 'failed': 0, 'tests': []}
        
        try:
            agent_node = AIAgentNode()
            
            # Test 1: Basic agent initialization
            test_name = "Agent initialization"
            try:
                self.assertEqual(agent_node.NODE_TYPE, "ai_agent")
                self.assertEqual(agent_node.DISPLAY_NAME, "AI Agent")
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
            
            # Test 2: Reactive mode execution
            test_name = "Reactive mode execution"
            try:
                input_data = {"message": "Hello, how can you help me?"}
                params = {
                    "goal": "Provide helpful assistance",
                    "reasoning_mode": "reactive",
                    "available_tools": [],
                    "memory_enabled": False,
                    "safety_level": "moderate"
                }
                context = {"user_id": "test_user", "tenant_id": "test_tenant"}
                
                result = agent_node.run(input_data, params, context)
                
                self.assertIn('agent_execution', result)
                self.assertIn('agent_output', result)
                self.assertIn('success', result)
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
            
            # Test 3: Planning mode execution
            test_name = "Planning mode execution"
            try:
                input_data = {"task": "Create a marketing campaign"}
                params = {
                    "goal": "Create a comprehensive marketing campaign plan",
                    "reasoning_mode": "planning",
                    "available_tools": ["http_request", "send_email"],
                    "memory_enabled": True,
                    "safety_level": "moderate",
                    "max_steps": 5
                }
                context = {"user_id": "test_user", "tenant_id": "test_tenant"}
                
                result = agent_node.run(input_data, params, context)
                
                self.assertIn('agent_execution', result)
                agent_exec = result['agent_execution']
                self.assertIn('reasoning_trace', agent_exec)
                self.assertIn('steps_taken', agent_exec)
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
            
            # Test 4: Parameter validation
            test_name = "Parameter validation"
            try:
                input_data = {"message": "Test"}
                params = {
                    "goal": "Test goal",
                    "reasoning_mode": "invalid_mode",  # Invalid mode
                    "safety_level": "moderate"
                }
                context = {"user_id": "test_user", "tenant_id": "test_tenant"}
                
                try:
                    agent_node.run(input_data, params, context)
                    # Should have raised an exception
                    raise AssertionError("Expected validation error for invalid reasoning mode")
                except Exception as e:
                    if "Invalid reasoning mode" in str(e):
                        results['tests'].append({'name': test_name, 'status': 'PASS'})
                        results['passed'] += 1
                        self.stdout.write(f"✓ {test_name}")
                    else:
                        raise e
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
            
            # Test 5: Schema validation
            test_name = "Schema validation"
            try:
                schema = agent_node.get_schema()
                
                self.assertIn('properties', schema)
                self.assertIn('goal', schema['properties'])
                self.assertIn('reasoning_mode', schema['properties'])
                self.assertIn('available_tools', schema['properties'])
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
        
        except Exception as e:
            self.stdout.write(f"✗ Agent node testing failed: {e}")
            results['failed'] += 1
        
        return results
    
    def test_tool_registry(self) -> Dict[str, Any]:
        """Test Tool Registry functionality."""
        self.stdout.write("🔧 Testing Tool Registry")
        results = {'passed': 0, 'failed': 0, 'tests': []}
        
        try:
            tool_registry = ToolRegistry()
            
            # Test 1: Built-in tools registration
            test_name = "Built-in tools registration"
            try:
                available_tools = tool_registry.get_available_tools({}, "moderate")
                
                self.assertGreater(len(available_tools), 0)
                
                # Check for expected built-in tools
                tool_names = [tool['name'] for tool in available_tools]
                self.assertIn('http_request', tool_names)
                self.assertIn('send_email', tool_names)
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
            
            # Test 2: Custom tool registration
            test_name = "Custom tool registration"
            try:
                custom_tool = ToolDefinition(
                    name="test_tool",
                    display_name="Test Tool",
                    description="A test tool for validation",
                    node_type="code",  # Assuming code node exists
                    input_schema={"type": "object", "properties": {"input": {"type": "string"}}},
                    output_schema={"type": "object", "properties": {"output": {"type": "string"}}},
                    permission_level=ToolPermissionLevel.READ_ONLY,
                    safety_constraints={"max_data_size": 1000},
                    usage_examples=[{"description": "Test example", "input": {"input": "test"}}],
                    cost_estimate=1,
                    execution_time_estimate=100
                )
                
                tool_registry.register_tool(custom_tool)
                
                # Verify tool is available
                available_tools = tool_registry.get_available_tools({}, "moderate")
                tool_names = [tool['name'] for tool in available_tools]
                self.assertIn('test_tool', tool_names)
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
            
            # Test 3: Permission filtering
            test_name = "Permission filtering"
            try:
                # Test with strict safety level
                strict_tools = tool_registry.get_available_tools({}, "strict")
                moderate_tools = tool_registry.get_available_tools({}, "moderate")
                
                # Strict should have fewer or equal tools
                self.assertLessEqual(len(strict_tools), len(moderate_tools))
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
            
            # Test 4: Tool execution simulation
            test_name = "Tool execution simulation"
            try:
                # This would normally execute a real tool, but we'll test the validation
                tool_info = tool_registry.get_tool_info("process_data", {}, "moderate")
                
                if tool_info:
                    self.assertIn('name', tool_info)
                    self.assertIn('description', tool_info)
                    self.assertIn('input_schema', tool_info)
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
            
            # Test 5: Usage statistics
            test_name = "Usage statistics"
            try:
                stats = tool_registry.get_tool_usage_stats({})
                
                self.assertIn('total_executions', stats)
                self.assertIn('success_rate', stats)
                self.assertIn('tool_usage', stats)
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
        
        except Exception as e:
            self.stdout.write(f"✗ Tool registry testing failed: {e}")
            results['failed'] += 1
        
        return results
    
    def test_memory_service(self) -> Dict[str, Any]:
        """Test Memory Service functionality."""
        self.stdout.write("🧠 Testing Memory Service")
        results = {'passed': 0, 'failed': 0, 'tests': []}
        
        try:
            memory_service = MemoryService()
            
            # Test 1: Memory saving
            test_name = "Memory saving"
            try:
                memory_id = memory_service.save_memory(
                    content="This is a test memory entry",
                    memory_type=MemoryType.SHORT_TERM,
                    metadata={"test": True, "category": "testing"},
                    user_id="test_user",
                    tenant_id="test_tenant",
                    session_id="test_session",
                    importance_score=0.8,
                    tags=["test", "memory"]
                )
                
                self.assertIsNotNone(memory_id)
                self.assertIsInstance(memory_id, str)
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
            
            # Test 2: Memory search
            test_name = "Memory search"
            try:
                from ...services.memory_service import MemoryQuery
                
                query = MemoryQuery(
                    query_text="test memory",
                    memory_types=[MemoryType.SHORT_TERM],
                    user_id="test_user",
                    tenant_id="test_tenant",
                    session_id="test_session",
                    max_results=10,
                    similarity_threshold=0.5
                )
                
                search_result = memory_service.search_memory(query)
                
                self.assertIn('memories', search_result.__dict__)
                self.assertIn('total_found', search_result.__dict__)
                self.assertIn('search_time_ms', search_result.__dict__)
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
            
            # Test 3: Context loading
            test_name = "Context loading"
            try:
                input_data = {"message": "What do you remember about testing?"}
                context = {
                    "user_id": "test_user",
                    "tenant_id": "test_tenant",
                    "session_id": "test_session"
                }
                
                memory_context = memory_service.load_context(input_data, context)
                
                self.assertIsInstance(memory_context, dict)
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
            
            # Test 4: Memory statistics
            test_name = "Memory statistics"
            try:
                stats = memory_service.get_memory_stats("test_user", "test_tenant")
                
                self.assertIn('total_memories', stats)
                self.assertIn('memory_by_type', stats)
                self.assertIn('active_sessions', stats)
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
            
            # Test 5: Memory cleanup
            test_name = "Memory cleanup"
            try:
                cleanup_stats = memory_service.cleanup_old_memories("test_user", "test_tenant", max_age_days=0)
                
                self.assertIn('short_term_cleaned', cleanup_stats)
                self.assertIn('long_term_cleaned', cleanup_stats)
                self.assertIn('total_cleaned', cleanup_stats)
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
        
        except Exception as e:
            self.stdout.write(f"✗ Memory service testing failed: {e}")
            results['failed'] += 1
        
        return results
    
    def test_prompt_manager(self) -> Dict[str, Any]:
        """Test Prompt Manager functionality."""
        self.stdout.write("📝 Testing Prompt Manager")
        results = {'passed': 0, 'failed': 0, 'tests': []}
        
        try:
            prompt_manager = PromptManager()
            
            # Test 1: Built-in prompts
            test_name = "Built-in prompts"
            try:
                # Test that built-in prompts are available
                reactive_prompt = prompt_manager.build_prompt(
                    'agent_reactive',
                    {
                        'goal': 'Test goal',
                        'input_data': {'message': 'Hello'},
                        'memory_context': {},
                        'available_tools': []
                    }
                )
                
                self.assertIsInstance(reactive_prompt, str)
                self.assertIn('Test goal', reactive_prompt)
                self.assertIn('Hello', reactive_prompt)
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
            
            # Test 2: Custom template creation
            test_name = "Custom template creation"
            try:
                template_id = prompt_manager.create_template(
                    name="test_template",
                    prompt_type=PromptType.CUSTOM,
                    template_content="Hello {{name}}, your task is: {{task}}",
                    variables=["name", "task"],
                    required_variables=["name", "task"]
                )
                
                self.assertIsNotNone(template_id)
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
            
            # Test 3: Version management
            test_name = "Version management"
            try:
                # Create a version for the test template
                if 'template_id' in locals():
                    version_id = prompt_manager.create_version(
                        template_id,
                        "Hello {{name}}, your updated task is: {{task}}",
                        "test_user"
                    )
                    
                    self.assertIsNotNone(version_id)
                    
                    # Activate the version
                    success = prompt_manager.activate_version(template_id, version_id, "test_user")
                    self.assertTrue(success)
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
            
            # Test 4: Prompt testing
            test_name = "Prompt testing"
            try:
                if 'template_id' in locals() and 'version_id' in locals():
                    test_cases = [
                        {
                            'variables': {'name': 'Alice', 'task': 'complete the project'},
                            'expected_outcome': {'contains': 'Alice', 'length_min': 10}
                        }
                    ]
                    
                    test_results = prompt_manager.test_prompt_version(template_id, version_id, test_cases)
                    
                    self.assertIn('success_rate', test_results)
                    self.assertIn('results', test_results)
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
            
            # Test 5: Performance metrics
            test_name = "Performance metrics"
            try:
                if 'template_id' in locals():
                    metrics = prompt_manager.get_performance_metrics(template_id)
                    
                    self.assertIn('total_executions', metrics)
                    self.assertIn('success_rate', metrics)
                    self.assertIn('average_execution_time_ms', metrics)
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
        
        except Exception as e:
            self.stdout.write(f"✗ Prompt manager testing failed: {e}")
            results['failed'] += 1
        
        return results
    
    def test_safety_controls(self) -> Dict[str, Any]:
        """Test AI Safety and Control functionality."""
        self.stdout.write("🛡️ Testing Safety Controls")
        results = {'passed': 0, 'failed': 0, 'tests': []}
        
        try:
            # Test AI Service safety
            ai_service = AIService()
            
            # Test 1: AI Service initialization
            test_name = "AI Service initialization"
            try:
                self.assertIsNotNone(ai_service.providers)
                self.assertIn(AIProvider.MOCK, ai_service.providers)
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
            
            # Test 2: Mock AI response generation
            test_name = "Mock AI response generation"
            try:
                response = ai_service.generate_response(
                    prompt="Hello, how are you?",
                    model_config={"provider": "mock", "model": "mock-gpt-4"},
                    context={"user_id": "test_user", "tenant_id": "test_tenant", "safety_level": "moderate"}
                )
                
                self.assertIn('response', response)
                self.assertIn('confidence', response)
                self.assertIn('tokens_used', response)
                self.assertIn('safety_flags', response)
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
            
            # Test 3: Safety validation
            test_name = "Safety validation"
            try:
                validation_result = ai_service.validate_response_safety(
                    "This is a safe and helpful response.",
                    "moderate"
                )
                
                self.assertIn('is_safe', validation_result)
                self.assertIn('safety_score', validation_result)
                self.assertIn('passed_checks', validation_result)
                self.assertIn('failed_checks', validation_result)
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
            
            # Test AI Validation Node
            validation_node = AIValidationNode()
            
            # Test 4: Validation node execution
            test_name = "Validation node execution"
            try:
                input_data = {
                    "response": "This is a test response that should pass validation."
                }
                params = {
                    "content_field": "response",
                    "validation_strategies": ["content_safety", "format_compliance"],
                    "safety_level": "moderate",
                    "fail_on_violation": False
                }
                context = {"user_id": "test_user", "tenant_id": "test_tenant"}
                
                result = validation_node.run(input_data, params, context)
                
                self.assertIn('validation_result', result)
                self.assertIn('validation_passed', result)
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
            
            # Test AI Guardrail Node
            guardrail_node = AIGuardrailNode()
            
            # Test 5: Guardrail node execution
            test_name = "Guardrail node execution"
            try:
                input_data = {
                    "response": "This response contains some damn inappropriate language."
                }
                params = {
                    "guardrail_types": ["content_filter"],
                    "content_filters": {
                        "content_fields": ["response"],
                        "forbidden_words": ["damn"],
                        "replacement": "[FILTERED]"
                    }
                }
                context = {"user_id": "test_user", "tenant_id": "test_tenant"}
                
                result = guardrail_node.run(input_data, params, context)
                
                self.assertIn('guardrail_result', result)
                # Check that content was filtered
                self.assertIn('[FILTERED]', result.get('response', ''))
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
        
        except Exception as e:
            self.stdout.write(f"✗ Safety controls testing failed: {e}")
            results['failed'] += 1
        
        return results
    
    def test_integration_scenarios(self) -> Dict[str, Any]:
        """Test integration scenarios combining multiple AI components."""
        self.stdout.write("🔗 Testing Integration Scenarios")
        results = {'passed': 0, 'failed': 0, 'tests': []}
        
        try:
            # Test 1: Agent with memory and tools
            test_name = "Agent with memory and tools"
            try:
                agent_node = AIAgentNode()
                
                input_data = {"message": "Help me analyze some data"}
                params = {
                    "goal": "Analyze data and provide insights",
                    "reasoning_mode": "conversational",
                    "available_tools": ["process_data"],
                    "memory_enabled": True,
                    "safety_level": "moderate"
                }
                context = {"user_id": "test_user", "tenant_id": "test_tenant", "session_id": "test_session"}
                
                result = agent_node.run(input_data, params, context)
                
                self.assertIn('agent_execution', result)
                self.assertTrue(result.get('success', False))
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
            
            # Test 2: Agent output validation pipeline
            test_name = "Agent output validation pipeline"
            try:
                # First run agent
                agent_node = AIAgentNode()
                agent_result = agent_node.run(
                    {"message": "Create a business plan"},
                    {
                        "goal": "Create a comprehensive business plan",
                        "reasoning_mode": "planning",
                        "available_tools": [],
                        "memory_enabled": False,
                        "safety_level": "moderate"
                    },
                    {"user_id": "test_user", "tenant_id": "test_tenant"}
                )
                
                # Then validate the output
                validation_node = AIValidationNode()
                validation_result = validation_node.run(
                    agent_result,
                    {
                        "content_field": "agent_execution.final_answer",
                        "validation_strategies": ["content_safety", "business_rules"],
                        "safety_level": "moderate",
                        "fail_on_violation": False
                    },
                    {"user_id": "test_user", "tenant_id": "test_tenant"}
                )
                
                self.assertIn('validation_result', validation_result)
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
            
            # Test 3: Complete AI workflow simulation
            test_name = "Complete AI workflow simulation"
            try:
                # Simulate a complete workflow: Agent -> Validation -> Guardrails
                
                # Step 1: Agent execution
                agent_node = AIAgentNode()
                agent_result = agent_node.run(
                    {"request": "Write a customer email"},
                    {
                        "goal": "Write a professional customer service email",
                        "reasoning_mode": "reactive",
                        "available_tools": [],
                        "memory_enabled": True,
                        "safety_level": "moderate"
                    },
                    {"user_id": "test_user", "tenant_id": "test_tenant"}
                )
                
                # Step 2: Validation
                validation_node = AIValidationNode()
                validated_result = validation_node.run(
                    agent_result,
                    {
                        "content_field": "agent_execution.final_answer",
                        "validation_strategies": ["content_safety"],
                        "safety_level": "moderate",
                        "fail_on_violation": False
                    },
                    {"user_id": "test_user", "tenant_id": "test_tenant"}
                )
                
                # Step 3: Guardrails
                guardrail_node = AIGuardrailNode()
                final_result = guardrail_node.run(
                    validated_result,
                    {
                        "guardrail_types": ["output_modifier"],
                        "modification_rules": {
                            "target_fields": ["agent_execution.final_answer"],
                            "add_disclaimer": True,
                            "disclaimer_text": "This email was generated by AI."
                        }
                    },
                    {"user_id": "test_user", "tenant_id": "test_tenant"}
                )
                
                # Verify complete pipeline
                self.assertIn('agent_execution', final_result)
                self.assertIn('validation_result', final_result)
                self.assertIn('guardrail_result', final_result)
                
                results['tests'].append({'name': test_name, 'status': 'PASS'})
                results['passed'] += 1
                self.stdout.write(f"✓ {test_name}")
            except Exception as e:
                results['tests'].append({'name': test_name, 'status': 'FAIL', 'error': str(e)})
                results['failed'] += 1
                self.stdout.write(f"✗ {test_name}: {e}")
        
        except Exception as e:
            self.stdout.write(f"✗ Integration testing failed: {e}")
            results['failed'] += 1
        
        return results
    
    def print_test_summary(self, test_results: Dict[str, Any]):
        """Print comprehensive test summary."""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("🎯 AI-Native Capabilities Test Summary")
        self.stdout.write("=" * 60)
        
        total_passed = 0
        total_failed = 0
        
        for component, results in test_results.items():
            passed = results.get('passed', 0)
            failed = results.get('failed', 0)
            total_passed += passed
            total_failed += failed
            
            status_icon = "✅" if failed == 0 else "❌"
            self.stdout.write(f"{status_icon} {component.upper()}: {passed} passed, {failed} failed")
            
            # Show failed tests
            if failed > 0:
                for test in results.get('tests', []):
                    if test['status'] == 'FAIL':
                        self.stdout.write(f"   ✗ {test['name']}: {test.get('error', 'Unknown error')}")
        
        self.stdout.write("\n" + "-" * 60)
        
        overall_status = "✅ ALL TESTS PASSED" if total_failed == 0 else f"❌ {total_failed} TESTS FAILED"
        self.stdout.write(f"OVERALL: {total_passed} passed, {total_failed} failed - {overall_status}")
        
        if total_failed == 0:
            self.stdout.write("\n🎉 AI-Native Capabilities implementation is working correctly!")
        else:
            self.stdout.write(f"\n⚠️  Please fix {total_failed} failing tests before deployment.")
    
    def assertEqual(self, first, second, msg=None):
        """Simple assertion helper."""
        if first != second:
            raise AssertionError(msg or f"{first} != {second}")
    
    def assertIn(self, member, container, msg=None):
        """Simple assertion helper."""
        if member not in container:
            raise AssertionError(msg or f"{member} not in {container}")
    
    def assertIsNotNone(self, obj, msg=None):
        """Simple assertion helper."""
        if obj is None:
            raise AssertionError(msg or "Object is None")
    
    def assertIsInstance(self, obj, cls, msg=None):
        """Simple assertion helper."""
        if not isinstance(obj, cls):
            raise AssertionError(msg or f"{obj} is not instance of {cls}")
    
    def assertGreater(self, first, second, msg=None):
        """Simple assertion helper."""
        if not first > second:
            raise AssertionError(msg or f"{first} not greater than {second}")
    
    def assertLessEqual(self, first, second, msg=None):
        """Simple assertion helper."""
        if not first <= second:
            raise AssertionError(msg or f"{first} not less than or equal to {second}")
    
    def assertTrue(self, expr, msg=None):
        """Simple assertion helper."""
        if not expr:
            raise AssertionError(msg or f"{expr} is not True")