# Missing Components Analysis

## 1. Authentication System
**Location**: `backend/authentication/`
**Strategy**: "Gmail-Only" Passwordless OTP.

The authentication flow is designed for simplicity and security, restricting access to users with `@gmail.com` addresses.

*   **Flow**:
    1.  **Request OTP**: User enters email at `/api/auth/send-otp/`.
    2.  **Validation**: Backend enforces `email.endswith('@gmail.com')`.
    3.  **Delivery**: `AuthService` generates a code and sends it via SMTP (managed by `MailService`, assumed).
    4.  **Verification**: User submits code at `/api/auth/verify-otp/`.
    5.  **Session/Token**: On success, the backend establishes a **Django Session** and returns **JWT Tokens** (Access/Refresh).
*   **Security**:
    *   **Throttling**: `AuthRateThrottle` limits attempts to 10/minute per IP.
    *   **Input Sanitization**: Basic checks in `SendOTPView`.

## 2. Notification System
**Location**: `backend/notifications/`
**Architecture**: Database-backed asynchronous alerts.

*   **Models**:
    *   `Notification`: Stores the actual alert (`title`, `message`, `type`, `is_read`). Types: `success`, `error`, `warning`, `info`.
    *   **`NotificationSettings`**: Per-user configuration to toggle channels (Email, Telegram, WhatsApp) and specific event types (e.g., mute "success" alerts).
*   **Service**: `create_notification()` is the central entry point. It checks user settings *before* creating the DB record or dispatching external alerts.

## 3. Infrastructure & Deployment
**Location**: `Automation/backend/Dockerfile`
**Stack**: Python 3.10 Slim on Debian.

*   **Server**: Uses `gunicorn` with **3 workers** and **2 threads** per worker (`--workers 3 --threads 2`).
*   **Dependencies**: `libpq-dev` (PostgreSQL), `git`, `curl`.
*   **Healthcheck**: Polls `http://localhost:8000/health/` every 30s.
*   **Startup**: Runs a custom validation script (`scripts/validate_env.py`) before starting the server.

## 4. Third-Party Integrations
**Location**: `backend/workflows/nodes/`
**Pattern**: All integrations follow a strict `ActionNode` pattern.

### Telegram (`telegram_send.py`)
*   **Mode**: Bot API (`https://api.telegram.org/bot<token>`).
*   **Smart Features**:
    *   **Chunking**: Automatically splits messages > 4096 chars.
    *   **Fallback**: Retries as plain text if Markdown parsing fails.
    *   **Auto-mapping**: If `message` input is empty, it intelligently pulls from `context.inputs['main']`.

### Discord (`discord_node.py`)
*   **Modes**:
    1.  **Webhook**: No auth required, just a URL. Supports username/avatar overrides.
    2.  **Bot**: Requires a `discord_bot` credential. Sends to a specific `Channel ID`.

### Google Sheets (`google_sheets_node.py`)
*   **Operations**: `append`, `get`, `update`, `clear`, `lookup`.
*   **Security**: Uses `Credential` model with encryption services to decrypt OAuth tokens at runtime.
*   **Data Handling**: Capable of parsing JSON strings into row arrays automatically.

---
**Conclusion**: The system is highly modular. Authentication is strict but simple. Integrations are isolated in their own node classes, sharing a common "Action" interface. Infrastructure is standard containerized Django.
