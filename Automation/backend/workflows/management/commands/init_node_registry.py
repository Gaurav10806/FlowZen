"""
Management command to initialize and test the node registry.

This command:
1. Discovers and registers all available nodes
2. Validates node schemas
3. Tests node instantiation
4. Reports registry statistics
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from workflows.nodes import node_registry, BaseNode


class Command(BaseCommand):
    help = 'Initialize and test the workflow node registry'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--test-nodes',
            action='store_true',
            help='Test instantiation of all registered nodes'
        )
        parser.add_argument(
            '--validate-schemas',
            action='store_true',
            help='Validate all node parameter schemas'
        )
        parser.add_argument(
            '--list-nodes',
            action='store_true',
            help='List all registered nodes with details'
        )
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Initializing Workflow Node Registry')
        )
        
        try:
            # Force auto-discovery
            self.stdout.write('📡 Discovering nodes...')
            node_registry.auto_discover()
            
            # Get registry statistics
            stats = node_registry.get_registry_stats()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Registry initialized with {stats["total_nodes"]} nodes'
                )
            )
            
            # Show categories
            self.stdout.write('\n📂 Node Categories:')
            for category, count in stats['categories'].items():
                self.stdout.write(f'  • {category}: {count} nodes')
            
            # List nodes if requested
            if options['list_nodes']:
                self._list_nodes()
            
            # Test nodes if requested
            if options['test_nodes']:
                self._test_nodes()
            
            # Validate schemas if requested
            if options['validate_schemas']:
                self._validate_schemas()
            
            self.stdout.write(
                self.style.SUCCESS('\n🎉 Node registry initialization complete!')
            )
            
        except Exception as e:
            raise CommandError(f'Failed to initialize node registry: {e}')
    
    def _list_nodes(self):
        """List all registered nodes with details."""
        self.stdout.write('\n📋 Registered Nodes:')
        
        schemas = node_registry.get_node_schemas()
        
        for node_type, schema in schemas.items():
            self.stdout.write(f'\n  🔧 {node_type}')
            self.stdout.write(f'     Name: {schema.get("name", "N/A")}')
            self.stdout.write(f'     Category: {schema.get("category", "N/A")}')
            self.stdout.write(f'     Description: {schema.get("description", "N/A")}')
            self.stdout.write(f'     Supports Retry: {schema.get("supports_retry", "N/A")}')
            self.stdout.write(f'     Default Timeout: {schema.get("default_timeout", "N/A")}s')
    
    def _test_nodes(self):
        """Test instantiation of all registered nodes."""
        self.stdout.write('\n🧪 Testing Node Instantiation:')
        
        node_types = node_registry.list_node_types()
        success_count = 0
        error_count = 0
        
        for node_type in node_types:
            try:
                node_class = node_registry.get_node_class(node_type)
                node_instance = node_class()
                
                # Test basic methods
                _ = node_instance.get_schema()
                _ = node_instance.validate_params({})
                
                self.stdout.write(f'  ✅ {node_type}')
                success_count += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ❌ {node_type}: {e}')
                )
                error_count += 1
        
        self.stdout.write(
            f'\n📊 Test Results: {success_count} passed, {error_count} failed'
        )
        
        if error_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️  {error_count} nodes failed instantiation tests'
                )
            )
    
    def _validate_schemas(self):
        """Validate all node parameter schemas."""
        self.stdout.write('\n🔍 Validating Node Schemas:')
        
        schemas = node_registry.get_node_schemas()
        success_count = 0
        error_count = 0
        
        for node_type, schema_info in schemas.items():
            try:
                schema = schema_info.get('parameter_schema', {})
                
                # Basic schema validation
                if not isinstance(schema, dict):
                    raise ValueError('Schema must be a dictionary')
                
                if schema.get('type') != 'object':
                    raise ValueError('Root schema type must be "object"')
                
                properties = schema.get('properties', {})
                if not isinstance(properties, dict):
                    raise ValueError('Properties must be a dictionary')
                
                required = schema.get('required', [])
                if not isinstance(required, list):
                    raise ValueError('Required must be a list')
                
                # Validate required fields exist in properties
                for field in required:
                    if field not in properties:
                        raise ValueError(f'Required field "{field}" not in properties')
                
                self.stdout.write(f'  ✅ {node_type}')
                success_count += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'  ❌ {node_type}: {e}')
                )
                error_count += 1
        
        self.stdout.write(
            f'\n📊 Schema Validation: {success_count} passed, {error_count} failed'
        )
        
        if error_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️  {error_count} nodes have invalid schemas'
                )
            )