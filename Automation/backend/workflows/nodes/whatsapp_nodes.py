from .base_node import TriggerNode, ActionNode, NodeExecutionError
from ..models import Credential, WhatsAppConversation, WhatsAppUsage, WhatsAppMessage, WhatsAppTemplate
from django.utils import timezone
import requests
import json
import logging
from datetime import timedelta
from ..utils.credential_resolver import resolve_credential_data

logger = logging.getLogger(__name__)

# WhatsAppTriggerNode moved to triggers/whatsapp_trigger.py


class WhatsAppSendNode(ActionNode):
    """
    PHASE 4: WhatsApp Send (State Machine)
    Strict lifecycle and limit enforcement.
    """
    NODE_TYPE = "whatsapp_send"
    CATEGORY = "communication"
    DISPLAY_NAME = "WhatsApp Send"
    DESCRIPTION = "Send a message via WhatsApp (Meta)"

    def evaluate_expression(self, value, input_data, context):
        """
        Evaluate expression using BaseNode's template resolution.
        Proxies to _resolve_templates which handles strings, dicts, lists safe.
        """
        return self._resolve_templates(value, input_data, context)

    def run(self, input_data, params, context):
        config = self.config
        
        # 1. Resolve Config (Static + Dynamic Params)
        if params: config.update(params)

        # 2. Resolve Inputs
        credential_id = config.get("credential_id")
        # Support both old 'phone_number' and new 'recipient_number'
        recipient = self.evaluate_expression(config.get("recipient_number") or config.get("phone_number"), input_data, context)
        if isinstance(recipient, str):
            recipient = recipient.strip()
        message_type = config.get("message_type") or config.get("message_mode", "text") 
        
        # Resolve Content or Template Variables
        content = self.evaluate_expression(config.get("message_text") or config.get("message_content", ""), input_data, context)
        
        # Optional Template Overrides
        template_name_override = config.get("template_name")
        template_language = config.get("template_language", "en_US")
        
        # Robust Template Params Parsing (JSON array or CSV)
        raw_params = config.get("template_params", "")
        template_params = []
        if raw_params:
            if isinstance(raw_params, list):
                template_params = raw_params
            elif isinstance(raw_params, str):
                try:
                    parsed = json.loads(raw_params)
                    template_params = parsed if isinstance(parsed, list) else [str(parsed)]
                except:
                    # Fallback to CSV
                    template_params = [p.strip() for p in raw_params.split(",") if p.strip()]
        
        # FIX: Resolve Templates in Params
        template_params = self._resolve_templates(template_params, input_data, context)


        
        # --- SMART FALLBACK FOR TEXT ---
        if message_type == 'text' and not content:
            # Try to get from main input
            main_input = context.get('inputs', {}).get('main', [])
            if main_input:
                if isinstance(main_input, list) and len(main_input) > 0:
                    first = main_input[0]
                    if isinstance(first, dict):
                        # Handle AI Agent dictionary output
                        content = first.get('response') or first.get('text') or first.get('content')
                        if not content:
                            content = json.dumps(first)
                    else:
                        content = str(first)
            
            # Fallback to input_data
            # Fallback to input_data
            if not content and input_data:
                 if isinstance(input_data, dict):
                     # Handle AI Agent dictionary output
                     content = input_data.get('response') or input_data.get('text') or input_data.get('content')
                     if not content:
                         content = json.dumps(input_data)
                 else:
                     content = str(input_data)

        if not credential_id or not recipient:
            raise NodeExecutionError("WhatsApp Account and Recipient Number are required")

        # 3. Get Credential
        try:
            credential = Credential.objects.get(id=credential_id)
        except Credential.DoesNotExist:
            raise NodeExecutionError("WhatsApp Credential not found")
        
        # Use robust resolver for decrypted data
        config = resolve_credential_data(credential)
        
        # Primary keys with Fallback for legacy
        phone_number_id = str(config.get("phone_number_id") or config.get("phone_id") or "").strip()
        access_token = str(config.get("access_token") or config.get("token") or "").strip()
        
        # Debug Logging (Hardened)
        logger.info(f"📌 Phone Number ID: {phone_number_id}")
        logger.info(f"📌 Token Present: {bool(access_token)}")

        if not phone_number_id or not access_token:
            raise NodeExecutionError(f"Invalid WhatsApp Credential: phone_number_id={phone_number_id}, token_present={bool(access_token)}")

        # 4. Determine Conversation State
        conversation = WhatsAppConversation.objects.filter(
            credential=credential,
            user_phone_number=recipient,
            is_active=True
        ).order_by('-started_at').first()

        metrics = self._get_service_window_status(credential, recipient, conversation)
        is_service_window_open = metrics['window_open']
        
        # 5. State Machine Execution
        start_new_conversation = False
        if conversation:
            if conversation.expires_at and timezone.now() > conversation.expires_at:
                conversation.is_active = False
                conversation.save()
                conversation = None
        
        if not conversation:
            start_new_conversation = True
        
        if start_new_conversation:
             if not self._check_and_increment_usage(credential):
                 raise NodeExecutionError("Monthly WhatsApp Limit Exceeded (1000).")
             
             expiry = metrics['last_user_ts'] + timedelta(hours=24) if metrics['last_user_ts'] else timezone.now() + timedelta(hours=24)
             if not metrics['last_user_ts']:
                 expiry = timezone.now() + timedelta(hours=24)
                      
             conversation = WhatsAppConversation.objects.create(
                 credential=credential,
                 user_phone_number=recipient,
                 started_at=timezone.now(),
                 expires_at=expiry,
                 is_active=True
             )
        
        # 6. Build API Request
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient,
        }
        
        if message_type == 'text':
            if not content:
                raise NodeExecutionError("Message text is required for Text mode.")
            payload["type"] = "text"
            payload["text"] = {"body": content, "preview_url": config.get("preview_url", False)}

        elif message_type == 'template':
            template_name = self.evaluate_expression(config.get("template_name", ""), input_data, context)
            template_lang = config.get("template_language", "en_US")
            
            if not template_name:
                raise NodeExecutionError("Template Name is required for Template mode.")

            # Strict Template Validation (Local)
            try:
                tpl = WhatsAppTemplate.objects.get(credential=credential, name=template_name, language=template_lang)
                if tpl.status != 'approved':
                    logger.warning(f"Template '{template_name}' state is {tpl.status}. Attempting to send anyway.")
            except WhatsAppTemplate.DoesNotExist:
                logger.warning(f"Template '{template_name}' not found in local DB. Proceeding with caution.")
                
            payload["type"] = "template"
            payload["template"] = {
                "name": template_name,
                "language": {"code": template_lang}
            }

            # Handle Template Variables (JSON)
            raw_vars = config.get("template_variables")
            if raw_vars:
                try:
                    if isinstance(raw_vars, str):
                        vars_data = json.loads(raw_vars)
                    else:
                        vars_data = raw_vars
                    
                    # FIX: Resolve Templates in Variables
                    vars_data = self._resolve_templates(vars_data, input_data, context)

                    if isinstance(vars_data, list):
                        payload["template"]["components"] = vars_data
                except Exception as e:
                    raise NodeExecutionError(f"Invalid JSON in Template Variables: {e}")

            # Handle Buttons Payload (Optional)
            buttons = config.get("buttons_payload")
            if buttons:
                try:
                    if isinstance(buttons, str):
                        buttons_data = json.loads(buttons)
                    else:
                        buttons_data = buttons
                    
                    # Merge buttons into components if not already present
                    if "components" not in payload["template"]:
                        payload["template"]["components"] = []
                    
                    # Example of adding buttons safely
                    if isinstance(buttons_data, list):
                        payload["template"]["components"].extend(buttons_data)
                except:
                    logger.warning("Failed to parse buttons_payload as JSON. Skipping.")

        # 7. Send Request (Retry Logic)
        url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # FINAL DEBUG LOG (User Requested)
        logger.info(f"📤 [WHATSAPP DEBUG] Sending to: {recipient} via PhoneID: {phone_number_id}")
        logger.info(f"📤 [WHATSAPP DEBUG] Payload: {json.dumps(payload)}")
        
        try:
            res_json = self._send_with_retry(url, headers, payload)

            wamid = res_json.get('messages', [{}])[0].get('id')
            
            # 8. Log & Update
            logger.info("✅ Message Delivered")
            if conversation:
                conversation.last_business_message_at = timezone.now()
                conversation.save()
            
            WhatsAppMessage.objects.create(
                credential=credential,
                conversation=conversation,
                direction='outbound',
                message_type=message_type,
                meta_message_id=wamid,
                content=res_json,
                status='sent',
                timestamp=timezone.now()
            )
            
            return {
                "success": True,
                "output": {
                    "status": "sent",
                    "recipient": recipient,
                    "wamid": wamid,
                    "raw": res_json
                }
            }
            
        except Exception as e:
            error_msg = str(e)
            # Detect 24h window expiry or Template Requirement
            is_24h_error = any(x in error_msg.lower() for x in ["outside 24h window", "use template"]) or "131047" in error_msg
            
            if is_24h_error:
                logger.warning("⚠️ 24h window expired → switching to template mode")
                
                # 1. Determine Template Name (User-provided or Priority List)
                template_name = template_name_override
                if not template_name:
                    priority_list = ["order_confirmed", "delivery_update", "feedback_request", "hello_world"]
                    template_name = priority_list[0] # Default to first in priority
                
                logger.info(f"📤 Sending template: {template_name}")
                
                # 2. Construct Template Payload
                fallback_payload = {
                    "messaging_product": "whatsapp",
                    "to": recipient,
                    "type": "template",
                    "template": {
                        "name": template_name,
                        "language": {"code": template_language}
                    }
                }
                
                if template_params:
                    fallback_payload["template"]["components"] = [{
                        "type": "body",
                        "parameters": [{"type": "text", "text": str(p)} for p in template_params]
                    }]
                
                # 3. Send Fallback
                try:
                    fallback_res = self._send_with_retry(url, headers, fallback_payload)
                    logger.info("✅ Template message delivered successfully")
                    
                    # Log Fallback Success
                    WhatsAppMessage.objects.create(
                        credential=credential,
                        conversation=conversation,
                        direction='outbound',
                        message_type='template_fallback',
                        meta_message_id=fallback_res.get('messages', [{}])[0].get('id'),
                        content=fallback_res,
                        status='sent',
                        timestamp=timezone.now()
                    )

                    return {
                        "success": True,
                        "mode": "template_fallback",
                        "template_used": template_name,
                        "output": {
                            "status": "sent",
                            "recipient": recipient,
                            "raw": fallback_res
                        }
                    }
                except Exception as fallback_err:
                    logger.error(f"Fallback Template Failed: {fallback_err}")
                    return {"success": False, "error": f"Original Error: {error_msg} | Fallback Error: {str(fallback_err)}"}

            logger.error(f"WhatsApp Send Failed: {e}")
            return {"success": False, "error": str(e)}

    def _send_with_retry(self, url, headers, payload, max_retries=3):
        """
        Sends request with exponential backoff for transient errors.
        """
        import time
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=10)
                
                # Success
                if response.status_code in [200, 201]:
                    return response.json()
                
                # Client Error (4xx) - Fail Fast (except 429)
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    try:
                        err_body = response.json()
                        err_msg = err_body.get('error', {}).get('message', response.text)
                        # CRITICAL DEBUG: Print full error body
                        print(f"❌ [META ERROR BODY]: {json.dumps(err_body)}")
                        logger.error(f"❌ [META ERROR BODY]: {json.dumps(err_body)}")
                    except:
                        err_msg = response.text
                    raise NodeExecutionError(f"Client Error ({response.status_code}): {err_msg}")

                
                # Retryable Errors (429, 5xx)
                logger.warning(f"Meta API Retryable Error ({response.status_code}). Attempt {attempt+1}/{max_retries}")
                last_error = f"HTTP {response.status_code}: {response.text}"
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Network Error: {e}. Attempt {attempt+1}/{max_retries}")
                last_error = str(e)
            
            # Backoff
            time.sleep(2 ** attempt)
        
        raise NodeExecutionError(f"Failed after {max_retries} attempts. Last error: {last_error}")

    def _get_service_window_status(self, credential, phone, conversation):
        """
        Check if we are within 24h of last user message.
        """
        last_ts = None
        if conversation and conversation.last_user_message_at:
            last_ts = conversation.last_user_message_at
        else:
            # Check logs
            last_msg = WhatsAppMessage.objects.filter(
                credential=credential,
                direction='inbound',
                user_phone_number=phone
            ).order_by('-timestamp').first()
            
            if last_msg:
                last_ts = last_msg.timestamp
            
        window_open = False
        if last_ts:
            if timezone.now() < last_ts + timedelta(hours=24):
                window_open = True
        
        return {'window_open': window_open, 'last_user_ts': last_ts}

    def _check_and_increment_usage(self, credential):
        """
        Checks 1000 limit. Increments if allowed.
        """
        current_month = timezone.now().strftime('%Y-%m')
        usage, _ = WhatsAppUsage.objects.get_or_create(credential=credential, month=current_month)
        
        if usage.conversation_count >= 1000:
            return False
            
        if usage.conversation_count == 900 and not usage.warning_sent:
            usage.warning_sent = True
            usage.save()
            logger.warning(f"⚠️ WhatsApp Soft Limit (900) reached for {credential.name}")
            
        usage.conversation_count += 1
        usage.save()
        return True

    @classmethod
    def get_schema(cls):
        return {
            "type": "object",
            "properties": {
                "credential_id": {
                    "type": "string",
                    "title": "WhatsApp Account",
                    "widget": "credential_select",
                    "widgetOptions": {"credentialType": ["meta_whatsapp"]},
                    "required": True
                },
                "recipient_number": {
                    "type": "string",
                    "title": "Recipient Number",
                    "description": "Phone number with country code (e.g. 1234567890). Supports templates.",
                    "required": True
                },
                "message_type": {
                    "type": "string",
                    "title": "Message Type",
                    "enum": ["text", "template"],
                    "default": "text"
                },
                "message_text": {
                    "type": "string",
                    "title": "Message Text",
                    "widget": "textarea",
                    "description": "If empty, uses incoming data. Supports templates.",
                    "displayOptions": {
                        "show": {
                            "message_type": ["text"]
                        }
                    }
                },
                "template_name": {
                    "type": "string",
                    "title": "Template Name",
                    "description": "Used in Template mode OR as fallback for 24h window errors. Exactly as in Meta dashboard.",
                    "displayOptions": {
                        "show": {
                            "message_type": ["template", "text"]
                        }
                    }
                },
                "template_language": {
                    "type": "string",
                    "title": "Template Language",
                    "default": "en_US",
                    "displayOptions": {
                        "show": {
                            "message_type": ["template", "text"]
                        }
                    }
                },
                "template_params": {
                    "type": "string",
                    "title": "Template Params (Simplified)",
                    "description": 'Comma-separated values or JSON array for body params: ["Ansh", "Pizza"]',
                    "displayOptions": {
                        "show": {
                            "message_type": ["template", "text"]
                        }
                    }
                },
                "template_variables": {
                    "type": "string",
                    "title": "Template Components (Advanced JSON)",
                    "widget": "textarea",
                    "placeholder": '[{"type": "body", "parameters": [{"type": "text", "text": "val"}]}]',
                    "displayOptions": {
                        "show": {
                            "message_type": ["template"]
                        }
                    }
                },
                "header_media_url": {
                    "type": "string",
                    "title": "Header Media URL",
                    "description": "Optional image/video URL for header. Supports templates.",
                    "displayOptions": {
                        "show": {
                            "message_type": ["template"]
                        }
                    }
                },
                "buttons_payload": {
                    "type": "string",
                    "title": "Buttons Payload (JSON)",
                    "widget": "textarea",
                    "displayOptions": {
                        "show": {
                            "message_type": ["template"]
                        }
                    }
                }
            },
            "required": ["credential_id", "recipient_number"]
        }
