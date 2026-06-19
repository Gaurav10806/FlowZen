# Frontend-Backend Data Flow Analysis

## 1. Overview
The application uses a **Hybrid Communication Model**:
*   **REST API (HTTP)**: For configuration, CRUD operations, and triggering workflows.
*   **WebSockets (WS)**: For real-time execution logs and status updates.

## 2. HTTP Layer (REST API)
**Frontend Client**: `Automation/frontend/js/api.js` (`APIManager` class)

### Key Characteristics
*   **Authentication**:
    *   Uses **Session-based Authentication** via Cookies.
    *   **CSRF Protection**: Extracts `csrftoken` from cookies and sends it in the `X-CSRFToken` header.
    *   `credentials: 'same-origin'` ensures cookies are sent with requests.
*   **Endpoints**:
    *   `GET /api/workflows/`: List workflows.
    *   `POST /api/workflows/`: Create new workflow.
    *   `PUT /api/workflows/<id>/`: Save workflow graph (JSON).
    *   `POST /api/workflows/<id>/execute/`: Trigger execution via Celery.
    *   `POST /api/oauth/gmail/initiate/`: Start OAuth flow.

### Data Flow Example: Saving a Workflow
1.  **Frontend**: `APIManager.saveWorkflow()` collects `nodes` and `edges` from the canvas.
2.  **Request**: `POST /api/workflows/` with JSON payload.
3.  **Backend**: `WorkflowSerializer.update()` (in `serializers.py`) receives the JSON.
4.  **Sync**: The backend updates the `Workflow` model AND synchronizes the `Node` and `WorkflowEdge` relational tables (Hybrid Schema).

## 3. Real-Time Layer (WebSockets)
**Frontend Client**: `Automation/frontend/js/core/execution-monitor.js` (`ExecutionMonitor` class)
**Backend Server**: `Automation/backend/workflows/consumers.py` (`ExecutionLogConsumer`)

### Architecture
1.  **Connection**:
    *   **Protocol**: `ws://` (or `wss://` in production).
    *   **Path**: `ws/execution/<execution_id>/` (Backend) vs `ws/executions/` (Frontend mismatch - see below).
2.  **Event Loop**:
    *   **Engine**: As the `EnhancedExecutionEngine` runs, it emits events (start, node_complete, error).
    *   **Layer**: `publish_execution_event` pushes these events to the Django Channels **Group** (`execution_<id>`).
    *   **Consumer**: `ExecutionLogConsumer` listens to this group and forwards messages to the connected WebSocket client.
    *   **Frontend**: `ExecutionMonitor.handleWebSocketMessage()` receives JSON and updates the UI (Green dots, logs, progress bars).

### ⚠️ Critical Mismatch Detected
*   **Frontend Expectation**: The `ExecutionMonitor` tries to connect to a **Global Stream** at `/ws/executions/` (Plural) to monitor *all* executions.
    *   Code: `const wsUrl = ... + '/ws/executions/';`
*   **Backend Reality**: The `routing.py` only defines a **Specific Stream** at `/ws/execution/(?P<execution_id>...)/` (Singular).
    *   Code: `re_path(r"ws/execution/(?P<execution_id>...)/$", ...)`

**Consequence**: The "Live Execution Monitor" dashboard will likely fail to connect (404 Error) unless the frontend is updated to connect to specific IDs, or the backend is updated to support a global "Firehose" channel.

## 4. Summary Diagram

```mermaid
graph TD
    Client[Frontend (React/JS)] -->|HTTP POST| API[Django REST API]
    API -->|Async Task| Celery[Celery Worker]
    Celery -->|Run| Engine[Execution Engine]
    
    Engine -->|Update| DB[(PostgreSQL)]
    Engine -->|Emit Event| Channel[Redis Channel Layer]
    
    Client -->|WebSocket| Consumer[Django Channels Consumer]
    Channel -->|Push| Consumer
    Consumer -->|Stream JSON| Client
```
