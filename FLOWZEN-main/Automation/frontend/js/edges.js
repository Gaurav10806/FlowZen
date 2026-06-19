// Enhanced Edge Management with Animations
class EdgeManager {
    constructor(canvasManager, nodeManager, animationManager) {
        this.canvasManager = canvasManager;
        this.nodeManager = nodeManager;
        this.animationManager = animationManager;
        this.edges = new Map();
        this.edgeCounter = 0;
        
        this.isConnecting = false;
        this.connectionStart = null;
        this.temporaryEdge = null;
        
        this.init();
    }
    
    init() {
        this.setupConnectionEvents();
    }
    
    setupConnectionEvents() {
        // Enhanced mouse move for temporary edge with smooth animation
        document.addEventListener('mousemove', (e) => {
            if (this.isConnecting && this.temporaryEdge) {
                this.updateTemporaryEdge(e);
            }
        });
        
        // Enhanced mouse up to end connection
        document.addEventListener('mouseup', (e) => {
            if (this.isConnecting) {
                this.endConnection(e);
            }
        });
        
        // Escape to cancel connection with animation
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isConnecting) {
                this.cancelConnection();
                
                // Show cancellation feedback
                if (window.notifications) {
                    window.notifications.info('Connection cancelled');
                }
            }
        });
    }
    
    startConnection(nodeId, connectionType, event) {
        if (connectionType !== 'output') return; // Only allow connections from output
        
        this.isConnecting = true;
        this.connectionStart = {
            nodeId: nodeId,
            type: connectionType
        };
        
        // Add connecting state to connection point
        const connectionPoint = event.target;
        connectionPoint.classList.add('connecting');
        
        // Create temporary edge with animation
        this.createTemporaryEdge(event);
        
        event.stopPropagation();
        event.preventDefault();
    }
    
    createTemporaryEdge(event) {
        const startPos = this.getConnectionPointPosition(
            this.connectionStart.nodeId, 
            this.connectionStart.type
        );
        
        if (!startPos) return;
        
        this.temporaryEdge = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        this.temporaryEdge.classList.add('edge', 'temporary');
        
        const canvasPos = this.canvasManager.screenToCanvas(event.clientX, event.clientY);
        const pathData = this.createCurvedPath(startPos.x, startPos.y, canvasPos.x, canvasPos.y);
        
        this.temporaryEdge.setAttribute('d', pathData);
        this.temporaryEdge.setAttribute('stroke', 'url(#connectionGradient)');
        this.canvasManager.edgesLayer.appendChild(this.temporaryEdge);
        
        // Animate temporary edge appearance
        if (this.animationManager) {
            this.temporaryEdge.style.opacity = '0';
            this.animationManager.animate(this.temporaryEdge, {
                opacity: '1'
            }, 200);
        }
    }
    
    updateTemporaryEdge(event) {
        if (!this.temporaryEdge) return;
        
        const startPos = this.getConnectionPointPosition(
            this.connectionStart.nodeId, 
            this.connectionStart.type
        );
        
        if (!startPos) return;
        
        const canvasPos = this.canvasManager.screenToCanvas(event.clientX, event.clientY);
        const pathData = this.createCurvedPath(startPos.x, startPos.y, canvasPos.x, canvasPos.y);
        
        this.temporaryEdge.setAttribute('d', pathData);
        
        // Add hover effect on potential target
        const target = event.target;
        if (target && target.classList.contains('connection-point') && 
            target.dataset.type === 'input') {
            
            const targetNodeElement = target.closest('.workflow-node');
            if (targetNodeElement && targetNodeElement.dataset.nodeId !== this.connectionStart.nodeId) {
                // Highlight potential target
                target.style.background = 'var(--success-color)';
                target.style.transform = 'translateY(-50%) scale(1.4)';
            }
        } else {
            // Remove highlights from all input points
            document.querySelectorAll('.connection-point.input').forEach(point => {
                point.style.background = '';
                point.style.transform = '';
            });
        }
    }
    
    endConnection(event) {
        if (!this.isConnecting) return;
        
        // Find target connection point
        const target = event.target;
        if (target && target.classList.contains('connection-point') && 
            target.dataset.type === 'input') {
            
            const targetNodeElement = target.closest('.workflow-node');
            if (targetNodeElement) {
                const targetNodeId = targetNodeElement.dataset.nodeId;
                
                // Don't connect to self
                if (targetNodeId !== this.connectionStart.nodeId) {
                    const edge = this.createEdge(this.connectionStart.nodeId, targetNodeId);
                    
                    if (edge) {
                        // Success animation
                        if (this.animationManager) {
                            this.animationManager.pulse(targetNodeElement, 'success');
                        }
                        
                        // Show success notification
                        if (window.notifications) {
                            window.notifications.success('Nodes connected successfully!', {
                                duration: 2000
                            });
                        }
                    }
                }
            }
        }
        
        this.cancelConnection();
    }
    
    cancelConnection() {
        this.isConnecting = false;
        this.connectionStart = null;
        
        // Remove connecting state from all connection points
        document.querySelectorAll('.connection-point.connecting').forEach(point => {
            point.classList.remove('connecting');
        });
        
        // Remove highlights
        document.querySelectorAll('.connection-point.input').forEach(point => {
            point.style.background = '';
            point.style.transform = '';
        });
        
        if (this.temporaryEdge) {
            // Animate temporary edge removal
            if (this.animationManager) {
                this.animationManager.animate(this.temporaryEdge, {
                    opacity: '0',
                    transform: 'scale(0.8)'
                }, 200).then(() => {
                    if (this.temporaryEdge && this.temporaryEdge.parentNode) {
                        this.temporaryEdge.remove();
                    }
                });
            } else {
                this.temporaryEdge.remove();
            }
            this.temporaryEdge = null;
        }
    }
    
    createEdge(fromNodeId, toNodeId) {
        // Check if edge already exists
        const existingEdge = Array.from(this.edges.values()).find(
            edge => edge.from === fromNodeId && edge.to === toNodeId
        );
        
        if (existingEdge) {
            // Show warning for duplicate connection
            if (window.notifications) {
                window.notifications.warning('Connection already exists between these nodes');
            }
            return null;
        }
        
        const edgeId = `edge_${++this.edgeCounter}`;
        const edgeData = {
            id: edgeId,
            from: fromNodeId,
            to: toNodeId,
            status: 'idle'
        };
        
        const edgeElement = this.createEdgeElement(edgeData);
        if (edgeElement) {
            this.canvasManager.edgesLayer.appendChild(edgeElement);
            this.edges.set(edgeId, edgeData);
            this.setupEdgeInteractions(edgeElement, edgeData);
            
            // Enhanced creation animation
            if (this.animationManager) {
                this.animationManager.animateConnectionDraw(edgeElement);
            }
            
            // Dispatch creation event
            document.dispatchEvent(new CustomEvent('edgeCreated', {
                detail: { id: edgeId, from: fromNodeId, to: toNodeId }
            }));
            
            return edgeData;
        }
        
        return null;
    }
    
    createEdgeElement(edgeData) {
        const fromPos = this.getConnectionPointPosition(edgeData.from, 'output');
        const toPos = this.getConnectionPointPosition(edgeData.to, 'input');
        
        if (!fromPos || !toPos) return null;
        
        const edge = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        edge.classList.add('edge', 'hover-glow');
        edge.dataset.edgeId = edgeData.id;
        
        const pathData = this.createCurvedPath(fromPos.x, fromPos.y, toPos.x, toPos.y);
        edge.setAttribute('d', pathData);
        edge.setAttribute('stroke', 'url(#connectionGradient)');
        edge.setAttribute('filter', 'url(#glow)');
        
        return edge;
    }
    
    createCurvedPath(x1, y1, x2, y2) {
        const dx = x2 - x1;
        const dy = y2 - y1;
        
        // Enhanced curve calculation for smoother connections
        const distance = Math.sqrt(dx * dx + dy * dy);
        const curvature = Math.min(distance * 0.4, 150);
        
        // Control points for smooth Bezier curve
        const cp1x = x1 + curvature;
        const cp1y = y1;
        const cp2x = x2 - curvature;
        const cp2y = y2;
        
        return `M ${x1} ${y1} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${x2} ${y2}`;
    }
    
    getConnectionPointPosition(nodeId, type) {
        const nodePos = this.nodeManager.getNodePosition(nodeId);
        if (!nodePos) return null;
        
        if (type === 'output') {
            return {
                x: nodePos.x + nodePos.width,
                y: nodePos.y + nodePos.height / 2
            };
        } else if (type === 'input') {
            return {
                x: nodePos.x,
                y: nodePos.y + nodePos.height / 2
            };
        }
        
        return null;
    }
    
    setupEdgeInteractions(edgeElement, edgeData) {
        // Enhanced edge selection with animation
        edgeElement.addEventListener('click', (e) => {
            e.stopPropagation();
            this.selectEdge(edgeData.id);
            
            // Selection animation
            if (this.animationManager) {
                this.animationManager.bounce(edgeElement, 0.3);
            }
        });
        
        // Enhanced hover effects with smooth transitions
        edgeElement.addEventListener('mouseenter', () => {
            if (!edgeElement.classList.contains('selected')) {
                if (this.animationManager) {
                    this.animationManager.animate(edgeElement, {
                        strokeWidth: '4',
                        filter: 'url(#glow) drop-shadow(0 0 8px rgba(79, 70, 229, 0.6))'
                    }, 200);
                }
            }
        });
        
        edgeElement.addEventListener('mouseleave', () => {
            if (!edgeElement.classList.contains('selected')) {
                if (this.animationManager) {
                    this.animationManager.animate(edgeElement, {
                        strokeWidth: '3',
                        filter: 'url(#glow)'
                    }, 200);
                }
            }
        });
        
        // Double-click to show edge properties
        edgeElement.addEventListener('dblclick', (e) => {
            e.stopPropagation();
            this.showEdgeProperties(edgeData);
        });
    }
    
    selectEdge(edgeId) {
        // Remove previous selection
        document.querySelectorAll('.edge.selected').forEach(edge => {
            edge.classList.remove('selected');
            if (this.animationManager) {
                this.animationManager.animate(edge, {
                    strokeWidth: '3',
                    filter: 'url(#glow)'
                }, 200);
            }
        });
        
        // Select new edge
        const edgeElement = document.querySelector(`[data-edge-id="${edgeId}"]`);
        if (edgeElement) {
            edgeElement.classList.add('selected');
            if (this.animationManager) {
                this.animationManager.animate(edgeElement, {
                    strokeWidth: '4',
                    filter: 'url(#glow) drop-shadow(0 0 12px rgba(79, 70, 229, 0.8))'
                }, 200);
            }
        }
        
        // Deselect nodes
        if (this.nodeManager) {
            this.nodeManager.selectNode(null);
        }
    }
    
    showEdgeProperties(edgeData) {
        // Show edge properties modal or panel
        if (window.notifications) {
            window.notifications.info(`Edge from ${edgeData.from} to ${edgeData.to}`, {
                duration: 3000
            });
        }
    }
    
    deleteEdge(edgeId) {
        const edgeElement = document.querySelector(`[data-edge-id="${edgeId}"]`);
        if (edgeElement) {
            // Delete animation
            if (this.animationManager) {
                this.animationManager.animate(edgeElement, {
                    opacity: '0',
                    strokeWidth: '1',
                    transform: 'scale(0.8)'
                }, 300).then(() => {
                    edgeElement.remove();
                });
            } else {
                edgeElement.remove();
            }
        }
        
        this.edges.delete(edgeId);
        
        // Dispatch deletion event
        document.dispatchEvent(new CustomEvent('edgeDeleted', {
            detail: { id: edgeId }
        }));
    }
    
    updateNodeEdges(nodeId) {
        // Update all edges connected to this node with smooth animation
        this.edges.forEach((edgeData, edgeId) => {
            if (edgeData.from === nodeId || edgeData.to === nodeId) {
                const edgeElement = document.querySelector(`[data-edge-id="${edgeId}"]`);
                if (edgeElement) {
                    const fromPos = this.getConnectionPointPosition(edgeData.from, 'output');
                    const toPos = this.getConnectionPointPosition(edgeData.to, 'input');
                    
                    if (fromPos && toPos) {
                        const pathData = this.createCurvedPath(fromPos.x, fromPos.y, toPos.x, toPos.y);
                        
                        // Smooth path update
                        if (this.animationManager) {
                            edgeElement.style.transition = 'd 0.1s ease-out';
                        }
                        edgeElement.setAttribute('d', pathData);
                    }
                }
            }
        });
    }
    
    removeNodeEdges(nodeId) {
        // Remove all edges connected to this node with animation
        const edgesToRemove = [];
        
        this.edges.forEach((edgeData, edgeId) => {
            if (edgeData.from === nodeId || edgeData.to === nodeId) {
                edgesToRemove.push(edgeId);
            }
        });
        
        // Stagger edge removal animations
        edgesToRemove.forEach((edgeId, index) => {
            setTimeout(() => {
                this.deleteEdge(edgeId);
            }, index * 100);
        });
    }
    
    // Animate data flow along edge
    animateDataFlow(edgeId, data) {
        const edgeElement = document.querySelector(`[data-edge-id="${edgeId}"]`);
        if (!edgeElement) return;
        
        // Add data flow class
        edgeElement.classList.add('data-flowing');
        
        // Create data particle
        if (this.animationManager) {
            this.animationManager.animateDataFlow(edgeElement, data);
        }
        
        // Remove data flow class after animation
        setTimeout(() => {
            edgeElement.classList.remove('data-flowing');
        }, 2000);
    }
    
    // Update edge status with visual feedback
    updateEdgeStatus(edgeId, status) {
        const edgeData = this.edges.get(edgeId);
        const edgeElement = document.querySelector(`[data-edge-id="${edgeId}"]`);
        
        if (edgeData && edgeElement) {
            edgeData.status = status;
            
            // Update visual appearance based on status
            switch (status) {
                case 'active':
                    edgeElement.setAttribute('stroke', 'var(--success-color)');
                    edgeElement.classList.add('data-flowing');
                    break;
                case 'error':
                    edgeElement.setAttribute('stroke', 'var(--error-color)');
                    if (this.animationManager) {
                        this.animationManager.shake(edgeElement);
                    }
                    break;
                case 'idle':
                default:
                    edgeElement.setAttribute('stroke', 'url(#connectionGradient)');
                    edgeElement.classList.remove('data-flowing');
                    break;
            }
        }
    }
    
    exportEdges() {
        return Array.from(this.edges.values()).map(edge => ({
            from: edge.from,
            to: edge.to,
            status: edge.status
        }));
    }
    
    importEdges(edgesData) {
        // Clear existing edges
        this.edges.clear();
        this.canvasManager.edgesLayer.innerHTML = '';
        
        // Recreate enhanced marker and gradients
        this.setupSVGDefinitions();
        
        // Create edges with staggered animations
        edgesData.forEach((edgeData, index) => {
            setTimeout(() => {
                this.createEdge(edgeData.from, edgeData.to);
            }, index * 200);
        });
    }
    
    clearEdges() {
        // Clear all edges with staggered animations
        const edgeIds = Array.from(this.edges.keys());
        edgeIds.forEach((edgeId, index) => {
            setTimeout(() => {
                this.deleteEdge(edgeId);
            }, index * 50);
        });
    }
    
    setupSVGDefinitions() {
        const defs = this.canvasManager.canvas.querySelector('defs');
        if (!defs) return;
        
        // Clear existing definitions
        defs.innerHTML = '';
        
        // Enhanced arrow marker
        const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
        marker.id = 'arrowhead';
        marker.setAttribute('markerWidth', '12');
        marker.setAttribute('markerHeight', '8');
        marker.setAttribute('refX', '11');
        marker.setAttribute('refY', '4');
        marker.setAttribute('orient', 'auto');
        marker.setAttribute('markerUnits', 'strokeWidth');
        
        const arrowPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        arrowPath.setAttribute('d', 'M0,0 L0,8 L12,4 z');
        arrowPath.setAttribute('fill', 'currentColor');
        
        marker.appendChild(arrowPath);
        defs.appendChild(marker);
        
        // Connection gradient
        const gradient = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
        gradient.id = 'connectionGradient';
        gradient.setAttribute('x1', '0%');
        gradient.setAttribute('y1', '0%');
        gradient.setAttribute('x2', '100%');
        gradient.setAttribute('y2', '0%');
        
        const stop1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
        stop1.setAttribute('offset', '0%');
        stop1.setAttribute('style', 'stop-color:#4f46e5;stop-opacity:1');
        
        const stop2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
        stop2.setAttribute('offset', '100%');
        stop2.setAttribute('style', 'stop-color:#7c3aed;stop-opacity:1');
        
        gradient.appendChild(stop1);
        gradient.appendChild(stop2);
        defs.appendChild(gradient);
        
        // Glow filter
        const filter = document.createElementNS('http://www.w3.org/2000/svg', 'filter');
        filter.id = 'glow';
        
        const blur = document.createElementNS('http://www.w3.org/2000/svg', 'feGaussianBlur');
        blur.setAttribute('stdDeviation', '3');
        blur.setAttribute('result', 'coloredBlur');
        
        const merge = document.createElementNS('http://www.w3.org/2000/svg', 'feMerge');
        const mergeNode1 = document.createElementNS('http://www.w3.org/2000/svg', 'feMergeNode');
        mergeNode1.setAttribute('in', 'coloredBlur');
        const mergeNode2 = document.createElementNS('http://www.w3.org/2000/svg', 'feMergeNode');
        mergeNode2.setAttribute('in', 'SourceGraphic');
        
        merge.appendChild(mergeNode1);
        merge.appendChild(mergeNode2);
        filter.appendChild(blur);
        filter.appendChild(merge);
        defs.appendChild(filter);
    }
}

// Enhanced delete key handling for edges
document.addEventListener('keydown', (e) => {
    if (e.key === 'Delete') {
        const selectedEdge = document.querySelector('.edge.selected');
        if (selectedEdge && window.edgeManager) {
            const edgeId = selectedEdge.dataset.edgeId;
            
            // Confirmation for edge deletion
            if (window.notifications) {
                window.notifications.confirm('Are you sure you want to delete this connection?', {
                    confirmText: 'Delete',
                    cancelText: 'Cancel'
                }).then(confirmed => {
                    if (confirmed) {
                        window.edgeManager.deleteEdge(edgeId);
                        window.notifications.success('Connection deleted');
                    }
                });
            } else {
                window.edgeManager.deleteEdge(edgeId);
            }
        }
    }
});

// Export for use in other modules
window.EdgeManager = EdgeManager;