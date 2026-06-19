from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from .views import SendOTPView, VerifyOTPView, MeView
from rest_framework_simplejwt.views import TokenRefreshView

from .views_forgot import ForgotPasswordView

urlpatterns = [
    path('send-otp/', csrf_exempt(SendOTPView.as_view()), name='send_otp'),
    path('verify-otp/', csrf_exempt(VerifyOTPView.as_view()), name='verify_otp'),
    path('me/', MeView.as_view(), name='me'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('forgot-password/', csrf_exempt(ForgotPasswordView.as_view()), name='forgot-password'),
]
