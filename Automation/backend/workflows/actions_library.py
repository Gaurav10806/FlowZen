import json
import time
import requests
import uuid
import hashlib
import hmac
import random
import logging
import csv
import io
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Third-party imports (handled gracefully if missing)
try:
    import openai
except ImportError:
    openai = None

try:
    import markdown as md
except ImportError:
    md = None

try:
    import feedparser
except ImportError:
    feedparser = None

from workflows.context import ActionContext, render_template

logger = logging.getLogger(__name__)

# ==============================================================================
# AI & ML ACTIONS
# ==============================================================================

def openai_chat_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """Execute OpenAI Chat Completion."""
    if not openai:
        return [{"json": {"error": "openai package not installed"}, "success": False}]

    config = node.config
    model = config.get("model", "gpt-4o")
    prompt_template = config.get("prompt", "")
    system_prompt = config.get("system_prompt", "You are a helpful assistant.")
    temperature = float(config.get("temperature", 0.7))
    
    api_key = None
    if node.credential and node.credential.type == 'openai_api':
        api_key = node.credential.encrypted_data.get('api_key')
    if not api_key:
        api_key = context.execution_context.get("OPENAI_API_KEY") 

    if not api_key:
        return [{"json": {"error": "Missing OpenAI API Key"}, "success": False}]

    client = openai.OpenAI(api_key=api_key)
    output_items = []
    for idx, item in enumerate(items):
        context.item_index = idx
        prompt = context.evaluate(prompt_template)
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature
            )
            content = response.choices[0].message.content
            output_items.append({
                "json": {**item.get("json", {}), "output": content, "model": model},
                "success": True
            })
        except Exception as e:
            output_items.append({"json": {"error": str(e)}, "success": False})
    return output_items

def sentiment_analysis_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """Analyze sentiment using OpenAI."""
    if not openai:
        return [{"json": {"error": "openai package not installed"}, "success": False}]

    config = node.config
    text_template = config.get("text", "{{ $json.text or $json.message or $json.content }}")
    
    api_key = None
    if node.credential and node.credential.type == 'openai_api':
        api_key = node.credential.encrypted_data.get('api_key')
    if not api_key:
        api_key = context.execution_context.get("OPENAI_API_KEY") 

    if not api_key:
        return [{"json": {"error": "Missing OpenAI API Key"}, "success": False}]

    client = openai.OpenAI(api_key=api_key)
    output_items = []
    for idx, item in enumerate(items):
        context.item_index = idx
        text = context.evaluate(text_template)
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Analyze the sentiment. Return JSON: {\"sentiment\": \"positive|negative|neutral\", \"confidence\": 0.9}"},
                    {"role": "user", "content": text}
                ],
                response_format={ "type": "json_object" }
            )
            res_json = json.loads(response.choices[0].message.content)
            output_items.append({"json": {**item.get("json", {}), **res_json}, "success": True})
        except Exception as e:
            output_items.append({"json": {"error": str(e)}, "success": False})
    return output_items

def image_generator_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """Generate images using DALL-E."""
    if not openai:
        return [{"json": {"error": "openai package not installed"}, "success": False}]

    config = node.config
    prompt_template = config.get("prompt", "")
    api_key = None
    if node.credential and node.credential.type == 'openai_api':
        api_key = node.credential.encrypted_data.get('api_key')
    if not api_key:
        api_key = context.execution_context.get("OPENAI_API_KEY")

    if not api_key:
        return [{"json": {"error": "Missing OpenAI API Key"}, "success": False}]

    client = openai.OpenAI(api_key=api_key)
    output_items = []
    for idx, item in enumerate(items):
        context.item_index = idx
        prompt = context.evaluate(prompt_template)
        try:
            response = client.images.generate(model="dall-e-3", prompt=prompt)
            output_items.append({"json": {"image_url": response.data[0].url}, "success": True})
        except Exception as e:
            output_items.append({"json": {"error": str(e)}, "success": False})
    return output_items

# ==============================================================================
# COMMUNICATION ACTIONS
# ==============================================================================

def whatsapp_send_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """Send WhatsApp Message via Meta Graph API."""
    config = node.config
    phone_number_id = config.get("phone_number_id")
    access_token = None
    if node.credential and node.credential.type == 'whatsapp_cloud':
        access_token = node.credential.encrypted_data.get('access_token')
        if not phone_number_id:
            phone_number_id = node.credential.encrypted_data.get('phone_number_id')

    if not access_token or not phone_number_id:
         return [{"json": {"error": "Missing WhatsApp Credentials"}, "success": False}]

    output_items = []
    url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    for idx, item in enumerate(items):
        context.item_index = idx
        recipient = context.evaluate(config.get("phone_number", ""))
        text = context.evaluate(config.get("message_content", ""))
        payload = {"messaging_product": "whatsapp", "to": recipient, "type": "text", "text": {"body": text}}
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            output_items.append({"json": resp.json(), "success": resp.status_code < 400})
        except Exception as e:
            output_items.append({"json": {"error": str(e)}, "success": False})
    return output_items

def telegram_send_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """Send Telegram Message."""
    bot_token = None
    if node.credential and node.credential.type == 'telegram_bot':
        bot_token = node.credential.encrypted_data.get('bot_token')
    if not bot_token:
        return [{"json": {"error": "Missing Telegram Bot Token"}, "success": False}]
    output_items = []
    base_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    for idx, item in enumerate(items):
        context.item_index = idx
        chat_id = context.evaluate(node.config.get("chat_id", ""))
        text = context.evaluate(node.config.get("text", ""))
        try:
            resp = requests.post(base_url, json={"chat_id": chat_id, "text": text}, timeout=10)
            output_items.append({"json": resp.json(), "success": resp.status_code == 200})
        except Exception as e:
            output_items.append({"json": {"error": str(e)}, "success": False})
    return output_items

def slack_message_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """Send message to Slack via Webhook."""
    webhook_url_template = node.config.get("webhook_url", "")
    message_template = node.config.get("message", "")
    output_items = []
    for idx, item in enumerate(items):
        context.item_index = idx
        url = context.evaluate(webhook_url_template)
        text = context.evaluate(message_template)
        if not url:
            output_items.append({"json": {"error": "Missing Webhook URL"}, "success": False})
            continue
        try:
            resp = requests.post(url, json={"text": text}, timeout=10)
            output_items.append({"json": {"status": resp.status_code}, "success": resp.status_code < 400})
        except Exception as e:
            output_items.append({"json": {"error": str(e)}, "success": False})
    return output_items

# ==============================================================================
# UTILITY ACTIONS
# ==============================================================================

def switch_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """Switch Case logic."""
    expression = node.config.get("expression", "")
    rules = node.config.get("rules", [])
    processed_items = []
    for idx, item in enumerate(items):
        context.item_index = idx
        val = context.evaluate(expression)
        matched_index = -1
        for i, rule in enumerate(rules):
            if str(val) == str(rule.get("value")):
                matched_index = i
                break
        out_idx = matched_index if matched_index != -1 else len(rules)
        new_item = item.copy()
        new_item["_output_index"] = out_idx
        processed_items.append(new_item)
    return processed_items

def date_time_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """Date & Time utilities."""
    operation = node.config.get("operation", "format")
    output_items = []
    for idx, item in enumerate(items):
        context.item_index = idx
        try:
            res = {}
            date_str = context.evaluate(node.config.get("date", "now"))
            dt = datetime.now() if date_str == "now" else datetime.fromisoformat(str(date_str).replace('Z', '+00:00'))
            if operation == "format":
                res["formatted"] = dt.strftime(node.config.get("format", "%Y-%m-%d %H:%M:%S"))
                res["iso"] = dt.isoformat()
            elif operation in ["add", "subtract"]:
                delta = timedelta(**{node.config.get("unit", "days"): int(node.config.get("amount", 0))})
                res["result"] = (dt - delta if operation == "subtract" else dt + delta).isoformat()
            output_items.append({"json": {**item.get("json", {}), **res}, "success": True})
        except Exception as e:
            output_items.append({"json": {"error": str(e)}, "success": False})
    return output_items

def crypto_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """Hashing and Encryption utilities."""
    operation = node.config.get("operation", "hash")
    algo = node.config.get("algorithm", "sha256")
    output_items = []
    for idx, item in enumerate(items):
        context.item_index = idx
        value = str(context.evaluate(node.config.get("value", "")))
        res = {}
        if operation == "hash":
            res["hash"] = getattr(hashlib, algo)(value.encode()).hexdigest()
        elif operation == "hmac":
            secret = node.config.get("secret", "")
            res["hmac"] = hmac.new(secret.encode(), value.encode(), getattr(hashlib, algo)).hexdigest()
        output_items.append({"json": {**item.get("json", {}), **res}, "success": True})
    return output_items

def random_generator_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """Generate random data."""
    data_type = node.config.get("data_type", "uuid")
    output_items = []
    for item in (items if items else [{}]):
        res = {}
        if data_type == "uuid": res["output"] = str(uuid.uuid4())
        elif data_type == "number": res["output"] = random.randint(int(node.config.get("min", 0)), int(node.config.get("max", 100)))
        output_items.append({"json": {**item.get("json", {}), **res} if items else res, "success": True})
    return output_items

def markdown_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """Convert Markdown to HTML."""
    if not md: return [{"json": {"error": "markdown package not installed"}, "success": False}]
    output_items = []
    for idx, item in enumerate(items):
        context.item_index = idx
        html = md.markdown(context.evaluate(node.config.get("content", "")))
        output_items.append({"json": {**item.get("json", {}), "html": html}, "success": True})
    return output_items

def rss_reader_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """Read RSS Feed."""
    if not feedparser: return [{"json": {"error": "feedparser package not installed"}, "success": False}]
    try:
        feed = feedparser.parse(node.config.get("url", ""))
        return [{"json": {"title": e.title, "link": e.link, "summary": e.get("summary")}, "success": True} for e in feed.entries[:20]]
    except Exception as e:
        return [{"json": {"error": str(e)}, "success": False}]

def json_processor_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """Process JSON data."""
    operation = node.config.get("operation", "parse")
    output_items = []
    for item in items:
        try:
            if operation == "stringify":
                output_items.append({"json": {"string": json.dumps(item.get("json", {}))}, "success": True})
            else:
                output_items.append({"json": item.get("json", {}), "success": True})
        except Exception as e:
            output_items.append({"json": {"error": str(e)}, "success": False})
    return output_items

def csv_processor_action(node, items: List[Dict], context: ActionContext) -> List[Dict]:
    """Process CSV data."""
    operation = node.config.get("operation", "parse")
    delimiter = node.config.get("delimiter", ",")
    if operation == "parse":
        output_items = []
        for idx, item in enumerate(items):
            context.item_index = idx
            text = str(context.evaluate(node.config.get("csv_data", "")))
            try:
                reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
                for row in reader: output_items.append({"json": row, "success": True})
            except Exception as e: output_items.append({"json": {"error": str(e)}, "success": False})
        return output_items
    else:
        try:
            f = io.StringIO()
            if items:
                writer = csv.DictWriter(f, fieldnames=items[0].get("json", {}).keys(), delimiter=delimiter)
                writer.writeheader()
                for item in items: writer.writerow(item.get("json", {}))
            return [{"json": {"csv": f.getvalue()}, "success": True}]
        except Exception as e: return [{"json": {"error": str(e)}, "success": False}]
