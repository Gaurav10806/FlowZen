"""
Normalization map for inconsistent frontend provider/type names.
"""

CREDENTIAL_TYPE_MAP = {
    # WhatsApp permutations
    "whatsapp": "meta_whatsapp",
    "whatsapp_business": "meta_whatsapp",
    "whatsapp_cloud": "meta_whatsapp",
    "meta_whatsapp": "meta_whatsapp",
    
    # Gmail/Google permutations (Types)
    "google_gmail": "gmail_oauth",
    "google_oauth": "gmail_oauth",
    "gmail_oauth": "gmail_oauth",
    "gmail": "gmail_oauth",
    
    # Telegram permutations
    "telegram": "telegram_bot",
    "telegram_bot": "telegram_bot",
    
    # SMTP permutations
    "smtp": "smtp_server",
    "smtp_server": "smtp_server",
    
    # AI permutations
    "ollama": "ollama_local",
    "ollama_local": "ollama_local",
    "ai_offline": "ollama_local",
    
    # API Key permutations
    "api_key": "general_api_key",
    "general_api_key": "general_api_key"
}

def normalize_credential_type(cred_type):
    """Normalize credential type to canonical version."""
    if not cred_type:
        return "general_api_key"
    return CREDENTIAL_TYPE_MAP.get(cred_type.lower(), cred_type.lower())
