// Enhanced Edge/Connection Management
class EdgeManager {
    constructor(canvasManager, nodeManager) {
        this.canvasManager = canvasManager;
        this.nodeManager = nodeManager;
        this.edges = new Map();
        this.edgeCounter = 0;
        
        this.isConnecting = false;
        this.connectionStart = null;
        this.temporaryEdge = null;
        
        this.init();
    }
    
    init() {
        this.setupConnectionEvents();
        this.setupEdgeInteractions();
    }
    
    setupConnectionEvents() {
        // Connection point interactions
        document.addEventListener('mousedown', (e) => {
            if (e.target.classList.contains('connection-point')) {
                e.stopPropagation();
                this.startConnection(e);
            }
        });
        
        document.addEventListener('mousemove', (e) => {
            if (this.isConnecting) {
                this.updateTemporaryConnection(e);
            }
        });
        
        document.addEventListener('mouseup', (e) => {
            if (this.isConnecting) {
                this.endConnection(e);
            }
        });
        
        // Prevent default drag behavior on connection points
        document.addEventListener('dragstart', (e) => {
            if (e.target.classList.contains('connection-point')) {
                e.preventDefault();
            }
        });
    }
    
    setupEdgeInteractions() {
        // Edge selection and deletion
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('edge')) {
                e.stopPropagation();
                this.selectEdge(e.target.dataset.edgeId);
            }
        });
        
        // Edge context menu
        document.addEventListener('contextmenu', (e) => {
            if (e.target.classList.contains('edge')) {
                e.preventDefault();
                this.showEdgeContextMenu(e, e.target.dataset.edgeId);
            }
        });
        
        // Keyboard shortcuts for edge operations
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }
            
            if (e.key === 'Delete' || e.key === 'Backspace') {
                this.deleteSelectedEdges();
            }
        });
    }
    
    startConnection(e) {
        const connectionPoint = e.target;
        const nodeElement = connectionPoint.closest('.workflow-node');
        
        if (!nodeElement) return;
        
        const nodeId = nodeElement.dataset.nodeId;
        const portType = connectionPoint.dataset.port;
        
        // Only allow connections from output ports
        if (portType !== 'output') return;
        
        this.isConnecting = true;
        this.connectionStart = {
            nodeId: nodeId,
            port: portType,
            element: connectionPoint,
            position: this.getConnectionPointPosition(connectionPoint)
        };
        
        // Create temporary edge for visual feedback
        this.createTemporaryEdge(this.connectionStart.position, { x: e.clientX, y: e.clientY });
        
        // Add visual feedback
        connectionPoint.classList.add('connecting');
        document.body.style.cursor = 'crosshair';
    }
    
    updateTemporaryConnection(e) {
        if (!this.isConnecting || !this.temporaryEdge) return;
        
        const canvasPos = this.canvasManager.screenToCanvas(e.clientX, e.clientY);
        this.updateTemporaryEdgePath(this.connectionStart.position, canvasPos);
        
        // Highlight valid connection targets
        this.highlightValidTargets(e);
    }
    
    endConnection(e) {
        if (!this.isConnecting) return;
        
        const targetElement = document.elementFromPoint(e.clientX, e.clientY);
        
        if (targetElement && targetElement.classList.contains('connection-point')) {
            const targetNodeElement = targetElement.closest('.workflow-node');
            
            if (targetNodeElement && targetElement.dataset.port === 'input') {
                const targetNodeId = targetNodeElement.dataset.nodeId;
                
                // Don't allow self-connections
                if (targetNodeId !== this.connectionStart.nodeId) {
                    this.createEdge(
                        this.connectionStart.nodeId,
                        targetNodeId,
                        this.connectionStart.port,
                        targetElement.dataset.port
                    );
                }
            }
        }
        
        this.cleanupConnection();
    }
    
    cleanupConnection() {
        this.isConnecting = false;
        
        // Remove temporary edge
        if (this.temporaryEdge) {
            this.temporaryEdge.remove();
            this.temporaryEdge = null;
        }
        
        // Remove visual feedback
        if (this.connectionStart) {
            this.connectionStart.element.classList.remove('connecting');
        }
        
        document.body.style.cursor = '';
        this.connectionStart = null;
        
        // Remove target highlighting
        document.querySelectorAll('.connection-point.valid-target').forEach(point => {
            point.classList.remove('valid-target');
        });
    }
    
    createEdge(sourceNodeId, targetNodeId, sourcePort, targetPort) {
        const edgeId = `edge_${++this.edgeCounter}`;
        
        // Check if connection already exists
        const existingEdge = this.findExistingEdge(sourceNodeId, targetNodeId, sourcePort, targetPort);
        if (existingEdge) {
            console.warn('Connection already exists');
            return null;
        }
        
        const edgeData = {
            id: edgeId,
            source: sourceNodeId,
            target: targetNodeId,
            sourcePort: sourcePort,
            targetPort: targetPort,
            condition: 'always',
            ui: {
                selected: false
            }
        };
        
        const edgeElement = this.createEdgeElement(edgeData);
        
        if (this.canvasManager.edgesLayer) {
            this.canvasManager.edgesLayer.appendChild(edgeElement);
        }
        
        this.edges.set(edgeId, edgeData);
        this.updateEdgePosition(edgeId);
        
        // Dispatch custom event
        document.dispatchEvent(new CustomEvent('edgeCreated', {
            detail: { edgeId, edgeData }
        }));
        
        return edgeData;
    }
    
    createEdgeElement(edgeData) {
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.classList.add('edge');
        path.dataset.edgeId = edgeData.id;
        path.setAttribute('marker-end', 'url(#arrowhead)');
        
        return path;
    }
    
    createTemporaryEdge(startPos, endPos) {
        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.classList.add('edge', 'temporary');
        
        if (this.canvasManager.edgesLayer) {
            this.canvasManager.edgesLayer.appendChild(path);
        }
        
        this.temporaryEdge = path;
        this.updateTemporaryEdgePath(startPos, endPos);
    }
    
    updateTemporaryEdgePath(startPos, endPos) {
        if (!this.temporaryEdge) return;
        
        const pathData = this.generateBezierPath(startPos, endPos);
        this.temporaryEdge.setAttribute('d', pathData);
    }
    
    updateEdgePosition(edgeId) {
        const edgeData = this.edges.get(edgeId);
        const edgeElement = document.querySelector(`[data-edge-id="${edgeId}"]`);
        
        if (!edgeData || !edgeElement) return;
        
        const sourceNode = document.querySelector(`[data-node-id="${edgeData.source}"]`);
        const targetNode = document.querySelector(`[data-node-id="${edgeData.target}"]`);
        
        if (!sourceNode || !targetNode) return;
        
        const sourcePoint = sourceNode.querySelector(`.connection-point.${edgeData.sourcePort}`);
        const targetPoint = targetNode.querySelector(`.connection-point.${edgeData.targetPort}`);
        
        if (!sourcePoint || !targetPoint) return;
        
        const startPos = this.getConnectionPointPosition(sourcePoint);
        const endPos = this.getConnectionPointPosition(targetPoint);
        
        const pathData = this.generateBezierPath(startPos, endPos);
        edgeElement.setAttribute('d', pathData);
    }
    
    generateBezierPath(startPos, endPos) {
        const dx = endPos.x - startPos.x;
        const dy = endPos.y - startPos.y;
        
        // Control points for smooth curves
        const controlOffset = Math.max(Math.abs(dx) * 0.5, 100);
        
        const cp1x = startPos.x + controlOffset;
        const cp1y = startPos.y;
        const cp2x = endPos.x - controlOffset;
        const cp2y = endPos.y;
        
        return `M ${startPos.x} ${startPos.y} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${endPos.x} ${endPos.y}`;
    }
    
    getConnectionPointPosition(connectionPoint) {
        const rect = connectionPoint.getBoundingClientRect();
        const canvasRect = this.canvasManager.canvas.getBoundingClientRect();
        
        const centerX = rect.left + rect.width / 2 - canvasRect.left;
        const centerY = rect.top + rect.height / 2 - canvasRect.top;
        
        return this.canvasManager.screenToCanvas(
            centerX + canvasRect.left,
            centerY + canvasRect.top
        );
    }
    
    highlightValidTargets(e) {
        // Remove previous highlights
        document.querySelectorAll('.connection-point.valid-target').forEach(point => {
            point.classList.remove('valid-target');
        });
        
        // Find connection points under cursor
        const elementsUnderCursor = document.elementsFromPoint(e.clientX, e.clientY);
        
        elementsUnderCursor.forEach(element => {
            if (element.classList.contains('connection-point') && 
                element.dataset.port === 'input') {
                
                const nodeElement = element.closest('.workflow-node');
                if (nodeElement && nodeElement.dataset.nodeId !== this.connectionStart.nodeId) {
                    element.classList.add('valid-target');
                }
            }
        });
    }
    
    findExistingEdge(sourceNodeId, targetNodeId, sourcePort, targetPort) {
        for (const [edgeId, edgeData] of this.edges) {
            if (edgeData.source === sourceNodeId &&
                edgeData.target === targetNodeId &&
                edgeData.sourcePort === sourcePort &&
                edgeData.targetPort === targetPort) {
                return edgeData;
            }
        }
        return null;
    }
    
    selectEdge(edgeId) {
        // Clear previous selections
        this.clearEdgeSelection();
        
        const edgeElement = document.querySelector(`[data-edge-id="${edgeId}"]`);
        const edgeData = this.edges.get(edgeId);
        
        if (edgeElement && edgeData) {
            edgeElement.classList.add('selected');
            edgeData.ui.selected = true;
            
            // Dispatch custom event
            document.dispatchEvent(new CustomEvent('edgeSelected', {
                detail: { edgeId, edgeData }
            }));
        }
    }
    
    clearEdgeSelection() {
        document.querySelectorAll('.edge.selected').forEach(edge => {
            edge.classList.remove('selected');
        });
        
        this.edges.forEach(edgeData => {
            edgeData.ui.selected = false;
        });
    }
    
    deleteEdge(edgeId) {
        const edgeElement = document.querySelector(`[data-edge-id="${edgeId}"]`);
        const edgeData = this.edges.get(edgeId);
        
        if (edgeElement) {
            edgeElement.remove();
        }
        
        if (edgeData) {
            this.edges.delete(edgeId);
            
            // Dispatch custom event
            document.dispatchEvent(new CustomEvent('edgeDeleted', {
                detail: { edgeId, edgeData }
            }));
        }
    }
    
    deleteSelectedEdges() {
        const selectedEdges = [];
        
        this.edges.forEach((edgeData, edgeId) => {
            if (edgeData.ui.selected) {
                selectedEdges.push(edgeId);
            }
        });
        
        selectedEdges.forEach(edgeId => {
            this.deleteEdge(edgeId);
        });
    }
    
    showEdgeContextMenu(e, edgeId) {
        // Create context menu for edge operations
        console.log(`Edge context menu for ${edgeId}`);
        // Implement context menu as needed
    }
    
    updateAllEdgePositions() {
        this.edges.forEach((edgeData, edgeId) => {
            this.updateEdgePosition(edgeId);
        });
    }
    
    // Animation for edge execution
    animateEdgeExecution(edgeId, duration = 2000) {
        const edgeElement = document.querySelector(`[data-edge-id="${edgeId}"]`);
        if (!edgeElement) return;
        
        edgeElement.classList.add('executing');
        
        setTimeout(() => {
            edgeElement.classList.remove('executing');
        }, duration);
    }
    
    // Get all edges data for serialization
    getEdgesData() {
        return Array.from(this.edges.values());
    }
    
    // Load edges from data
    loadEdgesData(edgesData) {
        // Clear existing edges
        this.clearAllEdges();
        
        // Create edges from data
        edgesData.forEach(edgeData => {
            const edgeElement = this.createEdgeElement(edgeData);
            
            if (this.canvasManager.edgesLayer) {
                this.canvasManager.edgesLayer.appendChild(edgeElement);
            }
            
            this.edges.set(edgeData.id, edgeData);
            
            // Update edge counter
            const edgeNum = parseInt(edgeData.id.split('_')[1]);
            if (edgeNum >= this.edgeCounter) {
                this.edgeCounter = edgeNum;
            }
        });
        
        // Update all positions after nodes are loaded
        setTimeout(() => {
            this.updateAllEdgePositions();
        }, 100);
    }
    
    clearAllEdges() {
        this.edges.forEach((edgeData, edgeId) => {
            this.deleteEdge(edgeId);
        });
        this.edgeCounter = 0;
    }
    
    // Listen for node position changes to update edges
    setupNodePositionListener() {
        document.addEventListener('nodeMoved', () => {
            this.updateAllEdgePositions();
        });
        
        // Listen for canvas transform changes
        if (this.canvasManager.canvas) {
            this.canvasManager.canvas.addEventListener('panUpdate', () => {
                this.updateAllEdgePositions();
            });
            
            this.canvasManager.canvas.addEventListener('zoomChange', () => {
                this.updateAllEdgePositions();
            });
        }
    }
}

// Initialize edge position updates when nodes move
document.addEventListener('DOMContentLoaded', () => {
    // This will be called by the main application
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = EdgeManager;
}