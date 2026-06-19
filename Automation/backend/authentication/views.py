from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.throttling import AnonRateThrottle
import logging
import os
from .services.auth import AuthService

logger = logging.getLogger(__name__)

# Strict throttling for Auth endpoints
class AuthRateThrottle(AnonRateThrottle):
    rate = '10/minute'

class SendOTPView(views.APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        email = request.data.get('email')

        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Domain Validation (Gmail Only) - Maintaining security policy
        if not email.endswith('@gmail.com'):
             return Response({'error': 'Only Gmail addresses are allowed'}, status=status.HTTP_400_BAD_REQUEST)

        # Generate & Send
        try:
            AuthService.generate_and_send_otp(email)
            return Response({'message': 'OTP sent successfully', 'email': email})
        except Exception as e:
            logger.error(f"Send OTP Error: {e}")
            return Response({'error': 'Failed to send OTP. Please try again.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


from django.contrib.auth import login
from django.contrib.auth.models import User

class VerifyOTPView(views.APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthRateThrottle]

    def post(self, request):
        email = request.data.get('email')
        code = request.data.get('code')

        if not email or not code:
            return Response({'error': 'Email and Code are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            tokens, error = AuthService.verify_login(email, code)
            
            if error:
                return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
            
            # Establish Django Session
            try:
                user = User.objects.get(email=email)
                login(request, user)
                logger.info(f"Session established for user: {email}")
            except Exception as e:
                logger.error(f"Failed to establish session for {email}: {e}")

            return Response(tokens)
            
        except Exception as e:
            logger.error(f"Verify OTP Error: {e}")
            return Response({'error': 'Verification failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class MeView(views.APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'is_staff': user.is_staff
        })

