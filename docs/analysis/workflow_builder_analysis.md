# Workflow Builder Analysis

## Overview
The Workflow Builder is a modular, event-driven frontend application built with vanilla JavaScript using a "Manager" pattern. It orchestrates the creation, configuration, and serialization of automation workflows.

## Core Architecture
The application is structured around specialized manager classes, coordinated by a central `WorkflowApp` (in `main.js`). The global state is distributed across these managers but accessible via the `window` object for inter-communication.

| Component | File | Responsibility |
|-----------|------|----------------|
| **WorkflowManager** | `js/core/workflow-manager.js` | Managing the workflow lifecycle (load, save, execute), auto-save, and version history. **Responsible for JSON serialization.** |
| **NodeManager** | `js/core/nodes.js` | Managing node state, DOM elements, drag-and-drop, selection, and configuration data. |
| **EdgeManager** | `js/edges.js` | Managing connections (SVG paths), validation, and edge state. |
| **ConfigManager** | `js/main.js` | Generating configuration forms for selected nodes and updating `NodeManager` state. |
| **AdvancedCanvas** | `js/core/advanced-canvas.js` | Handling the workspace view (pan, zoom, grid, minimap) and coordinate systems. |

## Data Flow & JSON Generation

The "source of truth" for the workflow is the runtime state held by `NodeManager` and `EdgeManager`. The `WorkflowManager` aggregates this state to generate the JSON.

### 1. Node Creation
- **Source**: Users drag nodes from the sidebar (managed by `EnhancedNodeLibrary`, though `NodeManager` creates the listeners).
- **Process**: `NodeManager.createNode` is called, creating a data object and a DOM element.
- **State**: The node data is stored in `NodeManager.nodes` (a Map).

### 2. Configuration
- **UI**: When a node is double-clicked or selected, `ConfigManager.showNodeConfig` is triggered.
- **Form Generation**: `ConfigManager` dynamically builds an HTML form based on `node.type`.
- **Update**: On save, `ConfigManager.saveNodeConfig` extracts form values and calls `NodeManager.updateNodeConfig`.
- **Result**: The `config` object within the node's state in `NodeManager` is updated.

### 3. Serialization (JSON Generation)
The `WorkflowManager.collectWorkflowData()` method is responsible for converting the runtime state into the final JSON structure for the backend.

**Serialization Logic:**
```javascript
collectWorkflowData() {
    // 1. Iterate over window.nodeManager.nodes
    const nodes = [];
    window.nodeManager.nodes.forEach(node => {
        nodes.push({
            id: node.id,
            name: node.name,
            type: node.type,
            position: node.position,
            config: node.config || {}, // <--- The crucial configuration data
            credentials: node.credentials,
            notes: node.notes || ''
        });
    });

    // 2. Iterate over window.edgeManager.edges
    const edges = [];
    window.edgeManager.edges.forEach(edge => {
        edges.push({
            id: edge.id,
            source: edge.sourceNode,
            target: edge.targetNode,
            sourcePort: edge.sourcePort || 'output',
            targetPort: edge.targetPort || 'input',
            condition: edge.condition || 'always'
        });
    });

    // 3. Combine
    return {
        nodes,
        edges,
        name: this.getWorkflowName(),
        description: this.getWorkflowDescription()
    };
}
```

## Config Manager Details
Contrary to the file structure suggesting `node-config-panel.js`, the **ConfigManager** is defined within `js/main.js`.

- **HTML Templates**: It uses template literals to generate distinct forms for `email`, `webhook`, `http`, `ai-agent`, `telegram_trigger`, etc.
- **Data Binding**: It manually maps form inputs (e.g., `#config-url`) to the `config` object keys.
- **Credential Integration**: It dynamically populates credential dropdowns using `window.credentialManager`.
- **Monaco Editor**: For code nodes, it initializes a Monaco Editor instance.

## Key Findings
1.  **Missing File**: `js/core/node-config-panel.js` is empty/unused. The logic resides in `main.js`.
2.  **Event Driven**: The system uses custom events (`nodeCreated`, `nodeConfigChanged`, `save-btn` click) to trigger saves and updates.
3.  **Authentication**: Credential selection in the UI stores the `credential_id` in the node's config, which the backend likely resolves during execution.

## Technical Debt / Discrepancy
There is a significant architectural disconnect between the **Enhanced Node Library** and the **Config Manager**:

1.  **Enhanced Node Library (`enhanced-node-library.js`)**: Designed to be dynamic. It registers nodes with a `fields` array, intending for the UI to generate forms based on these definitions (Data-Driven UI).
2.  **Config Manager (`main.js`)**: **Ignores** these dynamic definitions. Instead, it uses a massive `switch` statement with **hardcoded HTML strings** for every single node type (lines 697-1014).

**Impact**: 
- Adding a new node requires modifying `main.js` to add a new case to the switch statement, defeating the purpose of the modular registry.
- The `fields` defined in `enhanced-node-library.js` are effectively unused by the configuration panel.

## Recommendations
- **Refactoring**: Move `ConfigManager` from `main.js` to `js/core/node-config-panel.js` (or `config-manager.js`) to improve maintainability and match the file structure.
- **Standardization**: The current `switch` statement in `ConfigManager.getConfigForm` should be replaced with a dynamic form generator that consumes the `fields` array from `NODE_REGISTRY`. This would unify the architecture and allow new nodes to be added solely by registering them in the library.
