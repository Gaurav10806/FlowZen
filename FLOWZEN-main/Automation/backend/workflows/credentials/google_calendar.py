from typing import Dict, Any
import requests
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class GoogleCalendarCredential:
    """
    Google Calendar OAuth Credential Handler.
    Handles token refreshing and header generation.
    """
    
    TYPE = "google_calendar"
    TOKEN_URI = "https://oauth2.googleapis.com/token"
    
    @staticmethod
    def get_auth_headers(credential_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Get authorization headers, refreshing token if necessary.
        NOTE: In a real implementation, we would update the DB record if refreshed.
        For now, we return valid headers.
        """
        access_token = credential_data.get('access_token')
        expiry = credential_data.get('expiry') # ISO format
        refresh_token = credential_data.get('refresh_token')
        client_id = credential_data.get('client_id')
        client_secret = credential_data.get('client_secret')
        
        # Check if expired
        is_expired = False
        if expiry:
            try:
                exp_dt = datetime.fromisoformat(expiry.replace('Z', '+00:00'))
                if  datetime.utcnow().replace(tzinfo=None) >= (exp_dt.replace(tzinfo=None) - timedelta(minutes=5)):
                    is_expired = True
            except Exception as e:
                logger.warning(f"Error parsing expiry: {e}")
                is_expired = True
        else:
            is_expired = True
            
        if is_expired and refresh_token and client_id and client_secret:
            logger.info("Refreshing Google Calendar access token...")
            try:
                new_tokens = GoogleCalendarCredential.refresh_access_token(
                    client_id, client_secret, refresh_token
                )
                access_token = new_tokens.get('access_token')
                # In a full ORM context, we would save back to DB here.
                # Since this is a static helper, the caller (Service) might handle the update
                # or we just use it for this request.
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                raise Exception("Authentication failed: Could not refresh token")
                
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

    @staticmethod
    def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> Dict[str, Any]:
        """Call Google Token Endpoint to refresh."""
        payload = {
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token'
        }
        
        resp = requests.post(GoogleCalendarCredential.TOKEN_URI, data=payload)
        if not resp.ok:
            raise Exception(f"Token refresh failed: {resp.text}")
            
        return resp.json()
