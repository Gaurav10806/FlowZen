# Project Overview & Architecture Analysis

## 1. High-Level Architecture
**FlowZen** is a powerful automation platform inspired by tools like n8n or Zapier, built with a **Django** backend and a monolithic architecture that serves a frontend via Django templates. It uses a distributed task queue system for executing workflows.

### Core Technology Stack
-   **Backend Framework**: Django 5.0 + Django REST Framework (DRF)
-   **Database**: PostgreSQL
-   **Async Task Queue**: Celery 5.3 + Redis (Broker & Result Backend)
-   **Real-time**: Django Channels (WebSockets)
-   **Frontend**: Django Templates + Static Files (JS/CSS)
-   **Containerization**: Docker + Docker Compose

## 2. Directory Structure Breakdown

### Root Directory (`/`)
-   **`Automation/`**: The main source code repository.
-   **`docker/`**: Configuration files for Docker environments (`.env`).
-   **`scripts/`**: Utility scripts for maintenance and updates (`UPDATE_MANAGER.py`, `DEMO_COMMANDS.sh`).
-   **`Dockerfile`**: Defines the backend/worker logic.
    -   Based on `python:3.12-slim`.
    -   Installs system deps (`libpq-dev`, `build-essential`).
    -   Copies `Automation/backend` and `Automation/frontend`.
    -   Runs as non-root user `appuser`.
-   **`docker-compose.yml`**: Orchestrates 5 services:
    1.  `db` (PostgreSQL 16)
    2.  `redis` (Redis 7)
    3.  `backend` (Django API & Server)
    4.  `worker` (Celery Worker for executing tasks)
    5.  `beat` (Celery Beat for scheduled workflows)
-   **`requirements.txt`**: (Newly created) Lists all Python dependencies.

### Backend (`Automation/backend/`)
This is the core logic. Key directories:
-   **`project/`**: Django project settings.
    -   `settings.py`: Configures Apps, Middleware (Security, Tenant Isolation), Celery, Email (SMTP/Gmail OAuth), and Logging.
-   **`workflows/`**: The heart of the application.
    -   **`models.py`**: Defines the data schema (see section 3).
    -   **`nodes/`**: Implementation of individual nodes (HTTP, Email, AI, etc.).
    -   **`tasks.py`**: Celery tasks for executing workflows asynchronously.
    -   **`views.py`**: API endpoints for the frontend editor.
-   **`authentication/`**:
    -   Handles User Auth, OTP (One-Time Password) logic, and JWT token management.
-   **`notifications/`**:
    -   Likely handles system notifications (Email/WebSocket).

### Frontend (`Automation/frontend/`)
Served directly by Django:
-   **`templates/`**: HTML files (Jinja2/Django templates).
-   **`static/`**: Assets (CSS, Images).
-   **`js/`**: Client-side logic for the workflow editor.
-   **`css/`**: Styles.

## 3. Core Data Models (Deep Dive)

### Workflows (`Workflow`)
The "Blueprint" for automation.
-   **Fields**: `name`, `status` (draft/published), `graph` (JSON representation of nodes/edges), `trigger_data`.
-   **Features**: Versioning, Environments (dev/staging/prod), Webhook configurations.

### Nodes (`Node`)
The building blocks.
-   **Types**: `trigger`, `action`, `condition`.
-   **Action Types**: `http_request`, `email`, `ai_agent`, `python_code`, `delay`, etc.
-   **Execution Logic**: Each node has specific parameters stored in `config`.

### Executions (`WorkflowExecution`)
A single run of a workflow.
-   **Lifecycle**: `pending` -> `running` -> `completed` / `failed`.
-   **Data**: Stores `input_payload`, `result`, and execution logs.
-   **Tracing**: Uses `correlation_id` for tracking distributed tasks.

### Node Executions (`NodeExecution`)
The result of running a single node.
-   **Data**: `input_data`, `output`, `status`, `logs`.
-   **Retry Logic**: Configurable retries and backoff strategies.

### Credentials (`Credential`)
Secure storage for external API keys.
-   **Encryption**: Fields are encrypted at rest using `django-encrypted-model-fields`.
-   **Types**: `gmail_oauth`, `telegram_bot`, `openai_api_key`, etc.

## 4. Execution Flow (How it works)

1.  **Trigger**:
    -   **Manual**: User clicks "Run" in UI -> API call -> Celery Task.
    -   **Webhook**: External request -> API Endpoint -> Celery Task.
    -   **Schedule**: Celery Beat -> Periodic Task -> Celery Worker.
2.  **Orchestration**:
    -   The `workflow_engine` reads the `graph`.
    -   It determines the start node and traverses edges.
3.  **Task Processing**:
    -   Each node execution is a "job".
    -   If the node is async (e.g., Delay, Wait for Webhook), the state is saved to DB, and the task halts until resumption.
    -   If sync (e.g., Python Code, HTTP), it runs immediately in the Worker.

## 5. Security & Isolation
-   **Tenant Isolation**: Middleware ensures users only access their own data.
-   **ratelimit**: Prevents abuse of API endpoints.
-   **django-encrypted-model-fields**: Protects sensitive credentials in the DB.
-   **RestrictedPython**: Used for safely executing user-provided Python code (sandboxing).

## 6. requirements.txt Analysis
The definition file you requested contains:
-   **Frameworks**: `Django`, `djangorestframework`, `celery`.
-   **Database/Storage**: `psycopg2-binary` (Postgres), `redis`.
-   **Integrations**: `google-api-python-client` (Gmail/Calendar), `stripe` (Payments), `discord.py`.
-   **Utilities**: `requests`, `pillow` (Images), `pandas` (Data processing).
-   **Monitoring**: `sentry-sdk` (Error tracking), `django-prometheus` (Metrics).
