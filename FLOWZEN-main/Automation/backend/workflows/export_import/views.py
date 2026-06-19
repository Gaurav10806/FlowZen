"""
Workflow Export/Import API Views

This module provides REST API endpoints for workflow export and import operations.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from ..models import Workflow
from .core import export_workflow, import_workflow, validate_import


logger = logging.getLogger(__name__)


class WorkflowExportView(View):
    """API view for exporting workflows."""
    
    @method_decorator(login_required)
    def post(self, request, workflow_id):
        """
        Export a workflow to portable format.
        
        POST /api/workflows/{workflow_id}/export/
        """
        try:
            # Get workflow and check permissions
            workflow = get_object_or_404(Workflow, id=workflow_id, owner=request.user)
            
            # Parse request options
            try:
                options = json.loads(request.body.decode('utf-8')) if request.body else {}
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON in request body'}, status=400)
            
            # Set default options
            export_options = {
                'format': options.get('format', 'json'),
                'include_metadata': options.get('include_metadata', True),
                'sanitize_credentials': options.get('sanitize_credentials', True)
            }
            
            # Export workflow
            export_data = export_workflow(workflow, export_options)
            
            # Handle different response formats
            response_format = export_options['format']
            
            if response_format == 'download':
                # Create downloadable file
                filename = f"{workflow.name.replace(' ', '_')}_export.json"
                response = HttpResponse(
                    json.dumps(export_data, indent=2),
                    content_type='application/json'
                )
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
            
            elif response_format == 'file':
                # Store file and return download URL
                filename = f"exports/{workflow.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                file_content = ContentFile(json.dumps(export_data, indent=2).encode('utf-8'))
                file_path = default_storage.save(filename, file_content)
                
                # Generate download URL (expires in 1 hour)
                download_url = f"/api/exports/{workflow.id}/download/"
                expires_at = datetime.now() + timedelta(hours=1)
                
                return JsonResponse({
                    'success': True,
                    'export_data': export_data,
                    'download_url': download_url,
                    'expires_at': expires_at.isoformat(),
                    'file_path': file_path
                })
            
            else:  # format == 'json' (default)
                return JsonResponse({
                    'success': True,
                    'export_data': export_data
                })
                
        except Workflow.DoesNotExist:
            return JsonResponse({'error': 'Workflow not found'}, status=404)
        except ValueError as e:
            return JsonResponse({'error': str(e)}, status=400)
        except Exception as e:
            logger.error(f"Export failed for workflow {workflow_id}: {e}")
            return JsonResponse({'error': 'Export failed'}, status=500)


class WorkflowImportView(View):
    """API view for importing workflows."""
    
    @method_decorator(login_required)
    @method_decorator(csrf_exempt)
    def post(self, request):
        """
        Import a workflow from portable format.
        
        POST /api/workflows/import/
        """
        try:
            # Parse request data
            try:
                request_data = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON in request body'}, status=400)
            
            # Extract import data and options
            workflow_data = request_data.get('workflow_data')
            if not workflow_data:
                return JsonResponse({'error': 'workflow_data is required'}, status=400)
            
            import_options = request_data.get('options', {})
            
            # Set default options
            options = {
                'conflict_resolution': import_options.get('conflict_resolution', 'rename'),
                'credential_mapping': import_options.get('credential_mapping', {}),
                'activate_after_import': import_options.get('activate_after_import', False)
            }
            
            # Import workflow
            result = import_workflow(workflow_data, request.user, options)
            
            if result.success:
                response_data = {
                    'success': True,
                    'workflow_id': result.workflow_id,
                    'warnings': result.warnings,
                    'import_summary': result.import_summary
                }
                
                # Optionally activate workflow after import
                if options['activate_after_import'] and result.workflow_id:
                    try:
                        workflow = Workflow.objects.get(id=result.workflow_id)
                        workflow.status = 'published'
                        workflow.save()
                        response_data['activated'] = True
                    except Exception as e:
                        response_data['warnings'].append(f"Failed to activate workflow: {str(e)}")
                
                return JsonResponse(response_data)
            else:
                return JsonResponse({
                    'success': False,
                    'errors': result.errors,
                    'warnings': result.warnings
                }, status=400)
                
        except Exception as e:
            logger.error(f"Import failed: {e}")
            return JsonResponse({'error': 'Import failed'}, status=500)


class WorkflowImportValidateView(View):
    """API view for validating workflow imports (dry-run)."""
    
    @method_decorator(login_required)
    @method_decorator(csrf_exempt)
    def post(self, request):
        """
        Validate workflow import data without importing.
        
        POST /api/workflows/import/validate/
        """
        try:
            # Parse request data
            try:
                request_data = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError:
                return JsonResponse({'error': 'Invalid JSON in request body'}, status=400)
            
            # Extract workflow data
            workflow_data = request_data.get('workflow_data')
            if not workflow_data:
                return JsonResponse({'error': 'workflow_data is required'}, status=400)
            
            # Validate import
            result = validate_import(workflow_data)
            
            if result.success:
                # Generate additional validation info
                validation_info = self._generate_validation_info(workflow_data, request.user)
                
                return JsonResponse({
                    'valid': True,
                    'compatibility': validation_info['compatibility'],
                    'requirements': validation_info['requirements'],
                    'warnings': result.warnings,
                    'errors': []
                })
            else:
                return JsonResponse({
                    'valid': False,
                    'compatibility': {'status': 'incompatible'},
                    'requirements': {},
                    'warnings': result.warnings,
                    'errors': result.errors
                })
                
        except Exception as e:
            logger.error(f"Import validation failed: {e}")
            return JsonResponse({'error': 'Validation failed'}, status=500)
    
    def _generate_validation_info(self, workflow_data: Dict[str, Any], user) -> Dict[str, Any]:
        """Generate detailed validation information."""
        from ..models import Credential
        
        # Check platform compatibility
        compatibility = {
            'platform_version': 'compatible',
            'node_types': 'all_available',
            'features': 'supported'
        }
        
        # Check credential requirements
        requirements = {'credentials': []}
        
        # Extract credential placeholders
        credential_placeholders = set()
        
        def extract_credentials(params: Dict[str, Any]):
            for key, value in params.items():
                if isinstance(value, str) and value.startswith('CREDENTIAL_'):
                    credential_placeholders.add(value)
                elif isinstance(value, dict):
                    extract_credentials(value)
        
        # Check trigger and nodes for credentials
        if 'trigger' in workflow_data and 'params' in workflow_data['trigger']:
            extract_credentials(workflow_data['trigger']['params'])
        
        if 'nodes' in workflow_data:
            for node_data in workflow_data['nodes'].values():
                if 'params' in node_data:
                    extract_credentials(node_data['params'])
        
        # Get user's available credentials
        user_credentials = Credential.objects.filter(owner=user)
        
        for placeholder in credential_placeholders:
            # Get available credentials that could be used
            available_creds = [
                {'id': str(cred.id), 'name': cred.name, 'type': cred.type}
                for cred in user_credentials
            ]
            
            requirements['credentials'].append({
                'placeholder': placeholder,
                'type': 'unknown',  # Would need to infer from context
                'description': f'Credential required for workflow operation',
                'available_credentials': available_creds
            })
        
        return {
            'compatibility': compatibility,
            'requirements': requirements
        }


class WorkflowExportDownloadView(View):
    """API view for downloading exported workflow files."""
    
    @method_decorator(login_required)
    def get(self, request, workflow_id):
        """
        Download exported workflow file.
        
        GET /api/exports/{workflow_id}/download/
        """
        try:
            # Verify user owns the workflow
            workflow = get_object_or_404(Workflow, id=workflow_id, owner=request.user)
            
            # Find the most recent export file for this workflow
            # In production, you'd track export files in database
            import os
            from django.conf import settings
            
            exports_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
            if not os.path.exists(exports_dir):
                return JsonResponse({'error': 'Export file not found'}, status=404)
            
            # Look for export files for this workflow
            export_files = [
                f for f in os.listdir(exports_dir) 
                if f.startswith(str(workflow_id)) and f.endswith('.json')
            ]
            
            if not export_files:
                return JsonResponse({'error': 'Export file not found'}, status=404)
            
            # Get the most recent file
            latest_file = sorted(export_files)[-1]
            file_path = os.path.join(exports_dir, latest_file)
            
            # Read and return file
            with open(file_path, 'r') as f:
                export_data = f.read()
            
            filename = f"{workflow.name.replace(' ', '_')}_export.json"
            response = HttpResponse(export_data, content_type='application/json')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            return response
            
        except Workflow.DoesNotExist:
            return JsonResponse({'error': 'Workflow not found'}, status=404)
        except Exception as e:
            logger.error(f"Download failed for workflow {workflow_id}: {e}")
            return JsonResponse({'error': 'Download failed'}, status=500)


# Function-based views for simple endpoints
@login_required
@require_http_methods(["POST"])
@csrf_exempt
def export_workflow_simple(request, workflow_id):
    """
    Simple workflow export endpoint.
    
    POST /api/workflows/{workflow_id}/export/simple/
    """
    try:
        # Get workflow and check permissions
        workflow = get_object_or_404(Workflow, id=workflow_id, owner=request.user)
        
        # Export with default options
        export_data = export_workflow(workflow)
        
        return JsonResponse({
            'success': True,
            'workflow_name': workflow.name,
            'export_data': export_data
        })
        
    except Workflow.DoesNotExist:
        return JsonResponse({'error': 'Workflow not found'}, status=404)
    except Exception as e:
        logger.error(f"Simple export failed for workflow {workflow_id}: {e}")
        return JsonResponse({'error': 'Export failed'}, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def import_workflow_simple(request):
    """
    Simple workflow import endpoint.
    
    POST /api/workflows/import/simple/
    """
    try:
        # Parse request data
        try:
            request_data = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        workflow_data = request_data.get('workflow_data')
        if not workflow_data:
            return JsonResponse({'error': 'workflow_data is required'}, status=400)
        
        # Import with default options
        result = import_workflow(workflow_data, request.user)
        
        if result.success:
            return JsonResponse({
                'success': True,
                'workflow_id': result.workflow_id,
                'message': 'Workflow imported successfully',
                'warnings': result.warnings
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': result.errors
            }, status=400)
            
    except Exception as e:
        logger.error(f"Simple import failed: {e}")
        return JsonResponse({'error': 'Import failed'}, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def validate_import_simple(request):
    """
    Simple import validation endpoint.
    
    POST /api/workflows/import/validate/simple/
    """
    try:
        # Parse request data
        try:
            request_data = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        workflow_data = request_data.get('workflow_data')
        if not workflow_data:
            return JsonResponse({'error': 'workflow_data is required'}, status=400)
        
        # Validate import
        result = validate_import(workflow_data)
        
        return JsonResponse({
            'valid': result.success,
            'errors': result.errors,
            'warnings': result.warnings
        })
        
    except Exception as e:
        logger.error(f"Simple validation failed: {e}")
        return JsonResponse({'error': 'Validation failed'}, status=500)