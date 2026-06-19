from django.db import models
from django.conf import settings

class Notification(models.Model):
    TYPE_CHOICES = [
        ('success', 'Success'),
        ('error', 'Error'),
        ('warning', 'Warning'),
        ('info', 'Info'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='system_notifications')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='info')
    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.CharField(max_length=500, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.type.upper()}: {self.title}"


class NotificationSettings(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_settings')
    
    # Channels
    email_enabled = models.BooleanField(default=True)
    telegram_enabled = models.BooleanField(default=False)
    whatsapp_enabled = models.BooleanField(default=False)
    
    # Event Toggles (JSON for flexibility)
    # Keys: workflow_failed, workflow_success, credential_expired, system_update
    alert_types = models.JSONField(default=dict)
    
    # Quiet Hours
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_hours_start = models.TimeField(blank=True, null=True)
    quiet_hours_end = models.TimeField(blank=True, null=True)

    def __str__(self):
        return f"Settings for {self.user.username}"
