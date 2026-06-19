from typing import Dict, Any, List, Optional
import logging
from .base_node import ActionNode, NodeExecutionError
from .registry import register_node
from ..models import Credential

# Dependency Check
try:
    from google.cloud import bigquery
    from google.oauth2.credentials import Credentials as GoogleCredentials
except ImportError:
    bigquery = None
    GoogleCredentials = None

@register_node
class BigQueryNode(ActionNode):
    """
    BigQuery Node - Execute queries on Google BigQuery.
    Professional Edition: OAuth integration and standardized output.
    MVP: Only supports 'run_query' operation.
    """
    
    NODE_TYPE = "bigquery"
    DISPLAY_NAME = "Google BigQuery"
    DESCRIPTION = "Execute SQL queries on BigQuery data"
    CATEGORY = "DATA"
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        
        # 1. Dependency Check
        if bigquery is None:
            raise NodeExecutionError("BigQuery libraries not installed. Please run: pip install google-cloud-bigquery")

        operation = params.get('operation', 'run_query')
        project_id = self._resolve_template(params.get('project_id'), input_data, context)
        
        # Get credentials
        credential_id = params.get('credential_id')
        if not credential_id:
            raise NodeExecutionError("BigQuery credential is required")
            
        try:
            credential = Credential.objects.get(id=credential_id)
            
            # Helper to decrypt credential data (reused pattern)
            from ..services.credential_encryption import get_encryption_service
            svc = get_encryption_service()
            creds_data = {}
            if svc and credential.encrypted_data:
                 creds_data = svc.decrypt_credential_str(credential.encrypted_data) if isinstance(credential.encrypted_data, str) else credential.encrypted_data
            else:
                 creds_data = credential.encrypted_data

            if isinstance(creds_data, str):
                import json
                try: creds_data = json.loads(creds_data)
                except: raise NodeExecutionError("Invalid credential format")

            # Create Client
            # Check if using Service Account (JSON) or OAuth
            if 'private_key' in creds_data:
                 # Service Account
                 from google.oauth2 import service_account
                 creds = service_account.Credentials.from_service_account_info(creds_data)
            else:
                 # OAuth (User)
                 creds = GoogleCredentials(
                     token=creds_data.get('access_token'),
                     refresh_token=creds_data.get('refresh_token'),
                     token_uri=creds_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
                     client_id=creds_data.get('client_id'),
                     client_secret=creds_data.get('client_secret'),
                     scopes=creds_data.get('scopes', ['https://www.googleapis.com/auth/bigquery'])
                 )

            client = bigquery.Client(project=project_id, credentials=creds)
            
            result_data = {}
            meta_data = {
                "node_type": self.NODE_TYPE,
                "operation": operation,
                "project_id": project_id,
                "status": "success"
            }

            if operation == 'run_query':
                sql_query = self._resolve_template(params.get('sql_query'), input_data, context)
                if not sql_query:
                    raise NodeExecutionError("SQL Query is required")
                
                # Execute Query
                query_job = client.query(sql_query)
                rows = [dict(row) for row in query_job]
                
                result_data = {
                    "rows": rows,
                    "count": len(rows),
                    "job_id": query_job.job_id,
                    "total_bytes_processed": query_job.total_bytes_processed
                }
            
            # PHASE-2 Placeholders
            elif operation == 'insert_rows':
                raise NodeExecutionError("Insert Rows is not supported in MVP. Please use run_query with INSERT statement.")
            
            elif operation == 'list_tables':
                raise NodeExecutionError("List Tables is not supported in MVP.")

            else:
                raise NodeExecutionError(f"Unknown operation: {operation}")
            
            return {
                "output": result_data,
                "meta": meta_data
            }
            
        except Exception as e:
            self.logger.error(f"BigQuery operation failed: {e}")
            raise NodeExecutionError(f"BigQuery Failed: {e}")
    
    PROPERTIES = [
        {
            "name": "credential",
            "label": "Google OAuth Credential",
            "type": "credential_select",
            "credential_type": "google_bigquery",
            "required": True
        },
        {
            "name": "project_id",
            "label": "Project ID",
            "type": "text",
            "required": True
        },
        {
            "name": "operation",
            "label": "Operation",
            "type": "select",
            "default": "run_query",
            "options": [
                {"label": "Run Query", "value": "run_query"},
                {"label": "Insert Rows", "value": "insert_rows"},
                {"label": "List Tables", "value": "list_tables"}
            ]
        },
        {
            "name": "sql_query",
            "label": "SQL Query",
            "type": "textarea",
            "displayOptions": {
                "show": {"operation": ["run_query"]}
            }
        },
        {
            "name": "dataset_id",
            "label": "Dataset ID",
            "type": "text",
            "displayOptions": {
                "show": {"operation": ["insert_rows", "list_tables"]}
            }
        },
        {
            "name": "table_id",
            "label": "Table ID",
            "type": "text",
            "displayOptions": {
                "show": {"operation": ["insert_rows"]}
            }
        },
        {
            "name": "rows_json",
            "label": "Rows (JSON)",
            "type": "textarea",
            "displayOptions": {
                "show": {"operation": ["insert_rows"]}
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
