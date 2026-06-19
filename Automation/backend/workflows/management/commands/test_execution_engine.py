"""
Management command to test the workflow execution engine.

This command:
1. Tests the core execution engine
2. Validates workflow definitions
3. Runs sample workflows
4. Reports execution statistics
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from workflows.execution.core_engine import execute_workflow
from workflows.execution.django_executor import test_workflow_execution, execute_workflow_by_id
from workflows.models import Workflow, WorkflowExecution
from workflows.nodes import node_registry
import json
import time


class Command(BaseCommand):
    help = 'Test the workflow execution engine'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--test-core',
            action='store_true',
            help='Test core execution engine with sample workflows'
        )
        parser.add_argument(
            '--test-django',
            action='store_true',
            help='Test Django integration with database'
        )
        parser.add_argument(
            '--create-sample',
            action='store_true',
            help='Create sample workflow in database'
        )
        parser.add_argument(
            '--benchmark',
            action='store_true',
            help='Run performance benchmarks'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Testing Workflow Execution Engine')
        )
        
        try:
            # Initialize node registry
            self.stdout.write('📡 Initializing node registry...')
            node_registry.auto_discover()
            
            stats = node_registry.get_registry_stats()
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Node registry ready with {stats["total_nodes"]} nodes'
                )
            )
            
            # Test core engine if requested
            if options['test_core']:
                self._test_core_engine()
            
            # Test Django integration if requested
            if options['test_django']:
                self._test_django_integration()
            
            # Create sample workflow if requested
            if options['create_sample']:
                self._create_sample_workflow()
            
            # Run benchmarks if requested
            if options['benchmark']:
                self._run_benchmarks()
            
            self.stdout.write(
                self.style.SUCCESS('\n🎉 Execution engine testing complete!')
            )
            
        except Exception as e:
            raise CommandError(f'Testing failed: {e}')
    
    def _test_core_engine(self):
        """Test the core execution engine."""
        self.stdout.write('\n🧪 Testing Core Execution Engine:')
        
        # Simple workflow test
        simple_workflow = {
            "meta": {"name": "Simple Test", "version": "1.0.0"},
            "trigger": {
                "id": "trigger_1",
                "type": "manual_trigger",
                "params": {"test_data": {"message": "Hello World"}}
            },
            "nodes": {
                "logger_1": {
                    "id": "logger_1",
                    "type": "logger",
                    "params": {
                        "message": "Received: {{message}}",
                        "level": "info"
                    }
                }
            },
            "connections": {
                "trigger_1": ["logger_1"],
                "logger_1": []
            }
        }
        
        # Test execution
        start_time = time.time()
        result = execute_workflow(simple_workflow, {"user_data": {"test": True}})
        end_time = time.time()
        
        if result.success:
            self.stdout.write(f'  ✅ Simple workflow: {end_time - start_time:.3f}s')
            self.stdout.write(f'     Nodes executed: {len(result.node_results)}')
            self.stdout.write(f'     Final output keys: {list(result.final_output.keys())}')
        else:
            self.stdout.write(
                self.style.ERROR(f'  ❌ Simple workflow failed: {result.error_message}')
            )
        
        # Complex workflow test
        complex_workflow = {
            "meta": {"name": "Complex Test", "version": "1.0.0"},
            "trigger": {
                "id": "webhook_1",
                "type": "webhook_trigger",
                "params": {"path": "/test", "method": "POST"}
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
                "delay_1": {
                    "id": "delay_1",
                    "type": "delay",
                    "params": {"type": "seconds", "value": 0.1}
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
                "condition_1": ["delay_1"],
                "delay_1": ["transform_1"],
                "transform_1": []
            }
        }
        
        trigger_input = {
            "body": {"user": {"email": "test@example.com", "name": "Test User"}},
            "headers": {"content-type": "application/json"},
            "method": "POST"
        }
        
        start_time = time.time()
        result = execute_workflow(complex_workflow, trigger_input)
        end_time = time.time()
        
        if result.success:
            self.stdout.write(f'  ✅ Complex workflow: {end_time - start_time:.3f}s')
            self.stdout.write(f'     Condition matched: {result.final_output.get("condition_result", {}).get("matched")}')
            self.stdout.write(f'     Processed flag: {result.final_output.get("processed")}')
        else:
            self.stdout.write(
                self.style.ERROR(f'  ❌ Complex workflow failed: {result.error_message}')
            )
        
        # Error handling test
        error_workflow = {
            "meta": {"name": "Error Test", "version": "1.0.0"},
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
                        "type": "invalid_type",  # This will cause an error
                        "value": 1
                    }
                }
            },
            "connections": {
                "trigger_1": ["delay_1"],
                "delay_1": []
            }
        }
        
        result = execute_workflow(error_workflow, {})
        
        if not result.success and result.error_message:
            self.stdout.write(f'  ✅ Error handling: Correctly caught error')
        else:
            self.stdout.write(
                self.style.ERROR(f'  ❌ Error handling: Should have failed but succeeded')
            )
    
    def _test_django_integration(self):
        """Test Django integration."""
        self.stdout.write('\n🔗 Testing Django Integration:')
        
        try:
            # Get or create test user
            user, created = User.objects.get_or_create(
                username='test_execution_user',
                defaults={'email': 'test@example.com'}
            )
            
            if created:
                self.stdout.write('  📝 Created test user')
            
            # Create test workflow
            workflow_definition = {
                "meta": {"name": "Django Test Workflow", "version": "1.0.0"},
                "trigger": {
                    "id": "trigger_1",
                    "type": "manual_trigger",
                    "params": {"test_data": {"source": "django_test"}}
                },
                "nodes": {
                    "logger_1": {
                        "id": "logger_1",
                        "type": "logger",
                        "params": {
                            "message": "Django test execution: {{source}}",
                            "level": "info"
                        }
                    }
                },
                "connections": {
                    "trigger_1": ["logger_1"],
                    "logger_1": []
                }
            }
            
            workflow, created = Workflow.objects.get_or_create(
                name='Django Test Workflow',
                defaults={
                    'definition': workflow_definition,
                    'owner': user
                }
            )
            
            if created:
                self.stdout.write('  📝 Created test workflow')
            
            # Test execution
            result = execute_workflow_by_id(
                workflow_id=str(workflow.id),
                trigger_input={"user_data": {"test": "django"}},
                user_id=str(user.id)
            )
            
            if result.success:
                self.stdout.write(f'  ✅ Django execution: Success')
                
                # Check database records
                executions = WorkflowExecution.objects.filter(workflow=workflow)
                self.stdout.write(f'     Execution records: {executions.count()}')
                
                if executions.exists():
                    latest = executions.latest('created_at')
                    self.stdout.write(f'     Latest status: {latest.status}')
                    self.stdout.write(f'     Output keys: {list(latest.output_data.keys()) if latest.output_data else "None"}')
            else:
                self.stdout.write(
                    self.style.ERROR(f'  ❌ Django execution failed: {result.error_message}')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'  ❌ Django integration test failed: {e}')
            )
    
    def _create_sample_workflow(self):
        """Create a sample workflow in the database."""
        self.stdout.write('\n📝 Creating Sample Workflow:')
        
        try:
            # Get or create admin user
            user, created = User.objects.get_or_create(
                username='admin',
                defaults={
                    'email': 'admin@example.com',
                    'is_staff': True,
                    'is_superuser': True
                }
            )
            
            sample_definition = {
                "meta": {
                    "name": "Customer Onboarding Sample",
                    "description": "Sample customer onboarding workflow",
                    "version": "1.0.0",
                    "active": True
                },
                "trigger": {
                    "id": "webhook_signup",
                    "type": "webhook_trigger",
                    "name": "Customer Signup Webhook",
                    "params": {
                        "path": "/webhook/customer-signup",
                        "method": "POST",
                        "authentication": "none"
                    }
                },
                "nodes": {
                    "validate_email": {
                        "id": "validate_email",
                        "type": "conditional",
                        "name": "Validate Email",
                        "params": {
                            "conditions": [
                                {
                                    "type": "regex_match",
                                    "field": "customer.email",
                                    "value": "^[\\w\\.-]+@[\\w\\.-]+\\.[a-zA-Z]{2,}$",
                                    "path": "valid_email"
                                }
                            ],
                            "default_path": "invalid_email"
                        }
                    },
                    "log_signup": {
                        "id": "log_signup",
                        "type": "logger",
                        "name": "Log Signup",
                        "params": {
                            "message": "New customer signup: {{customer.name}} ({{customer.email}})",
                            "level": "info",
                            "include_data": True
                        }
                    },
                    "add_metadata": {
                        "id": "add_metadata",
                        "type": "data_transform",
                        "name": "Add Metadata",
                        "params": {
                            "transformations": [
                                {
                                    "type": "set_field",
                                    "field": "customer.signup_date",
                                    "value": "{{variables.execution.created_at}}"
                                },
                                {
                                    "type": "set_field",
                                    "field": "customer.source",
                                    "value": "website"
                                }
                            ]
                        }
                    }
                },
                "connections": {
                    "webhook_signup": ["validate_email"],
                    "validate_email": ["log_signup"],
                    "log_signup": ["add_metadata"],
                    "add_metadata": []
                }
            }
            
            workflow, created = Workflow.objects.get_or_create(
                name='Customer Onboarding Sample',
                defaults={
                    'definition': sample_definition,
                    'owner': user,
                    'active': True
                }
            )
            
            if created:
                self.stdout.write(f'  ✅ Created sample workflow: {workflow.id}')
                self.stdout.write(f'     Name: {workflow.name}')
                self.stdout.write(f'     Nodes: {len(sample_definition["nodes"])}')
                self.stdout.write(f'     Owner: {workflow.owner.username}')
            else:
                self.stdout.write(f'  ℹ️  Sample workflow already exists: {workflow.id}')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'  ❌ Failed to create sample workflow: {e}')
            )
    
    def _run_benchmarks(self):
        """Run performance benchmarks."""
        self.stdout.write('\n⚡ Running Performance Benchmarks:')
        
        # Simple workflow benchmark
        simple_workflow = {
            "meta": {"name": "Benchmark Simple", "version": "1.0.0"},
            "trigger": {
                "id": "trigger_1",
                "type": "manual_trigger",
                "params": {"test_data": {"counter": 0}}
            },
            "nodes": {
                "increment": {
                    "id": "increment",
                    "type": "data_transform",
                    "params": {
                        "transformations": [
                            {
                                "type": "set_field",
                                "field": "counter",
                                "value": 1
                            }
                        ]
                    }
                }
            },
            "connections": {
                "trigger_1": ["increment"],
                "increment": []
            }
        }
        
        # Run multiple executions
        iterations = 10
        total_time = 0
        
        for i in range(iterations):
            start_time = time.time()
            result = execute_workflow(simple_workflow, {})
            end_time = time.time()
            
            if result.success:
                total_time += (end_time - start_time)
            else:
                self.stdout.write(
                    self.style.ERROR(f'  ❌ Benchmark iteration {i+1} failed')
                )
                return
        
        avg_time = total_time / iterations
        self.stdout.write(f'  ✅ Simple workflow benchmark:')
        self.stdout.write(f'     Iterations: {iterations}')
        self.stdout.write(f'     Total time: {total_time:.3f}s')
        self.stdout.write(f'     Average time: {avg_time:.3f}s')
        self.stdout.write(f'     Executions/second: {1/avg_time:.1f}')
        
        # Complex workflow benchmark
        complex_workflow = {
            "meta": {"name": "Benchmark Complex", "version": "1.0.0"},
            "trigger": {
                "id": "trigger_1",
                "type": "manual_trigger",
                "params": {"test_data": {"value": 100}}
            },
            "nodes": {
                "condition_1": {
                    "id": "condition_1",
                    "type": "conditional",
                    "params": {
                        "conditions": [
                            {
                                "type": "greater_than",
                                "field": "value",
                                "value": 50,
                                "path": "high_value"
                            }
                        ],
                        "default_path": "low_value"
                    }
                },
                "transform_1": {
                    "id": "transform_1",
                    "type": "data_transform",
                    "params": {
                        "transformations": [
                            {
                                "type": "set_field",
                                "field": "category",
                                "value": "high"
                            },
                            {
                                "type": "set_field",
                                "field": "processed",
                                "value": True
                            }
                        ]
                    }
                },
                "logger_1": {
                    "id": "logger_1",
                    "type": "logger",
                    "params": {
                        "message": "Processed value: {{value}} as {{category}}",
                        "level": "info"
                    }
                }
            },
            "connections": {
                "trigger_1": ["condition_1"],
                "condition_1": ["transform_1"],
                "transform_1": ["logger_1"],
                "logger_1": []
            }
        }
        
        iterations = 5
        total_time = 0
        
        for i in range(iterations):
            start_time = time.time()
            result = execute_workflow(complex_workflow, {})
            end_time = time.time()
            
            if result.success:
                total_time += (end_time - start_time)
        
        avg_time = total_time / iterations
        self.stdout.write(f'  ✅ Complex workflow benchmark:')
        self.stdout.write(f'     Iterations: {iterations}')
        self.stdout.write(f'     Average time: {avg_time:.3f}s')
        self.stdout.write(f'     Nodes per execution: 4')
        self.stdout.write(f'     Node executions/second: {4/avg_time:.1f}')