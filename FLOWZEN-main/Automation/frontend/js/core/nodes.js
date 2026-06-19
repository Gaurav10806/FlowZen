// Enhanced Node Management - Create, Drag, Select, Configure
class NodeManager {
    constructor(canvasManager) {
        this.canvasManager = canvasManager;
        this.nodes = new Map();
        this.selectedNodes = new Set();
        this.draggedNode = null;
        this.nodeCounter = 0;

        this.dragOffset = { x: 0, y: 0 };
        this.isDragging = false;

        this.init();
    }

    init() {
        this.setupDragFromLibrary();
        this.setupNodeSelection();
        this.setupKeyboardShortcuts();
    }

    setupDragFromLibrary() {
        const nodeItems = document.querySelectorAll('.node-item');

        nodeItems.forEach(item => {
            // Make draggable
            item.draggable = true;

            item.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('text/plain', '');
                e.dataTransfer.setData('application/json', JSON.stringify({
                    type: item.dataset.type,
                    category: item.dataset.category
                }));
                item.classList.add('dragging');
            });

            item.addEventListener('dragend', () => {
                item.classList.remove('dragging');
            });
        });

        // Canvas drop handling
        if (this.canvasManager.canvas) {
            this.canvasManager.canvas.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'copy';
            });

            this.canvasManager.canvas.addEventListener('drop', (e) => {
                e.preventDefault();

                try {
                    const data = JSON.parse(e.dataTransfer.getData('application/json'));
                    const canvasPos = this.canvasManager.screenToCanvas(e.clientX, e.clientY);

                    this.createNode(data.type, data.category, canvasPos.x - 100, canvasPos.y - 50);
                } catch (error) {
                    console.error('Failed to create node from drop:', error);
                }
            });
        }
    }

    setupNodeSelection() {
        // Canvas click for deselection
        if (this.canvasManager.canvas) {
            this.canvasManager.canvas.addEventListener('mousedown', (e) => {
                if (e.target === this.canvasManager.canvas ||
                    e.target === this.canvasManager.nodesLayer ||
                    e.target === this.canvasManager.edgesLayer) {

                    if (!e.ctrlKey && !e.metaKey) {
                        this.clearSelection();
                    }
                }
            });
        }
    }

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return; // Don't handle shortcuts when typing
            }

            switch (e.key) {
                case 'Delete':
                case 'Backspace':
                    e.preventDefault();
                    this.deleteSelectedNodes();
                    break;
                case 'a':
                case 'A':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.selectAllNodes();
                    }
                    break;
                case 'c':
                case 'C':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.copySelectedNodes();
                    }
                    break;
                case 'v':
                case 'V':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.pasteNodes();
                    }
                    break;
                case 'd':
                case 'D':
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault();
                        this.duplicateSelectedNodes();
                    }
                    break;
            }
        });
    }

    createNode(type, category, x, y) {
        const nodeId = `node_${++this.nodeCounter}`;

        const nodeData = {
            id: nodeId,
            type: type,
            category: category,
            position: { x, y },
            config: this.getDefaultConfig(type),
            ui: {
                selected: false,
                dragging: false
            }
        };

        const nodeElement = this.createNodeElement(nodeData);

        if (this.canvasManager.nodesLayer) {
            this.canvasManager.nodesLayer.appendChild(nodeElement);
        }

        this.nodes.set(nodeId, nodeData);
        this.setupNodeInteractions(nodeElement, nodeData);

        // Dispatch custom event
        document.dispatchEvent(new CustomEvent('nodeCreated', {
            detail: { nodeId, nodeData }
        }));

        return nodeData;
    }

    createNodeElement(nodeData) {
        const node = document.createElement('div');
        node.className = 'workflow-node';
        node.dataset.nodeId = nodeData.id;
        node.style.left = nodeData.position.x + 'px';
        node.style.top = nodeData.position.y + 'px';

        const nodeInfo = this.getNodeInfo(nodeData.type);

        // Apply dynamic color from registry if available
        const iconStyle = nodeInfo.color
            ? `style="background: ${nodeInfo.color}20; color: ${nodeInfo.color}; border-color: ${nodeInfo.color}40;"`
            : '';

        node.innerHTML = `
            <div class="node-header">
                <div class="node-icon" ${iconStyle}>
                    <i class="${nodeInfo.icon}"></i>
                </div>
                <div class="node-title">${nodeInfo.title}</div>
                <div class="node-menu">
                    <i class="fas fa-ellipsis-v"></i>
                </div>
            </div>
            <div class="node-body">
                <div class="node-description">${nodeInfo.description}</div>
                <div class="node-config-preview"></div>
            </div>
            <div class="node-status">
                <span class="node-status-text">Ready</span>
                <span class="node-execution-time"></span>
            </div>
            <div class="connection-point input" data-port="input"></div>
            <div class="connection-point output" data-port="output"></div>
        `;

        return node;
    }

    setupNodeInteractions(nodeElement, nodeData) {
        // Node selection
        nodeElement.addEventListener('mousedown', (e) => {
            e.stopPropagation();

            if (e.ctrlKey || e.metaKey) {
                this.toggleNodeSelection(nodeData.id);
            } else {
                if (!this.selectedNodes.has(nodeData.id)) {
                    this.clearSelection();
                    this.selectNode(nodeData.id);
                }
            }

            // Start dragging
            this.startNodeDrag(e, nodeData.id);
        });

        // Double click to edit
        nodeElement.addEventListener('dblclick', (e) => {
            e.stopPropagation();
            this.editNode(nodeData.id);
        });

        // Context menu
        nodeElement.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            this.showNodeContextMenu(e, nodeData.id);
        });

        // Node menu button
        const menuBtn = nodeElement.querySelector('.node-menu');
        if (menuBtn) {
            menuBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.showNodeMenu(e, nodeData.id);
            });
        }
    }

    startNodeDrag(e, nodeId) {
        const nodeElement = document.querySelector(`[data-node-id="${nodeId}"]`);
        if (!nodeElement) return;

        this.isDragging = true;
        this.draggedNode = nodeId;

        const rect = nodeElement.getBoundingClientRect();
        const canvasRect = this.canvasManager.canvas.getBoundingClientRect();

        this.dragOffset = {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top
        };

        nodeElement.classList.add('dragging');

        // Setup drag event listeners
        const handleMouseMove = (e) => {
            if (this.isDragging && this.draggedNode) {
                this.updateNodeDrag(e);
            }
        };

        const handleMouseUp = () => {
            this.endNodeDrag();
            document.removeEventListener('mousemove', handleMouseMove);
            document.removeEventListener('mouseup', handleMouseUp);
        };

        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);
    }

    updateNodeDrag(e) {
        if (!this.draggedNode) return;

        const canvasPos = this.canvasManager.screenToCanvas(
            e.clientX - this.dragOffset.x,
            e.clientY - this.dragOffset.y
        );

        // Update all selected nodes if multiple are selected
        const nodesToMove = this.selectedNodes.has(this.draggedNode)
            ? Array.from(this.selectedNodes)
            : [this.draggedNode];

        const draggedNodeData = this.nodes.get(this.draggedNode);
        const deltaX = canvasPos.x - draggedNodeData.position.x;
        const deltaY = canvasPos.y - draggedNodeData.position.y;

        nodesToMove.forEach(nodeId => {
            this.moveNode(nodeId, deltaX, deltaY);
        });
    }

    endNodeDrag() {
        if (this.draggedNode) {
            const nodeElement = document.querySelector(`[data-node-id="${this.draggedNode}"]`);
            if (nodeElement) {
                nodeElement.classList.remove('dragging');
            }

            // Dispatch custom event
            document.dispatchEvent(new CustomEvent('nodeMoved', {
                detail: { nodeId: this.draggedNode }
            }));
        }

        this.isDragging = false;
        this.draggedNode = null;
        this.dragOffset = { x: 0, y: 0 };
    }

    moveNode(nodeId, deltaX, deltaY) {
        const nodeData = this.nodes.get(nodeId);
        const nodeElement = document.querySelector(`[data-node-id="${nodeId}"]`);

        if (!nodeData || !nodeElement) return;

        nodeData.position.x += deltaX;
        nodeData.position.y += deltaY;

        nodeElement.style.left = nodeData.position.x + 'px';
        nodeElement.style.top = nodeData.position.y + 'px';
    }

    selectNode(nodeId) {
        this.selectedNodes.add(nodeId);

        const nodeElement = document.querySelector(`[data-node-id="${nodeId}"]`);
        if (nodeElement) {
            nodeElement.classList.add('selected');
        }

        const nodeData = this.nodes.get(nodeId);
        if (nodeData) {
            nodeData.ui.selected = true;
        }

        // Dispatch custom event
        document.dispatchEvent(new CustomEvent('nodeSelected', {
            detail: { nodeId, selectedNodes: Array.from(this.selectedNodes) }
        }));
    }

    deselectNode(nodeId) {
        this.selectedNodes.delete(nodeId);

        const nodeElement = document.querySelector(`[data-node-id="${nodeId}"]`);
        if (nodeElement) {
            nodeElement.classList.remove('selected');
        }

        const nodeData = this.nodes.get(nodeId);
        if (nodeData) {
            nodeData.ui.selected = false;
        }

        // Dispatch custom event
        document.dispatchEvent(new CustomEvent('nodeDeselected', {
            detail: { nodeId, selectedNodes: Array.from(this.selectedNodes) }
        }));
    }

    toggleNodeSelection(nodeId) {
        if (this.selectedNodes.has(nodeId)) {
            this.deselectNode(nodeId);
        } else {
            this.selectNode(nodeId);
        }
    }

    clearSelection() {
        const selectedNodeIds = Array.from(this.selectedNodes);
        selectedNodeIds.forEach(nodeId => {
            this.deselectNode(nodeId);
        });
    }

    selectAllNodes() {
        this.nodes.forEach((nodeData, nodeId) => {
            this.selectNode(nodeId);
        });
    }

    deleteNode(nodeId) {
        const nodeData = this.nodes.get(nodeId);
        const nodeElement = document.querySelector(`[data-node-id="${nodeId}"]`);

        if (!nodeData || !nodeElement) return;

        // Remove from selection
        this.deselectNode(nodeId);

        // Remove from DOM
        nodeElement.remove();

        // Remove from data
        this.nodes.delete(nodeId);

        // Dispatch custom event
        document.dispatchEvent(new CustomEvent('nodeDeleted', {
            detail: { nodeId, nodeData }
        }));
    }

    deleteSelectedNodes() {
        const selectedNodeIds = Array.from(this.selectedNodes);
        selectedNodeIds.forEach(nodeId => {
            this.deleteNode(nodeId);
        });
    }

    copySelectedNodes() {
        const selectedNodeIds = Array.from(this.selectedNodes);
        const nodesToCopy = selectedNodeIds.map(nodeId => {
            const nodeData = this.nodes.get(nodeId);
            return { ...nodeData }; // Deep copy
        });

        // Store in clipboard (simplified)
        this.clipboard = nodesToCopy;

        console.log(`Copied ${nodesToCopy.length} nodes to clipboard`);
    }

    pasteNodes() {
        if (!this.clipboard || this.clipboard.length === 0) return;

        this.clearSelection();

        const pastedNodes = [];

        this.clipboard.forEach(nodeData => {
            const newNode = this.createNode(
                nodeData.type,
                nodeData.category,
                nodeData.position.x + 50, // Offset to avoid overlap
                nodeData.position.y + 50
            );

            // Copy configuration
            newNode.config = { ...nodeData.config };

            pastedNodes.push(newNode.id);
            this.selectNode(newNode.id);
        });

        console.log(`Pasted ${pastedNodes.length} nodes`);
    }

    duplicateSelectedNodes() {
        this.copySelectedNodes();
        this.pasteNodes();
    }

    editNode(nodeId) {
        // Dispatch custom event for configuration panel
        document.dispatchEvent(new CustomEvent('nodeEdit', {
            detail: { nodeId }
        }));
    }

    showNodeContextMenu(e, nodeId) {
        // Create context menu (implement as needed)
        console.log(`Context menu for node ${nodeId}`);
    }

    showNodeMenu(e, nodeId) {
        // Show node menu dropdown (implement as needed)
        console.log(`Node menu for node ${nodeId}`);
    }

    updateNodeConfig(nodeId, config) {
        const nodeData = this.nodes.get(nodeId);
        if (!nodeData) return;

        nodeData.config = { ...nodeData.config, ...config };

        // Update node preview
        this.updateNodePreview(nodeId);

        // Dispatch custom event
        document.dispatchEvent(new CustomEvent('nodeConfigChanged', {
            detail: { nodeId, config: nodeData.config }
        }));
    }

    updateNodePreview(nodeId) {
        const nodeData = this.nodes.get(nodeId);
        const nodeElement = document.querySelector(`[data-node-id="${nodeId}"]`);

        if (!nodeData || !nodeElement) return;

        const previewElement = nodeElement.querySelector('.node-config-preview');
        if (previewElement) {
            previewElement.innerHTML = this.generateConfigPreview(nodeData);
        }
    }

    generateConfigPreview(nodeData) {
        // Generate a preview of the node configuration
        const config = nodeData.config;
        const preview = [];

        Object.entries(config).forEach(([key, value]) => {
            if (value && typeof value === 'string' && value.length > 0) {
                preview.push(`${key}: ${value.substring(0, 20)}${value.length > 20 ? '...' : ''}`);
            }
        });

        return preview.slice(0, 2).join('<br>');
    }

    updateNodeStatus(nodeId, status, executionTime = null) {
        const nodeElement = document.querySelector(`[data-node-id="${nodeId}"]`);
        if (!nodeElement) return;

        // Update node class for visual status
        nodeElement.className = `workflow-node ${status}`;

        // Update status text
        const statusText = nodeElement.querySelector('.node-status-text');
        if (statusText) {
            statusText.textContent = status.charAt(0).toUpperCase() + status.slice(1);
        }

        // Update execution time
        if (executionTime !== null) {
            const timeElement = nodeElement.querySelector('.node-execution-time');
            if (timeElement) {
                timeElement.textContent = `${executionTime}ms`;
            }
        }
    }

    getDefaultConfig(nodeType) {
        const defaultConfigs = {
            'openai': {
                model: 'gpt-3.5-turbo',
                prompt: '',
                temperature: 0.7,
                max_tokens: 1000
            },
            'gmail': {
                to: '',
                subject: '',
                body: '',
                html: false
            },
            'http_request': {
                method: 'GET',
                url: '',
                headers: {},
                body: ''
            },
            'if_else': {
                condition: '',
                true_path: 'continue',
                false_path: 'stop'
            },
            'webhook': {
                url: '',
                method: 'POST',
                headers: {}
            },
            'database': {
                query: '',
                connection: ''
            },
            'variable': {
                name: '',
                value: '',
                type: 'string'
            }
        };

        return defaultConfigs[nodeType] || {};
    }

    getNodeInfo(nodeType) {
        // Priority 1: Check Global Registry (Enhanced Node Library)
        if (window.NODE_REGISTRY && window.NODE_REGISTRY[nodeType]) {
            const def = window.NODE_REGISTRY[nodeType];
            return {
                title: def.label || def.name,
                icon: def.icon,
                description: def.description || 'Custom Node',
                color: def.color // Pass color for dynamic styling
            };
        }

        const nodeInfos = {
            'openai': {
                title: 'OpenAI GPT',
                icon: 'fas fa-robot',
                description: 'AI text generation and processing'
            },
            'claude': {
                title: 'Claude AI',
                icon: 'fas fa-brain',
                description: 'Anthropic AI assistant'
            },
            'gmail': {
                title: 'Gmail',
                icon: 'fab fa-google',
                description: 'Send and receive emails'
            },
            'slack': {
                title: 'Slack',
                icon: 'fab fa-slack',
                description: 'Team messaging and notifications'
            },
            'discord': {
                title: 'Discord',
                icon: 'fab fa-discord',
                description: 'Community chat and notifications'
            },
            'http_request': {
                title: 'HTTP Request',
                icon: 'fas fa-paper-plane',
                description: 'Make API calls and web requests'
            },
            'webhook': {
                title: 'Webhook',
                icon: 'fas fa-link',
                description: 'Receive HTTP callbacks'
            },
            'if_else': {
                title: 'Conditional Logic',
                icon: 'fas fa-code-branch',
                description: 'If/else branching logic'
            },
            'switch': {
                title: 'Switch Router',
                icon: 'fas fa-random',
                description: 'Multi-path routing'
            },
            'postgresql': {
                title: 'PostgreSQL',
                icon: 'fas fa-elephant',
                description: 'Relational database operations'
            },
            'redis': {
                title: 'Redis',
                icon: 'fas fa-memory',
                description: 'In-memory cache operations'
            },
            'mongodb': {
                title: 'MongoDB',
                icon: 'fas fa-leaf',
                description: 'Document database operations'
            },
            'variable': {
                title: 'Variable Store',
                icon: 'fas fa-box',
                description: 'Store and retrieve data'
            },
            'graphql': {
                title: 'GraphQL',
                icon: 'fas fa-project-diagram',
                description: 'GraphQL query execution'
            },
            'rest_api': {
                title: 'REST API',
                icon: 'fas fa-exchange-alt',
                description: 'RESTful API operations'
            }
        };

        return nodeInfos[nodeType] || {
            title: nodeType.charAt(0).toUpperCase() + nodeType.slice(1),
            icon: 'fas fa-cog',
            description: 'Custom node'
        };
    }

    // Get all nodes data for serialization
    getNodesData() {
        return Array.from(this.nodes.values());
    }

    // Load nodes from data
    loadNodesData(nodesData) {
        // Clear existing nodes
        this.clearAllNodes();

        // Create nodes from data
        nodesData.forEach(nodeData => {
            const nodeElement = this.createNodeElement(nodeData);

            if (this.canvasManager.nodesLayer) {
                this.canvasManager.nodesLayer.appendChild(nodeElement);
            }

            this.nodes.set(nodeData.id, nodeData);
            this.setupNodeInteractions(nodeElement, nodeData);

            // Update node counter
            const nodeNum = parseInt(nodeData.id.split('_')[1]);
            if (nodeNum >= this.nodeCounter) {
                this.nodeCounter = nodeNum;
            }
        });
    }

    clearAllNodes() {
        this.nodes.forEach((nodeData, nodeId) => {
            this.deleteNode(nodeId);
        });
        this.nodeCounter = 0;
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NodeManager;
}