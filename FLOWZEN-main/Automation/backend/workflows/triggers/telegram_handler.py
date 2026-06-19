
import json
import logging
import re
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from workflows.models import Credential, TelegramConversation, TelegramMessage, WorkflowExecution, Workflow
from workflows.triggers.trigger_registry import trigger_registry
from workflows.tasks import execute_workflow_with_core_engine
from datetime import timedelta

logger = logging.getLogger(__name__)

def normalize_telegram_message(update):
    """
    Normalize Telegram update payload.
    Strips markdown symbols, extracts text, handles captions.
    """
    message = update.get('message') or update.get('edited_message') or update.get('channel_post') or update.get('my_chat_member') or update.get('callback_query', {}).get('message')
    
    # Callback Query Special Case
    if 'callback_query' in update:
         message = update['callback_query'].get('message')
         # If message is just a structure, use data
         if not message and 'data' in update['callback_query']:
             # Fabricate message for callback
             message = {
                 'text': update['callback_query']['data'],
                 'chat': {'id': update['callback_query']['from']['id']},
                 'from': update['callback_query']['from'],
                 'date': timezone.now().timestamp(),
                 'message_id': 0
             }

    if not message:
        return None

    text = message.get('text', '')
    caption = message.get('caption', '')
    final_text = text or caption or ''

    # Strip markdown symbols (simple approach)
    clean_text = final_text.strip()
    
    # Handle chat object safely
    chat_obj = message.get('chat', {})
    chat_id = str(chat_obj.get('id', ''))
    
    # Handle from object safely
    from_obj = message.get('from', {})
    
    return {
        'text': clean_text or "",
        'clean_text': clean_text or "",
        'command': clean_text.split(' ')[0].lower() if clean_text.startswith('/') else None,
        'chat_id': chat_id,
        'user_id': str(from_obj.get('id', '')) if (from_obj and from_obj.get('id')) else None,
        'username': from_obj.get('username') if from_obj else None,
        'date': message.get('date'),
        'message_id': str(message.get('message_id', '')),
        'is_bot': from_obj.get('is_bot', False),
        'is_group': int(chat_id) < 0 if chat_id and chat_id.lstrip('-').isdigit() else False, 
        'raw': message,
        'type': 'text' # Default
    }

def get_credential_by_token(token):
    """Find credential by bot token."""
    cache_key = f"telegram_token_cred_{token}"
    cached_id = cache.get(cache_key)
    if cached_id:
        return Credential.objects.filter(id=cached_id).first()

    from workflows.services.credential_encryption import get_encryption_service
    enc = get_encryption_service()

    for cred in Credential.objects.filter(type='telegram_bot'):
        data = cred.encrypted_data
        # Try all possible formats
        for attempt in [data]:
            # 1. Already a dict
            if isinstance(attempt, dict):
                cred_token = attempt.get('bot_token') or attempt.get('token')
                if cred_token == token:
                    cache.set(cache_key, cred.id, timeout=3600)
                    return cred
            # 2. Plain JSON string
            if isinstance(attempt, str):
                try:
                    parsed = json.loads(attempt)
                    cred_token = parsed.get('bot_token') or parsed.get('token')
                    if cred_token == token:
                        cache.set(cache_key, cred.id, timeout=3600)
                        return cred
                except Exception:
                    pass
                # 3. Encrypted string
                if enc:
                    try:
                        parsed = json.loads(enc.decrypt_credential_str(attempt))
                        cred_token = parsed.get('bot_token') or parsed.get('token')
                        if cred_token == token:
                            cache.set(cache_key, cred.id, timeout=3600)
                            return cred
                    except Exception:
                        pass

    # Last resort: match by token stored directly in name or webhook_url field
    for cred in Credential.objects.filter(type='telegram_bot'):
        if token in str(cred.encrypted_data):
            cache.set(cache_key, cred.id, timeout=3600)
            logger.info(f"Matched credential {cred.id} by raw token string search")
            return cred

    return None

@csrf_exempt
def telegram_webhook_view(request):
    """
    Global Telegram Webhook Handler.
    Endpoint: POST /api/webhooks/telegram/
    """
    logger.debug(f">>> [TELEGRAM WEBHOOK] Incoming request: {request.method} {request.path}")
    logger.debug(f">>> Headers: {dict(request.headers)}")
    
    if request.method == 'GET':
        return HttpResponse("Telegram Webhook Endpoint", status=200)

    if request.method != 'POST':
        return HttpResponse("Method not allowed", status=405)

    try:
        # Phase T17: Fail-Safe Global Error Handler
        try:
            body_unicode = request.body.decode('utf-8') if isinstance(request.body, bytes) else request.body
            payload = json.loads(body_unicode)
            
            # Guarantee payload is a dict
            if not isinstance(payload, dict):
                logger.warning(f"Telegram payload is not a dict: {type(payload)}")
                payload = {"raw_data": payload}
                
        except json.JSONDecodeError:
            return HttpResponse("Invalid JSON", status=200) # Generic 200

        # 1. Validate Bot Token & Get Credential (Phase 4 Logic)
        bot_token = None
        
        # A. Try Secret Token Header (Security check)
        secret_header = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
        # We accept 'flowzen_secure_v1' as a standard for this platform
        if secret_header and secret_header != "flowzen_secure_v1":
             logger.warning(f"Telegram webhook: Invalid secret token {secret_header}")
             return HttpResponse("Forbidden", status=403)

        # B. Identify Bot (Strictly from URL parameters for multi-bot support)
        bot_token = request.GET.get('token') or request.GET.get('bot_token')
        credential_id_param = request.GET.get('credential_id')
        
        # Extract from payload if sent (some custom setups)
        if not bot_token and isinstance(payload, dict) and 'bot' in payload and 'token' in payload['bot']:
            bot_token = payload['bot']['token']

        credential = None
        
        # Try by credential_id first (most reliable)
        if credential_id_param:
            try:
                credential = Credential.objects.get(id=credential_id_param, type='telegram_bot')
                logger.info(f"Matched credential by ID: {credential.name}")
            except Credential.DoesNotExist:
                pass

        # Fallback: match by token
        if not credential and bot_token:
            credential = get_credential_by_token(bot_token)
        
        # Last resort: if only one telegram bot exists, use it
        if not credential:
            creds = Credential.objects.filter(type='telegram_bot')
            if creds.count() == 1:
                credential = creds.first()
                logger.info(f"Using only available telegram credential: {credential.name}")
        
        if not credential:
            logger.warning("Telegram webhook: Unknown bot. Please re-register your bot in the dashboard.")
            return HttpResponse('{"ok": true}', content_type="application/json", status=200)

        logger.info(f"Telegram webhook: Identified bot {credential.name}")

        # 3. Stats & Normalization
        try:
            today = timezone.now().date()
            stats_key = f"telegram_stats_received_{today}"
            try:
                cache.incr(stats_key, 1)
            except ValueError:
                cache.set(stats_key, 1, timeout=86400)
        except:
             pass
        
        normalized = normalize_telegram_message(payload)
        if not normalized:
            return HttpResponse("OK")
            
        if normalized['is_bot']:
             return HttpResponse("OK")
             
        chat_id = normalized['chat_id']
        user_id = normalized['user_id']
        message_text = normalized['text']
        command = normalized['command']
        clean_text = normalized['clean_text']
        msg_type = normalized['type']
        
        # 4. Rate Limiting
        rate_key = f"telegram_rate_{user_id}"
        if cache.get(rate_key):
             logger.warning(f"Rate limit hit for user {user_id}")
             return HttpResponse("OK")
        cache.set(rate_key, 1, timeout=1) 
        
        # 5. Conversation Tracking
        defaults = {
             'user_id': user_id,
             'username': normalized['username'] or f"user_{user_id}",
             'is_group': normalized['is_group'],
             'last_message_at': timezone.now()
        }
        
        conversation, created = TelegramConversation.objects.update_or_create(
            credential=credential,
            chat_id=chat_id,
            defaults=defaults
        )
        
        if created:
             try:
                cache.incr(f"telegram_stats_conversations_{today}", 1)
             except ValueError:
                cache.set(f"telegram_stats_conversations_{today}", 1, timeout=86400)

        # 6. Log Message
        TelegramMessage.objects.create(
            credential=credential,
            conversation=conversation,
            direction='inbound',
            chat_id=chat_id,
            message_type='text',
            text=message_text,
            raw_payload=payload
        )
             
        # 7. Human Takeover Check
        if conversation.is_human_controlled:
             if command in ['/reset', '/start', '/bot']:
                 conversation.is_human_controlled = False
                 conversation.save()
             else:
                 try:
                    cache.incr(f"telegram_stats_takeovers_{today}", 1)
                 except ValueError:
                    cache.set(f"telegram_stats_takeovers_{today}", 1, timeout=86400)
                 return HttpResponse("OK")

        # 8. Trigger Workflows
        from workflows.models import Node
        from django.db.models import Q
        
        # Build robust query:
        # 1. Must be Telegram Trigger
        # 2. Workflow MUST be published (active)
        # 3. Credential must match (check both ForeignKey AND config JSON for robustness)
        
        trigger_filter = Q(action_type="telegram_trigger") & Q(workflow__status="published")
        
        if credential:
            # Check both strict relation (preferred) and config blob (fallback)
            cred_filter = Q(credential=credential) | Q(config__credential_id=str(credential.id))
            trigger_filter &= cred_filter
        
        trigger_nodes = Node.objects.filter(trigger_filter).select_related('workflow')
        
        if not trigger_nodes.exists() and credential:
            # Diagnose WHY it failed for better logs
            # Check if ANY node exists with this credential (ignoring status)
            any_nodes = Node.objects.filter(
                Q(action_type="telegram_trigger") & 
                (Q(credential=credential) | Q(config__credential_id=str(credential.id)))
            )
            any_node_count = any_nodes.count()
            
            if any_node_count > 0:
                logger.warning(f"Telegram Webhook: Credential matched {credential.name} (ID: {credential.id}) but linked workflow is NOT PUBLISHED. Found {any_node_count} drafts.")
            else:
                logger.warning(f"Telegram Webhook: Credential matched {credential.name} (ID: {credential.id}) but NO nodes are linked to it.")

        for node in trigger_nodes:
            workflow = node.workflow
            config = node.config
            
            # Event Check
            events = config.get('events', ['message'])
            is_command_msg = (command is not None)
            
            should_trigger = False
            if is_command_msg and 'command' in events:
                should_trigger = True
            elif not is_command_msg and 'message' in events:
                should_trigger = True
                
            if not should_trigger:
                continue

            # Group Check
            allow_groups = config.get('allow_groups', False)
            if conversation.is_group and not allow_groups and not is_command_msg:
                continue

            chatbot_mode = config.get('chatbot_mode', False)
            
            # Create Execution
            import uuid
            execution = WorkflowExecution.objects.create(
                workflow=workflow,
                tenant=workflow.tenant,
                status='pending',
                triggered_by='webhook',
                fingerprint=str(uuid.uuid4()), # Prevent Unique Constraint Violation (u_exec_tenant_fingerprint)
                root_context={'telegram_bot_credential_id': str(credential.id)}, # Persist credential globally for downstream nodes
                input_payload={
                    'message': message_text,
                    'text': clean_text,
                    'clean_text': clean_text,
                    'command': command,
                    'chat_id': chat_id,
                    'user_id': user_id,
                    'username': normalized['username'],
                    'message_id': normalized['message_id'],
                    'is_group': conversation.is_group,
                    'conversation_id': str(conversation.id),
                    'chatbot_mode': chatbot_mode,
                    'payload': payload,
                    'telegram_bot_credential_id': str(credential.id) # INJECTED VALID CREDENTIAL
                }
            )
            execute_workflow_with_core_engine.delay(str(execution.id))

        return HttpResponse("OK")

    except Exception as e:
        logger.error(f"Telegram Webhook Global Crash: {e}", exc_info=True)
        return HttpResponse("OK")

@csrf_exempt
def telegram_health_view(request):
    """
    Phase T14: Health Check Endpoint.
    GET /api/health/telegram/
    """
    if request.method != 'GET':
        return HttpResponse("Method not allowed", status=405)
        
    # Gather Metrics (from cache)
    today = timezone.now().date()
    stats = {
        "status": "ok",
        "webhook_reachable": True,
        "bots_active": Credential.objects.filter(type='telegram_bot').count(),
        "messages_received_today": cache.get(f"telegram_stats_received_{today}", 0),
        "active_conversations_today": cache.get(f"telegram_stats_conversations_{today}", 0),
        "human_takeovers_today": cache.get(f"telegram_stats_takeovers_{today}", 0)
    }
    
    return JsonResponse(stats)
@csrf_exempt
def telegram_register_view(request):
    """
    Automated Telegram Bot Registration.
    Endpoint: GET /api/v1/telegram/register/
    """
    import requests
    
    # 1. Inputs from GET
    credential_id = request.GET.get('credential_id')
    webhook_url = request.GET.get('webhook_url')
    bot_token = request.GET.get('token')
    
    # 2. Supplement from DB if possible
    if credential_id:
        try:
            credential = Credential.objects.get(id=credential_id)
            data = credential.encrypted_data
            if isinstance(data, str):
                try: data = json.loads(data)
                except: pass
            
            if not bot_token:
                bot_token = data.get("bot_token") or data.get("token")
            if not webhook_url:
                webhook_url = data.get("webhook_url")
        except:
            pass

    # 3. Validation & Sanitization
    if webhook_url:
        webhook_url = str(webhook_url).strip()
    
    if bot_token:
        bot_token = str(bot_token).strip()

    # DEBUG LOG (Captured by Docker)
    print(f">>> [TELEGRAM REGISTER] Method: {request.method}, Full GET: {dict(request.GET)}")
    print(f">>> [TELEGRAM REGISTER] Extracted: Token present={bool(bot_token)}, Webhook={webhook_url}")

    if not bot_token:
        return JsonResponse({"success": False, "message": "❌ Bot token missing. Please enter it first."}, status=400)

    if not webhook_url or not webhook_url.startswith("https://"):
        return JsonResponse({
            "success": False,
            "message": "❌ Telegram requires an HTTPS webhook URL. Please use an https:// link (e.g. ngrok)."
        }, status=400)

    # AUTO-FIX: Append token to webhook URL for robust identification if missing
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    parts = list(urlparse(webhook_url))
    query = parse_qs(parts[4])
    if 'token' not in query and 'bot_token' not in query:
        query['token'] = [bot_token]
        parts[4] = urlencode(query, doseq=True)
        webhook_url = urlunparse(parts)
        print(f">>> [TELEGRAM REGISTER] Upgraded Webhook URL: {webhook_url}")

    try:
        telegram_api = f"https://api.telegram.org/bot{bot_token}/setWebhook"
        resp = requests.post(telegram_api, json={
            "url": webhook_url,
            "secret_token": "flowzen_secure_v1"
        }, timeout=15)
        
        res_json = resp.json()
        
        return JsonResponse({
            "success": res_json.get("ok", False),
            "message": "✅ Telegram webhook registered successfully" if res_json.get("ok") else f"❌ Telegram Error: {res_json.get('description', 'Failed')}",
            "details": res_json,
            "webhook_url": webhook_url
        })
        
    except Exception as e:
        return JsonResponse({
            "success": False,
            "message": f"❌ Registration failed: {str(e)}"
        }, status=500)
