# Email System & Gmail Integration Analysis

This document details exactly how emails are sent in your FlowZen project, specifically focusing on the routing logic between **SMTP** and **Gmail OAuth**.

## 1. High-Level Execution Flow

When an "Email Node" is executed in a workflow, the process follows this path:

```mermaid
graph TD
    A[Workflow Execution] -->|Runs Node| B(EmailSenderNode)
    B -->|Calls| C{EmailDispatcher}
    C -->|Check Credential Type| D{Routing Logic}
    D -- Type: gmail_oauth --> E[GmailOAuthSender]
    D -- Type: smtp --> F[SMTPSender]
    E -->|HTTPS POST| G[Google Gmail API]
    F -->|TCP/IP| H[SMTP Server (e.g., AWS SES, SendGrid)]
```

## 2. Key Code Locations

| Component | File Location | Description |
| :--- | :--- | :--- |
| **Node Definition** | `Automation/backend/workflows/nodes/action_nodes.py` | The entry point. Handles user inputs (To, Subject, Body) and calls the dispatcher. |
| **Dispatcher** | `Automation/backend/workflows/email/dispatcher.py` | The brain. Decides *how* to send the email (SMTP vs OAuth). |
| **Gmail Sender** | `Automation/backend/workflows/email/gmail_oauth.py` | The specialized driver for Gmail API (token management, API calls). |
| **SMTP Sender** | `Automation/backend/workflows/email/smtp_sender.py` | The driver for standard SMTP protocols. |

---

## 3. Detailed Code Structure

### Step 1: The Node (`EmailSenderNode`)
**Location**: `nodes/action_nodes.py` (Line 254)

This class inherits from `ActionNode`.
1.  **`run()` method**:
    *   Resolves template variables (e.g., changing `{{ name }}` to `John`).
    *   Retrieves the linked `credential_id` from the node configuration.
    *   **Crucial Call**: It calls `dispatcher.send_email(...)` (Line 424).

### Step 2: The Dispatcher (`EmailDispatcher`)
**Location**: `email/dispatcher.py`

This is where the decision happens.
1.  **`send_email()` method**:
    *   Checks the `credential_id` (Lines 96-101).
    *   **IF** `credential.type` is `'gmail_oauth'`:
        *   Calls `self._send_via_gmail_oauth(...)`.
    *   **IF** `credential.type` is `'smtp'`:
        *   Calls `self._send_via_smtp(...)`.
    *   **Fallback**: If no credential is provided, it checks if the sender ends in `@gmail.com` and tries to find a default Gmail credential (Lines 140-144).

### Step 3: Gmail Execution (`GmailOAuthSender`)
**Location**: `email/gmail_oauth.py`

This does **NOT** use SMTP. It uses the REST API.
1.  **`get_oauth_tokens()`** (Line 44):
    *   Queries the specific `Credential` from the database.
    *   Decrypts the `encrypted_data` field to get `access_token` and `refresh_token`.
2.  **`send_email()`** (Line 321):
    *   Constructs a MIME email object (just like a normal email).
    *   **Base64 Encodes** the raw email bytes.
    *   **API Call**: Sends a `POST` request to `https://gmail.googleapis.com/gmail/v1/users/me/messages/send`.
    *   **Token Refresh**: If the API returns `401 Unauthorized`, it automatically uses the `refresh_token` to get a new `access_token` and retries (Lines 406-425).

### Step 4: SMTP Execution (`SMTPSender`)
**Location**: `email/smtp_sender.py`

1.  **`send_email()`**:
    *   Uses Python's standard `smtplib` or Django's `EmailMessage`.
    *   Connects to host/port (e.g., `smtp.gmail.com:587`).
    *   Performs `login()` with username/password.
    *   Sends the message via standard TCP socket.

## 4. How to Verify / Debug

If you are debugging:
1.  **Check the Logs**: The code is heavily instrumented with `logger.critical`. Look for lines starting with `🚀 ANTIGRAVITY_VERIFY` or `✅ GMAIL OAUTH RESULT`.
2.  **Dispatcher Logic**:
    *   Open `Automation/backend/workflows/email/dispatcher.py`.
    *   The routing logic is explicit at line 95 ("STRICT ROUTING").
3.  **Credential Data**:
    *   Ensure your `Credential` in the database has the correct `type`.
    *   `type='gmail_oauth'` -> Forces API.
    *   `type='smtp'` -> Forces SMTP.
