import logging
import requests
import json
from typing import Dict, Any, List, Optional
from urllib.parse import quote

from workflows.credentials.google_calendar import GoogleCalendarCredential

logger = logging.getLogger(__name__)

class GoogleCalendarService:
    """
    Wrapper for Google Calendar REST API.
    """
    
    BASE_URL = "https://www.googleapis.com/calendar/v3"
    
    def __init__(self, credential_data: Dict[str, Any]):
        self.credential_data = credential_data
        
    def _get_headers(self) -> Dict[str, str]:
        """Get authenticated headers using Credential helper."""
        return GoogleCalendarCredential.get_auth_headers(self.credential_data)
        
    def list_events(self, calendar_id: str = 'primary', 
                   time_min: str = None, 
                   time_max: str = None, 
                   max_results: int = 10,
                   single_events: bool = True) -> Dict[str, Any]:
        """
        List events from a calendar.
        """
        url = f"{self.BASE_URL}/calendars/{quote(calendar_id)}/events"
        
        params = {
            'maxResults': max_results,
            'singleEvents': str(single_events).lower(),
            'orderBy': 'startTime'
        }
        
        if time_min:
            params['timeMin'] = time_min
        if time_max:
            params['timeMax'] = time_max
            
        headers = self._get_headers()
        
        response = requests.get(url, headers=headers, params=params)
        
        if not response.ok:
            logger.error(f"Google Calendar List Error: {response.text}")
            raise Exception(f"Google API Error: {response.status_code} {response.reason}")
            
        return response.json()

    def create_event(self, calendar_id: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new event.
        """
        url = f"{self.BASE_URL}/calendars/{quote(calendar_id)}/events"
        headers = self._get_headers()
        
        # Standardize event body
        body = {
            "summary": event_data.get("summary", "New Event"),
            "description": event_data.get("description", ""),
            "start": event_data.get("start"), # {"dateTime": "...", "timeZone": "..."}
            "end": event_data.get("end"),
            "location": event_data.get("location", ""),
            "attendees": event_data.get("attendees", [])
        }
        
        response = requests.post(url, headers=headers, json=body)
        
        if not response.ok:
            logger.error(f"Google Calendar Create Error: {response.text}")
            raise Exception(f"Google API Error: {response.status_code} {response.reason}")
            
        return response.json()

    def update_event(self, calendar_id: str, event_id: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing event (PATCH).
        """
        url = f"{self.BASE_URL}/calendars/{quote(calendar_id)}/events/{quote(event_id)}"
        headers = self._get_headers()
        
        response = requests.patch(url, headers=headers, json=event_data)
        
        if not response.ok:
            logger.error(f"Google Calendar Update Error: {response.text}")
            raise Exception(f"Google API Error: {response.status_code} {response.reason}")
            
        return response.json()

    def delete_event(self, calendar_id: str, event_id: str) -> bool:
        """
        Delete an event.
        """
        url = f"{self.BASE_URL}/calendars/{quote(calendar_id)}/events/{quote(event_id)}"
        headers = self._get_headers()
        
        response = requests.delete(url, headers=headers)
        
        if not response.ok and response.status_code != 404:
             # 404 is technically success for delete
            logger.error(f"Google Calendar Delete Error: {response.text}")
            raise Exception(f"Google API Error: {response.status_code} {response.reason}")
            
        return True
