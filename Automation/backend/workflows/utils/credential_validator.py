"""
Utility to verify if a credential is fully configured based on required keys.
"""

def is_credential_configured(cred_type, data):
    """
    Return True if the data dictionary contains all required fields for the given credential type.
    """
    if not data or not isinstance(data, dict):
        return False
        
    required_fields = {
        "meta_whatsapp": ["access_token", "phone_number_id", "verify_token"],
        "gmail_oauth": ["client_id", "client_secret"],
        "gmail_oauth": ["client_id", "client_secret"],
        "google_calendar": ["client_id", "client_secret"],
        "telegram_bot": ["bot_token"],
        "smtp_server": ["host", "port", "username", "password"],
        "ollama_local": ["base_url"],
        "general_api_key": ["api_key"]
    }
    
    fields = required_fields.get(cred_type, [])
    for field in fields:
        if not data.get(field):
            # Special case for telegram where it might be 'token' instead of 'bot_token'
            if field == "bot_token" and data.get("token"):
                continue
            # Special case for whatsapp where it might be 'phone_id' instead of 'phone_number_id'
            if field == "phone_number_id" and data.get("phone_id"):
                continue
            return False
            
    return True
