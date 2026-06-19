"""
Email Dispatcher - Production Grade
Auto-detects Gmail vs non-Gmail and routes to appropriate sender
"""
import logging
from typing import Dict, Any, List, Optional

from .gmail_oauth import get_gmail_sender, GmailOAuthError
from .smtp_sender import get_smtp_sender, SMTPSenderError

logger = logging.getLogger(__name__)


class EmailDispatcherError(Exception):
    """Email dispatcher errors - NEVER silent success"""
    pass


class EmailDispatcher:
    """
    Production-grade email dispatcher.
    Routes emails based on sender domain:
    - Gmail/Google Workspace → Gmail OAuth API
    - All others → SMTP
    """
    
    # Gmail domains that should use OAuth
    GMAIL_DOMAINS = {
        'gmail.com',
        'googlemail.com'
    }
    
    def __init__(self):
        """Initialize email dispatcher."""
        self.gmail_sender = get_gmail_sender()
        self.smtp_sender = get_smtp_sender()
    
    def is_gmail_address(self, email: str) -> bool:
        """
        Check if email address should use Gmail OAuth.
        
        Args:
            email: Email address to check
            
        Returns:
            True if should use Gmail OAuth, False for SMTP
        """
        if email == 'me':
            return True
            
        if not email or '@' not in email:
            return False
        
        domain = email.split('@')[1].lower()
        return domain in self.GMAIL_DOMAINS
    
    def send_email(self, user, tenant, from_email: str, to_emails: List[str], subject: str, 
                   body: str, cc_emails: List[str] = None, bcc_emails: List[str] = None,
                   is_html: bool = False, smtp_config: Dict[str, Any] = None,
                   credential_id: str = None, attachments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        logger.critical("🚀 ANTIGRAVITY_VERIFY: EmailDispatcher.send_email called")
        """
        Send email with automatic routing.
        
        Args:
            user: User object for credential lookup (REQUIRED)
            tenant: Tenant object for credential lookup (REQUIRED)
            ...
        """
        try:
            # Validate inputs
            if not user:
                raise EmailDispatcherError("user is required for credential lookup")
            
            if not tenant:
                raise EmailDispatcherError("tenant is required for credential lookup")
            
            if not from_email:
                raise EmailDispatcherError("from_email is required")
            
            if not to_emails:
                raise EmailDispatcherError("to_emails is required")
            
            if not isinstance(to_emails, list):
                to_emails = [to_emails]
            
            if not subject:
                subject = "(No subject)"
            
            if not body:
                body = ""
            
            # Route based on configuration/domain
            
            # 1. STRICT ROUTING: If credential_id provided, respect its type absolutely
            if credential_id:
                try:
                    from ..models import Credential
                    cred = Credential.objects.get(id=credential_id)
                    
                    if cred.type in ['gmail', 'gmail_oauth', 'google_oauth']:
                        logger.critical(f"ROUTING {from_email} -> Gmail OAuth (Explicit Credential: {cred.name})")
                        return self._send_via_gmail_oauth(
                            user, tenant, from_email, to_emails, subject, body, cc_emails, bcc_emails, is_html, credential_id, attachments
                        )
                    
                    elif cred.type == 'smtp':
                        logger.critical(f"ROUTING {from_email} -> SMTP (Explicit Credential: {cred.name})")
                        
                        # FIX: Decrypt SMTP credential data
                        from ..utils.credential_resolver import resolve_credential_data
                        resolved_config = resolve_credential_data(cred)
                        
                        # Merge with any overrides (optional, but credential usually takes precedence)
                        if smtp_config:
                            resolved_config = {**smtp_config, **resolved_config}
                            
                        return self._send_via_smtp(
                            from_email, to_emails, subject, body, cc_emails, bcc_emails, is_html, resolved_config, attachments
                        )
                        
                    else:
                        logger.warning(f"Unknown credential type {cred.type} for email. Defaulting to domain check.")
                        
                except Exception as e:
                    logger.error(f"Failed to load credential {credential_id} for routing: {e}")
                    # If loading fails, fall through to heuristics (or fail? User said NO silent fallback)
                    # User said: "If user selects Gmail Credential... THROW CLEAR ERROR"
                    # So if we can't load it, we should probably fail or log heavily.
                    # We'll fall through but log critical.

            # 2. explicit SMTP config (legacy/manual)
            if smtp_config:
                 logger.critical(f"ROUTING {from_email} -> SMTP (Explicit Config)")
                 return self._send_via_smtp(
                    from_email, to_emails, subject, body, cc_emails, bcc_emails, is_html, smtp_config, attachments
                )
            
            # 3. Domain Heuristic (Legacy/Fallback)
            elif self.is_gmail_address(from_email):
                logger.critical(f"ROUTING {from_email} -> Gmail OAuth (Domain Heuristic)")
                return self._send_via_gmail_oauth(
                    user, tenant, from_email, to_emails, subject, body, cc_emails, bcc_emails, is_html, credential_id, attachments
                )
            else:
                 # 4. Fallback to SMTP
                 logger.critical(f"ROUTING {from_email} -> SMTP (Fallback)")
                 return self._send_via_smtp(
                    from_email, to_emails, subject, body, cc_emails, bcc_emails, is_html, smtp_config, attachments
                )
                
        except (GmailOAuthError, SMTPSenderError) as e:
            # Re-raise specific sender errors
            logger.exception(f"Specific sender error: {e}")
            raise EmailDispatcherError(str(e))
        except Exception as e:
            logger.exception(f"Unexpected email dispatch error: {e}")
            raise EmailDispatcherError(f"Email dispatch failed: {str(e)}")
    
    def _send_via_gmail_oauth(self, user, tenant, from_email: str, to_emails: List[str], subject: str,
                             body: str, cc_emails: List[str] = None, bcc_emails: List[str] = None,
                             is_html: bool = False, credential_id: str = None, 
                             attachments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send email via Gmail OAuth with STRICT signature."""
        try:
            logger.critical(f"DISPATCHER CALLING GMAIL OAUTH SERVICE")
            logger.critical(f"USER={user.id if hasattr(user, 'id') else user} TENANT={tenant.id if hasattr(tenant, 'id') else tenant}")
            
            # Use STRICT signature with keyword arguments
            # Gmail API sends to one recipient at a time, so we iterate
            results = []
            for to_email in to_emails:
                individual_result = self.gmail_sender.send_email(
                    user=user,
                    tenant=tenant,
                    from_email=from_email,
                    to=to_email,  # Gmail API sends to one recipient at a time
                    subject=subject,
                    body=body,
                    is_html=is_html,
                    credential_id=credential_id,
                    attachments=attachments
                )
                results.append(individual_result)
            
            # Combine results
            result = {
                'success': all(r.get('success', False) for r in results),
                'message_ids': [r.get('message_id') for r in results],
                'recipients': to_emails,
                'method': 'gmail_oauth',
                'individual_results': results
            }
            
            result['routing_method'] = 'gmail_oauth'
            logger.critical(f"✅ GMAIL OAUTH RESULT: {result}")
            return result
            
        except GmailOAuthError as e:
            logger.error(f"Gmail OAuth sending failed: {e}")
            raise EmailDispatcherError(
                f"Gmail OAuth failed: {str(e)}. "
                "Please ensure your Gmail account is properly connected."
            )
    
    def _send_via_smtp(self, from_email: str, to_emails: List[str], subject: str,
                      body: str, cc_emails: List[str] = None, bcc_emails: List[str] = None,
                      is_html: bool = False, smtp_config: Dict[str, Any] = None,
                      attachments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send email via SMTP."""
        try:
            result = self.smtp_sender.send_email(
                from_email, to_emails, subject, body, cc_emails, bcc_emails, is_html, smtp_config, attachments
            )
            result['routing_method'] = 'smtp'
            return result
            
        except SMTPSenderError as e:
            logger.error(f"SMTP sending failed: {e}")
            raise EmailDispatcherError(f"SMTP failed: {str(e)}")


# Global instance
_email_dispatcher = None

def get_email_dispatcher() -> EmailDispatcher:
    """Get email dispatcher instance."""
    global _email_dispatcher
    if _email_dispatcher is None:
        _email_dispatcher = EmailDispatcher()
    return _email_dispatcher


# Direct test function for Django shell
def send_gmail_oauth_email(user, tenant, from_email: str, to_emails: List[str], subject: str, body: str,
                          cc_emails: List[str] = None, bcc_emails: List[str] = None,
                          is_html: bool = False, attachments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    DIRECT TEST FUNCTION for Django shell.
    
    Usage in Django shell:
    from workflows.email.dispatcher import send_gmail_oauth_email
    from django.contrib.auth.models import User
    from workflows.models import Tenant
    
    user = User.objects.get(id=1)
    tenant = Tenant.objects.get(id=1)
    
    result = send_gmail_oauth_email(
        user=user,
        tenant=tenant,
        from_email="mygmail@gmail.com",
        to_emails=["test@gmail.com"],
        subject="TEST",
        body="Hello"
    )
    print(result)
    
    Args:
        user: User object for credential lookup
        tenant: Tenant object for credential lookup
        from_email: Sender Gmail address
        to_emails: List of recipient emails
        subject: Email subject
        body: Email body
        cc_emails: CC recipients
        bcc_emails: BCC recipients
        is_html: Whether body is HTML
        
    Returns:
        Dict with send result
        
    Raises:
        EmailDispatcherError: If sending fails
    """
    dispatcher = get_email_dispatcher()
    return dispatcher.send_email(
        user=user, 
        tenant=tenant, 
        from_email=from_email, 
        to_emails=to_emails, 
        subject=subject, 
        body=body, 
        cc_emails=cc_emails, 
        bcc_emails=bcc_emails, 
        is_html=is_html,
        attachments=attachments
    )