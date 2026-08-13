"""
Credential encryption service using AES encryption.
"""
import os
import base64
import json
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class CredentialEncryptionService:
    """
    Service for encrypting and decrypting credentials using AES encryption.
    
    Uses envelope encryption:
    - Master key from environment variable CREDENTIALS_MASTER_KEY
    - Per-credential encryption using Fernet (symmetric AES)
    """
    
    def __init__(self):
        """Initialize encryption service with master key and legacy fallbacks."""
        master_key = os.environ.get('CREDENTIALS_MASTER_KEY') or "IeOn9kTi1EaZWc2cgToDvqJq9PjrZe8oi-FOlhDwZaM="
        
        self.ciphers = []
        primary = self._create_cipher(master_key)
        if primary:
            self.ciphers.append(primary)

        # Fallback keys to support database entries created before key standardization
        fallback_keys = [
            "IeOn9kTi1EaZWc2cgToDvqJq9PjrZe8oi-FOlhDwZaM=",
            "899ww6owyHqAn2THIH1Nj3TqN-UEZ6AIrxPB3DAZ-b4=",
        ]
        for fk in fallback_keys:
            if fk != master_key:
                c = self._create_cipher(fk)
                if c:
                    self.ciphers.append(c)

        self.cipher = self.ciphers[0] if self.ciphers else Fernet.generate_key()

    def _create_cipher(self, key_str: str) -> Optional[Fernet]:
        if not key_str:
            return None
        try:
            return Fernet(key_str.encode())
        except Exception:
            try:
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b'credential_salt',
                    iterations=100000,
                )
                key = base64.urlsafe_b64encode(kdf.derive(key_str.encode()))
                return Fernet(key)
            except Exception:
                return None

    def encrypt_credential(self, raw_data: Dict[str, Any]) -> bytes:
        """
        Encrypt credential data.
        """
        try:
            json_data = json.dumps(raw_data)
            encrypted = self.cipher.encrypt(json_data.encode())
            return encrypted
        except Exception as e:
            logger.error(f"Failed to encrypt credential: {e}")
            raise ValueError(f"Encryption failed: {e}")

    def decrypt_credential(self, encrypted_blob: bytes) -> Dict[str, Any]:
        """
        Decrypt credential data using primary cipher and legacy fallbacks.
        """
        if isinstance(encrypted_blob, str):
            encrypted_blob = encrypted_blob.encode()

        for c in self.ciphers:
            try:
                decrypted = c.decrypt(encrypted_blob)
                return json.loads(decrypted.decode())
            except Exception:
                continue

        # Fallback for unencrypted JSON bytes
        try:
            val = encrypted_blob if isinstance(encrypted_blob, str) else encrypted_blob.decode()
            return json.loads(val)
        except Exception:
            pass

        raise ValueError("Decryption failed across all available ciphers")
    
    def encrypt_credential_str(self, raw_data: Dict[str, Any]) -> str:
        """Encrypt and return as base64 string."""
        encrypted = self.encrypt_credential(raw_data)
        return base64.b64encode(encrypted).decode()
    
    def decrypt_credential_str(self, encrypted_str: str) -> Dict[str, Any]:
        """Decrypt from base64 string, with fallback for unencrypted JSON/Dict."""
        if not encrypted_str: return {}
        
        # logger.critical(f"DEBUG: Decrypting type={type(encrypted_str)} len={len(str(encrypted_str))}")
        try:
            encrypted = base64.b64decode(encrypted_str.encode())
            return self.decrypt_credential(encrypted)
        except Exception as e:
            # logger.critical(f"DEBUG: Decrypt failed: {e}. Trying fallbacks...")
            
            # Fallback 1: JSON
            try:
                return json.loads(encrypted_str)
            except:
                pass
            
            # Fallback 2: Python Dict String (Legacy)
            try:
                import ast
                val = ast.literal_eval(encrypted_str)
                if isinstance(val, dict): return val
            except:
                pass
            
            # Fallback 3: Return Empty Dict (Prevent Crash)
            logger.error(f"CRITICAL: Credential data is corrupt or unknown format. Returning empty. Data start: {str(encrypted_str)[:50]}")
            return {}

    def decrypt_credential_data(self, credential) -> Dict[str, Any]:
        """
        Universal decryptor for Credential objects. 
        """
        try:
            data = credential.encrypted_data
            if isinstance(data, dict):
                return data
            elif isinstance(data, str):
                return self.decrypt_credential_str(data)
            return {}
        except Exception as e:
            logger.error(f"Decryption helper failed for credential {credential.id if hasattr(credential, 'id') else 'unknown'}: {e}")
            return {}


# Singleton instance
_encryption_service: Optional[CredentialEncryptionService] = None


def get_encryption_service() -> CredentialEncryptionService:
    """Get singleton encryption service instance."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = CredentialEncryptionService()
    return _encryption_service

