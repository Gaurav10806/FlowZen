from django.db import models
import hashlib
from django.utils import timezone
import datetime

class OTP(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
    ]

    email = models.EmailField()
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    otp_hash = models.CharField(max_length=128)  # Stores SHA-256 hash of the OTP
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.IntegerField(default=0)
    is_verified = models.BooleanField(default=False)

    class Meta:
        # distinct OTPs for different roles even if email is same (though rare)
        unique_together = ('email', 'role')
        indexes = [
            models.Index(fields=['email', 'role']),
        ]

    def is_expired(self):
        return timezone.now() > self.expires_at

    def max_attempts_reached(self):
        return self.attempts >= 5

    def verify(self, raw_code):
        """
        Verify the provided raw code against the stored hash.
        """
        if self.is_expired():
            return False
            
        # Hash the input code
        input_hash = hashlib.sha256(str(raw_code).encode('utf-8')).hexdigest()
        return input_hash == self.otp_hash

    def __str__(self):
        return f"OTP for {self.email} ({self.role})"
