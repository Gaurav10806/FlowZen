"""
Email Routing Service - Routes emails between Gmail OAuth and SMTP based on sender domain.
Implements the single Email node with automatic backend routing.
"""
import logging
from typing import Dict, Any, List, Tuple
from django.conf import settings

from .gmail_oauth_service import GmailOAuthService, GmailOAuthError
from ..email.smtp_sender import SMTPSender

logger = logging.getLogger(__name__)


class EmailRoutingError(Exception):
    """Email routing specific errors."""
    pass


class EmailRoutingService:
    """
    Service that routes email sending based on sender domain:
    - Gmail addresses (@gmail.com) -> Gmail OAuth API
    - All other addresses -> SMTP
    """
    
    def __init__(self, tenant=None):
        self.tenant = tenant
        self.gmail_service = GmailOAuthService()
        self.smtp_sender = SMTPSender()
    
    def is_gmail_address(self, email: str) -> bool:
        """
        Check if email address is a Gmail address.
        
        Args:
            email: Email address to check
            
        Returns:
            True if Gmail address, False otherwise
        """
        if not email or '@' not in email:
            return False
        
        domain = email.split('@')[1].lower()
        return domain == 'gmail.com'
    
    def send_email(self, to: str, subject: str, body: str, from_email: str, 
                   is_html: bool = False, smtp_config: Dict[str, Any] = None, 
                   user=None, tenant=None, attachments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Route and send email based on sender domain with STRICT context validation.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body
            from_email: Sender email address
            is_html: Whether body is HTML
            smtp_config: SMTP configuration for non-Gmail addresses
            user: User object (REQUIRED for Gmail addresses)
            tenant: Tenant object (REQUIRED for Gmail addresses)
            
        Returns:
            Dict with send result
            
        Raises:
            EmailRoutingError: If sending fails
        """
        try:
            logger.critical(f"🔥 EMAIL ROUTING SERVICE: FROM={from_email}, TO={to}")
            logger.critical(f"🔥 IS_GMAIL: {self.is_gmail_address(from_email)}")
            logger.critical(f"🔥 USER: {user.id if user else None}")
            logger.critical(f"🔥 TENANT: {tenant.id if tenant else None}")
            
            # Route based on sender domain
            if self.is_gmail_address(from_email):
                return self._send_via_gmail_oauth(to, subject, body, from_email, is_html, user, tenant, attachments)
            else:
                return self.smtp_sender.send_email(
                    from_email=from_email,
                    to_emails=[to],
                    subject=subject,
                    body=body,
                    is_html=is_html,
                    smtp_config=smtp_config,
                    attachments=attachments
                )
                
        except Exception as e:
            logger.error(f"❌ EMAIL ROUTING FAILED: {e}")
            raise EmailRoutingError(f"Failed to send email: {str(e)}")
    
    def send_email_to_multiple(self, recipients: List[str], subject: str, body: str, 
                              from_email: str, is_html: bool = False, 
                              user=None, tenant=None, smtp_config: Dict[str, Any] = None,
                              attachments: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Send email to multiple recipients with automatic routing.
        
        Args:
            recipients: List of recipient email addresses
            subject: Email subject
            body: Email body
            from_email: Sender email address
            is_html: Whether body is HTML
            user: User object (REQUIRED for Gmail addresses)
            tenant: Tenant object (REQUIRED for Gmail addresses)
            smtp_config: SMTP configuration for non-Gmail addresses
            attachments: List of dictionaries, each with 'filename', 'content', 'mimetype'
            
        Returns:
            List of send results for each recipient
        """
        results = []
        
        # Route based on sender domain
        if self.is_gmail_address(from_email):
            # Use Gmail OAuth for all recipients
            try:
                gmail_results = self.gmail_service.send_email_to_multiple(
                    recipients, subject, body, from_email, is_html,
                    user=user, tenant=tenant, attachments=attachments
                )
                results.extend(gmail_results)
            except Exception as e:
                # If Gmail fails, add error for all recipients
                for recipient in recipients:
                    results.append({
                        'success': False,
                        'error': str(e),
                        'recipient': recipient,
                        'method': 'gmail',
                        'from': from_email
                    })
        else:
            # Use SMTP for all recipients
            try:
                smtp_results = self.smtp_sender.send_email_to_multiple(
                    from_email=from_email,
                    to_emails=recipients,
                    subject=subject,
                    body=body,
                    is_html=is_html,
                    smtp_config=smtp_config,
                    attachments=attachments
                )
                results.extend(smtp_results)
            except Exception as e:
                # If SMTP fails, add error for all recipients
                for recipient in recipients:
                    results.append({
                        'success': False,
                        'error': str(e),
                        'recipient': recipient,
                        'method': 'smtp',
                        'from': from_email
                    })
        
        return results
    
    def _send_via_gmail_oauth(self, to: str, subject: str, body: str, from_email: str, 
                             is_html: bool = False, user=None, tenant=None, 
                             attachments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Send email via Gmail OAuth API with STRICT user/tenant context.
        
        Args:
            to: Recipient email
            subject: Email subject
            body: Email body
            from_email: Gmail sender address
            is_html: Whether body is HTML
            user: User object (REQUIRED for Gmail OAuth)
            tenant: Tenant object (REQUIRED for Gmail OAuth)
            attachments: List of dictionaries, each with 'filename', 'content', 'mimetype'
            
        Returns:
            Send result dict
            
        Raises:
            EmailRoutingError: If Gmail OAuth sending fails
        """
        from django.conf import settings
        
        # CRITICAL: Check if Gmail OAuth is enabled at all
        if not getattr(settings, 'GMAIL_OAUTH_ENABLED', False):
            raise EmailRoutingError(
                "Gmail OAuth is not configured. "
                "Set GMAIL_OAUTH_CLIENT_ID and GMAIL_OAUTH_CLIENT_SECRET environment variables."
            )
        
        # STRICT VALIDATION: HARD REQUIRE user and tenant for Gmail OAuth
        if not user:
            raise EmailRoutingError(
                "User context is REQUIRED for Gmail OAuth. "
                "Cannot send Gmail emails without user authentication."
            )
        
        if not tenant:
            raise EmailRoutingError(
                "Tenant context is REQUIRED for Gmail OAuth. "
                "Cannot send Gmail emails without tenant context."
            )
        
        try:
            # CRITICAL: Pass user and tenant to Gmail service
            result = self.gmail_service.send_email(
                user=user,
                tenant=tenant,
                to=to, 
                subject=subject, 
                body=body, 
                from_email=from_email, 
                is_html=is_html,
                attachments=attachments
            )
            logger.critical(f"✅ EMAIL SENT VIA GMAIL OAUTH: FROM={from_email}, TO={to}, USER={user.id}, TENANT={tenant.id}")
            return result
            
        except GmailOAuthError as e:
            # Gmail OAuth specific error - don't fallback to SMTP for security
            logger.error(f"❌ GMAIL OAUTH FAILED: FROM={from_email}, ERROR={e}")
            raise EmailRoutingError(
                f"Gmail OAuth failed: {str(e)}. "
                "Please ensure your Gmail account is properly connected."
            )
        except Exception as e:
            logger.error(f"❌ UNEXPECTED GMAIL OAUTH ERROR: {e}")
            raise EmailRoutingError(f"Gmail sending failed: {str(e)}")
    

    
    def validate_email_config(self, from_email: str, smtp_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Validate email configuration for the given sender.
        
        Args:
            from_email: Sender email address
            smtp_config: SMTP configuration for non-Gmail addresses
            
        Returns:
            Validation result dict
        """
        try:
            if self.is_gmail_address(from_email):
                # Validate Gmail OAuth
                credential = self.gmail_service.get_gmail_credential(from_email)
                if not credential:
                    return {
                        'valid': False,
                        'method': 'gmail',
                        'error': f'No Gmail OAuth credential found for {from_email}',
                        'suggestion': 'Please connect your Gmail account in the credentials section'
                    }
                
                validation = self.gmail_service.validate_gmail_credential(credential)
                validation['method'] = 'gmail'
                return validation
            else:
                # Validate SMTP configuration
                if smtp_config:
                    # Custom SMTP config provided
                    required_fields = ['host', 'port']
                    missing_fields = [field for field in required_fields if not smtp_config.get(field)]
                    
                    if missing_fields:
                        return {
                            'valid': False,
                            'method': 'custom_smtp',
                            'error': f'Missing SMTP configuration: {", ".join(missing_fields)}'
                        }
                    
                    return {
                        'valid': True,
                        'method': 'custom_smtp',
                        'smtp_host': smtp_config.get('host'),
                        'smtp_port': smtp_config.get('port')
                    }
                else:
                    # Django SMTP settings
                    email_backend = getattr(settings, 'EMAIL_BACKEND', '')
                    
                    if 'console' in email_backend.lower():
                        return {
                            'valid': False,
                            'method': 'django_smtp',
                            'error': 'Console email backend detected - emails will not be delivered',
                            'suggestion': 'Configure SMTP settings in Django configuration'
                        }
                    
                    email_host = getattr(settings, 'EMAIL_HOST', '')
                    if not email_host:
                        return {
                            'valid': False,
                            'method': 'django_smtp',
                            'error': 'No EMAIL_HOST configured in Django settings'
                        }
                    
                    return {
                        'valid': True,
                        'method': 'django_smtp',
                        'backend': email_backend,
                        'host': email_host,
                        'port': getattr(settings, 'EMAIL_PORT', 25)
                    }
                    
        except Exception as e:
            return {
                'valid': False,
                'error': f'Validation error: {str(e)}'
            }


# Singleton instance
_email_routing_service = None

def get_email_routing_service(tenant=None) -> EmailRoutingService:
    """Get email routing service instance."""
    global _email_routing_service
    if _email_routing_service is None or _email_routing_service.tenant != tenant:
        _email_routing_service = EmailRoutingService(tenant=tenant)
    return _email_routing_service