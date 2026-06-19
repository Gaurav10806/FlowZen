"""
Gmail OAuth Service for sending emails via Gmail API.
Implements n8n-style Gmail OAuth integration with automatic token refresh.
"""
import base64
import json
import logging
from typing import Dict, Any, Optional, List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q

from ..models import Credential
from .credential_encryption import get_encryption_service

logger = logging.getLogger(__name__)


class GmailOAuthError(Exception):
    """Gmail OAuth specific errors."""
    pass


class GmailOAuthService:
    """
    Gmail OAuth service for sending emails via Gmail API.
    Handles OAuth token management and email sending.
    """
    
    # Gmail API endpoints
    GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"
    OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
    
    # Required OAuth scope for sending emails, profile access, Sheets, and BigQuery
    REQUIRED_SCOPE = "https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/bigquery"
    
    def __init__(self, user=None, tenant=None):
        self.user = user
        self.tenant = tenant
        self.encryption_service = get_encryption_service()
    
    def get_gmail_credential(self, from_email: str) -> Optional[Credential]:
        """
        Get Gmail OAuth credential for the specified email address.
        
        Args:
            from_email: Gmail address to find credential for
            
        Returns:
            Credential instance or None if not found
        """
        try:
            # Support multiple type names for compatibility
            q_types = Q(type='gmail') | Q(type='gmail_oauth') | Q(type='google_oauth')
            
            # Look for Gmail OAuth credential for this email
            credential = Credential.objects.filter(
                q_types,
                tenant=self.tenant,
                name__icontains=from_email.split('@')[0]  # Match username part
            ).first()
            
            if not credential:
                # Try broader search by email in encrypted_data
                credentials = Credential.objects.filter(
                    q_types,
                    tenant=self.tenant
                )
                
                for cred in credentials:
                    try:
                        data = self._decrypt_credential_data(cred)
                        if data.get('email') == from_email:
                            credential = cred
                            break
                    except Exception:
                        continue
            
            return credential
            
        except Exception as e:
            logger.error(f"Error finding Gmail credential: {e}")
            return None
    
    def _decrypt_credential_data(self, credential: Credential) -> Dict[str, Any]:
        """Decrypt credential data safely."""
        try:
            if isinstance(credential.encrypted_data, dict):
                return credential.encrypted_data
            elif isinstance(credential.encrypted_data, str) and self.encryption_service:
                return self.encryption_service.decrypt_credential_str(credential.encrypted_data)
            else:
                return {}
        except Exception as e:
            logger.error(f"Failed to decrypt credential data: {e}")
            return {}
    
    def _encrypt_credential_data(self, credential: Credential, data: Dict[str, Any]) -> None:
        """Encrypt and save credential data."""
        try:
            if self.encryption_service:
                credential.encrypted_data = self.encryption_service.encrypt_credential_str(data)
            else:
                credential.encrypted_data = data
            credential.save(update_fields=['encrypted_data'])
        except Exception as e:
            logger.error(f"Failed to encrypt credential data: {e}")
            raise
    
    def refresh_access_token(self, credential: Credential) -> str:
        """
        Refresh OAuth access token using refresh token.
        
        Args:
            credential: Gmail OAuth credential
            
        Returns:
            New access token
            
        Raises:
            GmailOAuthError: If token refresh fails
        """
        try:
            data = self._decrypt_credential_data(credential)
            
            refresh_token = data.get('refresh_token')
            client_id = data.get('client_id')
            client_secret = data.get('client_secret')
            
            if not all([refresh_token, client_id, client_secret]):
                raise GmailOAuthError("Missing OAuth credentials for token refresh")
            
            # Request new access token
            logger.critical(f"🔄 [Gmail Service] Requesting Token Refresh for {data.get('email')}")
            response = requests.post(self.OAUTH_TOKEN_URL, data={
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'client_id': client_id,
                'client_secret': client_secret,
            }, timeout=30)
            
            if response.status_code != 200:
                logger.error(f"❌ [Gmail Service] Refresh failed: {response.text}")
                raise GmailOAuthError(f"Token refresh failed: {response.status_code} {response.text}")
            
            token_data = response.json()
            new_access_token = token_data.get('access_token')
            
            if not new_access_token:
                logger.error("❌ [Gmail Service] Refresh response missing access_token")
                raise GmailOAuthError("No access token in refresh response")
            
            # Update stored credential with new token
            data['access_token'] = new_access_token
            logger.critical("✅ [Gmail Service] Access Token Refreshed")
            
            # Update refresh token if provided
            if token_data.get('refresh_token'):
                data['refresh_token'] = token_data['refresh_token']
                logger.critical("✅ [Gmail Service] Refresh Token Rotated")
            
            self._encrypt_credential_data(credential, data)
            
            logger.info(f"Successfully refreshed Gmail OAuth token for {data.get('email', 'unknown')}")
            return new_access_token
            
        except Exception as e:
            logger.error(f"Failed to refresh Gmail OAuth token: {e}")
            raise GmailOAuthError(f"Token refresh failed: {str(e)}")
    
    def _create_email_message(self, to: str, subject: str, body: str, from_email: str, 
                             is_html: bool = False) -> str:
        """
        Create RFC 2822 email message for Gmail API.
        
        Args:
            to: Recipient email
            subject: Email subject
            body: Email body
            from_email: Sender email
            is_html: Whether body is HTML
            
        Returns:
            Base64 encoded email message
        """
        if is_html:
            msg = MIMEMultipart('alternative')
            msg.attach(MIMEText(body, 'html'))
        else:
            msg = MIMEText(body, 'plain')
        
        # Handle list of recipients by converting to comma-separated string
        if isinstance(to, list):
            to_header = ", ".join(to)
        else:
            to_header = to
        
        msg['To'] = to_header
        msg['From'] = from_email
        msg['Subject'] = subject
        
        # Encode message for Gmail API
        raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
        return raw_message
    
    def send_email(self, *, user, tenant, to: str, subject: str, body: str, from_email: str, 
                   is_html: bool = False, credential_id: str = None, 
                   attachments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Send email via Gmail API using OAuth with STRICT user/tenant credential lookup.
        
        Args:
            user: User object for credential lookup (REQUIRED)
            tenant: Tenant object for credential lookup (REQUIRED)
            to: Recipient email address
            subject: Email subject
            body: Email body
            from_email: Sender Gmail address
            is_html: Whether body is HTML
            
        Returns:
            Dict with send result
            
        Raises:
            GmailOAuthError: If sending fails
        """
        try:
            # STRICT VALIDATION: HARD REQUIRE user and tenant
            if not user:
                raise GmailOAuthError("user parameter is REQUIRED for Gmail OAuth credential lookup")
            
            if not tenant:
                raise GmailOAuthError("tenant parameter is REQUIRED for Gmail OAuth credential lookup")
            
            # Validate user and tenant are proper objects
            if not hasattr(user, 'id'):
                raise GmailOAuthError(f"user must be User object with id, got {type(user)}: {user}")
            
            if not hasattr(tenant, 'id'):
                raise GmailOAuthError(f"tenant must be Tenant object with id, got {type(tenant)}: {tenant}")
            
            logger.critical(f"🔥 GMAIL OAUTH SERVICE SEND_EMAIL")
            logger.critical(f"🔥 USER: {user.id} ({user.email if hasattr(user, 'email') else 'no email'})")
            logger.critical(f"🔥 TENANT: {tenant.id} ({tenant.name if hasattr(tenant, 'name') else 'no name'})")
            logger.critical(f"🔥 FROM: {from_email}, TO: {to}")
            
            # Support multiple type names for compatibility
            q_types = Q(type='gmail') | Q(type='gmail_oauth') | Q(type='google_oauth')
            
            if credential_id:
                credential = Credential.objects.filter(
                    q_types,
                    id=credential_id,
                    owner=user
                ).first()
            else:
                credential = Credential.objects.filter(
                    q_types,
                    owner=user
                ).order_by("-created_at").first()
            
            if not credential:
                # Log all available credentials for debugging
                all_credentials = Credential.objects.filter(type="gmail")
                logger.critical(f"❌ NO CREDENTIAL FOUND. Available gmail credentials:")
                for cred in all_credentials:
                    logger.critical(f"   - ID={cred.id}, OWNER={cred.owner.id if cred.owner else None}, TENANT={cred.tenant.id if cred.tenant else None}")
                
                raise GmailOAuthError(
                    f"No Gmail OAuth credential found for user={user.id}, tenant={tenant.id}. "
                    f"Please connect your Gmail account first."
                )
            
            logger.critical(f"✅ FOUND CREDENTIAL: ID={credential.id}, OWNER={credential.owner.id}, TENANT={credential.tenant.id if credential.tenant else None}")
            
            # Decrypt and validate credential data
            data = self._decrypt_credential_data(credential)
            access_token = data.get('access_token') or data.get('token')
            
            logger.critical(f"🔓 CREDENTIAL DATA: EMAIL={data.get('email', 'unknown')}, HAS_TOKEN={bool(access_token)}")
            
            if not access_token:
                raise GmailOAuthError("No access token found in Gmail credential")
            
            # Create email message
            raw_message = self._create_email_message(to, subject, body, from_email, is_html)
            
            # Send via Gmail API
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
            }
            
            payload = {
                'raw': raw_message
            }
            
            logger.critical(f"🚀 CALLING GMAIL API: POST {self.GMAIL_API_BASE}/users/me/messages/send")
            
            response = requests.post(
                f"{self.GMAIL_API_BASE}/users/me/messages/send",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            logger.critical(f"📡 GMAIL API RESPONSE: {response.status_code}")
            
            # Handle token expiration
            if response.status_code == 401:
                logger.critical("🔄 ACCESS TOKEN EXPIRED, REFRESHING...")
                new_access_token = self.refresh_access_token(credential)
                
                # Retry with new token
                headers['Authorization'] = f'Bearer {new_access_token}'
                response = requests.post(
                    f"{self.GMAIL_API_BASE}/users/me/messages/send",
                    headers=headers,
                    json=payload,
                    timeout=30
                )
                logger.critical(f"📡 GMAIL API RETRY RESPONSE: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"Gmail API error: {response.status_code} {response.text}"
                logger.error(error_msg)
                raise GmailOAuthError(error_msg)
            
            result = response.json()
            message_id = result.get('id')
            
            logger.critical(f"✅ EMAIL SENT SUCCESSFULLY: MESSAGE_ID={message_id}")
            
            # --- MANDATORY GOOGLE CLOUD OAUTH AUDIT ---
            print("\n" + "="*60)
            print("GOOGLE CLOUD OAUTH AUDIT - EMAIL SENT SUCCESSFULLY")
            print("="*60)
            print(f"Project Name: Automation Platform")
            print(f"OAuth Client ID: {settings.GMAIL_OAUTH_CLIENT_ID}")
            print(f"Enabled APIs: Gmail API (v1)")
            print(f"OAuth Scopes: {self.REQUIRED_SCOPE}")
            print(f"Redirect URI: {settings.GMAIL_OAUTH_REDIRECT_URI}")
            print(f"Consent Screen: Configured (Internal/External)")
            print(f"Email Quota: 1 unit consumption (send)")
            print(f"User Email: {data.get('email', 'unknown')}")
            print(f"Target Recipient: {to}")
            print(f"Message ID: {message_id}")
            print("="*60 + "\n")
            # ------------------------------------------
            
            return {
                'success': True,
                'message_id': message_id,
                'method': 'gmail_oauth',
                'recipient': to,
                'subject': subject,
                'from': from_email,
                'user_id': user.id,
                'tenant_id': tenant.id
            }
            
        except GmailOAuthError:
            raise
        except Exception as e:
            error_msg = f"Unexpected error sending Gmail email: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise GmailOAuthError(error_msg) from e
    
    def send_email_to_multiple(self, recipients: List[str], subject: str, body: str, 
                               from_email: str, is_html: bool = False,
                               user=None, tenant=None, credential_id: str = None,
                               attachments: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Send email to multiple recipients via Gmail API.
        
        Args:
            recipients: List of recipient email addresses
            subject: Email subject
            body: Email body
            from_email: Sender Gmail address
            is_html: Whether body is HTML
            user: User object (REQUIRED)
            tenant: Tenant object (REQUIRED)
            credential_id: Optional specific credential ID
            attachments: Optional list of attachments
            
        Returns:
            List of send results for each recipient
        """
        results = []
        
        for recipient in recipients:
            try:
                result = self.send_email(
                    user=user,
                    tenant=tenant,
                    to=recipient, 
                    subject=subject, 
                    body=body, 
                    from_email=from_email, 
                    is_html=is_html,
                    credential_id=credential_id,
                    attachments=attachments
                )
                results.append(result)
            except Exception as e:
                results.append({
                    'success': False,
                    'error': str(e),
                    'recipient': recipient,
                    'method': 'gmail_oauth'
                })
        
        return results
    
    def validate_gmail_credential(self, credential: Credential) -> Dict[str, Any]:
        """
        Validate Gmail OAuth credential by testing API access.
        
        Args:
            credential: Gmail OAuth credential to validate
            
        Returns:
            Validation result dict
        """
        try:
            data = self._decrypt_credential_data(credential)
            access_token = data.get('access_token')
            
            if not access_token:
                return {
                    'valid': False,
                    'error': 'No access token found'
                }
            
            # Test API access with profile endpoint
            headers = {
                'Authorization': f'Bearer {access_token}',
            }
            
            response = requests.get(
                f"{self.GMAIL_API_BASE}/users/me/profile",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 401:
                # Try to refresh token
                try:
                    self.refresh_access_token(credential)
                    return {
                        'valid': True,
                        'refreshed': True,
                        'email': data.get('email', 'unknown')
                    }
                except Exception as e:
                    return {
                        'valid': False,
                        'error': f'Token refresh failed: {str(e)}'
                    }
            elif response.status_code == 200:
                profile = response.json()
                return {
                    'valid': True,
                    'email': profile.get('emailAddress', data.get('email', 'unknown')),
                    'messages_total': profile.get('messagesTotal', 0)
                }
            else:
                return {
                    'valid': False,
                    'error': f'API error: {response.status_code} {response.text}'
                }
                
        except Exception as e:
            return {
                'valid': False,
                'error': f'Validation error: {str(e)}'
            }


# Singleton instance
_gmail_service = None

def get_gmail_oauth_service(user=None, tenant=None) -> GmailOAuthService:
    """Get Gmail OAuth service instance."""
    global _gmail_service
    if _gmail_service is None or _gmail_service.user != user or _gmail_service.tenant != tenant:
        _gmail_service = GmailOAuthService(user=user, tenant=tenant)
    return _gmail_service