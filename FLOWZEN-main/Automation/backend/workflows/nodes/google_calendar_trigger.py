from typing import Dict, Any
from datetime import datetime, timedelta
from .base_node import TriggerNode, NodeExecutionError
from .registry import register_node
from workflows.services.google_calendar_service import GoogleCalendarService
from workflows.models import Credential

@register_node
class GoogleCalendarTriggerNode(TriggerNode):
    """
    Google Calendar Trigger Node.
    Polls for new or updated events based on time window.
    """
    
    NODE_TYPE = "google_calendar_trigger"
    DISPLAY_NAME = "Google Calendar Trigger"
    DESCRIPTION = "Triggers workflow when events are created or updated"
    CATEGORY = "triggers"
    SUPPORTS_RETRY = False
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute polling logic.
        """
        # 1. Resolve Credential
        credential_id = params.get('credential_id')
        if not credential_id:
             raise NodeExecutionError("Missing Google Calendar credential")

        try:
            credential = Credential.objects.get(id=credential_id, type='google_calendar')
            cred_data = credential.encrypted_data
        except Credential.DoesNotExist:
            raise NodeExecutionError(f"Credential {credential_id} not found")
            
        # 2. Initialize Service
        service = GoogleCalendarService(cred_data)
        
        # 3. Determine Time Window
        # In a real polling system, we'd use stored state (last_sync_time).
        # Here we use a "Lookback Window" based on poll interval.
        calendar_id = params.get('calendar_id', 'primary')
        poll_interval_min = int(params.get('poll_interval', 1))
        
        # Safety margin to ensure we don't miss events between ticks
        lookback_minutes = poll_interval_min + 1 
        
        now = datetime.utcnow()
        time_min_dt = now - timedelta(minutes=lookback_minutes)
        time_min = time_min_dt.isoformat() + 'Z' # UTC
        
        # 4. Fetch Events
        try:
            # We list events updated/started after time_min
            # Google API uses 'updatedMin' for sync, 
            # OR logic: events starting in this window.
            # Standard n8n practice: triggered on specific event "Event Created" or "Event Starting".
            
            trigger_on = params.get('trigger_on', 'event_created')
            
            # Since standard list_events wrapper uses timeMin for 'start time', 
            # we might need to adjust or rely on 'updatedMin' if we want modification triggers.
            # But our Service wrapper `list_events` uses `timeMin` effectively as "Overlap or Start".
            
            # Simplified Logic: Get events active/starting in window
            events_result = service.list_events(calendar_id, time_min=time_min)
            events = events_result.get('items', [])
            
            # Filter matches manually if needed (e.g. only new vs updated)
            # For this MVP, we return ALL found events in window.
            # In production, we would need deduplication against a DB of seen IDs.
            
            if not events:
                # No events found
                return {
                    "success": True,
                    "output": None # Engine handles "no fire"
                }

            # If events found, we return them.
            # Engine standard: If a trigger returns a list, it usually triggers once per item 
            # OR creates a list output.
            # Here we return the list as 'events' key.
            
            return {
                "success": True,
                "output": {
                    "events": events,
                    "count": len(events),
                    "trigger_type": trigger_on,
                    "calendar_id": calendar_id
                }
            }
            
        except Exception as e:
            self.logger.error(f"Google Calendar Trigger Failed: {e}")
            raise NodeExecutionError(f"Google Calendar Trigger Error: {str(e)}")

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "credential_id": {
                    "type": "string",
                    "title": "Google Credential",
                    "widget": "credential_select",
                    "credential_type": "google_calendar"
                },
                "calendar_id": {
                    "type": "string",
                    "title": "Calendar ID",
                    "default": "primary"
                },
                "trigger_on": {
                    "type": "string",
                    "title": "Trigger On",
                    "enum": ["event_created", "event_starting"],
                    "default": "event_created",
                    "description": "Condition to trigger workflow"
                },
                "poll_interval": {
                    "type": "integer",
                    "title": "Poll Interval (Minutes)",
                    "default": 1,
                    "minimum": 1,
                    "description": "How often to check for new events"
                }
            },
            "required": ["credential_id", "poll_interval"]
        }
