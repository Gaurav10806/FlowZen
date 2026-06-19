"""
Google Drive Node

This module contains the Google Drive node implementation.
"""

from typing import Dict, Any, List
import base64
from .base_node import ActionNode, NodeExecutionError
from .registry import register_node
from ..services.google_drive_service import GoogleDriveService
from ..models import Credential

@register_node
class GoogleDriveNode(ActionNode):
    """
    Google Drive node - interacts with Google Drive API.
    """
    
    NODE_TYPE = "google_drive"
    DISPLAY_NAME = "Google Drive"
    DESCRIPTION = "Upload, List, and Manage files on Google Drive"
    CATEGORY = "integrations"
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Google Drive operation.
        """
        operation = params.get('operation', 'upload')
        
        # Get credentials
        credential_id = params.get('credential_id') or getattr(self.config, 'credential_id', None)
        if not credential_id:
            raise NodeExecutionError("Google Drive credential is required")
            
        try:
            credential = Credential.objects.get(id=credential_id)
            
            # Helper to decrypt credential data
            from ..services.credential_encryption import get_encryption_service
            svc = get_encryption_service()
            creds_data = {}
            if svc and credential.encrypted_data:
                 creds_data = svc.decrypt_credential_str(credential.encrypted_data) if isinstance(credential.encrypted_data, str) else credential.encrypted_data
            else:
                 creds_data = credential.encrypted_data

            service = GoogleDriveService(creds_data) # Requires scopes
            
            result = {}
            
            if operation == 'upload':
                # File Name
                filename = self._resolve_template(params.get('filename', 'file.txt'), input_data, context)
                
                # File Content (Base64 or String)
                # Check for binary input from previous node (HTTP, etc)
                content = None
                mime_type = params.get('mime_type', 'text/plain')
                
                # 1. Try explicit 'content' parameter
                if params.get('content'):
                    content_str = self._resolve_template(params.get('content'), input_data, context)
                    content = content_str.encode('utf-8')
                    
                # 2. Try 'binary' input from HTTP node
                elif input_data.get('binary'):
                    # Expect structure: { "binary": { "data": "base64...", "mime_type": "..." } }
                    bin_data = input_data['binary']
                    if 'data' in bin_data:
                         try:
                             content = base64.b64decode(bin_data['data'])
                             mime_type = bin_data.get('mime_type', mime_type)
                             filename = bin_data.get('name', filename) # Auto-name if available
                         except:
                             self.logger.warning("Failed to decode binary input")

                if content is None:
                    raise NodeExecutionError("No content provided for upload")
                
                parent_id = self._resolve_template(params.get('parent_id'), input_data, context)
                
                output = service.upload_file(filename, content, mime_type, parent_id)
                result = {
                    'file_id': output.get('id'),
                    'file_name': output.get('name'),
                    'web_link': output.get('webViewLink'),
                    'status': 'success'
                }
                
            elif operation == 'list':
                query = self._resolve_template(params.get('query', ''), input_data, context)
                limit = int(params.get('limit', 10))
                
                files = service.list_files(query, limit)
                result = {
                    'files': files,
                    'count': len(files),
                    'status': 'success'
                }
                
            elif operation == 'create_folder':
                folder_name = self._resolve_template(params.get('folder_name', 'New Folder'), input_data, context)
                parent_id = self._resolve_template(params.get('parent_id'), input_data, context)
                
                output = service.create_folder(folder_name, parent_id)
                result = {
                    'folder_id': output.get('id'),
                    'folder_name': output.get('name'),
                    'web_link': output.get('webViewLink'),
                    'status': 'success'
                }
            
            elif operation == 'delete':
                file_id = self._resolve_template(params.get('file_id'), input_data, context)
                service.delete_file(file_id)
                result = {
                    'deleted_id': file_id,
                    'status': 'success'
                }

            else:
                raise NodeExecutionError(f"Unknown operation: {operation}")
                
            return result
            
        except Exception as e:
            self.logger.error(f"Google Drive operation failed: {e}")
            raise NodeExecutionError(f"Google Drive failed: {e}")
    
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "credential_id": {
                    "type": "string",
                    "title": "Credential",
                    "widget": "credential_select",
                    "credential_type": "google_drive" # or google_oauth
                },
                "operation": {
                    "type": "string",
                    "enum": ["upload", "list", "create_folder", "delete"],
                    "default": "upload",
                    "title": "Operation"
                },
                # Upload Params
                "filename": {
                    "type": "string",
                    "title": "File Name",
                    "default": "file.txt",
                    "description": "Output filename (Upload only)"
                },
                "content": {
                    "type": "string",
                    "title": "Text Content",
                    "description": "Text content to upload. Leave empty if using Binary input from HTTP Node."
                },
                "mime_type": {
                    "type": "string",
                    "title": "MIME Type",
                    "default": "text/plain"
                },
                "parent_id": {
                    "type": "string",
                    "title": "Parent Folder ID",
                    "description": "ID of parent folder (Upload/Create Folder)"
                },
                # List Params
                "query": {
                    "type": "string",
                    "title": "Search Query",
                    "description": "Drive API query (e.g. \"name contains 'contract' and mimeType = 'application/vnd.google-apps.folder'\")"
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "title": "Limit"
                },
                # Create Folder Params
                "folder_name": {
                    "type": "string",
                    "title": "Folder Name",
                    "default": "New Folder"
                },
                # Delete Params
                "file_id": {
                    "type": "string",
                    "title": "File ID",
                    "description": "ID of file/folder to delete"
                }
            },
            "required": ["credential_id", "operation"]
        }
