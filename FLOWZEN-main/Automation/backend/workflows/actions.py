"""
Action implementations for different node types.
Each action is a callable that takes (node, items, context) and returns items list or dict.
"""
import json
import time
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Callable, Optional, List
from jinja2 import Template, Environment, BaseLoader
import logging
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
import redis
from django.conf import settings
import base64



from workflows.expression_evaluator import ExpressionEvaluator
# Import extended action library
from workflows.actions_library import (
    openai_chat_action,
    image_generator_action,
    whatsapp_send_action,
    telegram_send_action,
    slack_message_action,
    sentiment_analysis_action,
    json_processor_action,
    csv_processor_action,
    switch_action,
    date_time_action,
    crypto_action,
    random_generator_action,
    markdown_action,
    rss_reader_action
)

logger = logging.getLogger(__name__)



from workflows.context import ActionContext, render_template


def http_request_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """
    Execute HTTP request action - processes items.
    
    Config format:
    {
        "method": "GET|POST|PUT|DELETE",
        "url": "https://api.example.com/{{ $json.user_id }}",
        "headers": {"Authorization": "Bearer {{ $json.token }}"},
        "body": "{{ $json }}",
        "timeout": 30,
        "execution_mode": "each"  # each, all, batch
    }
    """
    config = node.config
    method = config.get("method", "GET").upper()
    url_template = config.get("url", "")
    headers_template = config.get("headers", {})
    body_template = config.get("body")
    timeout = config.get("timeout", 30)
    execution_mode = config.get("execution_mode", "each")
    
    # Load credential if specified
    credential_headers = {}
    credential_id = config.get("credential_id")
    if credential_id and node.credential:
        try:
            credential_headers = node.credential.get_auth_header()
        except Exception as e:
            logger.warning(f"Failed to load credential: {e}")
    
    def redact(obj):
        try:
            if isinstance(obj, dict):
                out = {}
                for k, v in obj.items():
                    lk = str(k).toLowerCase() if hasattr(k, 'lower') else str(k).lower()
                    if any(s in lk for s in ["authorization","token","password","secret","api_key","apikey","key"]):
                        out[k] = "***"
                    else:
                        out[k] = redact(v)
                return out
            if isinstance(obj, list):
                return [redact(x) for x in obj]
            return obj
        except Exception:
            return obj
    
    def oauth2_refresh_if_needed(resp, headers):
        try:
            if resp.status_code != 401:
                return headers
            cred = getattr(node, "credential", None)
            if not cred or cred.type != "oauth2":
                return headers
            data = cred.encrypted_data or {}
            refresh_token = data.get("refresh_token")
            token_url = data.get("token_url")
            client_id = data.get("client_id")
            client_secret = data.get("client_secret")
            if not (refresh_token and token_url and client_id):
                return headers
            # Refresh
            r = requests.post(token_url, data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret or "",
            }, timeout=timeout)
            if r.status_code == 200:
                token_json = {}
                try:
                    token_json = r.json()
                except Exception:
                    token_json = {}
                access_token = token_json.get("access_token")
                if access_token:
                    # Update model
                    data["access_token"] = access_token
                    try:
                        node.credential.encrypted_data = data
                        node.credential.save(update_fields=["encrypted_data"])
                    except Exception:
                        pass
                    headers["Authorization"] = f"Bearer {access_token}"
            return headers
        except Exception as e:
            logger.warning(f"OAuth2 refresh failed: {e}")
            return headers
    
    output_items = []
    
    if execution_mode == "each":
        # Process each item separately
        for idx, item in enumerate(items):
            context.item_index = idx
            
            # Evaluate expressions
            url = context.evaluate(url_template)
            headers = {}
            for key, value_template in headers_template.items():
                headers[key] = str(context.evaluate(value_template))
            
            # Inject credential headers
            headers.update(credential_headers)
            
            body = None
            if body_template:
                body = context.evaluate(body_template)
            
            # Make HTTP request
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body if isinstance(body, dict) else None,
                    data=body if isinstance(body, str) else None,
                    timeout=timeout,
                )
                
                # Attempt refresh if unauthorized
                if response.status_code == 401:
                    headers = oauth2_refresh_if_needed(response, headers)
                    if headers.get("Authorization"):  # Retry once
                        response = requests.request(
                            method=method,
                            url=url,
                            headers=headers,
                            json=body if isinstance(body, dict) else None,
                            data=body if isinstance(body, str) else None,
                            timeout=timeout,
                        )
                
                output_item = {
                    "json": {
                        "status_code": response.status_code,
                        "headers": redact(dict(response.headers)),
                        "body": (
                            redact(response.json())
                            if response.headers.get("content-type", "").startswith("application/json")
                            else response.text
                        ),
                        "success": 200 <= response.status_code < 300,
                        "request": {
                            "method": method,
                            "url": url,
                            "headers": redact(headers),
                            "body": redact(body) if isinstance(body, (dict, list)) else (str(body)[:512] if isinstance(body, str) else None),
                        }
                    },
                    "binary": {}
                }
                output_items.append(output_item)
                
            except requests.exceptions.RequestException as e:
                output_item = {
                    "json": {
                        "error": str(e),
                        "success": False,
                        "request": {
                            "method": method,
                            "url": url,
                            "headers": redact(headers),
                            "body": redact(body) if isinstance(body, (dict, list)) else (str(body)[:512] if isinstance(body, str) else None),
                        }
                    },
                    "binary": {}
                }
                output_items.append(output_item)
    elif execution_mode == "all":
        # Process all items in one request (merge items)
        # For now, process as batch
        pass
    elif execution_mode == "batch":
        # Process in batches
        batch_size = config.get("batch_size", 10)
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            # Process batch
            pass
    
    return output_items


def email_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """
    Send email action with automatic Gmail OAuth / SMTP routing.
    
    ROUTING LOGIC:
    - Gmail addresses (@gmail.com) -> Gmail OAuth API (requires OAuth credential)
    - All other addresses -> SMTP (uses Django settings or custom config)
    
    PHASE-1: Uses NodeEffect to prevent duplicate sends on retries.
    
    Config format:
    {
        "from": "sender@example.com",  # Auto-routes based on domain
        "to": "{{ $json.email }}",
        "subject": "Notification",
        "body": "Hello {{ $json.name }}",
        "is_html": false,
        # Optional SMTP config for non-Gmail addresses:
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_user": "user@example.com",
        "smtp_password": "password",
        "smtp_use_tls": true
    }
    """
    from workflows.services.node_effect_service import NodeEffectService, EffectAlreadyApplied
    from workflows.services.email_routing_service import get_email_routing_service, EmailRoutingError
    
    config = node.config if hasattr(node, 'config') else (node if isinstance(node, dict) else {})
    if not isinstance(config, dict):
        config = {}
    
    output_items = []
    
    # PHASE-1: Get execution/node_execution for NodeEffect
    execution = context.execution
    node_execution = context.node_execution
    node_id = getattr(node, 'node_id', None) or (config.get('node_id') if isinstance(config, dict) else None) or "unknown"
    
    # Get email routing service
    tenant = execution.tenant if execution else None
    email_service = get_email_routing_service(tenant=tenant)
    
    for idx, item in enumerate(items):
        context.item_index = idx
        
        # Evaluate expressions - support both formats
        to_email = context.evaluate(config.get("to") or config.get("to_email", ""))
        subject = context.evaluate(config.get("subject", ""))
        body = context.evaluate(config.get("body", ""))
        
        # Prepare SMTP config
        smtp_config = None
        
        # Determine routing based on credential type if available, otherwise fallback to domain check
        use_gmail_service = False
        
        if credential_id:
            try:
                from .models import Credential
                cred = Credential.objects.get(id=credential_id)
                
                if cred.type == 'gmail_oauth':
                    use_gmail_service = True
                    # Ensure from_email is set to credential's email if not overridden
                    if not from_email:
                        try:
                            from workflows.services.gmail_oauth_service import GmailOAuthService
                            service = GmailOAuthService()
                            data = service._decrypt_credential_data(cred)
                            from_email = data.get('email')
                        except:
                            from_email = cred.encrypted_data.get('email') if isinstance(cred.encrypted_data, dict) else None
                            
                elif cred.type == 'smtp':
                    use_gmail_service = False
                    # Extract SMTP details from credential
                    from workflows.services.credential_encryption import get_encryption_service
                    enc_service = get_encryption_service()
                    data = cred.encrypted_data
                    if isinstance(data, str) and enc_service:
                        data = enc_service.decrypt_credential_str(data)
                    
                    if not isinstance(data, dict):
                         data = {}

                    smtp_config = {
                        "host": data.get("host"),
                        "port": int(data.get("port", 587)),
                        "username": data.get("username"),
                        "password": data.get("password"),
                        "use_tls": data.get("use_tls", True),
                        "use_ssl": data.get("use_ssl", False),
                    }
                    
                    # If from_email is missing, try to use username as fallback
                    if not from_email:
                        from_email = data.get("username")
                        
            except Exception as e:
                logger.error(f"Error loading credential {credential_id}: {e}")

        # Fallback to legacy behavior if no credential object or partial config
        if not smtp_config and not use_gmail_service and not email_service.is_gmail_address(from_email):
             smtp_config = {}
             if config.get("smtp_host"):
                smtp_config = {
                    "host": config.get("smtp_host"),
                    "port": config.get("smtp_port", 587),
                    "username": config.get("smtp_user", ""),
                    "password": config.get("smtp_password", ""),
                    "use_tls": config.get("smtp_use_tls", True),
                    "use_ssl": config.get("smtp_use_ssl", False),
                }
        
        # PHASE-1: Compute effect token per recipient
        to_list = [e.strip() for e in str(to_email).split(",") if e.strip()]
        recipients_sent = []
        recipients_skipped = []
        
        for recipient in to_list:
            # Compute effect token for this recipient
            input_hash_data = {
                "to": recipient,
                "subject": subject,
                "body": body,
                "from": from_email,
                "routing_method": "gmail_oauth" if email_service.is_gmail_address(from_email) else "smtp"
            }
            effect_token = NodeEffectService.compute_effect_token(
                execution_id=context.execution_id,
                node_id=node_id,
                input_data=input_hash_data,
                recipient=recipient,  # Per-recipient effects
            )
            
            # PHASE-1: Check if effect already applied
            if execution and execution.tenant:
                if NodeEffectService.check_effect_applied(execution.tenant, effect_token):
                    logger.info(f"Email effect already applied for {recipient} (token: {effect_token[:16]}...)")
                    recipients_skipped.append({
                        "recipient": recipient,
                        "skipped": True,
                        "reason": "already_sent",
                        "method": "gmail_oauth" if email_service.is_gmail_address(from_email) else "smtp"
                    })
                    continue
            
            try:
                # CRITICAL: Extract user and tenant from execution context
                user = context.execution_context.get("user")
                tenant = context.execution_context.get("tenant")
                
                if not user and execution:
                    # Fallback: Get user from execution input_payload (support _user_id and user_id)
                    payload = execution.input_payload or {}
                    user_id = payload.get('_user_id') or payload.get('user_id')
                    
                    if user_id:
                        try:
                            from django.contrib.auth.models import User
                            user = User.objects.get(id=int(user_id))
                        except (User.DoesNotExist, ValueError):
                            logger.warning(f"User {user_id} not found for execution {execution.id}")

                if not tenant and execution:
                     tenant = execution.tenant
                
                # CRITICAL LOGGING: Verify context is available
                logger.critical(f"🔥 EMAIL ACTION CONTEXT: USER={user.id if user else None}, TENANT={tenant.id if tenant else None}")
                
                # STRICT VALIDATION: For Gmail addresses, REQUIRE user and tenant
                if email_service.is_gmail_address(from_email):
                    if not user:
                        raise EmailRoutingError(
                            f"Gmail address {from_email} requires user context. "
                            "Please ensure workflow execution includes user authentication."
                        )
                    
                    if not tenant:
                        # Try execution tenant again
                        if execution and execution.tenant:
                            tenant = execution.tenant
                        else:
                            raise EmailRoutingError(
                                f"Gmail address {from_email} requires tenant context. "
                                "Please ensure workflow execution includes tenant context."
                            )
                
                # Route email based on credential type if known, otherwise fallback to domain routing
                if use_gmail_service:
                    # Force Gmail OAuth regardless of domain (supports Google Workspace)
                     result = email_service._send_via_gmail_oauth(
                        to=recipient,
                        subject=subject,
                        body=body,
                        from_email=from_email,
                        is_html=is_html,
                        user=user,
                        tenant=tenant
                    )
                else:
                    # Standard routing (SMTP or auto-detect)
                    # For strict Gmail enforcement, checks are inside send_email usually, 
                    # but we rely on email_service.is_gmail_address check above.
                    result = email_service.send_email(
                        to=recipient,
                        subject=subject,
                        body=body,
                        from_email=from_email,
                        is_html=is_html,
                        smtp_config=smtp_config,
                        user=user,  # CRITICAL: Pass user context
                        tenant=tenant  # CRITICAL: Pass tenant context
                    )
                
                # PHASE-1: Record effect AFTER successful send
                if execution and node_execution and execution.tenant:
                    try:
                        NodeEffectService.record_effect(
                            execution=execution,
                            node_execution=node_execution,
                            node_id=node_id,
                            effect_token=effect_token,
                            effect_type="email_sent",
                            effect_data={
                                "recipient": recipient,
                                "subject": subject,
                                "from": from_email,
                                "method": result.get("method", "unknown")
                            }
                        )
                    except EffectAlreadyApplied:
                        # Race condition - another worker already sent
                        logger.warning(f"Effect token {effect_token[:16]}... already exists (race condition)")
                        recipients_skipped.append({
                            "recipient": recipient,
                            "skipped": True,
                            "reason": "already_sent",
                            "method": result.get("method", "unknown")
                        })
                        continue
                
                recipients_sent.append({
                    "recipient": recipient,
                    "success": True,
                    "method": result.get("method", "unknown"),
                    "message_id": result.get("message_id")
                })
                
            except EmailRoutingError as e:
                logger.error(f"Email routing failed for {recipient}: {e}")
                recipients_sent.append({
                    "recipient": recipient,
                    "success": False,
                    "error": str(e),
                    "method": "gmail_oauth" if email_service.is_gmail_address(from_email) else "smtp"
                })
            except Exception as e:
                logger.error(f"Email action failed for {recipient}: {e}", exc_info=True)
                recipients_sent.append({
                    "recipient": recipient,
                    "success": False,
                    "error": str(e),
                    "method": "gmail_oauth" if email_service.is_gmail_address(from_email) else "smtp"
                })
            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                logger.error(f"Email action CRITICAL FAILURE: {e}\n{error_trace}")
                recipients_sent.append({
                    "recipient": recipient,
                    "success": False,
                    "error": str(e),
                    "method": "unknown"
                })
        
        # Aggregate results
        output_item = {
            "success": len(recipients_sent) > 0 and all(r.get("success", False) for r in recipients_sent),
            "output": {
                "sent_count": len([r for r in recipients_sent if r.get("success", False)]),
                "recipients": recipients_sent,
            },
            "error": None,
            "json": {
                "success": len(recipients_sent) > 0 and all(r.get("success", False) for r in recipients_sent),
                "recipients": recipients_sent + recipients_skipped,
                "sent_count": len([r for r in recipients_sent if r.get("success", False)]),
                "skipped_count": len(recipients_skipped),
                "routing_info": {
                    "from_email": from_email,
                    "is_gmail": email_service.is_gmail_address(from_email),
                    "method": "gmail_oauth" if email_service.is_gmail_address(from_email) else "smtp"
                }
            },
            "binary": {}
        }
        output_items.append(output_item)
    
    return output_items


def delay_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """
    Delay action - sleep for specified duration.
    Supports seconds, minutes, hours.
    
    Config format:
    {
        "amount": 5,
        "unit": "seconds"  # seconds, minutes, hours
        # OR legacy format:
        "duration": 5  # seconds
    }
    """
    config = node.config if hasattr(node, 'config') else (node if isinstance(node, dict) else {})
    if not isinstance(config, dict):
        config = {}
    
    # Support both new format (amount/unit) and legacy (duration)
    if "amount" in config:
        amount = config.get("amount", 1)
        unit = config.get("unit", "seconds").lower()
        
        # Convert to seconds
        if unit.startswith("min"):
            duration = float(amount) * 60
        elif unit.startswith("hour"):
            duration = float(amount) * 3600
        else:
            duration = float(amount)
    else:
        # Legacy format
        duration_template = config.get("duration", 1)
        if isinstance(duration_template, str):
            duration = context.evaluate(duration_template)
            if not isinstance(duration, (int, float)):
                duration = 1
        else:
            duration = float(duration_template)
    
    # Safety: max 5 minutes
    MAX_DELAY = 300
    if duration > MAX_DELAY:
        logger.warning(f"Delay {duration}s exceeds max {MAX_DELAY}s, capping")
        duration = MAX_DELAY
    
    if duration < 0:
        duration = 0
    
    time.sleep(duration)
    
    # Return items as-is
    return items


def condition_action(node, items: List[Dict], context: ActionContext) -> Dict[str, List[Dict]]:
    """
    Condition action - splits items into true/false branches.
    
    Config format:
    {
        "expression": "{{ $json.status }} == 'active'"
    }
    
    Returns:
        {
            "true": [items that match condition],
            "false": [items that don't match]
        }
    """
    config = node.config
    condition_expression = config.get("expression", "True")
    
    true_items = []
    false_items = []
    
    for idx, item in enumerate(items):
        context.item_index = idx
        
        try:
            result = context.evaluate(condition_expression)
            if result:
                true_items.append(item)
            else:
                false_items.append(item)
        except Exception as e:
            # On error, send to false branch
            false_items.append(item)
    
    return {
        "true": true_items,
        "false": false_items
    }


def transform_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """
    Transform data action - applies transformation to each item.
    
    Config format:
    {
        "transform": {
            "user_id": "{{ $json.id }}",
            "email": "{{ $json.email }}",
            "full_name": "{{ $json.first_name }} {{ $json.last_name }}"
        }
    }
    """
    config = node.config
    transform_template = config.get("transform", {})
    
    output_items = []
    
    for idx, item in enumerate(items):
        context.item_index = idx
        
        # Apply transformation
        transformed_json = {}
        for key, value_template in transform_template.items():
            if isinstance(value_template, str):
                transformed_json[key] = context.evaluate(value_template)
            elif isinstance(value_template, dict):
                # Nested transformation
                nested = {}
                for nkey, nvalue in value_template.items():
                    nested[nkey] = context.evaluate(nvalue) if isinstance(nvalue, str) else nvalue
                transformed_json[key] = nested
            else:
                transformed_json[key] = value_template
        
        output_item = {
            "json": transformed_json,
            "binary": item.get("binary", {})  # Preserve binary data
        }
        output_items.append(output_item)
    
    return output_items


def code_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """
    Code action - execute Python code in safe sandbox.
    
    Config format:
    {
        "code": "result = []\nfor item in items:\n    result.append({'json': {'doubled': item['json']['value'] * 2}})\nreturn result"
    }
    """
    config = node.config if hasattr(node, 'config') else (node if isinstance(node, dict) else {})
    if isinstance(config, dict):
        code = config.get("code", "")
    else:
        code = str(config) if config else ""
    
    if not code:
        return [{
            "json": {
                "error": "No code provided",
                "success": False
            },
            "binary": {}
        }]
    
    try:
        from workflows.code_sandbox import execute_code_safely
        # Execute code in sandbox
        output_items = execute_code_safely(code, items, context.execution_context)
        return output_items
    except Exception as e:
        logger.error(f"Code execution failed: {e}", exc_info=True)
        return [{
            "json": {
                "error": str(e),
                "success": False
            },
            "binary": {}
        }]


def function_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """
    Function Node - execute JavaScript-like code (using Python for now).
    This is an alias for code_action but can be extended for JS execution.
    
    Config format:
    {
        "code": "JavaScript or Python code to execute"
    }
    """
    # For now, use Python code execution
    # In future, can add JS execution via PyMiniRacer or similar
    return code_action(node, items, context)


def script_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """
    Script action (alias for code_action) - execute Python code for each item.
    """
    return code_action(node, items, context)


def loop_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """
    Loop action - processes items in a loop.
    
    Config format:
    {
        "loop_type": "for_each" | "while" | "range",
        "loop_expression": "{{ $json.items }}",  # Array to iterate over
        "item_name": "item",  # Variable name for current item
        "index_name": "index"  # Variable name for current index
    }
    """
    config = node.config
    loop_type = config.get("loop_type", "for_each")
    loop_expression = config.get("loop_expression", "[]")
    item_name = config.get("item_name", "item")
    index_name = config.get("index_name", "index")
    
    output_items = []
    
    for idx, input_item in enumerate(items):
        context.item_index = idx
        
        # Evaluate loop expression to get array to iterate
        loop_array = context.evaluate(loop_expression)
        
        if not isinstance(loop_array, list):
            loop_array = [loop_array] if loop_array else []
        
        # Process each item in loop
        for loop_idx, loop_item in enumerate(loop_array):
            # Create new item with loop context
            loop_context_item = input_item.copy()
            loop_context_item["json"] = loop_context_item.get("json", {}).copy()
            loop_context_item["json"][item_name] = loop_item
            loop_context_item["json"][index_name] = loop_idx
            loop_context_item["json"]["_loop"] = {
                "index": loop_idx,
                "total": len(loop_array)
            }
            
            output_items.append(loop_context_item)
    
    return output_items


def merge_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """
    Merge action - merges items from multiple input branches.
    
    Config format:
    {
        "merge_strategy": "append" | "merge" | "keep_first" | "keep_last",
        "merge_keys": ["id"]  # Keys to match items for merging
    }
    """
    config = node.config
    merge_strategy = config.get("merge_strategy", "append")
    merge_keys = config.get("merge_keys", [])
    
    # Get items from all parent nodes
    all_items = []
    for node_id, node_items in context.node_outputs.items():
        all_items.extend(node_items)
    
    if merge_strategy == "append":
        # Simply append all items
        return all_items
    elif merge_strategy == "merge" and merge_keys:
        # Merge items with matching keys
        merged = {}
        for item in all_items:
            item_json = item.get("json", {})
            key_value = tuple(item_json.get(key) for key in merge_keys)
            if key_value in merged:
                # Merge JSON data
                merged[key_value]["json"].update(item_json)
            else:
                merged[key_value] = item.copy()
        return list(merged.values())
    elif merge_strategy == "keep_first":
        return all_items[:1] if all_items else []
    elif merge_strategy == "keep_last":
        return all_items[-1:] if all_items else []
    else:
        return all_items


def set_variables_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """
    Set Variables action - sets variables in execution context.
    
    Config format:
    {
        "variables": {
            "var1": "{{ $json.value }}",
            "var2": "static_value"
        }
    }
    """
    config = node.config
    variables_template = config.get("variables", {})
    
    output_items = []
    
    for idx, item in enumerate(items):
        context.item_index = idx
        
        # Evaluate and set variables
        variables = {}
        for var_name, var_value_template in variables_template.items():
            if isinstance(var_value_template, str):
                variables[var_name] = context.evaluate(var_value_template)
            else:
                variables[var_name] = var_value_template
        
        # Add variables to item JSON
        output_item = item.copy()
        output_item["json"] = output_item.get("json", {}).copy()
        output_item["json"]["_variables"] = variables
        
        # Also add to execution context for downstream nodes
        if context.execution_context:
            context.execution_context.update(variables)
        
        output_items.append(output_item)
    
    return output_items


# AI Agent Action Wrapper
def ai_agent_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """
    Wrapper for AIAgentNode execution.
    """
    try:
        from workflows.nodes.ai_agent_node import AIAgentNode
        
        # Construct node data for initialization
        node_data = {
            "id": getattr(node, "node_id", "unknown"),
            "type": "ai_agent",
            "config": node.config if hasattr(node, "config") else (node if isinstance(node, dict) else {})
        }
        
        agent_node = AIAgentNode(node_data)
        
        # Prepare context
        exec_context = {
            "execution_id": context.execution_id,
            "execution_context": context.execution_context,
            "tenant_id": context.execution.tenant_id if context.execution else None,
            "user_id": context.execution.created_by_id if context.execution else None
        }
        
        # Execute node run method ONCE with ALL inputs (Join behavior)
        # AIAgentNode expects a list of inputs to resolve multi-port data
        result = agent_node.run(
            input_data=items,
            context=exec_context
        )
        
        # Result should be a single output item (or list, but agent usually returns one response)
        # Wrap it in standard item structure
        output_data = result.get("output", result)
        
        return [{
            "json": output_data,
            "success": result.get("success", True),
            "binary": {}
        }]
        
    except Exception as e:
        logger.error(f"AI Agent Action Failed: {e}", exc_info=True)
        return [{
            "success": False,
            "json": {"error": str(e)},
            "binary": {}
        }]



def get_google_creds(node):
    """Helper to convert stored Google Credential to Google Credentials object."""
    if not node.credential or node.credential.type != 'google_oauth':
        raise ValueError("Node requires a 'google_oauth' credential")
    
    data = node.credential.encrypted_data
    return Credentials(
        token=data.get('token'),
        refresh_token=data.get('refresh_token'),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=data.get('client_id'),
        client_secret=data.get('client_secret'),
        scopes=data.get('scopes', [])
    )

def google_sheets_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    config = node.config
    operation = config.get("operation", "append")
    spreadsheet_id = config.get("spreadsheet_id")
    range_name = config.get("range", "Sheet1!A1")
    
    creds = get_google_creds(node)
    service = build('sheets', 'v4', credentials=creds)
    sheet = service.spreadsheets()

    results = []
    
    for idx, item in enumerate(items):
        context.item_index = idx
        # Evaluate dynamic values
        eval_spreadsheet = context.evaluate(spreadsheet_id)
        eval_range = context.evaluate(range_name)
        
        if operation == "append":
            # Extract row data from 'values' or flat list
            values = item.get("json", {}).get("values", [])
            if not values:
                 # Auto-flatten if no explicit values
                 values = [list(item.get("json", {}).values())]
            
            body = {'values': values}
            res = sheet.values().append(
                spreadsheetId=eval_spreadsheet, range=eval_range,
                valueInputOption="USER_ENTERED", body=body).execute()
            results.append({"json": res, "success": True})
            
        elif operation == "read":
            res = sheet.values().get(spreadsheetId=eval_spreadsheet, range=eval_range).execute()
            rows = res.get('values', [])
            # Convert rows to items
            for row in rows:
                results.append({"json": {"row": row}, "success": True})

    return results

def google_drive_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    config = node.config
    operation = config.get("operation", "list")
    
    creds = get_google_creds(node)
    service = build('drive', 'v3', credentials=creds)
    
    results = []
    
    for idx, item in enumerate(items):
        context.item_index = idx # Propagate context if needed for evaluation
        
        if operation == "list":
            query = config.get("query", "")
            res = service.files().list(q=query, pageSize=10).execute()
            files = res.get('files', [])
            for f in files:
                results.append({"json": f, "success": True})
                
        elif operation == "upload":
            # Very basic upload logic (stub) - usually requires BinaryFile handling
            pass
            
    if not results: return items # Passthrough if no op
    return results

def youtube_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    config = node.config
    operation = config.get("operation", "search")
    
    creds = get_google_creds(node)
    service = build('youtube', 'v3', credentials=creds)
    
    results = []
    for idx, item in enumerate(items):
        context.item_index = idx
        
        if operation == "search":
            query = context.evaluate(config.get("query", "python"))
            req = service.search().list(part="snippet", q=query, maxResults=5)
            res = req.execute()
            for vid in res.get('items', []):
                results.append({"json": vid, "success": True})
                
    return results

def discord_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    config = node.config
    webhook_url = config.get("webhook_url") # If webhook mode
    channel_id = config.get("channel_id") # If bot mode
    message = config.get("message", "")
    mode = config.get("mode", "webhook")
    
    # Credential check
    bot_token = None
    if node.credential and node.credential.type == 'discord_bot':
        bot_token = node.credential.encrypted_data.get('bot_token')

    for idx, item in enumerate(items):
        context.item_index = idx
        msg_content = context.evaluate(message)
        
        if mode == "webhook":
            url = context.evaluate(webhook_url)
            requests.post(url, json={"content": msg_content})
        elif mode == "bot" and bot_token:
            cid = context.evaluate(channel_id)
            headers = {"Authorization": f"Bot {bot_token}"}
            url = f"https://discord.com/api/v10/channels/{cid}/messages"
            requests.post(url, json={"content": msg_content}, headers=headers)
            
    return items

def memory_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """Redis-backed memory for Get/Set variables across executions."""
    config = node.config
    operation = config.get("operation", "set") # set/get
    key = config.get("key")
    value = config.get("value")
    scope = config.get("scope", "workflow") # workflow, user, global
    
    r = redis.Redis.from_url(settings.CELERY_BROKER_URL)
    
    for idx, item in enumerate(items):
        context.item_index = idx
        eval_key = context.evaluate(key)
        
        # Namespace key
        if scope == "workflow":
            redis_key = f"mem:wf:{context.execution.workflow_id}:{eval_key}"
        elif scope == "user":
            redis_key = f"mem:user:{context.execution.created_by_id}:{eval_key}"
        else:
            redis_key = f"mem:global:{eval_key}"
            
        if operation == "set":
            eval_val = context.evaluate(value)
            r.set(redis_key, str(eval_val)) # Store as string
            item["json"][f"memory_{eval_key}"] = eval_val
            
        elif operation == "get":
            val = r.get(redis_key)
            if val:
                val = val.decode('utf-8')
            item["json"][eval_key] = val
            
    return items

def logger_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """
    Logger action - logs message and data.
    """
    config = node.config if hasattr(node, 'config') else (node if isinstance(node, dict) else {})
    message_template = config.get("message", "Logging items")
    level = config.get("level", "info").lower()
    include_data = config.get("include_data", True)
    
    for idx, item in enumerate(items):
        context.item_index = idx
        message = context.evaluate(message_template)
        
        log_msg = f"[FLOWZEN] {message}"
        if include_data:
            log_msg += f" | Data: {json.dumps(item.get('json', {}))}"
            
        if level == "error":
            logger.error(log_msg)
        elif level == "warning":
            logger.warning(log_msg)
        else:
            logger.info(log_msg)
            
    return items


# Action registry
ACTION_REGISTRY: Dict[str, Callable] = {
    "http_request": http_request_action,
    "http-request": http_request_action,  # Hyphenated alias
    "http": http_request_action,  # Alias
    "email": email_action,
    "email_send": email_action,  # Alias
    "email-send": email_action,  # Hyphenated alias
    "email_sender": email_action,  # EmailSenderNode alias
    "delay": delay_action,
    "condition": condition_action,
    "transform": transform_action,
    "code": code_action,
    "function": function_action,  # Function node (JS execution)
    "script": script_action,
    "logger": logger_action,
    "loop": loop_action,
    "merge": merge_action,
    "set_variables": set_variables_action,
    "set_variable": set_variables_action,  # Alias
    "trigger": lambda node, items, context: items,  # Trigger just passes through
    # CRITICAL: Add missing trigger types
    "webhook": lambda node, items, context: items,  # Webhook trigger passes through
    "webhook_trigger": lambda node, items, context: items, # Alias
    "webhook-trigger": lambda node, items, context: items,  # Hyphenated alias
    "schedule": lambda node, items, context: items,  # Schedule trigger passes through  
    "schedule_trigger": lambda node, items, context: items, # Alias
    "schedule-trigger": lambda node, items, context: items, # Hyphenated alias
    "manual": lambda node, items, context: items,  # Manual trigger passes through
    "manual_trigger": lambda node, items, context: items, # Alias
    "manual-trigger": lambda node, items, context: items,  # Hyphenated alias
    # Add specific trigger node types
    "manual_trigger": lambda node, items, context: items,  # Manual trigger node
    "schedule_trigger": lambda node, items, context: items,  # Schedule trigger node
    "ai_agent": ai_agent_action,  # Register AI Agent
    "ai-agent": ai_agent_action,  # Hyphenated alias
    # Extended Ecosystem
    "google_sheets": google_sheets_action,
    "google_drive": google_drive_action,
    "youtube": youtube_action,
    "discord": discord_action,
    "memory": memory_action,
    "model_openai": openai_chat_action,
    "image_generator": image_generator_action,
    "whatsapp_send": whatsapp_send_action,
    "whatsapp_trigger": lambda node, items, context: items,
    "telegram_send": telegram_send_action,
    "switch-case": switch_action,
    "switch": switch_action,
    "date_time": date_time_action,
    "crypto": crypto_action,
    "random_generator": random_generator_action,
    "markdown": markdown_action,
    "rss_read": rss_reader_action,
    "slack_message": slack_message_action,
    "slack-message": slack_message_action, # Hyphenated alias
    "slack": slack_message_action,
    "sentiment-analysis": sentiment_analysis_action,
    "json-processor": json_processor_action,
    "json_processor": json_processor_action,
    "csv-processor": csv_processor_action,
    "csv_processor": csv_processor_action,
    "inspector": lambda node, items, context: items, # Passthrough
}


def get_action(action_type: str) -> Optional[Callable]:
    """Get action function by type."""
    return ACTION_REGISTRY.get(action_type)

