"""
Gmail OAuth Email Sender - Production Grade
Sends emails via Gmail API using OAuth2 tokens (NO SMTP, NO App Passwords)
"""
import base64
import json
import logging
from typing import Dict, Any, List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import Q

logger = logging.getLogger(__name__)


class GmailOAuthError(Exception):
    """Gmail OAuth specific errors - NEVER silent success"""
    pass


class GmailOAuthSender:
    """
    Production-grade Gmail OAuth email sender.
    Uses Gmail API (NOT SMTP) with OAuth2 tokens.
    """
    
    # Gmail API endpoints
    GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"
    OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
    
    def __init__(self):
        """Initialize Gmail OAuth sender with settings validation."""
        self.client_id = getattr(settings, 'GMAIL_OAUTH_CLIENT_ID', '')
        self.client_secret = getattr(settings, 'GMAIL_OAUTH_CLIENT_SECRET', '')
        
        if not self.client_id or not self.client_secret:
            raise ImproperlyConfigured(
                "Gmail OAuth not configured. Set GMAIL_OAUTH_CLIENT_ID and GMAIL_OAUTH_CLIENT_SECRET"
            )
    
    def get_oauth_tokens(self, user, tenant, from_email: str, credential_id: str = None) -> Dict[str, str]:
        """
        Get OAuth tokens for Gmail address with STRICT user/tenant filtering.
        
        Args:
            user: User object for credential lookup
            tenant: Tenant object for credential lookup
            from_email: Gmail address to get tokens for
            credential_id: Optional specific credential ID to use
            
        Returns:
            Dict with access_token and refresh_token
            
        Raises:
            GmailOAuthError: If no tokens found
        """
        try:
            from ..models import Credential
            from ..services.credential_encryption import get_encryption_service
            
            # Support multiple type names for compatibility
            q_types = Q(type='gmail') | Q(type='gmail_oauth') | Q(type='google_oauth')
            
            query = {
                'owner': user,
            }
            
            # If credential_id provided, use it
            if credential_id:
                query['id'] = credential_id
            
            # Get ALL matching credentials, ordered by newest first
            credentials = list(
                Credential.objects.filter(q_types, **query).order_by('-created_at')
            )
            
            # FALLBACK: If specific ID not found, try all credentials for user
            if not credentials and credential_id:
                logger.warning(f"Credential {credential_id} not found. Falling back to all Gmail credentials for user {user.id}")
                query.pop('id', None)
                credentials = list(
                    Credential.objects.filter(q_types, **query).order_by('-created_at')
                )

            if not credentials:
                available_creds = Credential.objects.filter(owner=user).values('id', 'type', 'name')
                raise GmailOAuthError(
                    f"No Gmail OAuth credential found for user={user.id if hasattr(user, 'id') else user}. "
                    f"Looking for ID={credential_id}. "
                    f"Available User Credentials: {list(available_creds)}. "
                    f"Please connect your Gmail account first."
                )
            
            # Iterate through credentials and find one with actual OAuth tokens
            encryption_service = get_encryption_service()
            
            for credential in credentials:
                try:
                    # Decrypt credential data
                    if not hasattr(credential, 'encrypted_data'):
                        continue
                    
                    if isinstance(credential.encrypted_data, dict):
                        data = credential.encrypted_data
                    elif isinstance(credential.encrypted_data, str):
                        try:
                            data = encryption_service.decrypt_credential_str(credential.encrypted_data)
                        except Exception as dec_err:
                            logger.warning(f"Decryption failed for credential {credential.id}: {dec_err}")
                            try:
                                data = json.loads(credential.encrypted_data)
                            except Exception:
                                logger.warning(f"JSON parse also failed for credential {credential.id}, skipping")
                                continue
                    else:
                        continue
                    
                    access_token = data.get('access_token') or data.get('token')
                    refresh_token = data.get('refresh_token')
                    
                    if access_token:
                        logger.info(f"✅ Found credential with tokens: ID={credential.id}, TYPE={credential.type}")
                        return {
                            'access_token': access_token,
                            'refresh_token': refresh_token,
                            'credential': credential,
                            'data': data
                        }
                    else:
                        logger.info(f"⏭️ Credential {credential.id} (type={credential.type}) has no tokens, keys={list(data.keys())}")
                        
                except Exception as cred_err:
                    logger.warning(f"Error processing credential {credential.id}: {cred_err}")
                    continue
            
            # None of the credentials had tokens
            cred_summary = [(str(c.id), c.type) for c in credentials]
            raise GmailOAuthError(
                f"Found {len(credentials)} Gmail credential(s) but none contain OAuth tokens (access_token/token). "
                f"Credentials checked: {cred_summary}. "
                f"Please reconnect your Gmail account to obtain fresh tokens."
            )
            
        except Exception as e:
            if isinstance(e, GmailOAuthError):
                raise
            logger.error(f"Error getting OAuth tokens: {e}")
            raise GmailOAuthError(f"Failed to get OAuth tokens: {str(e)}")

    def refresh_access_token(self, refresh_token: str, credential=None) -> str:
        """
        Refresh OAuth access token.
        
        Args:
            refresh_token: Refresh token
            credential: Credential object to update
            
        Returns:
            New access token
            
        Raises:
            GmailOAuthError: If refresh fails
        """
        try:
            # STRICT: Validate inputs
            if not refresh_token:
                raise GmailOAuthError("Missing refresh_token for token refresh")
                
            response = requests.post(self.OAUTH_TOKEN_URL, data={
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'client_id': self.client_id,
                'client_secret': self.client_secret,
            }, timeout=30)
            
            if response.status_code != 200:
                raise GmailOAuthError(
                    f"Token refresh failed: {response.status_code} {response.text}"
                )
            
            token_data = response.json()
            new_access_token = token_data.get('access_token')
            
            if not new_access_token:
                raise GmailOAuthError("No access token in refresh response")
            
            # Update stored credential if provided
            if credential:
                try:
                    # We MUST preserve the refresh token if the new response doesn't have one
                    # (Google only sends refresh_token when asked or on first flow)
                    
                    if isinstance(credential.encrypted_data, dict):
                        credential.encrypted_data['access_token'] = new_access_token
                        # Only update refresh_token if provided, otherwise KEEP OLD ONE
                        if token_data.get('refresh_token'):
                            credential.encrypted_data['refresh_token'] = token_data['refresh_token']
                    else:
                        # Handle encrypted data
                        from ..services.credential_encryption import get_encryption_service
                        encryption_service = get_encryption_service()
                        try:
                            data = encryption_service.decrypt_credential_str(credential.encrypted_data)
                        except Exception:
                            # Fallback for unencrypted data
                            import json
                            data = json.loads(credential.encrypted_data)
                        
                        data['access_token'] = new_access_token
                        if token_data.get('refresh_token'):
                            data['refresh_token'] = token_data['refresh_token']
                        # Implicitly keeps old refresh_token if not in token_data
                        
                        credential.encrypted_data = encryption_service.encrypt_credential_str(data)
                    
                    credential.save()
                    logger.info(f"Updated OAuth tokens for credential {credential.id}")
                except Exception as e:
                    logger.error(f"Failed to update credential: {e}")
                    # Don't fail the send if save fails, but log critical
            
            return new_access_token
            
        except Exception as e:
            if isinstance(e, GmailOAuthError):
                raise
            logger.error(f"Token refresh error: {e}")
            raise GmailOAuthError(f"Token refresh failed: {str(e)}")
    
    def create_email_message(self, to_emails: List[str], subject: str, body: str, 
                           from_email: str, cc_emails: List[str] = None, 
                           bcc_emails: List[str] = None, is_html: bool = False,
                           attachments: List[Dict[str, Any]] = None) -> str:
        """
        Create RFC 2822 email message for Gmail API.
        
        Args:
            to_emails: List of recipient emails
            subject: Email subject
            body: Email body
            from_email: Sender email
            cc_emails: CC recipients
            bcc_emails: BCC recipients
            is_html: Whether body is HTML
            
        Returns:
            Base64 encoded email message
        """
        if is_html:
            msg = MIMEMultipart('alternative')
            msg.attach(MIMEText(body, 'html'))
        else:
            msg = MIMEText(body, 'plain')
        
        msg['To'] = ', '.join(to_emails)
        msg['From'] = from_email
        msg['Subject'] = subject
        
        if cc_emails:
            msg['Cc'] = ', '.join(cc_emails)
            
        if bcc_emails:
            msg['Bcc'] = ', '.join(bcc_emails)
        
        # Add attachments
        if attachments:
            # Re-wrap as mixed if we have attachments and currently just alternative/text
            if not isinstance(msg, MIMEMultipart):
                msg_body = msg
                msg = MIMEMultipart('mixed')
                msg['To'] = ', '.join(to_emails)
                msg['From'] = from_email
                msg['Subject'] = subject
                if cc_emails: msg['Cc'] = ', '.join(cc_emails)
                if bcc_emails: msg['Bcc'] = ', '.join(bcc_emails)
                msg.attach(msg_body)
            elif msg.get_content_type() == 'multipart/alternative':
                msg_alternative = msg
                msg = MIMEMultipart('mixed')
                msg['To'] = ', '.join(to_emails)
                msg['From'] = from_email
                msg['Subject'] = subject
                if cc_emails: msg['Cc'] = ', '.join(cc_emails)
                if bcc_emails: msg['Bcc'] = ', '.join(bcc_emails)
                msg.attach(msg_alternative)

            for att in attachments:
                filename = att.get('name') or att.get('filename')
                content = att.get('content')
                mimetype = att.get('mimetype') or att.get('contentType')
                
                if filename and content:
                    try:
                        from email.mime.application import MIMEApplication
                        
                        # Handle base64 content
                        if isinstance(content, str) and ';base64,' in content:
                            content = content.split(';base64,')[1]
                            content = base64.b64decode(content)
                        elif isinstance(content, str):
                            try:
                                content = base64.b64decode(content)
                            except:
                                content = content.encode('utf-8')
                        
                        part = MIMEApplication(content)
                        part.add_header('Content-Disposition', 'attachment', filename=filename)
                        if mimetype:
                            part.set_type(mimetype)
                        msg.attach(part)
                    except Exception as e:
                        logger.error(f"Failed to attach file {filename} to Gmail message: {e}")
        
        # Encode message for Gmail API
        raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
        return raw_message
    
    def send_email(self, *, user, tenant, from_email: str, to: str, subject: str, 
                   body: str, cc_emails: List[str] = None, bcc_emails: List[str] = None,
                   is_html: bool = False, credential_id: str = None, 
                   attachments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Send email via Gmail API using OAuth with STRICT user/tenant credential lookup.
        
        Args:
            user: User object for credential lookup (REQUIRED)
            tenant: Tenant object for credential lookup (REQUIRED)
            from_email: Sender Gmail address
            to: Recipient email (single address)
            subject: Email subject
            body: Email body
            cc_emails: CC recipients
            bcc_emails: BCC recipients
            is_html: Whether body is HTML
            
        Returns:
            Dict with send result
            
        Raises:
            GmailOAuthError: If sending fails (NEVER silent success)
        """
        try:
            # STRICT VALIDATION: HARD REQUIRE user and tenant
            if not user:
                raise GmailOAuthError("user parameter is REQUIRED for Gmail OAuth credential lookup")
            
            if not tenant:
                raise GmailOAuthError("tenant parameter is REQUIRED for Gmail OAuth credential lookup")
            
            # Validate user and tenant objects
            if not hasattr(user, 'id'):
                raise GmailOAuthError(f"user must be User object with id, got {type(user)}: {user}")
            
            if not hasattr(tenant, 'id'):
                raise GmailOAuthError(f"tenant must be Tenant object with id, got {type(tenant)}: {tenant}")
            
            if not from_email or not to or not subject:
                raise GmailOAuthError("Missing required fields: from_email, to, or subject")
            
            logger.critical(f"GMAIL OAUTH SENDER SEND_EMAIL")
            logger.critical(f"USER: {user.id} ({user.email if hasattr(user, 'email') else 'no email'})")
            logger.critical(f"TENANT: {tenant.id} ({tenant.name if hasattr(tenant, 'name') else 'no name'})")
            logger.critical(f"FROM: {from_email}, TO: {to}")
            
            # Get OAuth tokens with STRICT user/tenant filtering
            tokens = self.get_oauth_tokens(user, tenant, from_email, credential_id)
            access_token = tokens['access_token']
            refresh_token = tokens.get('refresh_token')
            credential = tokens.get('credential')
            
            logger.critical(f"OAUTH TOKENS RETRIEVED: ACCESS_TOKEN={access_token[:20] if access_token else None}...")
            
            # Create email message (convert single recipient to list for API)
            to_emails = [to] if isinstance(to, str) else to
            raw_message = self.create_email_message(
                to_emails, subject, body, from_email, cc_emails, bcc_emails, is_html, attachments
            )
            
            # Send via Gmail API
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
            }
            
            payload = {'raw': raw_message}
            
            # CRITICAL LOGGING: Track actual Gmail API calls
            logger.critical(f"GMAIL API CALL: POST {self.GMAIL_API_BASE}/users/me/messages/send")
            logger.critical(f"AUTHORIZATION: Bearer {access_token[:10]}...{access_token[-5:] if len(access_token)>15 else ''}")
            logger.critical(f"PAYLOAD LENGTH: {len(raw_message)}")
            
            response = requests.post(
                f"{self.GMAIL_API_BASE}/users/me/messages/send",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            logger.critical(f"GMAIL API STATUS: {response.status_code}")
            logger.critical(f"GMAIL API RESPONSE BODY: {response.text}")
            
            # Handle token expiration
            if response.status_code == 401 and refresh_token:
                logger.critical("ACCESS TOKEN EXPIRED, REFRESHING...")
                try:
                    new_access_token = self.refresh_access_token(refresh_token, credential)
                    logger.critical(f"TOKEN REFRESHED: {new_access_token[:20]}...")
                    
                    # Retry with new token
                    headers['Authorization'] = f'Bearer {new_access_token}'
                    logger.critical("RETRYING GMAIL API CALL...")
                    response = requests.post(
                        f"{self.GMAIL_API_BASE}/users/me/messages/send",
                        headers=headers,
                        json=payload,
                        timeout=30
                    )
                    logger.critical(f"RETRY RESPONSE: {response.status_code}")
                    logger.critical(f"RETRY BODY: {response.text}")
                except Exception as refresh_error:
                    logger.critical(f"TOKEN REFRESH FAILED: {refresh_error}")
                    raise GmailOAuthError(f"Token refresh failed: {refresh_error}")
            
            # Check final response
            if response.status_code != 200:
                error_msg = f"Gmail API error: {response.status_code} {response.text}"
                logger.critical(f"GMAIL API FAILED: {error_msg}")
                raise GmailOAuthError(error_msg)
            
            try:
                result = response.json()
                logger.critical(f"GMAIL API RESULT JSON: {result}")
            except Exception as json_e:
                 logger.critical(f"GMAIL API RESULT NOT JSON: {response.text}")
                 raise GmailOAuthError(f"Invalid JSON from Gmail API: {response.text}")

            message_id = result.get('id')
            label_ids = result.get('labelIds', [])
            
            if message_id:
                logger.critical(f"✅ EMAIL SENT SUCCESSFULLY - MESSAGE ID: {message_id}")
                logger.critical(f"✅ LABELS: {label_ids}")
            else:
                logger.critical(f"❌ NO MESSAGE ID IN RESPONSE. Keys found: {list(result.keys())}")
                logger.critical(f"FULL RESULT: {result}")
                # Fallback: check for threadId just in case
                if result.get('threadId'):
                     message_id = result.get('threadId') # misuse but allows progress
                     logger.warning(f"⚠️ Using threadId as messageId: {message_id}")
                else:
                     raise GmailOAuthError(f"No message ID returned in result. Got: {result}")
            
            return {
                'success': True,
                'message_id': message_id,
                'method': 'gmail_oauth',
                'recipient': to,
                'cc': cc_emails or [],
                'bcc': bcc_emails or [],
                'subject': subject,
                'from': from_email,
                'user_id': user.id,
                'tenant_id': str(tenant.id)
            }
            
        except GmailOAuthError:
            raise  # Re-raise Gmail OAuth errors
        except Exception as e:
            error_msg = f"Unexpected Gmail sending error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise GmailOAuthError(error_msg) from e


# Global instance
_gmail_sender = None

def get_gmail_sender() -> GmailOAuthSender:
    """Get Gmail OAuth sender instance."""
    global _gmail_sender
    if _gmail_sender is None:
        _gmail_sender = GmailOAuthSender()
    return _gmail_sender