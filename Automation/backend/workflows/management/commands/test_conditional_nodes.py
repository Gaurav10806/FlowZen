"""
Django management command to test conditional node functionality.

This command creates test workflows with conditional nodes and executes them
to verify the conditional logic works correctly.
"""

import json
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from workflows.models import Workflow, WorkflowExecution, Tenant
from workflows.tasks import execute_workflow_with_core_engine
from workflows.services.conditional_engine_extension import ConditionalEngineExtension


class Command(BaseCommand):
    help = 'Test conditional node functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Username of the workflow owner (defaults to first superuser)',
        )
        parser.add_argument(
            '--test-case',
            type=str,
            choices=['simple', 'complex', 'validation', 'all'],
            default='all',
            help='Which test case to run',
        )
        parser.add_argument(
            '--execute',
            action='store_true',
            help='Execute the test workflows after creating them',
        )

    def handle(self, *args, **options):
        # Get user
        username = options.get('user')
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'User "{username}" not found')
                )
                return
        else:
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                self.stdout.write(
                    self.style.ERROR('No superuser found. Please create one first.')
                )
                return

        # Get or create tenant
        tenant, created = Tenant.objects.get_or_create(
            slug=f"{user.username}-workspace",
            defaults={
                'name': f"{user.username}'s Workspace"
            }
        )

        test_case = options.get('test_case')
        execute_workflows = options.get('execute')

        if test_case in ['simple', 'all']:
            self._test_simple_conditional(user, tenant, execute_workflows)

        if test_case in ['complex', 'all']:
            self._test_complex_conditional(user, tenant, execute_workflows)

        if test_case in ['validation', 'all']:
            self._test_validation_workflow(user, tenant, execute_workflows)

        self.stdout.write(
            self.style.SUCCESS('Conditional node testing completed!')
        )

    def _test_simple_conditional(self, user, tenant, execute=False):
        """Test simple true/false conditional logic."""
        self.stdout.write("Creating simple conditional test workflow...")

        workflow_graph = {
            "nodes": [
                {
                    "id": "manual_trigger_1",
                    "type": "manual_trigger",
                    "label": "Manual Start",
                    "position": {"x": 100, "y": 100},
                    "config": {
                        "test_data": {
                            "user": {"status": "premium", "email": "test@example.com"}
                        }
                    }
                },
                {
                    "id": "check_status",
                    "type": "conditional",
                    "label": "Check User Status",
                    "position": {"x": 300, "y": 100},
                    "config": {
                        "left_operand": "user.status",
                        "operator": "equals",
                        "right_operand": "premium",
                        "case_sensitive": True
                    }
                },
                {
                    "id": "premium_action",
                    "type": "logger",
                    "label": "Premium User Action",
                    "position": {"x": 500, "y": 50},
                    "config": {
                        "message": "Premium user detected: {{user.email}}",
                        "level": "info"
                    }
                },
                {
                    "id": "standard_action",
                    "type": "logger",
                    "label": "Standard User Action",
                    "position": {"x": 500, "y": 150},
                    "config": {
                        "message": "Standard user detected: {{user.email}}",
                        "level": "info"
                    }
                }
            ],
            "edges": [
                {
                    "id": "edge_1",
                    "source": "manual_trigger_1",
                    "target": "check_status"
                },
                {
                    "id": "edge_2",
                    "source": "check_status",
                    "target": "premium_action",
                    "condition": "true"
                },
                {
                    "id": "edge_3",
                    "source": "check_status",
                    "target": "standard_action",
                    "condition": "false"
                }
            ]
        }

        workflow = Workflow.objects.create(
            name="Simple Conditional Test",
            description="Test basic true/false conditional logic",
            graph=workflow_graph,
            status="published",
            owner=user,
            tenant=tenant
        )

        self.stdout.write(f"  Created workflow: {workflow.id}")

        # Validate conditional edges
        errors = ConditionalEngineExtension.validate_conditional_edges(workflow_graph)
        if errors:
            self.stdout.write(
                self.style.WARNING(f"  Validation warnings: {errors}")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("  Workflow validation passed")
            )

        if execute:
            self._execute_test_workflow(workflow, {"user": {"status": "premium", "email": "premium@test.com"}})
            self._execute_test_workflow(workflow, {"user": {"status": "standard", "email": "standard@test.com"}})

    def _test_complex_conditional(self, user, tenant, execute=False):
        """Test complex conditional logic with multiple operators."""
        self.stdout.write("Creating complex conditional test workflow...")

        workflow_graph = {
            "nodes": [
                {
                    "id": "manual_trigger_2",
                    "type": "manual_trigger",
                    "label": "Manual Start",
                    "position": {"x": 100, "y": 100},
                    "config": {
                        "test_data": {
                            "order": {"total": 1500, "items": 3},
                            "customer": {"type": "vip", "country": "US"}
                        }
                    }
                },
                {
                    "id": "check_order_value",
                    "type": "conditional",
                    "label": "Check Order Value",
                    "position": {"x": 300, "y": 100},
                    "config": {
                        "left_operand": "{{order.total}}",
                        "operator": "greater_than",
                        "right_operand": "1000"
                    }
                },
                {
                    "id": "check_customer_type",
                    "type": "conditional",
                    "label": "Check Customer Type",
                    "position": {"x": 500, "y": 50},
                    "config": {
                        "left_operand": "customer.type",
                        "operator": "equals",
                        "right_operand": "vip"
                    }
                },
                {
                    "id": "check_country",
                    "type": "conditional",
                    "label": "Check Country",
                    "position": {"x": 700, "y": 25},
                    "config": {
                        "left_operand": "customer.country",
                        "operator": "in_list",
                        "right_operand": "[\"US\", \"CA\", \"UK\"]"
                    }
                },
                {
                    "id": "vip_domestic_processing",
                    "type": "logger",
                    "label": "VIP Domestic Processing",
                    "position": {"x": 900, "y": 25},
                    "config": {
                        "message": "VIP domestic order: ${{order.total}}",
                        "level": "info"
                    }
                },
                {
                    "id": "vip_international_processing",
                    "type": "logger",
                    "label": "VIP International Processing",
                    "position": {"x": 900, "y": 75},
                    "config": {
                        "message": "VIP international order: ${{order.total}}",
                        "level": "info"
                    }
                },
                {
                    "id": "regular_high_value",
                    "type": "logger",
                    "label": "Regular High Value",
                    "position": {"x": 500, "y": 125},
                    "config": {
                        "message": "Regular high-value order: ${{order.total}}",
                        "level": "info"
                    }
                },
                {
                    "id": "standard_processing",
                    "type": "logger",
                    "label": "Standard Processing",
                    "position": {"x": 300, "y": 200},
                    "config": {
                        "message": "Standard order: ${{order.total}}",
                        "level": "info"
                    }
                }
            ],
            "edges": [
                {"source": "manual_trigger_2", "target": "check_order_value"},
                {"source": "check_order_value", "target": "check_customer_type", "condition": "true"},
                {"source": "check_order_value", "target": "standard_processing", "condition": "false"},
                {"source": "check_customer_type", "target": "check_country", "condition": "true"},
                {"source": "check_customer_type", "target": "regular_high_value", "condition": "false"},
                {"source": "check_country", "target": "vip_domestic_processing", "condition": "true"},
                {"source": "check_country", "target": "vip_international_processing", "condition": "false"}
            ]
        }

        workflow = Workflow.objects.create(
            name="Complex Conditional Test",
            description="Test complex multi-level conditional logic",
            graph=workflow_graph,
            status="published",
            owner=user,
            tenant=tenant
        )

        self.stdout.write(f"  Created workflow: {workflow.id}")

        # Get conditional paths info
        paths_info = ConditionalEngineExtension.get_conditional_paths_info(workflow_graph)
        self.stdout.write(f"  Conditional paths: {json.dumps(paths_info, indent=2)}")

        if execute:
            # Test different scenarios
            test_cases = [
                {"order": {"total": 1500}, "customer": {"type": "vip", "country": "US"}},
                {"order": {"total": 1500}, "customer": {"type": "vip", "country": "FR"}},
                {"order": {"total": 1500}, "customer": {"type": "regular", "country": "US"}},
                {"order": {"total": 500}, "customer": {"type": "vip", "country": "US"}},
            ]
            
            for i, test_data in enumerate(test_cases):
                self.stdout.write(f"  Executing test case {i+1}: {test_data}")
                self._execute_test_workflow(workflow, test_data)

    def _test_validation_workflow(self, user, tenant, execute=False):
        """Test validation workflow with various operators."""
        self.stdout.write("Creating validation test workflow...")

        workflow_graph = {
            "nodes": [
                {
                    "id": "manual_trigger_3",
                    "type": "manual_trigger",
                    "label": "Data Input",
                    "position": {"x": 100, "y": 100},
                    "config": {
                        "test_data": {
                            "email": "test@example.com",
                            "age": 25,
                            "phone": "1234567890",
                            "country": "US"
                        }
                    }
                },
                {
                    "id": "validate_email",
                    "type": "conditional",
                    "label": "Validate Email",
                    "position": {"x": 300, "y": 50},
                    "config": {
                        "left_operand": "email",
                        "operator": "contains",
                        "right_operand": "@"
                    }
                },
                {
                    "id": "validate_age",
                    "type": "conditional",
                    "label": "Validate Age",
                    "position": {"x": 500, "y": 50},
                    "config": {
                        "left_operand": "{{age}}",
                        "operator": "greater_equal",
                        "right_operand": "18"
                    }
                },
                {
                    "id": "validate_phone",
                    "type": "conditional",
                    "label": "Validate Phone",
                    "position": {"x": 700, "y": 50},
                    "config": {
                        "left_operand": "phone",
                        "operator": "regex_match",
                        "right_operand": "^\\d{10}$"
                    }
                },
                {
                    "id": "all_valid",
                    "type": "logger",
                    "label": "All Valid",
                    "position": {"x": 900, "y": 50},
                    "config": {
                        "message": "All validations passed for {{email}}",
                        "level": "info"
                    }
                },
                {
                    "id": "validation_failed",
                    "type": "logger",
                    "label": "Validation Failed",
                    "position": {"x": 500, "y": 150},
                    "config": {
                        "message": "Validation failed",
                        "level": "warning"
                    }
                }
            ],
            "edges": [
                {"source": "manual_trigger_3", "target": "validate_email"},
                {"source": "validate_email", "target": "validate_age", "condition": "true"},
                {"source": "validate_email", "target": "validation_failed", "condition": "false"},
                {"source": "validate_age", "target": "validate_phone", "condition": "true"},
                {"source": "validate_age", "target": "validation_failed", "condition": "false"},
                {"source": "validate_phone", "target": "all_valid", "condition": "true"},
                {"source": "validate_phone", "target": "validation_failed", "condition": "false"}
            ]
        }

        workflow = Workflow.objects.create(
            name="Validation Conditional Test",
            description="Test validation workflow with various operators",
            graph=workflow_graph,
            status="published",
            owner=user,
            tenant=tenant
        )

        self.stdout.write(f"  Created workflow: {workflow.id}")

        if execute:
            # Test valid and invalid data
            test_cases = [
                {"email": "valid@example.com", "age": 25, "phone": "1234567890", "country": "US"},
                {"email": "invalid-email", "age": 25, "phone": "1234567890", "country": "US"},
                {"email": "valid@example.com", "age": 16, "phone": "1234567890", "country": "US"},
                {"email": "valid@example.com", "age": 25, "phone": "invalid", "country": "US"},
            ]
            
            for i, test_data in enumerate(test_cases):
                self.stdout.write(f"  Executing validation test {i+1}: {test_data}")
                self._execute_test_workflow(workflow, test_data)

    def _execute_test_workflow(self, workflow, test_data):
        """Execute a test workflow with given data."""
        try:
            # Create execution
            execution = WorkflowExecution.objects.create(
                workflow=workflow,
                tenant=workflow.tenant,
                input_payload=test_data,
                input_items=[{"json": test_data}],
                triggered_by='manual'
            )

            self.stdout.write(f"    Created execution: {execution.id}")

            # Execute synchronously for testing
            # Note: In production, this would be async via Celery
            from workflows.tasks import execute_workflow
            execute_workflow(str(execution.id))

            # Refresh execution to get results
            execution.refresh_from_db()

            self.stdout.write(f"    Execution status: {execution.status}")
            if execution.status == 'success':
                self.stdout.write(
                    self.style.SUCCESS(f"    ✓ Test passed")
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"    ✗ Test failed: {execution.error_message}")
                )

            # Show node results for debugging
            if execution.node_results:
                for node_id, result in execution.node_results.items():
                    if 'condition_result' in result:
                        condition = result['condition_result']
                        self.stdout.write(
                            f"      Node {node_id}: {condition.get('result')} -> {condition.get('execution_path')}"
                        )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"    Execution failed: {e}")
            )