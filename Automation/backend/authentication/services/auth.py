import random
import hashlib
import uuid
import logging
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import User
from authentication.models import OTP
from rest_framework_simplejwt.tokens import RefreshToken
from .mail import MailService
from workflows.models import Tenant, Organization, Membership

logger = logging.getLogger(__name__)

class AuthService:
    
    @staticmethod
    def generate_and_send_otp(email):
        """
        Generates a secure OTP, hashes it, stores it, and sends via email.
        """
        if not email:
            raise ValueError("Email is required")
            
        # 1. Generate 6-digit secure random code
        secure_random = random.SystemRandom()
        otp_code = "".join([str(secure_random.randint(0, 9)) for _ in range(6)])
        
        # 2. Hash it
        otp_hash = hashlib.sha256(otp_code.encode('utf-8')).hexdigest()
        
        # 3. Store in DB (Upsert)
        expiry = timezone.now() + timedelta(minutes=5)
        
        OTP.objects.update_or_create(
            email=email,
            defaults={
                'otp_hash': otp_hash,
                'expires_at': expiry,
                'created_at': timezone.now(),
                'attempts': 0,
                'is_verified': False
            }
        )
        
        # 4. Send Email
        success = MailService.send_otp_email(email, otp_code, role='user')
        if not success:
            raise Exception("Failed to send email")
            
        return True

    @staticmethod
    def verify_login(email, raw_code):
        """
        Verifies the OTP and returns tokens if valid.
        """
        try:
            otp_record = OTP.objects.get(email=email)
        except OTP.DoesNotExist:
            return None, "Invalid request"

        # Check attempts
        if otp_record.max_attempts_reached():
            otp_record.delete()
            return None, "Too many failed attempts. Please request a new code."

        # Check expiry
        if otp_record.is_expired():
            return None, "Code expired"

        # Verify Hash
        input_hash = hashlib.sha256(str(raw_code).encode('utf-8')).hexdigest()
        if input_hash != otp_record.otp_hash:
            otp_record.attempts += 1
            otp_record.save()
            return None, "Invalid code"

        # Success!
        otp_record.is_verified = True
        otp_record.delete() # Security: One-time use

        # Get or Create User
        user, created = AuthService._get_or_create_user(email)
        
        # Generate Tokens
        refresh = RefreshToken.for_user(user)
        # Custom Claims
        refresh['email'] = email

        # Ensure Tenant Membership (Auto-fix for "Access denied")
        if not Membership.objects.filter(user=user).exists():
            logger.info(f"User {user.email} has no tenant. Creating personal workspace.")
            try:
                # 1. Create Tenant
                tenant_slug = f"{user.username}-{uuid.uuid4().hex[:6]}"
                tenant = Tenant.objects.create(
                    name=f"{user.username}'s Workspace",
                    slug=tenant_slug
                )
                
                # 2. Create Organization
                # Ensure unique slug
                org_slug = f"{user.username}-org-{uuid.uuid4().hex[:6]}"
                org = Organization.objects.create(
                    tenant=tenant, 
                    name=f"{user.username}'s Org",
                    slug=org_slug
                )
                
                # 3. Create Membership
                Membership.objects.create(
                    user=user,
                    organization=org,
                    role='owner' 
                )
                logger.info(f"Created Tenant/Org/Membership for {user.email}")
            except Exception as e:
                logger.error(f"Failed to auto-create tenant for {user.email}: {e}")
                pass

        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'email': user.email,
                'username': user.username
            }
        }, None

    @staticmethod
    def _get_or_create_user(email):
        """
        Gets or creates a Django User.
        """
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            username = email.split('@')[0]
            if User.objects.filter(username=username).exists():
                username = f"{username}_{uuid.uuid4().hex[:4]}"
                
            user = User.objects.create_user(username=username, email=email)
            user.set_unusable_password() 
            
        return user, False

