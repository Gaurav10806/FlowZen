import logging
from typing import Dict, Any
from .base_node import BaseNode, NodeExecutionError
from .registry import register_node
from ..models import Credential
from ..services.google_calendar_service import GoogleCalendarService

logger = logging.getLogger(__name__)

@register_node
class GoogleCalendarNode(BaseNode):
    """
    Google Calendar Node for performing CRUD operations on events.
    """
    NODE_TYPE = "google_calendar"
    CATEGORY = "DATA"
    DISPLAY_NAME = "Google Calendar"

    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Google Calendar operation with standardized logic.
        """
        # 1. Resolve configuration
        operation = params.get("operation", "list_events")
        calendar_id = self._resolve_template(params.get("calendar_id", "primary"), input_data, context)
        
        # 'summary' is the standardized field name (mapping to Event Title in UI)
        summary = self._resolve_template(params.get("summary", ""), input_data, context)
        if not summary:
            summary = input_data.get("summary") or input_data.get("event_title") or input_data.get("title")

        start_datetime = self._resolve_template(params.get("start_datetime", ""), input_data, context) or input_data.get("start_datetime")
        end_datetime = self._resolve_template(params.get("end_datetime", ""), input_data, context) or input_data.get("end_datetime")
        event_id = self._resolve_template(params.get("event_id", ""), input_data, context) or input_data.get("event_id") or input_data.get("id")
        max_results = int(params.get("max_results", 10))

        # 2. Get Credential ID
        # Support both 'credential' (schema) and 'credential_id' (legacy/engine)
        cred_id = params.get("credential") or params.get("credential_id")
        if not cred_id:
            raise NodeExecutionError("Google OAuth credential is required.")

        try:
            # 3. Load Credential from DB
            try:
                credential = Credential.objects.get(id=cred_id)
            except Credential.DoesNotExist:
                raise NodeExecutionError(f"Credential not found: {cred_id}")

            # 4. Decrypt Data
            from ..services.credential_encryption import get_encryption_service
            svc = get_encryption_service()
            cred_data = {}
            if svc and credential.encrypted_data:
                cred_data = svc.decrypt_credential_str(credential.encrypted_data) if isinstance(credential.encrypted_data, str) else credential.encrypted_data
            else:
                cred_data = credential.encrypted_data

            # 5. Initialize Service
            service = GoogleCalendarService(cred_data)
            
            result_data = {}
            
            if operation == "create_event":
                if not summary or not start_datetime or not end_datetime:
                    raise NodeExecutionError("Summary (Event Title), Start Time, and End Time are required for 'create_event'.")
                
                event_payload = {
                    'summary': summary,
                    'start': {'dateTime': start_datetime},
                    'end': {'dateTime': end_datetime}
                }
                result_data = service.create_event(calendar_id, event_payload)

            elif operation == "list_events":
                result = service.list_events(calendar_id=calendar_id, max_results=max_results)
                result_data = result.get('items', [])

            elif operation == "delete_event":
                if not event_id:
                    raise NodeExecutionError("Event ID is required for 'delete_event'.")
                success = service.delete_event(calendar_id, event_id)
                result_data = {"status": "deleted", "event_id": event_id}

            elif operation == "update_event":
                if not event_id:
                    raise NodeExecutionError("Event ID is required for 'update_event'.")
                
                # We can pass partial data for patching
                patch_data = {}
                if summary: patch_data['summary'] = summary
                if start_datetime: patch_data['start'] = {'dateTime': start_datetime}
                if end_datetime: patch_data['end'] = {'dateTime': end_datetime}
                
                result_data = service.update_event(calendar_id, event_id, patch_data)

            else:
                raise NodeExecutionError(f"Unsupported operation: {operation}")

            # 6. Return Standardized Output
            return {
                "output": result_data,
                "meta": {
                    "node_type": self.NODE_TYPE,
                    "operation": operation,
                    "status": "success",
                    "calendar_id": calendar_id
                }
            }

        except Exception as e:
            logger.exception(f"Google Calendar execution failed: {e}")
            raise NodeExecutionError(f"Google Calendar error: {str(e)}")
