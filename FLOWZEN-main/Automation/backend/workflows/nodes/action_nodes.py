"""
Action Nodes

This module contains all action node implementations.
Action nodes perform operations and transform data in workflows.
"""

import requests
import time
import json
import random
import re
import math
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base_node import ActionNode, NodeExecutionError
from .registry import register_node


@register_node
class HttpRequestNode(ActionNode):
    """
    HTTP request node - makes API calls to external services.
    
    This is one of the most commonly used action nodes.
    Supports:
    - Persistent Cookies (Cookie Jar)
    - Binary File Downloads
    - Detailed Metrics
    - Advanced Auth
    """
    
    NODE_TYPE = "http_request"
    DISPLAY_NAME = "HTTP Request (V2)"
    DESCRIPTION = "Make HTTP requests with Cookie Jar and File Support"
    CATEGORY = "actions"
    DEFAULT_TIMEOUT = 30
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute HTTP request with configured parameters.
        """
        # Extract and resolve parameters
        url = self._resolve_template(params.get('url', ''), input_data, context)
        method = params.get('method', 'GET').upper()
        headers = params.get('headers', {})
        body = params.get('body', {})
        timeout = params.get('timeout', self.DEFAULT_TIMEOUT)
        follow_redirects = params.get('follow_redirects', True)
        verify_ssl = params.get('verify_ssl', True)
        
        # Resolve templates in headers and body
        headers = self._resolve_templates(headers, input_data, context)
        try:
            body = self._resolve_templates(body, input_data, context)
        except:
             # If body template resolution fails (e.g. binary data), keep as is
             pass
        
        self.logger.info(f"Making {method} request to {url}")
        
        try:
            # Configure session with retries
            session = requests.Session()
            
            # --- V2: COOKIE JAR SUPPORT ---
            # Retrieve cookies from context (shared across workflow)
            if context and 'cookies' in context:
                 try: session.cookies.update(context['cookies'])
                 except: pass # Ignore cookie loading errors
            
            # Configure retry strategy
            retry_strategy = Retry(
                total=params.get('retry_count', 3),
                backoff_factor=params.get('retry_backoff', 1),
                status_forcelist=[429, 500, 502, 503, 504]
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            # Prepare request data
            request_kwargs = {
                'method': method,
                'url': url,
                'headers': headers,
                'timeout': timeout,
                'allow_redirects': follow_redirects,
                'verify': verify_ssl
            }
            
            # Add body for methods that support it
            if method in ['POST', 'PUT', 'PATCH']:
                content_type = headers.get('Content-Type', '').lower()
                if 'application/json' in content_type or not content_type:
                    request_kwargs['json'] = body
                elif 'application/x-www-form-urlencoded' in content_type:
                    request_kwargs['data'] = body
                else:
                    # Treat as raw string or bytes
                    if isinstance(body, (dict, list)):
                         request_kwargs['data'] = json.dumps(body)
                    else:
                         request_kwargs['data'] = body
            
            # Make request
            start_time = time.time()
            response = session.request(**request_kwargs)
            latency_ms = int((time.time() - start_time) * 1000)
            
            # --- V2: UPDATE COOKIE JAR ---
            if context is not None:
                # Convert cookiejar to dict for serialization
                if 'cookies' not in context: context['cookies'] = {}
                try: context['cookies'].update(session.cookies.get_dict())
                except: pass

            # Parse response
            is_binary = False
            response_data = None
            binary_content = None
            
            content_type = response.headers.get('Content-Type', '').lower()
            binary_types = ['image/', 'audio/', 'video/', 'application/pdf', 'application/zip', 'application/octet-stream']
            
            # --- V2: BINARY FILE HANDLING ---
            if any(t in content_type for t in binary_types):
                import base64
                is_binary = True
                # Return generic "Binary Data" message in JSON, actual data in 'binary' key
                response_data = {"message": "Binary File Downloaded", "type": content_type, "size": len(response.content)}
                binary_content = {
                    "data": base64.b64encode(response.content).decode('ascii'),
                    "mime_type": content_type,
                    "name": "downloaded_file"
                }
            else:
                try:
                    response_data = response.json()
                except ValueError:
                    response_data = response.text
            
            # Check for HTTP errors if configured
            if params.get('fail_on_error', True) and not response.ok:
                raise NodeExecutionError(
                    f"HTTP {response.status_code}: {response.reason}",
                    node_type=self.NODE_TYPE
                )
            
            result = {
                'http_response': {
                    'status_code': response.status_code,
                    'headers': dict(response.headers),
                    'data': response_data,
                    'url': response.url,
                    'elapsed_ms': latency_ms,
                    'size_bytes': len(response.content)
                },
                'data': response_data,  # Shortcut for next nodes
                'status_code': response.status_code  # Common field
            }
            
            if is_binary:
                result['binary'] = binary_content
            
            # --- V2: DETAILED METRICS ---
            result['http_metrics'] = {
                'latency_ms': latency_ms,
                'content_type': content_type,
                'size_bytes': len(response.content)
            }
                
            return result
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"HTTP request failed: {e}")
            raise NodeExecutionError(f"HTTP request failed: {e}", node_type=self.NODE_TYPE)
    
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "title": "URL",
                    "description": "Target URL for HTTP request (supports templates like {{variable}})",
                    "format": "uri"
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
                    "default": "GET",
                    "title": "HTTP Method"
                },
                "headers": {
                    "type": "object",
                    "title": "Headers",
                    "description": "HTTP headers to send (supports templates)",
                    "default": {
                        "Content-Type": "application/json"
                    }
                },
                "body": {
                    "type": "object",
                    "title": "Request Body",
                    "description": "JSON body (text) or Dictionary (JSON) (supports templates)"
                },
                "timeout": {
                    "type": "integer",
                    "default": 30,
                    "minimum": 1,
                    "maximum": 300,
                    "title": "Timeout (seconds)"
                },
                "retry_count": {
                    "type": "integer",
                    "default": 3,
                    "minimum": 0,
                    "maximum": 10,
                    "title": "Retry Count"
                },
                "retry_backoff": {
                    "type": "number",
                    "default": 1,
                    "minimum": 0.1,
                    "maximum": 10,
                    "title": "Retry Backoff Factor"
                },
                "follow_redirects": {
                    "type": "boolean",
                    "default": True,
                    "title": "Follow Redirects"
                },
                "verify_ssl": {
                    "type": "boolean",
                    "default": True,
                    "title": "Verify SSL Certificate"
                },
                "fail_on_error": {
                    "type": "boolean",
                    "default": True,
                    "title": "Fail on HTTP Error Status"
                }
            },
            "required": ["url"]
        }


@register_node
class EmailSenderNode(ActionNode):
    """
    Email sender node - Production-grade email sending with auto-routing.
    Gmail addresses use Gmail OAuth API, others use SMTP.
    """
    
    NODE_TYPE = "send_email"
    DISPLAY_NAME = "Send Email"
    DESCRIPTION = "Send emails with automatic Gmail OAuth / SMTP routing"
    CATEGORY = "actions"
    
    def __init__(self, node_data: Dict[str, Any] = None, **kwargs):
        """Initialize with config safety."""
        super().__init__(node_data, **kwargs)
        # Ensure config is available even if super init didn't set it (defensive)
        if not hasattr(self, 'config') or self.config is None:
             self.config = {}

    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute email sending with professional-grade resolution.
        """
        try:
            from django.contrib.auth import get_user_model
            from workflows.email.dispatcher import get_email_dispatcher
            from ..models import Tenant
            
            User = get_user_model()
            config = self.config.copy()
            if params: config.update(params)

            # 1. Resolve User & Tenant
            user_id = context.get('user_id') or input_data.get('_user_id')
            user = None
            if user_id:
                try:
                    user = User.objects.get(pk=user_id)
                except: pass

            tenant_id = context.get('tenant_id') or input_data.get('_tenant_id')
            tenant = None
            if tenant_id:
                try: tenant = Tenant.objects.get(id=tenant_id)
                except: pass

            # 2. Resolve Email Fields
            credential_id = config.get('credential_id') or config.get('credential')
            
            # Recipient Normalization (Comma-separated or List)
            def normalize_emails(val):
                if not val: return []
                resolved = self._resolve_template(val, input_data, context)
                if isinstance(resolved, list): return [str(e).strip() for e in resolved if e]
                return [e.strip() for e in str(resolved).split(',') if e.strip()]

            to_emails = normalize_emails(config.get('to_email') or config.get('to'))
            cc_emails = normalize_emails(config.get('cc_emails') or config.get('cc'))
            bcc_emails = normalize_emails(config.get('bcc_emails') or config.get('bcc'))

            if not to_emails and user and user.email:
                to_emails = [user.email]

            if not to_emails:
                raise ValueError("No recipient email specified.")

            subject = self._resolve_template(config.get('subject', 'No Subject'), input_data, context)
            body = self._resolve_template(config.get('email_body') or config.get('body', ''), input_data, context)
            from_email = self._resolve_template(config.get('from', user.email if user else ''), input_data, context)
            
            # --- ROBUST FALLBACK (Requirement Refinement) ---
            if not body:
                self.logger.critical(f"🔍 EmailSenderNode: Empty body detected. Entering fallback. input_data keys: {list(input_data.keys())}")
                # 1. Try to get from Direct Main Input (n8n-style)
                main_input = []
                if hasattr(context, 'inputs'): main_input = context.inputs.get('main', [])
                elif isinstance(context, dict): main_input = context.get('inputs', {}).get('main', [])

                if main_input and isinstance(main_input, list):
                    # Try to find the most useful text in input items
                    for item in main_input:
                        data = item.get('json', item) if isinstance(item, dict) else item
                        if isinstance(data, dict):
                            val = data.get('output') or data.get('text') or data.get('content')
                            if val and isinstance(val, str):
                                body = val
                                break
                    if not body and main_input:
                         # Fallback to first item's string representation if no common keys
                         first_item = main_input[0].get('json', main_input[0]) if isinstance(main_input[0], dict) else main_input[0]
                         if isinstance(first_item, str): body = first_item

                # 2. Try to get from Node Outputs (Topological parent)
                if not body:
                    node_outputs = {}
                    if hasattr(context, 'node_outputs'): node_outputs = context.node_outputs
                    elif isinstance(context, dict): node_outputs = context.get('node_outputs', {})
                    
                    if node_outputs:
                        # Find the most recent node result (excluding current)
                        curr_id = (context.get('current_node_id') if isinstance(context, dict) else getattr(context, 'current_node_id', None))
                        # Iterate backwards to find the last completed node
                        for nid, res in reversed(list(node_outputs.items())):
                            if nid == curr_id: continue
                            # res is usually {"json": payload, "raw": raw}
                            payload = res.get('json') if isinstance(res, dict) and 'json' in res else res
                            if isinstance(payload, str) and payload:
                                body = payload
                                break
                            elif isinstance(payload, dict):
                                val = payload.get('output') or payload.get('text') or payload.get('content')
                                if val and isinstance(val, str):
                                    body = val
                                    break
                
                # 3. Final Fallback to Flat input_data (Merged Workflow State)
                if not body and input_data:
                    val = input_data.get('output') or input_data.get('text') or input_data.get('content')

                    # Handle dictionary output (e.g. from AI Agent)
                    if isinstance(val, dict):
                         val = val.get('response') or val.get('text') or val.get('content')

                    if val and isinstance(val, str) and val.strip():
                        body = val.strip()
                    else:
                        # Only dump if it's small/simple, otherwise return descriptive error
                        if len(input_data) < 20:
                            body = f"[Auto-Generated Body]\n{json.dumps(input_data, indent=2)}"
                        else:
                            body = "Error: Could not automatically determine email body. Please configure the Email Body field."

            content_type = config.get('content_type', 'plain_text')
            is_html = (content_type == 'html') or config.get('is_html', False)

            # 3. Handle Attachments (MVP: URL-based)
            attachments = []
            raw_attachments = config.get('attachments')
            if raw_attachments:
                try:
                    if isinstance(raw_attachments, str):
                        try:
                            attachments_data = json.loads(raw_attachments)
                        except json.JSONDecodeError:
                             raise ValueError("Invalid JSON format in Attachments field.")
                    else:
                        attachments_data = raw_attachments
                    
                    if not isinstance(attachments_data, list):
                        raise ValueError("Attachments must be a JSON list of objects.")

                    for att in attachments_data:
                        if not isinstance(att, dict) or not att.get('url'):
                            raise ValueError(f"Each attachment must be an object with a 'url' key. Found: {att}")
                        
                        # Add to attachments list
                        attachments.append(att)

                except ValueError as e:
                    raise e # Re-raise for node error
                except Exception as e:
                    self.logger.warning(f"Unexpected error in attachment validation: {e}")

            # Also check old binary format for backward compatibility
            if input_data.get('binary'):
                for key, val in input_data.get('binary').items():
                    if isinstance(val, dict) and 'path' in val:
                        attachments.append(val['path'])

            # 4. Send Email
            dispatcher = get_email_dispatcher()
            result = dispatcher.send_email(
                user=user,
                tenant=tenant,
                from_email=from_email,
                to_emails=to_emails,
                subject=subject,
                body=body,
                cc_emails=cc_emails,
                bcc_emails=bcc_emails,
                credential_id=credential_id,
                is_html=is_html,
                smtp_config=config.get('smtp_config'),
                attachments=attachments
            )

            # 5. Professional Output
            if result and result.get('success'):
                return {
                    "success": True,
                    "output": {
                        "status": "sent",
                        "to": to_emails,
                        "provider": result.get('method', 'unknown'),
                        "message_id": result.get('message_id') or result.get('id') or "sent-ok",
                        "raw_result": result
                    }
                }
            else:
                error_msg = result.get('error') if result else "Unknown dispatch error"
                return {"success": False, "error": error_msg, "details": result}

        except Exception as e:
            return {"success": False, "error": str(e)}
    
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "credential_id": {
                    "type": "string",
                    "title": "Email Credential",
                    "widget": "credential_select", 
                    "credential_type": "email",
                    "required": True
                },
                "to_email": {
                    "type": "string",
                    "title": "To Email",
                    "description": "Recipient address or comma-separated list. Supports templates.",
                    "required": True
                },
                "cc_emails": {
                    "type": "string",
                    "title": "CC Email",
                    "description": "CC recipients, comma-separated. Supports templates."
                },
                "bcc_emails": {
                    "type": "string",
                    "title": "BCC Email", 
                    "description": "BCC recipients, comma-separated. Supports templates."
                },
                "subject": {
                    "type": "string",
                    "title": "Subject",
                    "description": "Email subject. Supports templates.",
                    "required": True
                },
                "email_body": {
                    "type": "string",
                    "title": "Email Body",
                    "widget": "textarea",
                    "description": "If empty, uses incoming data. Supports templates."
                },
                "content_type": {
                    "type": "string",
                    "title": "Content Type",
                    "enum": ["plain_text", "html"],
                    "default": "plain_text"
                },
                "attachments": {
                    "type": "string",
                    "title": "Attachments (JSON)",
                    "widget": "textarea",
                    "placeholder": '[{"filename": "report.pdf", "url": "https://..."}]',
                    "description": "JSON list of objects with 'filename' and 'url'."
                },
                "from": {
                    "type": "string",
                    "title": "From Email",
                    "description": "Optional override for sender address."
                },
                "smtp_config": {
                    "type": "object",
                    "title": "SMTP Configuration (Fallback)",
                    "properties": {
                        "host": {"type": "string", "title": "SMTP Host"},
                        "port": {"type": "integer", "title": "SMTP Port", "default": 587},
                        "username": {"type": "string", "title": "Username"},
                        "password": {"type": "string", "title": "Password", "format": "password"},
                        "use_tls": {"type": "boolean", "title": "Use TLS", "default": True},
                        "use_ssl": {"type": "boolean", "title": "Use SSL", "default": False}
                    }
                }
            },
            "required": ["credential_id", "to_email", "subject"]
        }


@register_node
class SlackMessageNode(ActionNode):
    """
    Slack message node - sends messages to Slack channels or users.
    """
    
    NODE_TYPE = "slack_message"
    DISPLAY_NAME = "Send Slack Message"
    DESCRIPTION = "Send messages to Slack channels or direct messages"
    CATEGORY = "actions"
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send Slack message with configured parameters.
        """
        # Resolve template variables
        channel = self._resolve_template(params['channel'], input_data, context)
        message = self._resolve_template(params['message'], input_data, context)
        
        # Get Slack configuration
        webhook_url = params.get('webhook_url') or context.get('credentials', {}).get('slack_webhook_url')
        bot_token = params.get('bot_token') or context.get('credentials', {}).get('slack_bot_token')
        
        self.logger.info(f"Sending Slack message to {channel}")
        
        try:
            if webhook_url:
                result = self._send_via_webhook(webhook_url, channel, message, params)
            elif bot_token:
                result = self._send_via_api(bot_token, channel, message, params)
            else:
                raise NodeExecutionError("Slack webhook URL or bot token not configured")
            
            return {
                'slack_sent': True,
                'slack_result': result,
                'channel': channel,
                'message_length': len(message)
            }
            
        except Exception as e:
            self.logger.error(f"Slack message failed: {e}")
            raise NodeExecutionError(f"Slack message failed: {e}", node_type=self.NODE_TYPE)
    
    def _send_via_webhook(self, webhook_url: str, channel: str, message: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send message via Slack webhook."""
        payload = {
            "text": message,
            "channel": channel if channel.startswith('#') or channel.startswith('@') else f"#{channel}"
        }
        
        # Add optional formatting
        if params.get('username'):
            payload['username'] = params['username']
        if params.get('icon_emoji'):
            payload['icon_emoji'] = params['icon_emoji']
        if params.get('icon_url'):
            payload['icon_url'] = params['icon_url']
        
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        
        return {
            'method': 'webhook',
            'status': 'sent'
        }
    
    def _send_via_api(self, bot_token: str, channel: str, message: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send message via Slack Web API."""
        url = "https://slack.com/api/chat.postMessage"
        headers = {
            "Authorization": f"Bearer {bot_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "channel": channel,
            "text": message
        }
        
        # Add optional formatting
        if params.get('blocks'):
            payload['blocks'] = params['blocks']
        if params.get('attachments'):
            payload['attachments'] = params['attachments']
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        if not result.get('ok'):
            raise NodeExecutionError(f"Slack API error: {result.get('error')}")
        
        return {
            'method': 'api',
            'message_ts': result.get('ts'),
            'channel_id': result.get('channel')
        }
    
    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "channel": {
                    "type": "string",
                    "title": "Channel",
                    "description": "Slack channel or user (e.g., #general, @username) - supports templates"
                },
                "message": {
                    "type": "string",
                    "title": "Message",
                    "description": "Message text to send (supports templates)"
                },
                "webhook_url": {
                    "type": "string",
                    "title": "Webhook URL",
                    "description": "Slack webhook URL (if using webhook method)",
                    "format": "uri"
                },
                "bot_token": {
                    "type": "string",
                    "title": "Bot Token",
                    "description": "Slack bot token (if using API method)",
                    "format": "password"
                },
                "username": {
                    "type": "string",
                    "title": "Bot Username",
                    "description": "Custom username for the bot (webhook only)"
                },
                "icon_emoji": {
                    "type": "string",
                    "title": "Icon Emoji",
                    "description": "Emoji to use as bot icon (e.g., :robot_face:)"
                },
                "icon_url": {
                    "type": "string",
                    "title": "Icon URL",
                    "description": "URL of image to use as bot icon",
                    "format": "uri"
                }
            },
            "required": ["channel", "message"]
        }


@register_node
class CodeNode(ActionNode):
    """
    Code node - executes custom Python code.
    WARNING: This allows arbitrary code execution. Ensure environment is sandboxed in production.
    Expanded Sandbox V2: Includes math, random, re, datetime.
    """
    
    NODE_TYPE = "code"
    DISPLAY_NAME = "Python Code (V2)"
    DESCRIPTION = "Execute custom Python code with expanded standard library"
    CATEGORY = "utilities"
    
    def run(self, input_data: Dict[str, Any], params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute python code securely using RestrictedPython.
        """
        code = params.get('code', '')
        if not code:
            return {"result": None, "error": "No code provided"}
            
        try:
            from RestrictedPython import safe_builtins, compile_restricted
            from RestrictedPython.Guards import safe_globals_default, guarded_iter_unpack_sequence
            from RestrictedPython.PrintCollector import PrintCollector
        except ImportError:
            self.logger.error("RestrictedPython not installed. Falling back to basic check (UNSAFE).")
            # Basic backup logic if library somehow fails
            if any(term in code for term in ['import os', 'subprocess', 'open(']):
                 return {"success": False, "error": "Security Error: Dangerous terms detected."}
            
            local_scope = {"input_data": input_data, "context": context, "result": None}
            exec(f"def user_fn(input_data, context):\n" + "\n".join(f"    {l}" for l in code.split('\n')) + "\nresult = user_fn(input_data, context)", {}, local_scope)
            return local_scope['result'] if isinstance(local_scope['result'], dict) else {"result": local_scope['result']}

        # Setup Restricted Environment
        _print_ = PrintCollector
        _getattr_ = getattr
        
        # Build safe globals (V2 Expanded)
        safe_globals = safe_globals_default.copy()
        safe_globals.update({
            '_print_': _print_,
            '_getattr_': _getattr_,
            '_getiter_': iter,
            '_iter_unpack_sequence_': guarded_iter_unpack_sequence,
            'input_data': input_data,
            'context': context,
            'json': json,
            'datetime': datetime,
            'timedelta': timedelta,
            'time': time,
            'math': math,
            'random': random,
            're': re
        })

        try:
            # Wrap code in a function to allow 'return'
            indented_code = "\n".join(f"    {line}" for line in code.split('\n'))
            wrapper_code = f"def user_function(input_data, context):\n{indented_code}\n\nresult = user_function(input_data, context)"

            byte_code = compile_restricted(wrapper_code, '<inline_code>', 'exec')
            
            # Execute in restricted scope
            exec(byte_code, safe_globals)
            
            # Get captured result
            result = safe_globals.get('result')
            
            # Capture printed output for debugging
            logs = ""
            try:
                logs = safe_globals.get('_print_')()
            except:
                pass
            
            response = result if isinstance(result, dict) else {"result": result}
            if logs:
                response["_logs"] = logs
            return response
            
        except Exception as e:
            self.logger.error(f"Restricted Code execution failed: {e}")
            return {"success": False, "error": f"Execution Error: {str(e)}"}

    @classmethod
    def get_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "title": "Python Code",
                    "description": "Python code to execute. Return a dictionary. Available vars: input_data, context. Modules: math, random, re, json, datetime.",
                    "widget": "code_editor",
                    "language": "python",
                    "default": "return {'message': 'Hello World'}"
                }
            },
            "required": ["code"]
        }
