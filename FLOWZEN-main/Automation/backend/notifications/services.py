from .models import Notification, NotificationSettings
import logging

logger = logging.getLogger(__name__)

def create_notification(user, type, title, message, link=None):
    """
    Central service to create notifications based on user settings.
    """
    try:
        if not user:
            return

        # 1. Check Settings
        settings, _ = NotificationSettings.objects.get_or_create(user=user)
        
        # Check Quiet Hours
        # (Simplified logic: if enabled, we strictly might skip or just queue. For now we save but maybe don't "push")
        # For MVP, we save to DB regardless so Inbox sees it, but "Push" (Email/TG) would be blocked.
        
        # 2. Key Toggles Check (e.g. if type is 'error' and they disabled errors)
        # Note: We'll implement strict mapping if needed, but for now we default to Allowing DB entry.

        # 3. Create DB Entry
        Notification.objects.create(
            user=user,
            type=type,
            title=title,
            message=message,
            link=link
        )

        # 4. Future: Dispatch to Email/Telegram if enabled
        if settings.email_enabled and type == 'error':
            # send_email_alert(...)
            pass

    except Exception as e:
        logger.error(f"Failed to create notification: {e}")
