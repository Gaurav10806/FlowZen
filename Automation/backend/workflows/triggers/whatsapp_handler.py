import json
import logging
import hmac
import hashlib
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from ..models import Credential, Workflow, WorkflowExecution, WhatsAppConversation, WhatsAppMessage, WhatsAppUsage
from ..execution.core_engine import WorkflowExecutionEngine
# from ..execution.django_executor import DjangoWorkflowExecutor # MOVED INSIDE FUNCTION
from ..utils.credential_resolver import resolve_credential_data
# Use local logger
logger = logging.getLogger(__name__)

# Constants
CONVERSATION_LIMIT_HARD = 1000
CONVERSATION_LIMIT_SOFT = 900

def normalize_encrypted_data(raw):
    """
    Safely ensures data is a dictionary.
    If raw is string, json.loads it.
    If raw is None, fallbacks to {}.
    """
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except:
            return {}
    return raw or {}

@csrf_exempt
def handle_whatsapp_webhook(request):
    """
    Global Webhook Endpoint for Meta WhatsApp Cloud API.
    Routes incoming messages to workflows based on Phone Number ID.
    STRICT IMPLEMENTATION: Validates signatures, does NOT create conversations.
    """
    
    # 1. VERIFICATION REQUEST (GET)
    logger.info(f"Processing WhatsApp Webhook: {request.method}")
    print(f"DEBUG: WhatsApp Webhook {request.method}")
    
    if request.method == 'GET':
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        if mode == 'subscribe' and token:
            creds = Credential.objects.filter(type='meta_whatsapp')
            matched = False
            for cred in creds:
                data = resolve_credential_data(cred)
                if data.get('verify_token') == token:
                    matched = True
                    break
            
            if matched:
                return HttpResponse(challenge, status=200)
            else:
                return HttpResponseForbidden("Verification token mismatch")
        
        return HttpResponseForbidden("Missing parameters")

    # 2. EVENT NOTIFICATION (POST)
    if request.method == 'POST':
        try:
            payload_bytes = request.body
            payload = json.loads(payload_bytes.decode('utf-8'))
            
            entries = payload.get('entry', [])
            if not entries:
                return HttpResponse("EVENT_RECEIVED", status=200)

            for entry in entries:
                for change in entry.get('changes', []):
                    value = change.get('value', {})
                    metadata = value.get('metadata', {})
                    phone_number_id = metadata.get('phone_number_id')
                    
                    if not phone_number_id:
                        continue
                        
                    # 2.2 Lookup Credential
                    try:
                        credential = find_credential_by_phone_id(phone_number_id)
                        if not credential:
                            logger.warning(f"⚠️ Unknown Phone ID: {phone_number_id}")
                            return JsonResponse({"status": "ignored"}, status=200)
                    except Exception as e:
                        logger.error(f"Credential Lookup Crash: {e}", exc_info=True)
                        return JsonResponse({"status": "ignored"}, status=200)

                    # 2.3 Strict Signature & Data Handling
                    data = resolve_credential_data(credential)
                    app_secret = data.get('app_secret')
                    
                    if app_secret:
                        signature = request.headers.get('X-Hub-Signature-256', '')
                        if not validate_signature(payload_bytes, signature, app_secret):
                             logger.warning("❌ Signature Mismatch")
                             # Return 200 even on mismatch to satisfy Meta webhook requirements
                             return HttpResponse("EVENT_RECEIVED", status=200)

                    # 2.4 Process Messages
                    if 'messages' in value:
                        process_payload_messages(credential, value)
                    
                    # 2.5 Process Statuses
                    if 'statuses' in value:
                        process_payload_statuses(credential, value)
                        
            return HttpResponse("EVENT_RECEIVED", status=200)
            
        except Exception as e:
            logger.error(f"❌ WhatsApp Webhook Internal Error: {e}", exc_info=True)
            # HARDENING: Always return 200 to prevent Meta retries on local failures
            return HttpResponse("EVENT_RECEIVED", status=200)

    return HttpResponse("OK", status=200)



def process_payload_statuses(credential, value):
    """
    Process status updates (sent, delivered, read, failed).
    Updates WhatsAppMessage model.
    """
    statuses = value.get('statuses', [])
    for status_data in statuses:
        wamid = status_data.get('id')
        status = status_data.get('status') # sent, delivered, read, failed
        timestamp_str = status_data.get('timestamp')
        
        # Parse timestamp
        try:
            ts = timezone.datetime.fromtimestamp(int(timestamp_str), tz=timezone.utc)
        except:
            ts = timezone.now()
            
        try:
            msg = WhatsAppMessage.objects.get(meta_message_id=wamid)
            
            # Idempotency / Progression Check
            # Don't revert 'read' to 'delivered'
            if msg.status == 'read' and status in ['sent', 'delivered']:
                continue
            if msg.status == 'delivered' and status == 'sent':
                continue
                
            msg.status = status
            
            if status == 'delivered':
                msg.delivered_at = ts
            elif status == 'read':
                msg.read_at = ts
            elif status == 'failed':
                errors = status_data.get('errors', [])
                if errors:
                    err = errors[0]
                    msg.error_code = str(err.get('code'))
                    msg.error_message = err.get('title')
            
            msg.save()
            logger.info(f"Updated Message {wamid} status to {status}")
            
        except WhatsAppMessage.DoesNotExist:
            logger.warning(f"Status update for unknown message: {wamid}")
        except Exception as e:
            logger.error(f"Error updating status: {e}")



def validate_signature(payload_bytes, signature_header, app_secret):
    """
    Validates X-Hub-Signature-256.
    """
    if not signature_header.startswith('sha256='):
        return False
    
    expected_mac = hmac.new(
        key=app_secret.encode('utf-8'),
        msg=payload_bytes,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    received_mac = signature_header.split('sha256=')[1]
    return hmac.compare_digest(expected_mac, received_mac)


def find_credential_by_phone_id(phone_number_id):
    """
    Finds a Meta WhatsApp credential matching this phone_number_id.
    Standardizes on string comparison and supports both 'phone_id' and 'phone_number_id' keys.
    """
    try:
        phone_id_str = str(phone_number_id).strip()
        logger.info(f"🔍 Searching WhatsApp credential for phone_id={phone_id_str}")

        # Filter only provider="meta_whatsapp" for strictness
        creds = Credential.objects.filter(provider="meta_whatsapp")
        
        for cred in creds:
            data = resolve_credential_data(cred)
            
            # Normalize keys: PRIMARY is phone_number_id, FALLBACK is phone_id
            stored_id = data.get("phone_number_id") or data.get("phone_id")
            logger.info(f"Checking credential {cred.id}: stored_id={stored_id}")

            if stored_id == phone_id_str:
                logger.info(f"✅ Credential Matched")
                return cred
                
    except Exception as e:
        logger.error(f"💥 Error during WhatsApp credential lookup: {e}", exc_info=True)
        
    return None


def process_payload_messages(credential, value):
    """
    Process batch of messages. 
    Strict Rule: DO NOT CREATE CONVERSATION.
    """
    messages = value.get('messages', [])
    contacts = value.get('contacts', [])
    
    for msg in messages:
        wa_id = msg.get('from')
        msg_type = msg.get('type')
        msg_id = msg.get('id')
        
        # 1. Resolve Active Conversation (if any)
        # We need this to check 'is_human_controlled' flag AND update expiry
        conversation = WhatsAppConversation.objects.filter(
            credential=credential, 
            user_phone_number=wa_id,
            is_active=True
        ).order_by('-started_at').first()
        
        # 1.1 Update Expiry if exists (Rolling 24h window)
        # "A conversation lasts exactly 24 hours from the last user message."
        if conversation:
            # We must parse the message timestamp or use now
            # Meta timestamp is unix epoch
            try:
                msg_ts = int(msg.get('timestamp', 0))
                msg_dt = timezone.datetime.fromtimestamp(msg_ts, tz=timezone.utc)
            except:
                msg_dt = timezone.now()
                
            conversation.last_user_message_at = msg_dt
            conversation.expires_at = msg_dt + timezone.timedelta(hours=24)
            conversation.save(update_fields=['last_user_message_at', 'expires_at'])

        
        # 2. Extract Content & Check for Human Takeover commands
        content_text = ""
        media_metadata = {}
        
        # Phase 4 Enhancement: Normalize Media & Safety
        if msg_type == 'text':
            content_text = msg.get('text', {}).get('body', '')
        elif msg_type == 'button':
            content_text = msg.get('button', {}).get('text', '') 
        elif msg_type in ['image', 'video', 'document', 'audio', 'sticker']:
            media = msg.get(msg_type, {})
            content_text = media.get('caption', '') or f"[{msg_type.upper()} RECEIVED]"
            media_metadata = {
                'id': media.get('id'),
                'mime_type': media.get('mime_type'),
                'sha256': media.get('sha256')
            }
            
            # STRICT AI SAFETY: Auto-escalate Audio/Document/Sticker to Human
            if msg_type in ['audio', 'document', 'sticker']:
                if conversation:
                    if not conversation.is_human_controlled:
                        conversation.is_human_controlled = True
                        conversation.save(update_fields=['is_human_controlled'])
                        logger.info(f"🛡️ Safety Escalation: {msg_type} from {wa_id} -> Human Takeover")
                        # Optional: Notify user? "I've paused AI to let a human review your file."
        
        elif msg_type == 'location':
            loc = msg.get('location', {})
            content_text = f"Location: {loc.get('latitude')}, {loc.get('longitude')}"
        elif msg_type == 'contacts':
            content_text = "[CONTACTS RECEIVED]"

        # Check for explicit resume command
        if content_text.strip().lower() == "/ai resume":
            if conversation:
                conversation.is_human_controlled = False
                conversation.save(update_fields=['is_human_controlled'])
                logger.info(f"🤖 AI Resumed for {wa_id}")
                continue # Skip processing this message

        # 3. Log Inbound Message (Audit)
        try:
             # Fix: Idempotency check to prevent "duplicate key" crash
             if not WhatsAppMessage.objects.filter(meta_message_id=msg_id).exists():
                 WhatsAppMessage.objects.create(
                     credential=credential,
                     conversation=conversation, # May be None
                     user_phone_number=wa_id,   # New field for quick lookup
                     direction='inbound',
                     # message_id=msg_id, # FIX: Model does not have this field
                     meta_message_id=msg_id,
                     message_type=msg_type,
                     content=msg, # Store raw full payload
                     timestamp=timezone.now()
                 )
             else:
                 logger.info(f"Duplicate message {msg_id} skipped.")
        except Exception as e:
            logger.error(f"Failed to log inbound message: {e}")
            
        # 4. Trigger Workflows
        # Pass conversation state so the Trigger Node can decide whether to halt.
        trigger_workflows(credential, wa_id, content_text, msg, conversation)


def trigger_workflows(credential, user_phone, text, raw_msg, conversation):
    """
    Triggers workflows listening to this credential.
    """
    # Import Core Engine Task
    from ..tasks import execute_workflow_with_core_engine
    
    # 1. Find Workflows
    # Optimization: Filter by workflows owned by credential owner
    workflows = Workflow.objects.filter(
        owner=credential.owner,
        status='published'
    )
    
    triggered = False
    for wf in workflows:
        nodes = wf.graph.get('nodes', [])
        for node in nodes:
            node_type = (node.get('action_type') or node.get('type', '')).lower()
            
            if node_type == 'whatsapp_trigger':
                # strict credential check
                conf_cred = node.get('config', {}).get('credential_id')
                if conf_cred == str(credential.id):
                    
                    # Prepare Input (Clean & Flat to prevent Circular Reference)
                    input_payload = {
                        'from': user_phone,             # Meta Standard (User requested)
                        'phone_number': user_phone,     # Backward Compatibility
                        'text': text,                   
                        'message_type': raw_msg.get('type'),
                        'sender_name': raw_msg.get('profile', {}).get('name', 'Unknown'), 
                        'wamid': raw_msg.get('id'),
                        'timestamp': raw_msg.get('timestamp'),
                        'conversation_id': str(conversation.id) if conversation else None,
                        'is_human_controlled': conversation.is_human_controlled if conversation else False,
                        'credential_id': str(credential.id),
                        'meta_whatsapp_credential_id': str(credential.id) # Standard naming for dependent nodes
                    }
                    
                    try:
                        logger.info(f"🚀 Triggering Workflow {wf.id} (WhatsApp)")
                        
                        # FIX: Manually create execution to set triggered_by='webhook'
                        import uuid
                        execution = WorkflowExecution.objects.create(
                            workflow=wf,
                            tenant=wf.tenant,
                            status='pending',
                            input_payload=input_payload,
                            triggered_by='webhook',
                            created_by=wf.owner,
                            fingerprint=str(uuid.uuid4())
                        )
                        
                        # Execute using Core Engine Task (Async)
                        execute_workflow_with_core_engine.delay(str(execution.id))
                        
                    except Exception as e:
                        logger.error(f"Workflow Trigger Failed: {e}", exc_info=True)
