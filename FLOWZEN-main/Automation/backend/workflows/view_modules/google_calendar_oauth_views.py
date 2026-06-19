import logging
import requests
from django.conf import settings
from django.shortcuts import redirect
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.db import transaction
from ..models import Credential

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_google_calendar_credential(request):
    """
    Save Google Calendar credentials (Client ID/Secret) before OAuth flow.
    """
    user_id = request.user.id
    logger.critical(f"🚀 [GCal Save] Request received from user={user_id}")
    
    try:
        data = request.data
        client_id = data.get('client_id', '').strip()
        client_secret = data.get('client_secret', '').strip()
        email = data.get('email', '').strip()
        
        errors = {}
        if not client_id:
            errors['client_id'] = "Client ID is required"
        if not client_secret:
            errors['client_secret'] = "Client Secret is required"
            
        if errors:
            logger.error(f"❌ [GCal Save] Validation failed: {errors}")
            return Response({'success': False, 'errors': errors}, status=400)

        # Encrypt
        from ..services.credential_encryption import get_encryption_service
        svc = get_encryption_service()
        if not svc:
            logger.error("❌ [GCal Save] Encryption service unavailable")
            return Response({'success': False, 'error': 'Server configuration error (Encryption)'}, status=500)
            
        secret_payload = {'client_id': client_id, 'client_secret': client_secret}
        if email: 
            secret_payload['email'] = email

        encrypted_blob = svc.encrypt_credential_str(secret_payload)
        
        with transaction.atomic():
            cred_name = f"Google Calendar - {email}" if email else "Google Calendar"
            
            defaults = {
                'name': cred_name,
                'encrypted_data': encrypted_blob,
                'provider': 'google',
                'type': 'google_calendar'
            }
            if email: 
                defaults['email'] = email
            
            cred, created = Credential.objects.select_for_update().update_or_create(
                owner=request.user,
                provider='google',
                type='google_calendar',
                defaults=defaults
            )
            
            logger.critical(f"✅ [GCal Save] Success. CredID: {cred.id} (Created: {created}) for user_id={user_id}")
            
            return Response({
                'success': True,
                'credential_id': str(cred.id),
                'email': cred.email,
                'provider': 'google_calendar',
                'message': 'Google Calendar credentials saved securely.'
            })

    except Exception as e:
        logger.exception(f"❌ [GCal Save] Exception: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def start_google_calendar_oauth(request):
    """
    Initiate Google Calendar OAuth flow.
    """
    credential_id = request.data.get('credential_id') or request.query_params.get('credential_id')
    logger.critical(f"🚀 [GCal OAuth Start] Request for credential_id={credential_id} by user={request.user.id}")

    if not credential_id:
        return Response({'error': 'Credential ID required'}, status=400)

    try:
        cred = Credential.objects.get(id=credential_id, owner=request.user)
        
        # Resolve Client ID
        client_id = None
        from ..services.credential_encryption import get_encryption_service
        svc = get_encryption_service()
        if svc and cred.encrypted_data:
            data = svc.decrypt_credential_str(cred.encrypted_data) if isinstance(cred.encrypted_data, str) else cred.encrypted_data
            client_id = data.get('client_id')
            
            
        if not client_id:
             return Response({'error': 'No Client ID found in credential'}, status=400)
             
        # Verification Logging
        masked_id = f"{client_id[:15]}...{client_id[-5:]}" if client_id and len(client_id) > 20 else client_id
        logger.critical(f"👉 USING CLIENT ID: {masked_id}")
             
        scope = "https://www.googleapis.com/auth/calendar https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/userinfo.email"
        
        # Dynamic Redirect URI
        from django.urls import reverse
        from urllib.parse import urlencode
        from django.conf import settings

        # Use configured redirect_uri
        redirect_uri = settings.GOOGLE_CALENDAR_REDIRECT_URI
        
        logger.critical(f"   [GCal OAuth Start] Redirect URI: {redirect_uri}")
        logger.critical(f"👉 CRITICAL: Ensure this EXACT URL is in Google Console: {redirect_uri}")
        
        # State: UserID : CredentialID
        state = f"{request.user.id}:{credential_id}"
        
        params = {
            'scope': scope,
            'access_type': 'offline',
            'include_granted_scopes': 'true',
            'response_type': 'code',
            'state': state,
            'redirect_uri': redirect_uri,
            'client_id': client_id,
            'prompt': 'consent'
        }
        
        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
        
        return Response({'url': auth_url})

    except Credential.DoesNotExist:
        return Response({'error': 'Credential not found'}, status=404)
    except Exception as e:
        logger.exception(f"❌ [GCal OAuth Start] Failed: {e}")
        return Response({'error': str(e)}, status=500)

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def google_calendar_oauth_callback(request):
    """
    Handle Google Calendar OAuth callback.
    """
    logger.critical("🚀 [GCal OAuth Callback] OAuth callback hit")
    
    code = request.GET.get('code') or request.data.get('code')
    error = request.GET.get('error')
    state = request.GET.get('state')
    
    if error:
        logger.error(f"❌ [GCal OAuth Callback] Google error: {error}")
        return redirect(f'/credentials/?error={error}')
    if not code or not state:
        logger.error("❌ [GCal OAuth Callback] Missing code or state")
        return redirect('/credentials/?error=Invalid callback from Google. Please try again.')
        
    try:
        user_id_str, credential_id = state.split(':', 1)
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(id=user_id_str)
        cred = Credential.objects.get(id=credential_id, owner=user)
        
        # Resolve Secrets
        from ..services.credential_encryption import get_encryption_service
        svc = get_encryption_service()
        data = svc.decrypt_credential_str(cred.encrypted_data) if isinstance(cred.encrypted_data, str) else cred.encrypted_data
        
        client_id = data.get('client_id')
        client_secret = data.get('client_secret')
        
        # Exchange Token
        token_url = "https://oauth2.googleapis.com/token"
        
        from django.urls import reverse
        # Use configured redirect_uri
        redirect_uri = settings.GOOGLE_CALENDAR_REDIRECT_URI

        logger.critical(f"   [GCal OAuth Callback] Exchanging code with redirect_uri={redirect_uri}")
        
        resp = requests.post(token_url, data={
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        })
        
        if not resp.ok:
            logger.error(f"❌ [GCal OAuth Callback] Token exchange failed: {resp.text}")
            return redirect(f'/credentials/?error=Failed to exchange code for tokens. Google returned: {resp.status_code}')
            
        token_data = resp.json()
        logger.critical(f"✅ [GCal OAuth Callback] Tokens received")
        
        # Persistence Logic
        data['access_token'] = token_data.get('access_token')
        
        # PRESERVE refresh_token (Google only sends it once unless prompt=consent is used)
        if token_data.get('refresh_token'):
            logger.info("   [GCal OAuth Callback] NEW refresh_token received")
            data['refresh_token'] = token_data.get('refresh_token')
        elif not data.get('refresh_token'):
            logger.warning("⚠️ [GCal OAuth Callback] No refresh_token in response AND none in DB")
            
        # Store metadata
        data['expires_in'] = token_data.get('expires_in')
        if data.get('expires_in'):
            from datetime import datetime, timedelta
            expiry_time = datetime.utcnow() + timedelta(seconds=int(data['expires_in']))
            data['expiry'] = expiry_time.isoformat() + 'Z'
            
        data['scope'] = token_data.get('scope')
        data['token_type'] = token_data.get('token_type', 'Bearer')
            
        # Fetch User Email (Userinfo API)
        user_info_resp = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", 
                                     headers={'Authorization': f"Bearer {data['access_token']}"})
        if user_info_resp.ok:
            email = user_info_resp.json().get('email')
            if email:
                data['email'] = email
                cred.email = email
                cred.name = f"Google Calendar - {email}"
        
        # Save
        cred.encrypted_data = svc.encrypt_credential_str(data)
        cred.save()
        
        logger.critical(f"✅ [GCal OAuth Callback] Credential stored successfully. ID: {cred.id}")
        return redirect('/credentials/?status=success_google_calendar_connected')
        
    except Exception as e:
        logger.exception(f"❌ [GCal OAuth Callback] Unexpected Error: {e}")
        return redirect(f'/credentials/?error=unexpected_error')

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def google_calendar_oauth_status(request):
    """
    Check if Google Calendar is authenticated.
    """
    credential_id = request.GET.get('credential_id')
    if not credential_id:
        return Response({'isAuthenticated': False, 'error': 'No ID'}, status=400)

    try:
        cred = Credential.objects.get(id=credential_id, owner=request.user)
        from ..services.credential_encryption import get_encryption_service
        svc = get_encryption_service()
        is_authenticated = False
        
        if svc and cred.encrypted_data:
            data = svc.decrypt_credential_str(cred.encrypted_data) if isinstance(cred.encrypted_data, str) else cred.encrypted_data
            if data.get('access_token'):
                is_authenticated = True
                
        return Response({
            'isAuthenticated': is_authenticated,
            'email': cred.email,
            'credential_id': str(cred.id)
        })
    except:
        return Response({'isAuthenticated': False}, status=404)
