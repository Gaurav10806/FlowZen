import os
import io
import shutil
import base64
from typing import Dict, Any, List, Optional
from .base_node import ActionNode, NodeExecutionError
from .registry import register_node

# Security Constraint
ALLOWED_ROOT = os.path.abspath("/tmp/workflows/")
# Ensure base directory exists
os.makedirs(ALLOWED_ROOT, exist_ok=True)

@register_node
class FileStorageNode(ActionNode):
    """
    File Storage Node - Basic file operations within a sandboxed directory.
    Professional Edition: Strict path validation and encoding support.
    """
    
    NODE_TYPE = "file_storage"
    DISPLAY_NAME = "File Storage"
    DESCRIPTION = "Read and write files in sandboxed storage"
    CATEGORY = "data"
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        operation = params.get('operation', 'read')
        file_path_input = self._resolve_template(params.get('file_path'), input_data, context)
        
        # Security: Path Validation
        file_path = self._validate_path(file_path_input)
        
        result_data = {}
        meta_data = {
            "node_type": self.NODE_TYPE,
            "operation": operation,
            "file_path": file_path_input, # Show original input for clarity
            "status": "success"
        }
        
        try:
            encoding = params.get('encoding', 'utf-8')

            if operation == 'read':
                if not os.path.exists(file_path):
                     raise NodeExecutionError(f"File not found: {file_path_input}")
                
                with open(file_path, 'rb') as f:
                    raw_bytes = f.read()

                if encoding == 'base64':
                    output_data = base64.b64encode(raw_bytes).decode('ascii')
                else:
                    try:
                        output_data = raw_bytes.decode(encoding)
                    except Exception as e:
                        raise NodeExecutionError(f"Decoding failed for {encoding}: {e}")

                result_data = {
                    "content": output_data,
                    "encoding": encoding,
                    "size": len(raw_bytes),
                    "file_path": file_path_input
                }
            
            elif operation in ('write', 'append'):
                content = self._resolve_template(params.get('content'), input_data, context)
                overwrite = params.get('overwrite', True)
                
                mode = 'ab' if operation == 'append' else 'wb'
                
                if operation == 'write' and not overwrite and os.path.exists(file_path):
                     raise NodeExecutionError(f"File exists and overwrite is disabled: {file_path_input}")
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                if encoding == 'base64':
                    try:
                        raw_bytes = base64.b64decode(content)
                    except Exception as e:
                        raise NodeExecutionError(f"Invalid Base64 content: {e}")
                else:
                    raw_bytes = str(content).encode(encoding)

                with open(file_path, mode) as f:
                    f.write(raw_bytes)
                
                result_data = {
                    "written": True,
                    "size": os.path.getsize(file_path),
                    "file_path": file_path_input
                }

            elif operation == 'delete':
                if os.path.exists(file_path):
                    os.remove(file_path)
                    result_data = {"deleted": True}
                else:
                    result_data = {"deleted": False, "message": "File not found"}
            
            else:
                 raise NodeExecutionError(f"Unknown operation: {operation}")

            return {
                "output": result_data,
                "meta": meta_data
            }

        except Exception as e:
            self.logger.error(f"File operation failed: {e}")
            raise NodeExecutionError(f"File Error: {str(e)}")

    def _validate_path(self, relative_path: str) -> str:
        """
        Securely resolve and validate path is within ALLOWED_ROOT.
        """
        if not relative_path:
             raise NodeExecutionError("File path is required")
        
        # Remove leading slashes to treat as relative to root
        clean_path = relative_path.lstrip(os.sep).lstrip('/')
        
        # Resolve absolute path
        abs_path = os.path.abspath(os.path.join(ALLOWED_ROOT, clean_path))
        
        # Check traversal
        if not abs_path.startswith(ALLOWED_ROOT):
             raise NodeExecutionError("Access denied: Path outside allowed root (/tmp/workflows/)")
        
        return abs_path

    PROPERTIES = [
        {
            "name": "operation",
            "label": "Operation",
            "type": "select",
            "options": [
                {"label": "Read", "value": "read"},
                {"label": "Write", "value": "write"},
                {"label": "Append", "value": "append"},
                {"label": "Delete", "value": "delete"}
            ],
            "default": "read"
        },
        {
            "name": "file_path",
            "label": "File Path",
            "type": "text",
            "required": True
        },
        {
            "name": "encoding",
            "label": "Encoding",
            "type": "select",
            "default": "utf-8",
            "options": [
                {"label": "UTF-8", "value": "utf-8"},
                {"label": "ASCII", "value": "ascii"},
                {"label": "Binary (Base64)", "value": "base64"}
            ],
            "displayOptions": {
                "show": {"operation": ["read", "write", "append"]}
            }
        },
        {
            "name": "content",
            "label": "Content (Write/Append)",
            "type": "textarea",
            "displayOptions": {
                "show": {"operation": ["write", "append"]}
            }
        },
        {
            "name": "overwrite",
            "label": "Overwrite",
            "type": "toggle",
            "default": True,
            "displayOptions": {
                "show": {"operation": ["write"]}
            }
        }
    ]

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": cls.PROPERTIES,
            "required": [p["name"] for p in cls.PROPERTIES if p.get("required")]
        }
