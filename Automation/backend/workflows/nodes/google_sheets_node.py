"""
Google Sheets Node

This module contains the Google Sheets node implementation.
"""

from typing import Dict, Any, List
from .base_node import ActionNode, NodeExecutionError
from .registry import register_node
from ..services.google_sheets_service import GoogleSheetsService
from ..models import Credential

@register_node
@register_node
class GoogleSheetsNode(ActionNode):
    """
    Google Sheets node - interacts with Google Sheets API.
    Professional Edition: Full CRUD support with standardized output.
    """
    
    NODE_TYPE = "google_sheets"
    DISPLAY_NAME = "Google Sheets"
    DESCRIPTION = "Read, write, update, and clear Google Sheets"
    CATEGORY = "integrations"
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Google Sheets operation with standardized output.
        """
        operation = params.get('operation', 'append')
        spreadsheet_id = self._resolve_template(params.get('spreadsheet_id'), input_data, context)
        range_name = self._resolve_template(params.get('range'), input_data, context)
        
        # Get credentials
        credential_id = params.get('credential_id') or getattr(self.config, 'credential_id', None)
        if not credential_id:
            raise NodeExecutionError("Google Sheets credential is required")
            
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

            service = GoogleSheetsService(creds_data)
            
            result_data = {}
            meta_data = {
                "node_type": self.NODE_TYPE,
                "operation": operation,
                "status": "success",
                "spreadsheet_id": spreadsheet_id
            }
            
            if operation == 'append':
                # Smart Value Resolution
                values_input = params.get('values')
                values = self._resolve_template(values_input, input_data, context)
                
                # Check for smart fallback to incoming data if empty
                if not values or values == '[]':
                    if isinstance(input_data, dict):
                        # Extract values from input dict if logical
                        # For now, simplistic fallback to just values of the dict
                        values = [list(input_data.values())]
                    elif isinstance(input_data, list):
                        values = [input_data]
                
                if isinstance(values, str):
                    import json
                    try: values = json.loads(values)
                    except: values = [[values]] # Treat as single cell
                
                if not isinstance(values, list):
                    values = [[values]]
                
                # Ensure list of lists
                if values and not isinstance(values[0], list):
                    values = [values]
                    
                output = service.append_values(spreadsheet_id, range_name, values)
                result_data = {
                    'updated_cells': output.get('updates', {}).get('updatedCells'),
                    'updated_range': output.get('updates', {}).get('updatedRange'),
                    'rows_appended': len(values)
                }
                
            elif operation == 'get':
                rows = service.get_values(spreadsheet_id, range_name)
                # Parse Logic: Optional 'first_row_as_headers' support could go here
                result_data = {
                    'rows': rows,
                    'count': len(rows) if rows else 0
                }
                
            elif operation == 'update':
                values = self._resolve_template(params.get('values'), input_data, context)
                if isinstance(values, str):
                    import json
                    try: values = json.loads(values)
                    except: values = [[values]]
                if not isinstance(values, list):
                    values = [[values]]
                    
                output = service.update_values(spreadsheet_id, range_name, values)
                result_data = {
                    'updated_cells': output.get('updatedCells'),
                    'updated_range': output.get('updatedRange')
                }
                
            elif operation == 'clear':
                output = service.clear_values(spreadsheet_id, range_name)
                result_data = {
                    'cleared_range': output.get('clearedRange')
                }
            
            elif operation == 'lookup':
                sheet_name = params.get('sheet_name', 'Sheet1')
                column = params.get('lookup_column', 'A')
                value = self._resolve_template(params.get('lookup_value', ''), input_data, context)
                
                row_num = service.find_row(spreadsheet_id, sheet_name, column, value)
                
                if row_num:
                    result_data = {
                        'found': True,
                        'row_number': row_num,
                        'value': value
                    }
                else:
                    if params.get('fail_if_not_found', False):
                        raise NodeExecutionError(f"Value '{value}' not found in column {column}")
                    result_data = {
                        'found': False,
                        'row_number': None,
                        'value': value
                    }
                    meta_data['status'] = 'not_found'

            else:
                raise NodeExecutionError(f"Unknown operation: {operation}")
                
            # Standardized Output Contract
            return {
                "output": result_data,
                "meta": meta_data
            }
            
        except Exception as e:
            self.logger.error(f"Google Sheets operation failed: {e}")
            raise NodeExecutionError(f"Google Sheets failed: {e}")
    
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "credential_id": {
                    "type": "string",
                    "title": "Google Credential",
                    "widget": "credential_select",
                    "credential_type": "google_sheets", # Frontend maps this to google_oauth usually
                    "required": True
                },
                "operation": {
                    "type": "string",
                    "enum": ["append", "get", "update", "clear", "lookup"],
                    "default": "append",
                    "title": "Operation"
                },
                "spreadsheet_id": {
                    "type": "string",
                    "title": "Spreadsheet ID",
                    "description": "ID from the Google Sheets URL",
                    "required": True
                },
                "range": {
                    "type": "string",
                    "title": "Range",
                    "description": "A1 notation (e.g., 'Sheet1!A1:B10'). Required for Get/Update/Clear.",
                    "displayOptions": {
                        "show": {
                            "operation": ["append", "get", "update", "clear"]
                        }
                    }
                },
                "values": {
                    "type": "string",
                    "title": "Values (JSON)",
                    "widget": "textarea",
                    "description": "Array of arrays for rows (e.g. [['A', 'B']]). If empty, tries to use incoming data.",
                    "displayOptions": {
                        "show": {
                            "operation": ["append", "update"]
                        }
                    }
                },
                "sheet_name": {
                    "type": "string",
                    "title": "Sheet Name",
                    "default": "Sheet1",
                    "description": "Target sheet name",
                    "displayOptions": {
                        "show": {
                            "operation": ["lookup"]
                        }
                    }
                },
                "lookup_column": {
                    "type": "string",
                    "title": "Lookup Column",
                    "default": "A",
                    "description": "Column letter to search (e.g. A)",
                    "displayOptions": {
                        "show": {
                            "operation": ["lookup"]
                        }
                    }
                },
                "lookup_value": {
                    "type": "string",
                    "title": "Lookup Value",
                    "description": "Value to find",
                    "displayOptions": {
                        "show": {
                            "operation": ["lookup"]
                        }
                    }
                },
                "fail_if_not_found": {
                    "type": "boolean",
                    "default": False,
                    "title": "Fail if not found",
                    "displayOptions": {
                        "show": {
                            "operation": ["lookup"]
                        }
                    }
                }
            },
            "required": ["spreadsheet_id", "operation"]
        }
