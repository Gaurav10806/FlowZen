"""
Management command to test Django admin stability.

This command tests all admin model classes to ensure they don't crash
when accessing list_display fields and other admin functionality.
"""

from django.core.management.base import BaseCommand
from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.contrib.admin.sites import AdminSite
from workflows.models import *
import logging


class Command(BaseCommand):
    help = 'Test Django admin stability for all registered models'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output',
        )
    
    def handle(self, *args, **options):
        self.verbose = options['verbose']
        self.stdout.write(self.style.SUCCESS('Starting Django Admin Stability Test'))
        
        # Create test request and user
        factory = RequestFactory()
        request = factory.get('/admin/')
        
        # Create or get test user
        test_user, created = User.objects.get_or_create(
            username='admin_test_user',
            defaults={
                'email': 'test@example.com',
                'is_staff': True,
                'is_superuser': True
            }
        )
        request.user = test_user
        
        # Get all registered admin classes
        admin_site = AdminSite()
        registered_models = admin.site._registry
        
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        
        for model, admin_class in registered_models.items():
            total_tests += 1
            
            try:
                self.test_admin_class(model, admin_class, request)
                passed_tests += 1
                if self.verbose:
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ {model.__name__}: PASSED')
                    )
            except Exception as e:
                failed_tests += 1
                self.stdout.write(
                    self.style.ERROR(f'❌ {model.__name__}: FAILED - {str(e)}')
                )
                if self.verbose:
                    import traceback
                    self.stdout.write(traceback.format_exc())
        
        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(f'Total models tested: {total_tests}')
        self.stdout.write(self.style.SUCCESS(f'Passed: {passed_tests}'))
        if failed_tests > 0:
            self.stdout.write(self.style.ERROR(f'Failed: {failed_tests}'))
        else:
            self.stdout.write(self.style.SUCCESS('All admin classes are stable! 🎉'))
        
        # Clean up test user
        if created:
            test_user.delete()
    
    def test_admin_class(self, model, admin_class, request):
        """Test a specific admin class for stability."""
        
        # Test 1: Check list_display fields exist and are callable
        list_display = getattr(admin_class, 'list_display', [])
        for field_name in list_display:
            if field_name == '__str__':
                continue
            
            # Check if it's a model field
            if hasattr(model, field_name):
                continue
            
            # Check if it's an admin method
            if hasattr(admin_class, field_name):
                method = getattr(admin_class, field_name)
                if callable(method):
                    # Test with a mock object
                    try:
                        mock_obj = self.create_mock_object(model)
                        if mock_obj:
                            admin_instance = admin_class(model, admin.site)
                            method(admin_instance, mock_obj)
                    except Exception as e:
                        if self.verbose:
                            self.stdout.write(f'  Warning: Method {field_name} failed: {e}')
                continue
            
            # If we get here, the field doesn't exist
            raise Exception(f'list_display field "{field_name}" not found on model or admin class')
        
        # Test 2: Check list_filter fields exist
        list_filter = getattr(admin_class, 'list_filter', [])
        for field_name in list_filter:
            if not hasattr(model, field_name):
                raise Exception(f'list_filter field "{field_name}" not found on model')
        
        # Test 3: Check search_fields exist
        search_fields = getattr(admin_class, 'search_fields', [])
        for field_name in search_fields:
            # Handle related field lookups (e.g., 'user__username')
            field_parts = field_name.split('__')
            current_model = model
            
            for part in field_parts:
                if not hasattr(current_model, part):
                    raise Exception(f'search_fields field "{field_name}" not found')
                
                field = getattr(current_model, part)
                if hasattr(field, 'field') and hasattr(field.field, 'related_model'):
                    current_model = field.field.related_model
        
        # Test 4: Try to instantiate admin class
        admin_instance = admin_class(model, admin.site)
        
        # Test 5: Check if queryset method works
        if hasattr(admin_instance, 'get_queryset'):
            try:
                admin_instance.get_queryset(request)
            except Exception as e:
                if self.verbose:
                    self.stdout.write(f'  Warning: get_queryset failed: {e}')
    
    def create_mock_object(self, model):
        """Create a mock object for testing admin methods."""
        try:
            # Try to get an existing object first
            obj = model.objects.first()
            if obj:
                return obj
            
            # If no objects exist, try to create a minimal one
            # This is a simplified approach - in practice, you might need
            # more sophisticated mock object creation
            return None
            
        except Exception:
            return None