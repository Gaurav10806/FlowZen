"""
SMTP Email Sender - Production Grade
For non-Gmail addresses using SMTP
"""
import smtplib
import logging
from typing import Dict, Any, List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives
import base64
import mimetypes

logger = logging.getLogger(__name__)


class SMTPSenderError(Exception):
    """SMTP sender specific errors - NEVER silent success"""
    pass


class SMTPSender:
    """
    Production-grade SMTP email sender for non-Gmail addresses.
    """
    
    def __init__(self):
        """Initialize SMTP sender."""
        pass
    
    def send_email(self, from_email: str, to_emails: List[str], subject: str, 
                   body: str, cc_emails: List[str] = None, bcc_emails: List[str] = None,
                   is_html: bool = False, smtp_config: Dict[str, Any] = None,
                   attachments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Send email via SMTP.
        
        Args:
            from_email: Sender email address
            to_emails: List of recipient emails
            subject: Email subject
            body: Email body
            cc_emails: CC recipients
            bcc_emails: BCC recipients
            is_html: Whether body is HTML
            smtp_config: Custom SMTP configuration
            
        Returns:
            Dict with send result
            
        Raises:
            SMTPSenderError: If sending fails (NEVER silent success)
        """
        try:
            # Validate inputs
            if not from_email or not to_emails or not subject:
                raise SMTPSenderError("Missing required fields: from_email, to_emails, or subject")
            
            if not isinstance(to_emails, list):
                to_emails = [to_emails]
            
            # Use custom SMTP config or Django settings
            if smtp_config:
                return self._send_via_custom_smtp(
                    from_email, to_emails, subject, body, cc_emails, bcc_emails, is_html, smtp_config, attachments
                )
            else:
                return self._send_via_django_smtp(
                    from_email, to_emails, subject, body, cc_emails, bcc_emails, is_html, attachments
                )
                
        except SMTPSenderError:
            raise  # Re-raise SMTP errors
        except Exception as e:
            logger.error(f"Unexpected SMTP error: {e}")
            raise SMTPSenderError(f"SMTP sending failed: {str(e)}")
    
    def _send_via_django_smtp(self, from_email: str, to_emails: List[str], subject: str,
                             body: str, cc_emails: List[str] = None, bcc_emails: List[str] = None,
                             is_html: bool = False, attachments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send email via Django's email backend."""
        try:
            # Prepare recipient list
            all_recipients = to_emails[:]
            if cc_emails:
                all_recipients.extend(cc_emails)
            if bcc_emails:
                all_recipients.extend(bcc_emails)
            
            # Send email using Django's EmailMessage
            mail = EmailMultiAlternatives(
                subject=subject or "(No subject)",
                body=body if not is_html else "",
                from_email=from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                to=to_emails,
                cc=cc_emails,
                bcc=bcc_emails
            )
            
            if is_html:
                mail.attach_alternative(body, "text/html")
            
            # Add attachments
            if attachments:
                for att in attachments:
                    filename = att.get('name') or att.get('filename')
                    content = att.get('content')
                    mimetype = att.get('mimetype') or att.get('contentType')
                    
                    if filename and content:
                        try:
                            # If content is base64, decode it
                            if isinstance(content, str) and ';base64,' in content:
                                content = content.split(';base64,')[1]
                                content = base64.b64decode(content)
                            elif isinstance(content, str):
                                # Assume it might be raw string, or try to decode if it looks like b64
                                try:
                                    content = base64.b64decode(content)
                                except:
                                    content = content.encode('utf-8')
                            
                            mail.attach(filename, content, mimetype)
                        except Exception as attachment_error:
                            logger.error(f"Failed to attach file {filename}: {attachment_error}")
            
            mail.send(fail_silently=False)
            
            logger.info(f"Successfully sent email via Django SMTP from {from_email} to {to_emails}")
            
            return {
                'success': True,
                'method': 'django_smtp',
                'recipients': to_emails,
                'cc': cc_emails or [],
                'bcc': bcc_emails or [],
                'subject': subject,
                'from': from_email,
                'backend': getattr(settings, 'EMAIL_BACKEND', 'unknown')
            }
            
        except Exception as e:
            logger.error(f"Django SMTP failed: {e}")
            raise SMTPSenderError(f"Django SMTP failed: {str(e)}")
    
    def _send_via_custom_smtp(self, from_email: str, to_emails: List[str], subject: str,
                             body: str, cc_emails: List[str] = None, bcc_emails: List[str] = None,
                             is_html: bool = False, smtp_config: Dict[str, Any] = None,
                             attachments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send email via custom SMTP configuration."""
        try:
            # Extract SMTP config
            host = smtp_config.get('host')
            port = smtp_config.get('port', 587)
            username = smtp_config.get('username', '')
            password = smtp_config.get('password', '')
            use_tls = smtp_config.get('use_tls', True)
            use_ssl = smtp_config.get('use_ssl', False)
            
            if not host:
                raise SMTPSenderError("SMTP host is required in smtp_config")
            
            # Create message
            if is_html:
                msg = MIMEMultipart('alternative')
                msg.attach(MIMEText(body, 'html'))
            else:
                msg = MIMEText(body, 'plain')
            
            msg['From'] = from_email
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = subject
            
            # Add attachments
            if attachments:
                # If we have attachments, we MUST ensure the top-level is MIMEMultipart('mixed')
                # but our current structure might be just alternative
                if not isinstance(msg, MIMEMultipart):
                    # Wrap current msg (text) into a new multipart/mixed
                    msg_body = msg
                    msg = MIMEMultipart('mixed')
                    msg['From'] = from_email
                    msg['To'] = ', '.join(to_emails)
                    msg['Subject'] = subject
                    msg.attach(msg_body)
                elif msg.get_content_type() == 'multipart/alternative':
                     # Re-wrap as mixed
                    msg_alternative = msg
                    msg = MIMEMultipart('mixed')
                    msg['From'] = from_email
                    msg['To'] = ', '.join(to_emails)
                    msg['Subject'] = subject
                    msg.attach(msg_alternative)

                for att in attachments:
                    filename = att.get('name') or att.get('filename')
                    content = att.get('content')
                    mimetype = att.get('mimetype') or att.get('contentType')
                    
                    if filename and content:
                        try:
                            from email.mime.application import MIMEApplication
                            
                            # If content is base64, decode it
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
                        except Exception as attachment_error:
                            logger.error(f"Failed to attach file {filename} in custom SMTP: {attachment_error}")
            
            if cc_emails:
                msg['Cc'] = ', '.join(cc_emails)
            
            if bcc_emails:
                msg['Bcc'] = ', '.join(bcc_emails)
            
            # Prepare all recipients
            all_recipients = to_emails[:]
            if cc_emails:
                all_recipients.extend(cc_emails)
            if bcc_emails:
                all_recipients.extend(bcc_emails)
            
            # Send email
            if use_ssl:
                server = smtplib.SMTP_SSL(host, port)
            else:
                server = smtplib.SMTP(host, port)
                if use_tls:
                    server.starttls()
            
            if username and password:
                server.login(username, password)
            
            server.send_message(msg, to_addrs=all_recipients)
            server.quit()
            
            logger.info(f"Successfully sent email via custom SMTP from {from_email} to {to_emails}")
            
            return {
                'success': True,
                'method': 'custom_smtp',
                'recipients': to_emails,
                'cc': cc_emails or [],
                'bcc': bcc_emails or [],
                'subject': subject,
                'from': from_email,
                'smtp_host': host,
                'smtp_port': port
            }
            
        except Exception as e:
            logger.error(f"Custom SMTP failed: {e}")
            raise SMTPSenderError(f"Custom SMTP failed: {str(e)}")

    def send_email_to_multiple(self, from_email: str, to_emails: List[str], subject: str,
                               body: str, cc_emails: List[str] = None, bcc_emails: List[str] = None,
                               is_html: bool = False, smtp_config: Dict[str, Any] = None,
                               attachments: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Send email to multiple recipients via SMTP.
        
        Returns:
            List of result dicts for each recipient
        """
        results = []
        for recipient in to_emails:
            try:
                result = self.send_email(
                    from_email=from_email,
                    to_emails=[recipient],
                    subject=subject,
                    body=body,
                    cc_emails=cc_emails,
                    bcc_emails=bcc_emails,
                    is_html=is_html,
                    smtp_config=smtp_config,
                    attachments=attachments
                )
                results.append(result)
            except Exception as e:
                results.append({
                    'success': False,
                    'error': str(e),
                    'recipient': recipient,
                    'method': 'smtp'
                })
        return results
    
    def test_connection(self, smtp_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Test SMTP connection and credentials without sending an email.
        """
        try:
            host = smtp_config.get('host')
            port = int(smtp_config.get('port', 587))
            username = smtp_config.get('username', '')
            password = smtp_config.get('password', '')
            use_tls = smtp_config.get('use_tls', True)
            use_ssl = smtp_config.get('use_ssl', False)
            
            if not host:
                return False, "SMTP host is required"

            if use_ssl:
                server = smtplib.SMTP_SSL(host, port, timeout=10)
            else:
                server = smtplib.SMTP(host, port, timeout=10)
                if use_tls:
                    server.starttls()

            if username and password:
                server.login(username, password)
            
            # NOOP is a safe way to test connection validity
            code, msg = server.noop()
            server.quit()
            
            if code == 250:
                return True, "SMTP connection and authentication successful."
            else:
                return False, f"Server returned unexpected code: {code} - {msg.decode()}"
                
        except Exception as e:
            logger.warning(f"SMTP connection test failed: {e}")
            return False, str(e)


# Global instance
_smtp_sender = None

def get_smtp_sender() -> SMTPSender:
    """Get SMTP sender instance."""
    global _smtp_sender
    if _smtp_sender is None:
        _smtp_sender = SMTPSender()
    return _smtp_sender