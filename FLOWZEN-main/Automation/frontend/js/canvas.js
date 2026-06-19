// Canvas Management - Pan, Zoom, Coordinate System
class CanvasManager {
    constructor() {
        this.canvas = document.getElementById('canvas');
        this.nodesLayer = document.getElementById('nodes-layer');
        this.edgesLayer = document.getElementById('edges-layer');
        
        this.scale = 1;
        this.translateX = 0;
        this.translateY = 0;
        
        this.isPanning = false;
        this.lastPanPoint = { x: 0, y: 0 };
        
        this.init();
    }
    
    init() {
        this.setupEventListeners();
        this.updateTransform();
        this.updateZoomIndicator();
    }
    
    setupEventListeners() {
        // Pan functionality
        this.canvas.addEventListener('mousedown', (e) => {
            if (e.target === this.canvas || e.target === this.nodesLayer || e.target === this.edgesLayer) {
                this.startPan(e);
            }
        });
        
        document.addEventListener('mousemove', (e) => {
            if (this.isPanning) {
                this.updatePan(e);
            }
        });
        
        document.addEventListener('mouseup', () => {
            this.endPan();
        });
        
        // Zoom functionality
        this.canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            this.zoom(e.deltaY > 0 ? -0.1 : 0.1, e.clientX, e.clientY);
        });
        
        // Zoom buttons
        document.getElementById('zoom-in').addEventListener('click', () => {
            this.zoom(0.2);
        });
        
        document.getElementById('zoom-out').addEventListener('click', () => {
            this.zoom(-0.2);
        });
        
        // Prevent context menu
        this.canvas.addEventListener('contextmenu', (e) => {
            e.preventDefault();
        });
    }
    
    startPan(e) {
        this.isPanning = true;
        this.canvas.classList.add('panning');
        this.lastPanPoint = { x: e.clientX, y: e.clientY };
    }
    
    updatePan(e) {
        if (!this.isPanning) return;
        
        const deltaX = e.clientX - this.lastPanPoint.x;
        const deltaY = e.clientY - this.lastPanPoint.y;
        
        this.translateX += deltaX;
        this.translateY += deltaY;
        
        this.updateTransform();
        
        this.lastPanPoint = { x: e.clientX, y: e.clientY };
    }
    
    endPan() {
        this.isPanning = false;
        this.canvas.classList.remove('panning');
    }
    
    zoom(delta, centerX = null, centerY = null) {
        const oldScale = this.scale;
        this.scale = Math.max(0.1, Math.min(3, this.scale + delta));
        
        if (centerX !== null && centerY !== null) {
            // Zoom towards mouse position
            const rect = this.canvas.getBoundingClientRect();
            const x = centerX - rect.left;
            const y = centerY - rect.top;
            
            const scaleRatio = this.scale / oldScale;
            this.translateX = x - (x - this.translateX) * scaleRatio;
            this.translateY = y - (y - this.translateY) * scaleRatio;
        }
        
        this.updateTransform();
        this.updateZoomIndicator();
    }
    
    updateTransform() {
        const transform = `translate(${this.translateX}px, ${this.translateY}px) scale(${this.scale})`;
        this.nodesLayer.style.transform = transform;
        this.edgesLayer.style.transform = transform;
    }
    
    updateZoomIndicator() {
        const zoomLevel = document.getElementById('zoom-level');
        zoomLevel.textContent = Math.round(this.scale * 100) + '%';
    }
    
    // Convert screen coordinates to canvas coordinates
    screenToCanvas(screenX, screenY) {
        const rect = this.canvas.getBoundingClientRect();
        const x = (screenX - rect.left - this.translateX) / this.scale;
        const y = (screenY - rect.top - this.translateY) / this.scale;
        return { x, y };
    }
    
    // Convert canvas coordinates to screen coordinates
    canvasToScreen(canvasX, canvasY) {
        const rect = this.canvas.getBoundingClientRect();
        const x = canvasX * this.scale + this.translateX + rect.left;
        const y = canvasY * this.scale + this.translateY + rect.top;
        return { x, y };
    }
    
    // Get canvas bounds
    getCanvasBounds() {
        const rect = this.canvas.getBoundingClientRect();
        return {
            left: -this.translateX / this.scale,
            top: -this.translateY / this.scale,
            right: (rect.width - this.translateX) / this.scale,
            bottom: (rect.height - this.translateY) / this.scale,
            width: rect.width / this.scale,
            height: rect.height / this.scale
        };
    }
    
    // Center view on nodes
    centerView() {
        const nodes = document.querySelectorAll('.workflow-node');
        if (nodes.length === 0) return;
        
        let minX = Infinity, minY = Infinity;
        let maxX = -Infinity, maxY = -Infinity;
        
        nodes.forEach(node => {
            const x = parseFloat(node.style.left) || 0;
            const y = parseFloat(node.style.top) || 0;
            const width = node.offsetWidth;
            const height = node.offsetHeight;
            
            minX = Math.min(minX, x);
            minY = Math.min(minY, y);
            maxX = Math.max(maxX, x + width);
            maxY = Math.max(maxY, y + height);
        });
        
        const centerX = (minX + maxX) / 2;
        const centerY = (minY + maxY) / 2;
        
        const rect = this.canvas.getBoundingClientRect();
        this.translateX = rect.width / 2 - centerX * this.scale;
        this.translateY = rect.height / 2 - centerY * this.scale;
        
        this.updateTransform();
    }
    
    // Reset view
    resetView() {
        this.scale = 1;
        this.translateX = 0;
        this.translateY = 0;
        this.updateTransform();
        this.updateZoomIndicator();
    }
}

// Export for use in other modules
window.CanvasManager = CanvasManager;