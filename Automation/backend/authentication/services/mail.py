from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class MailService:
    @staticmethod
    def send_otp_email(to_email, otp_code, role):
        """
        Sends an OTP email to the user.
        """
        subject = "Your Login Code - FlowZen Automation"
        
        # Determine strict wording based on role
        if role == 'admin':
            subject = "🔒 SECURE ADMIN LOGIN - FlowZen Automation"
            warning = "Use this code to access the Administrative Console."
        else:
            warning = "If you did not request this code, please ignore this email."

        message_text = f"Your login code is: {otp_code}\n\n{warning}\n\nThis code expires in 5 minutes."
        
        # Simple HTML template for production feel
        html_message = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; border: 1px solid #e0e0e0; border_radius: 8px; max-width: 500px;">
            <h2 style="color: #333;">Login Verification</h2>
            <p style="font-size: 16px; color: #555;">Use the following code to sign in:</p>
            <div style="background-color: #f4f4f4; padding: 15px; text-align: center; border-radius: 5px; margin: 20px 0;">
                <span style="font-size: 24px; font-weight: bold; letter-spacing: 5px; color: #000;">{otp_code}</span>
            </div>
            <p style="font-size: 14px; color: #666; margin-top: 20px;">{warning}</p>
            <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
            <p style="font-size: 12px; color: #999;">This code enables access to your FlowZen account. Never share it with anyone.</p>
        </div>
        """

        try:
            send_mail(
                subject=subject,
                message=message_text,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                html_message=html_message,
                fail_silently=False
            )
            logger.info(f"OTP email sent successfully to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send OTP email to {to_email}: {e}")
            return False
