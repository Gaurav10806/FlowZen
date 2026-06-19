from typing import Dict, Any, List, Optional
import json
import logging
from .base_node import ActionNode, NodeExecutionError
from .registry import register_node
from ..models import Credential

# Safe Driver Imports
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None

try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

try:
    import sqlite3
    SQLITE_AVAILABLE = True
except ImportError:
    SQLITE_AVAILABLE = False

@register_node
class DatabaseQueryNode(ActionNode):
    """
    Database Query Node - Execute SQL queries on Postgres, MySQL, or SQLite.
    Professional Edition: Parameterized queries, connection pooling (todo), and standardized output.
    """
    
    NODE_TYPE = "database_query"
    DISPLAY_NAME = "Database Query"
    DESCRIPTION = "Execute SQL queries on external databases"
    CATEGORY = "data"
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        
        db_type = params.get('db_type', 'postgres')
        sql_query = self._resolve_template(params.get('sql_query'), input_data, context)
        
        # Parameter Resolution (JSON or Dictionary)
        query_params_input = params.get('query_params')
        query_params = self._resolve_template(query_params_input, input_data, context)
        
        if isinstance(query_params, str) and query_params.strip():
            try:
                query_params = json.loads(query_params)
            except Exception as e:
                raise NodeExecutionError(f"Invalid JSON in query_params: {e}")
        
        if not isinstance(query_params, (dict, list, tuple)) and query_params is not None:
             # If it's a single value, wrap it? No, explicit is better. 
             # Allow None for no params.
             query_params = None

        credential_id = params.get('credential_id')
        
        result_data = {}
        meta_data = {
            "node_type": self.NODE_TYPE,
            "db_type": db_type,
            "status": "success"
        }

        try:
            if db_type == 'postgres':
                if not PSYCOPG2_AVAILABLE:
                    raise NodeExecutionError("PostgreSQL driver (psycopg2) not installed.")
                
                connection = self._get_postgres_connection(credential_id)
                try:
                    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                        # SECURITY: Parameterized Query
                        cursor.execute(sql_query, query_params)
                        
                        if cursor.description:
                            rows = cursor.fetchall()
                            result_data = {
                                "rows": rows,
                                "count": len(rows)
                            }
                        else:
                            connection.commit()
                            result_data = {
                                "rows": [],
                                "count": cursor.rowcount,
                                "message": "Query executed successfully"
                            }
                finally:
                    connection.close()
            
            elif db_type == 'mysql':
                if not MYSQL_AVAILABLE:
                    raise NodeExecutionError("MySQL driver (mysql-connector-python) not installed.")
                
                connection = self._get_mysql_connection(credential_id)
                try:
                    cursor = connection.cursor(dictionary=True)
                    # SECURITY: Parameterized Query
                    cursor.execute(sql_query, query_params)
                    
                    if cursor.with_rows:
                        rows = cursor.fetchall()
                        result_data = {
                            "rows": rows,
                            "count": len(rows)
                        }
                    else:
                        connection.commit()
                        result_data = {
                            "rows": [],
                            "count": cursor.rowcount,
                            "message": "Query executed successfully"
                        }
                    cursor.close()
                finally:
                    connection.close()

            elif db_type == 'sqlite':
                # For SQLite, credential might be a file path or generic "sqlite_file" cred
                # MVP: Use a specific path or allowed directory
                # SECURITY: Enforce path restrictions like FileStorageNode? 
                # For now, let's assume it connects to a specific db file defined in creds or config.
                # Since we don't have a specific credential type for SQLite yet, we'll skip strict cred check 
                # and maybe allow a 'db_path' param for local testing IF allowed.
                # IMPLEMENTATION CHOICE: Disable SQLite for general users for security unless strictly sandboxed.
                # But for this MVP let's implement safe execution if requested.
                
                # ... skipping implementation for now to focus on Postgres/MySQL as priority ...
                raise NodeExecutionError("SQLite support not yet enabled for security reasons.")

            else:
                 raise NodeExecutionError(f"Unsupported database type: {db_type}")

            return {
                "output": result_data,
                "meta": meta_data
            }

        except Exception as e:
            self.logger.error(f"Database query failed: {e}")
            raise NodeExecutionError(f"Database Error: {e}")

    def _get_postgres_connection(self, credential_id):
        if not credential_id:
            raise NodeExecutionError("Credential required for Postgres")
        
        cred = Credential.objects.get(id=credential_id)
        data = cred.get_decrypted_data() # Assuming generic helper or implement manual
        
        # Fallback manual decryption if helper not available on model
        if isinstance(data, str) and not isinstance(data, dict):
             # Try simple decrypt 
             from ..services.credential_encryption import get_encryption_service
             svc = get_encryption_service()
             if svc: data = svc.decrypt_credential_str(cred.encrypted_data)
        
        if isinstance(data, str):
             data = json.loads(data)

        return psycopg2.connect(
            host=data.get('host'),
            port=data.get('port', 5432),
            database=data.get('database'),
            user=data.get('user') or data.get('username'),
            password=data.get('password')
        )

    def _get_mysql_connection(self, credential_id):
        if not credential_id:
            raise NodeExecutionError("Credential required for MySQL")
        
        cred = Credential.objects.get(id=credential_id)
        # ... same decryption logic ...
        from ..services.credential_encryption import get_encryption_service
        svc = get_encryption_service()
        data = cred.encrypted_data
        if svc: 
             dec = svc.decrypt_credential_str(data) if isinstance(data, str) else data
             if isinstance(dec, str): 
                  try: data = json.loads(dec)
                  except: pass
             else: data = dec

        return mysql.connector.connect(
            host=data.get('host'),
            port=int(data.get('port', 3306)),
            database=data.get('database'),
            user=data.get('user') or data.get('username'),
            password=data.get('password')
        )

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "db_type": {
                    "type": "string",
                    "title": "Database Type",
                    "enum": ["postgres", "mysql"], # SQLite disabled for now
                    "default": "postgres"
                },
                "credential_id": {
                    "type": "string",
                    "title": "Credential",
                    "widget": "credential_select",
                    "credential_type": "database_credentials", # needs generic type or specific
                    "required": True
                },
                "sql_query": {
                    "type": "string",
                    "title": "SQL Query",
                    "widget": "textarea", # TODO: SQL Editor widget if available
                    "default": "SELECT * FROM users LIMIT 10;",
                    "description": "Use ? or %s for parameters depending on DB type"
                },
                "query_params": {
                    "type": "string",
                    "title": "Query Parameters (JSON)",
                    "widget": "textarea",
                    "description": "List or Dict of parameters for safe execution. E.g. [1, 'active'] or {'status': 'active'}"
                }
            },
            "required": ["db_type", "credential_id", "sql_query"]
        }
