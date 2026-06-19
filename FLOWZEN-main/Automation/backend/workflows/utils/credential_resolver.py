"""
Utility for resolving and decrypting credentials.
"""
import logging
from ..services.credential_encryption import get_encryption_service

logger = logging.getLogger(__name__)

def resolve_credential_data(credential):
    """
    Decrypt and return the data dictionary for a Credential object.
    Handles both string (encrypted) and dict (legacy/plain) types.
    """
    if not credential:
        return {}
        
    encrypted_data = credential.encrypted_data
    if not encrypted_data:
        return {}
        
    if isinstance(encrypted_data, dict):
        return encrypted_data
        
    try:
        svc = get_encryption_service()
        if svc:
            return svc.decrypt_credential_str(encrypted_data)
    except Exception as e:
        logger.error(f"Failed to decrypt credential {credential.id}: {e}")
        # FALLBACK: Try parsing as raw JSON (Dev/Migration support)
        import json
        try:
            return json.loads(encrypted_data)
        except:
            pass
        
    return {}
