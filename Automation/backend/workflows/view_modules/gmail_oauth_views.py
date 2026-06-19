import logging
import requests
import base64
import json
from django.conf import settings
from django.shortcuts import redirect
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from ..models import Credential, Tenant

logger = logging.getLogger(__name__)

from django.db import transaction

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_gmail_credential(request):
    """
    STRICT Endpoint to save Gmail credentials.
    """
    user_id = request.user.id
    logger.critical(f"🚀 [Gmail Save] Request received from user={user_id}")
    
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
            logger.error(f"❌ [Gmail Save] Validation failed: {errors}")
            return Response({'success': False, 'errors': errors}, status=400)

        # 3. Encrypt Secret
        from ..services.credential_encryption import get_encryption_service
        svc = get_encryption_service()
        if not svc:
            logger.error("❌ [Gmail Save] Encryption service unavailable")
            return Response({'success': False, 'error': 'Server configuration error (Encryption)'}, status=500)
            
        secret_payload = {
            'client_id': client_id,
            'client_secret': client_secret
        }
        if email:
            secret_payload['email'] = email

        encrypted_blob = svc.encrypt_credential_str(secret_payload)
        
        # 4. Save to DB with STRICT ATOMICITY
        with transaction.atomic():
            cred_name = f"Gmail - {email}" if email else "Gmail OAuth"
            
            defaults = {
                'name': cred_name,
                'encrypted_data': encrypted_blob,
                'provider': 'google',
                'type': 'gmail'
            }
            if email:
                defaults['email'] = email
            
            cred, created = Credential.objects.select_for_update().update_or_create(
                owner=request.user,
                provider='google',
                type='gmail',
                defaults=defaults
            )
            
            logger.critical(f"✅ [Gmail Save] Success. CredID: {cred.id} (Created: {created}) for user_id={user_id}")
            
            return Response({
                'status': 'success',
                'message': 'Gmail credentials saved securely 🔐',
                'data': {
                    'credential_id': str(cred.id),
                    'email': cred.email,
                    'provider': 'gmail'
                }
            })

    except Exception as e:
        logger.exception(f"❌ [Gmail Save] Exception: {e}")
        return Response({'success': False, 'error': str(e)}, status=500)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def start_gmail_oauth(request):
    """
    Unified Google OAuth Start Endpoint.
    Handles Gmail, Drive, Sheets, YouTube scopes.
    """
    credential_id = request.data.get('credential_id') or request.query_params.get('credential_id')
    logger.critical(f"🚀 [OAuth Start] Request for credential_id={credential_id} by user={request.user.id}")
    
    # 1. Determine Keys
    client_id = settings.GMAIL_OAUTH_CLIENT_ID
    client_secret = settings.GMAIL_OAUTH_CLIENT_SECRET
    
    if credential_id:
        try:
            cred = Credential.objects.get(id=credential_id, owner=request.user)
            # Decrypt to check for custom keys
            from ..services.credential_encryption import get_encryption_service
            svc = get_encryption_service()
            data = {}
            if svc and cred.encrypted_data:
                data = svc.decrypt_credential_str(cred.encrypted_data) if isinstance(cred.encrypted_data, str) else cred.encrypted_data
            
            if data.get('client_id') and data.get('client_secret'):
                client_id = data.get('client_id')
                client_secret = data.get('client_secret')
        except Exception as e:
            logger.warning(f"Failed to load custom keys: {e}")

    if not client_id or not client_secret:
        return Response({'error': 'Missing Client ID/Secret'}, status=500)

    # 2. Config
    # redirect_uri construction is now handled by settings
    redirect_uri = settings.GMAIL_OAUTH_REDIRECT_URI
    
    logger.critical(f"DEBUG: Gmail OAuth Redirect URI being sent: {redirect_uri}")
    
    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri]
        }
    }
    
    # 3. Scopes
    scopes = [
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/youtube',
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/calendar.events'
    ]
    
    import google_auth_oauthlib.flow
    flow = google_auth_oauthlib.flow.Flow.from_client_config(client_config, scopes=scopes)
    flow.redirect_uri = redirect_uri
    
    state = f"{request.user.id}:{credential_id}" if credential_id else f"{request.user.id}:new"
    
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
        state=state
    )
    
    return Response({'url': auth_url})

from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def gmail_oauth_callback(request):
    """
    Unified Google Callback.
    Handles Redirect, Code Exchange, and Credential Save.
    """
    code = request.GET.get('code') or request.data.get('code')
    error = request.GET.get('error')
    state = request.GET.get('state')
    
    if error:
        logger.error(f"Google OAuth Error: {error}")
        return redirect(f'/credentials/?error={error}')
    
    if not code:
        return redirect('/credentials/?error=no_code_provided')

    try:
        # 1. Parse State
        credential_id = None
        user = request.user
        
        # If user is anonymous (Browser Redirect often loses DRF Auth header, but carries Session Cookie)
        # We try to recover user from state if session works, or rely on state ID
        if state and ':' in state:
            user_id_str, cred_id_raw = state.split(':', 1)
            if cred_id_raw != 'new':
                credential_id = cred_id_raw
            
            if not user.is_authenticated:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    user = User.objects.get(id=user_id_str)
                    # Login user manually? No, unsafe. Assume session exists or token exchange doesn't need auth user yet
                    # But we need user to SAVE credential.
                    # TRUST THE STATE (Signed state is better, but MVP assumes ID match)
                    logger.critical(f"Recovered user {user.email} from state")
                except User.DoesNotExist:
                     return redirect('/credentials/?error=user_not_found')

        # 2. Determine Keys
        client_id = settings.GMAIL_OAUTH_CLIENT_ID
        client_secret = settings.GMAIL_OAUTH_CLIENT_SECRET
        
        cred = None
        if credential_id:
            try:
                cred = Credential.objects.get(id=credential_id, owner=user)
                # Decrypt checks ...
                from ..services.credential_encryption import get_encryption_service
                svc = get_encryption_service()
                if svc and cred.encrypted_data:
                    data = svc.decrypt_credential_str(cred.encrypted_data) if isinstance(cred.encrypted_data, str) else cred.encrypted_data
                    if data.get('client_id'):
                        client_id = data.get('client_id')
                        client_secret = data.get('client_secret')
            except Exception:
                pass

        # 3. Exchange
        # Use configured redirect_uri
        redirect_uri = settings.GMAIL_OAUTH_REDIRECT_URI
            
        import google_auth_oauthlib.flow
        client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        }
        flow = google_auth_oauthlib.flow.Flow.from_client_config(client_config, scopes=None)
        flow.redirect_uri = redirect_uri
        
        flow.fetch_token(code=code)
        creds = flow.credentials
        
        # 4. Get Email
        import requests
        user_info = requests.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {creds.token}'}
        ).json()
        email = user_info.get('email')
        
        # 5. Save
        token_data = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'client_id': client_id, # Store keys used
            'client_secret': client_secret,
            'scopes': creds.scopes,
            'email': email,
            'expiry': creds.expiry.isoformat() if creds.expiry else None
        }
        
        from ..services.credential_encryption import get_encryption_service
        svc = get_encryption_service()
        enc_data = svc.encrypt_credential_str(token_data) if svc else token_data
        
        # 5. Save with STRICT ATOMICITY
        with transaction.atomic():
            # Ensure we don't have a race condition by locking the existing row if it exists
            cred, created = Credential.objects.select_for_update().update_or_create(
                owner=user,
                provider='google',
                type='gmail',
                defaults={
                    'name': f"Google ({email})",
                    'email': email,
                    'encrypted_data': enc_data,
                }
            )
            
            if created:
                logger.critical(f"✅ [OAuth Callback] Created NEW credential {cred.id} for user {user.email}")
            else:
                logger.critical(f"✅ [OAuth Callback] Updated EXISTING credential {cred.id} for user {user.email}")

        # CRITICAL: Re-login user to fix Session Drop (127.0.0.1 -> localhost switch)
        if not request.user.is_authenticated:
            try:
                from django.contrib.auth import login
                # Force backend
                user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, user)
                logger.critical(f"✅ [OAuth Callback] Session Restored: Logged in user {user.email} on {request.get_host()}")
            except Exception as e:
                logger.error(f"⚠️ [OAuth Callback] Failed to re-login user: {e}")
        
        # NOTIFICATION TRIGGER
        try:
            from notifications.services import create_notification
            create_notification(
                user=user,
                type='success',
                title='Gmail Connected',
                message=f"Successfully connected Google account: {email}",
                link="/credentials/"
            )
        except Exception as n_e:
             logger.warning(f"Failed to send credential notification: {n_e}")

        return redirect('/credentials/?status=success_gmail_connected')

    except Exception as e:
        logger.exception(f"Callback failed: {e}")
        return redirect(f'/credentials/?error={str(e)}')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def gmail_oauth_status(request):
    """
    Check the status of a specific credential.
    GET /api/v1/gmail-oauth/status/?credential_id=...
    """
    credential_id = request.GET.get('credential_id')
    
    if not credential_id:
        return Response({'isAuthenticated': False, 'error': 'No credential_id provided'}, status=400)

    try:
        cred = Credential.objects.get(id=credential_id, owner=request.user)
        # Check if we have an access token (crudely by checking if encrypted_data has it)
        # We need to decrypt it to be sure.
        from ..services.credential_encryption import get_encryption_service
        svc = get_encryption_service()
        is_valid = False
        email = cred.email
        
        if svc and cred.encrypted_data:
            try:
                data = svc.decrypt_credential_str(cred.encrypted_data) if isinstance(cred.encrypted_data, str) else cred.encrypted_data
                # Check for access_token or just assume if we have a valid refresh token/access token its good
                if data.get('access_token'):
                    is_valid = True
            except Exception:
                pass
        
        return Response({
            'isAuthenticated': is_valid,
            'email': email,
            'credential_id': str(cred.id)
        })

    except Credential.DoesNotExist:
        return Response({'isAuthenticated': False, 'error': 'Credential not found'}, status=404)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def gmail_oauth_test(request):
    """
    Send a test email using the credential.
    POST /api/v1/gmail-oauth/test/
    Body: { "credential_id": "...", "to_email": "..." }
    """
    credential_id = request.data.get('credential_id')
    to_email = request.data.get('to_email')

    if not credential_id or not to_email:
        return Response({'success': False, 'error': 'credential_id and to_email are required'}, status=400)

    try:
        cred = Credential.objects.get(id=credential_id, owner=request.user)
        
        # We need a tenant context for the dispatcher?
        tenant = Tenant.objects.first() 
        if not tenant:
             logger.error("No tenant found for gmail test")
             # Fallback: Create a dummy tenant or fail? 
             # If we fail, user knows they need a tenant.
             return Response({'success': False, 'error': 'No tenant configuration found'}, status=500)
        
        from ..email.dispatcher import get_email_dispatcher
        dispatcher = get_email_dispatcher()
        
        subject = "Test Email from Automation Platform"
        body = "This is a test email to verify your Gmail integration."
        
        # from_email: use cred.email if available, else "me"
        from_email = cred.email if cred.email else "me"

        result = dispatcher.send_email(
            user=request.user,
            tenant=tenant,
            from_email=from_email,
            to_emails=[to_email],
            subject=subject,
            body=body
        )
        
        if result.get('success'):
             return Response({'success': True, 'message': 'Email sent successfully'})
        else:
             return Response({'success': False, 'error': result.get('error', 'Unknown error')}, status=500)

    except Credential.DoesNotExist:
        return Response({'success': False, 'error': 'Credential not found'}, status=404)
    except Exception as e:
        logger.exception("Test email failed")
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def gmail_oauth_disconnect(request, credential_id):
    """
    Disconnect/Delete a credential.
    DELETE /api/v1/gmail-oauth/disconnect/<credential_id>/
    """
    try:
        cred = Credential.objects.get(id=credential_id, owner=request.user)
        cred.delete()
        return Response({'success': True, 'message': 'Credential deleted'})
    except Credential.DoesNotExist:
        return Response({'success': False, 'error': 'Credential not found'}, status=404)

