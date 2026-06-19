"""
Initialize DEV UI System

This management command initializes the DEV UI system by:
1. Discovering and syncing node types
2. Setting up safety mechanisms
3. Creating initial configuration
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission, Group
from django.contrib.contenttypes.models import ContentType

from workflows.dev_integration import get_dev_ui_manager, patch_execution_engine_for_dev_ui


class Command(BaseCommand):
    help = 'Initialize DEV UI system'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--create-permissions',
            action='store_true',
            help='Create DEV UI permissions and groups',
        )
        parser.add_argument(
            '--sync-nodes',
            action='store_true',
            help='Sync node types from registry',
        )
        parser.add_argument(
            '--patch-engine',
            action='store_true',
            help='Patch execution engine with safety mechanisms',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Run all initialization steps',
        )
    
    def handle(self, *args, **options):
        """Execute the command."""
        if options['all']:
            options['create_permissions'] = True
            options['sync_nodes'] = True
            options['patch_engine'] = True
        
        if options['create_permissions']:
            self.create_permissions()
        
        if options['sync_nodes']:
            self.sync_node_types()
        
        if options['patch_engine']:
            self.patch_execution_engine()
        
        self.stdout.write(
            self.style.SUCCESS('DEV UI initialization completed successfully')
        )
    
    def create_permissions(self):
        """Create DEV UI permissions and groups."""
        self.stdout.write('Creating DEV UI permissions...')
        
        try:
            # Get or create content type for workflows
            from workflows.models import Workflow
            content_type = ContentType.objects.get_for_model(Workflow)
            
            # Create DEV UI permission
            permission, created = Permission.objects.get_or_create(
                codename='dev_ui_access',
                name='Can access DEV UI',
                content_type=content_type,
            )
            
            if created:
                self.stdout.write(f'  Created permission: {permission.name}')
            else:
                self.stdout.write(f'  Permission already exists: {permission.name}')
            
            # Create DEV UI group
            group, created = Group.objects.get_or_create(name='DEV UI Users')
            if created:
                self.stdout.write(f'  Created group: {group.name}')
                group.permissions.add(permission)
            else:
                self.stdout.write(f'  Group already exists: {group.name}')
                if permission not in group.permissions.all():
                    group.permissions.add(permission)
                    self.stdout.write(f'  Added permission to group: {group.name}')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to create permissions: {e}')
            )
    
    def sync_node_types(self):
        """Sync node types from registry."""
        self.stdout.write('Syncing node types from registry...')
        
        try:
            dev_manager = get_dev_ui_manager()
            result = dev_manager.sync_node_metadata()
            
            self.stdout.write(f'  Discovered: {result["discovered"]} node types')
            self.stdout.write(f'  New: {result["new"]} node types')
            self.stdout.write(f'  Existing: {result["existing"]} node types')
            
            if result['new_types']:
                self.stdout.write('  New node types:')
                for node_type in result['new_types']:
                    self.stdout.write(f'    - {node_type}')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to sync node types: {e}')
            )
    
    def patch_execution_engine(self):
        """Patch execution engine with safety mechanisms."""
        self.stdout.write('Patching execution engine with safety mechanisms...')
        
        try:
            patch_execution_engine_for_dev_ui()
            self.stdout.write('  Execution engine patched successfully')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to patch execution engine: {e}')
            )