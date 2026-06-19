# Credential System Analysis

## 1. Overview
The Credential System is designed for **Zero-Trust Security**. It ensures sensitive data (API keys, tokens, passwords) is never stored in plain text and is only decrypted at the exact moment of usage.

**Key Components:**
*   **Model**: `Credential` (PostgreSQL)
*   **Encryption**: `CredentialEncryptionService` (AES-256 / Fernet)
*   **API**: `CredentialViewSet` (Validation & Testing)
*   **Usage**: Nodes & Services (Decryption on demand)

## 2. Data Model (`Credential`)
**Location**: `backend/workflows/models.py` (Line 644)

The model acts as a secure vault. It does *not* store secrets in separate columns. Instead, it bundles them into a single encrypted JSON blob.

### Fields
*   **`name`**: User-friendly label (e.g., "My Production Bot").
*   **`type`**: The specific integration type (e.g., `telegram_bot`, `gmail_oauth`, `ollama_local`).
*   **`provider`**: Broad category (e.g., `telegram`, `google`, `meta`).
*   **`encrypted_data`**: `JSONField` storing the **encrypted** cyphertext.
    *   *Note*: While the field type is JSON, the values inside are base64-encoded encrypted strings managed by the service layer.
*   **`owner` / `tenant`**: Enforces strict multi-tenancy and ownership constraints.
*   **`environment`**: Scoped to `dev`, `staging`, or `production`.

### Constraints
*   **Uniqueness**: `(owner, provider, type)` must be unique. A user cannot have two "Default Telegram Bots" effectively to prevent ambiguity, though they can have multiple if types differ. (Wait, the constraint is `unique_credential_per_user_svc`).

## 3. Encryption Strategy
**Service**: `backend/workflows/services/credential_encryption.py`

*   **Algorithm**: **AES (Fernet)** implementation via `cryptography` library.
*   **Key Management**:
    *   Uses `CREDENTIALS_MASTER_KEY` from environment variables.
    *   Supports purely random keys or PBKDF2 derived keys.
*   **Flow**:
    1.  **Encrypt**: `encrypt_credential_str(dict)` -> `base64_string`
    2.  **Decrypt**: `decrypt_credential_str(string)` -> `dict`

## 4. API Layer (`CredentialViewSet`)
**Location**: `backend/workflows/views.py`

This layer acts as the **Security Gatekeeper**.

1.  **Creation/Update**:
    *   Receives plain text data from the Frontend (over HTTPS).
    *   Immediately calls `CredentialEncryptionService` to encrypt the payload.
    *   Saves *only* the encrypted blob to the database.
2.  **Validation**:
    *   **Strict Checks**: For `ai_offline` (Ollama), it actually pings the server to ensure connectivity before saving.
3.  **Connectivity Testing (`/test/`)**:
    *   Allows users to "Test Connection" without running a workflow.
    *   Supports: Telegram (`getMe`), WhatsApp (`/me`), SMTP (Login), Ollama (`/tags`).

## 5. Usage Pattern
Nodes do not decrypt credentials manually. They use helper methods or services.

### Method 1: `get_auth_header()`
The `Credential` model has a helper method `get_auth_header()` that decrypts and formats standard headers:
*   `Bearer <token>`
*   `Basic <base64>`
*   `X-API-Key <key>`

### Method 2: Service Decryption
Complex integrations (like Gmail) use their specific services:
1.  Fetch `Credential` from DB.
2.  Pass to `GmailOAuthService`.
3.  Service calls `encryption_service.decrypt_credential_data(cred)`.
4.  Service uses valid tokens to make API calls.

## 6. Security Summary
*   **At Rest**: Encrypted in PostgreSQL.
*   **In Transit**: HTTPS (Standard).
*   **In Use**: Decrypted only in memory scope of the execution/request.
*   **Isolation**: Tenant-scoped to prevent unauthorized access.
