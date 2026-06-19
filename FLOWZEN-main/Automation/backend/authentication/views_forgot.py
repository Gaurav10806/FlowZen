from django.shortcuts import render
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return render(request, 'auth/forgot_password.html')

    def post(self, request):
        email = request.data.get('email')
        # In a real app, logic to generate token and send email would go here
        # For now, we simulate success
        return render(request, 'auth/forgot_password.html', {
            'success_message': f"If an account exists for {email}, a reset link has been sent."
        })
