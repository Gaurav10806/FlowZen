# Backend Core Mechanics Analysis

## 1. Execution Engine Architecture

The FlowZen execution engine follows a strict **3-Layer Architecture** to separate concerns between asynchronous task management, Django integration, and core execution logic.

### Layer 1: The Messenger (Celery Tasks)
*   **File**: `backend/workflows/tasks.py`
*   **Role**: Entry point for asynchronous execution.
*   **Key Function**: `execute_workflow_with_core_engine(execution_id)`
*   **Responsibility**:
    1.  Receives the execution request from the queue.
    2.  Delegates immediately to Layer 2 (`DjangoWorkflowExecutor`).
    3.  Handles success/failure notifications (Email/In-App).
    4.  **Does NOT** contain execution logic.

### Layer 2: The Integrator (Django Executor)
*   **File**: `backend/workflows/execution/django_executor.py`
*   **Role**: Bridge between the database and the raw execution logic.
*   **Key Class**: `DjangoWorkflowExecutor`
*   **Responsibility**:
    1.  **Hooks**: Injects `DjangoExecutionHooks` into the engine. These hooks intercept engine events (Node Start, Node Complete, Error) and persist them to the PostgreSQL database (`ExecutionLog`, `NodeExecution`).
    2.  **Real-time Updates**: Pushes events to the Frontend via WebSockets (`publish_execution_event`).
    3.  **Context**: Loads User and Tenant context from the database to pass to the engine.

### Layer 3: The Brain (Enhanced Execution Engine)
*   **File**: `backend/workflows/services/enhanced_execution_engine.py`
*   **Role**: The deterministic state machine that actually runs the workflow.
*   **Key Class**: `EnhancedExecutionEngine`
*   **Key Logic (`run()` method)**:
    1.  **Initialization**: Marks trigger nodes as `READY` in the `NodeExecutionQueue`.
    2.  **Execution Loop**:
        *   Polls for `READY` nodes using `NodeExecutionQueue.get_ready_nodes()`.
        *   **Concurrency Locking**: Acquires a lock for each node to prevent race conditions in parallel executions.
        *   **Execution**: Calls `execute_node()`, which locates the Action class (e.g., `HttpRequestAction`) and runs it.
        *   **Propagation**: On success, calculates which child nodes are now ready (`mark_parents_completed_and_check_children`).
    3.  **Validation**:
        *   **Silent Failure Detection**: explicitly checks if critical nodes (like Actions or Emails) actually ran. If a workflow finishes "success" but did nothing, it overrides the status to `FAILED`.
    4.  **Idempotency**: Checks if a node has already been executed (to handle retries without side effects).

## 2. Middleware & Security
The application wraps every request in a fortress of middleware (`backend/workflows/middleware_security.py`).

| Middleware | Purpose |
| :--- | :--- |
| **`TenantIsolationMiddleware`** | **CRITICAL**. Intercepts every request. Checks the `Membership` table. If the user doesn't belong to the requested Tenant, it returns `403 Forbidden` instantly. Prevents data leaks. |
| **`PayloadSizeLimitMiddleware`** | Defends against DoS attacks. Rejects payloads > 10MB (Executions) or > 1MB (Default). |
| **`RateLimitMiddleware`** | Uses Redis to track request counts. Limits usage by User ID or IP address (failed auth). |
| **`SecurityAuditMiddleware`** | Logs access to sensitive endpoints (`/credentials/`, `/webhook/`) for compliance. |
| **`InputSanitizationMiddleware`** | Strips dangerous characters (null bytes, script tags) from POST requests to prevent Injection/XSS. |

## 3. Data Flow & State Management

### The "Queue-Based" State Machine
Unlike simple linear scripts, this engine is **Graph-Based and State-Driven**.

1.  **Node State**: Each node execution has a status: `PENDING` -> `READY` -> `LOCKED` -> `RUNNING` -> `COMPLETED` (or `FAILED`).
2.  **Data Passing**:
    *   **N8N Style**: Inputs are grouped by "Handle" (e.g., `main`, `false_branch`).
    *   **Lazy Evaluation**: Data is pulled from parent nodes only when the child is ready to run.
3.  **Observability**:
    *   Every step emits a `WebSocket` event.
    *   Every step creates a `NodeExecution` DB record.
    *   This ensures the Frontend "Live View" is always in sync with the Backend.

## 4. Error Handling & Retries
*   **Task Level**: If the Celery task crashes, it is **NOT** retried automatically to prevent "Zombie Loops" (infinite crashing).
*   **Node Level**:
    *   If a node fails (e.g., API timeout), `RetryService` checks the `retry_policy`.
    *   It uses **Exponential Backoff** (wait 1s, 2s, 4s...) before trying again.
    *   If retries perform, it marks the node as `FAILED` and creates a `DeadLetterItem` for later inspection.
