// Advanced Canvas Features - Minimap, Grid, Snap, Selection Box
class AdvancedCanvas extends CanvasManager {
    constructor() {
        super();

        this.minimap = null;
        this.minimapVisible = false;
        this.gridVisible = true;
        this.snapToGrid = true;
        this.gridSize = 20;

        this.selectionBox = null;
        this.isSelecting = false;
        this.selectionStart = { x: 0, y: 0 };

        this.viewportBounds = { x: 0, y: 0, width: 0, height: 0 };

        // Smart Zoom Limits
        this.MIN_SCALE = 0.2;
        this.MAX_SCALE = 4.0;

        this.initAdvancedFeatures();
    }

    initAdvancedFeatures() {
        this.createMinimap();
        this.createGrid();
        this.setupSelectionBox();
        this.setupKeyboardShortcuts();
        this.updateViewportBounds();
    }

    createMinimap() {
        const minimapContainer = document.createElement('div');
        minimapContainer.className = 'minimap-container';
        minimapContainer.innerHTML = `
            <div class="minimap-header">
                <span>Minimap</span>
                <button class="minimap-toggle" onclick="advancedCanvas.toggleMinimap()">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="minimap-canvas">
                <canvas id="minimap-canvas" width="200" height="150"></canvas>
                <div class="minimap-viewport"></div>
            </div>
        `;

        document.body.appendChild(minimapContainer);
        this.minimap = minimapContainer;

        // Setup minimap interactions
        const minimapCanvas = minimapContainer.querySelector('#minimap-canvas');
        const viewport = minimapContainer.querySelector('.minimap-viewport');

        minimapCanvas.addEventListener('click', (e) => {
            this.handleMinimapClick(e);
        });

        viewport.addEventListener('mousedown', (e) => {
            this.startMinimapDrag(e);
        });

        this.updateMinimap();
    }

    createGrid() {
        const gridSvg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        gridSvg.className = 'canvas-grid';
        gridSvg.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 1;
        `;

        const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        const pattern = document.createElementNS('http://www.w3.org/2000/svg', 'pattern');
        pattern.setAttribute('id', 'grid-pattern');
        pattern.setAttribute('width', this.gridSize);
        pattern.setAttribute('height', this.gridSize);
        pattern.setAttribute('patternUnits', 'userSpaceOnUse');

        const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        path.setAttribute('d', `M ${this.gridSize} 0 L 0 0 0 ${this.gridSize}`);
        path.setAttribute('fill', 'none');
        path.setAttribute('stroke', '#e5e7eb');
        path.setAttribute('stroke-width', '1');
        path.setAttribute('opacity', '0.5');

        pattern.appendChild(path);
        defs.appendChild(pattern);
        gridSvg.appendChild(defs);

        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('width', '100%');
        rect.setAttribute('height', '100%');
        rect.setAttribute('fill', 'url(#grid-pattern)');

        gridSvg.appendChild(rect);

        if (this.canvas) {
            this.canvas.appendChild(gridSvg);
        }

        this.gridElement = gridSvg;
        this.updateGrid();
    }

    setupSelectionBox() {
        const selectionBox = document.createElement('div');
        selectionBox.className = 'selection-box';
        selectionBox.style.cssText = `
            position: absolute;
            border: 2px dashed #4f46e5;
            background: rgba(79, 70, 229, 0.1);
            pointer-events: none;
            z-index: 1000;
            display: none;
        `;

        if (this.canvas) {
            this.canvas.appendChild(selectionBox);
        }

        this.selectionBox = selectionBox;

        // Setup selection events
        this.canvas.addEventListener('mousedown', (e) => {
            if (e.target === this.canvas && e.ctrlKey) {
                this.startSelection(e);
            }
        });

        document.addEventListener('mousemove', (e) => {
            if (this.isSelecting) {
                this.updateSelection(e);
            }
        });

        document.addEventListener('mouseup', () => {
            if (this.isSelecting) {
                this.endSelection();
            }
        });
    }

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }

            switch (e.key) {
                case 'g':
                    if (e.ctrlKey) {
                        e.preventDefault();
                        this.toggleGrid();
                    }
                    break;
                case 'm':
                    if (e.ctrlKey) {
                        e.preventDefault();
                        this.toggleMinimap();
                    }
                    break;
                case '0':
                    if (e.ctrlKey) {
                        e.preventDefault();
                        this.resetView();
                    }
                    break;
                case '1':
                    if (e.ctrlKey) {
                        e.preventDefault();
                        this.fitToView();
                    }
                    break;
                case 's':
                    if (e.ctrlKey && e.shiftKey) {
                        e.preventDefault();
                        this.toggleSnapToGrid();
                    }
                    break;
            }
        });
    }

    // Grid Management
    updateGrid() {
        if (!this.gridElement) return;

        const pattern = this.gridElement.querySelector('#grid-pattern');
        if (pattern) {
            const scaledSize = this.gridSize * this.scale;
            pattern.setAttribute('width', scaledSize);
            pattern.setAttribute('height', scaledSize);

            const path = pattern.querySelector('path');
            if (path) {
                path.setAttribute('d', `M ${scaledSize} 0 L 0 0 0 ${scaledSize}`);
            }
        }

        this.gridElement.style.transform = `translate(${this.translateX}px, ${this.translateY}px)`;
        this.gridElement.style.display = this.gridVisible ? 'block' : 'none';
    }

    toggleGrid() {
        this.gridVisible = !this.gridVisible;
        this.updateGrid();

        // Show notification
        if (window.notificationManager) {
            window.notificationManager.info(
                `Grid ${this.gridVisible ? 'enabled' : 'disabled'}`,
                { duration: 2000 }
            );
        }
    }

    toggleSnapToGrid() {
        this.snapToGrid = !this.snapToGrid;

        if (window.notificationManager) {
            window.notificationManager.info(
                `Snap to grid ${this.snapToGrid ? 'enabled' : 'disabled'}`,
                { duration: 2000 }
            );
        }
    }

    snapToGridPosition(x, y) {
        if (!this.snapToGrid) return { x, y };

        return {
            x: Math.round(x / this.gridSize) * this.gridSize,
            y: Math.round(y / this.gridSize) * this.gridSize
        };
    }

    // Minimap Management
    updateMinimap() {
        if (!this.minimap || !this.minimapVisible) return;

        const canvas = this.minimap.querySelector('#minimap-canvas');
        const ctx = canvas.getContext('2d');
        const viewport = this.minimap.querySelector('.minimap-viewport');

        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Draw background
        ctx.fillStyle = '#f9fafb';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        // Draw nodes (simplified)
        const nodes = document.querySelectorAll('.workflow-node');
        const scale = 0.1; // Minimap scale

        nodes.forEach(node => {
            const rect = node.getBoundingClientRect();
            const canvasRect = this.canvas.getBoundingClientRect();

            const x = (rect.left - canvasRect.left) * scale;
            const y = (rect.top - canvasRect.top) * scale;
            const width = rect.width * scale;
            const height = rect.height * scale;

            ctx.fillStyle = '#4f46e5';
            ctx.fillRect(x, y, width, height);
        });

        // Update viewport indicator
        const canvasRect = this.canvas.getBoundingClientRect();
        const viewportWidth = canvasRect.width * scale;
        const viewportHeight = canvasRect.height * scale;
        const viewportX = -this.translateX * scale;
        const viewportY = -this.translateY * scale;

        viewport.style.cssText = `
            position: absolute;
            left: ${viewportX}px;
            top: ${viewportY}px;
            width: ${viewportWidth}px;
            height: ${viewportHeight}px;
            border: 2px solid #4f46e5;
            background: rgba(79, 70, 229, 0.1);
            pointer-events: auto;
            cursor: move;
        `;
    }

    toggleMinimap() {
        this.minimapVisible = !this.minimapVisible;

        if (this.minimap) {
            this.minimap.style.display = this.minimapVisible ? 'block' : 'none';

            if (this.minimapVisible) {
                this.updateMinimap();
            }
        }
    }

    handleMinimapClick(e) {
        const rect = e.target.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // Convert minimap coordinates to canvas coordinates
        const scale = 0.1;
        const canvasX = x / scale;
        const canvasY = y / scale;

        // Center the view on the clicked point
        const canvasRect = this.canvas.getBoundingClientRect();
        this.translateX = -(canvasX - canvasRect.width / 2);
        this.translateY = -(canvasY - canvasRect.height / 2);

        this.updateTransform();
        this.updateMinimap();
    }

    // Selection Box
    startSelection(e) {
        this.isSelecting = true;
        const canvasPos = this.screenToCanvas(e.clientX, e.clientY);
        this.selectionStart = canvasPos;

        this.selectionBox.style.display = 'block';
        this.selectionBox.style.left = `${e.clientX}px`;
        this.selectionBox.style.top = `${e.clientY}px`;
        this.selectionBox.style.width = '0px';
        this.selectionBox.style.height = '0px';
    }

    updateSelection(e) {
        if (!this.isSelecting) return;

        const startScreen = this.canvasToScreen(this.selectionStart.x, this.selectionStart.y);

        const left = Math.min(startScreen.x, e.clientX);
        const top = Math.min(startScreen.y, e.clientY);
        const width = Math.abs(e.clientX - startScreen.x);
        const height = Math.abs(e.clientY - startScreen.y);

        this.selectionBox.style.left = `${left}px`;
        this.selectionBox.style.top = `${top}px`;
        this.selectionBox.style.width = `${width}px`;
        this.selectionBox.style.height = `${height}px`;
    }

    endSelection() {
        this.isSelecting = false;
        this.selectionBox.style.display = 'none';

        // Find nodes within selection box
        const boxRect = this.selectionBox.getBoundingClientRect();
        const selectedNodes = [];

        document.querySelectorAll('.workflow-node').forEach(node => {
            const nodeRect = node.getBoundingClientRect();

            if (nodeRect.left >= boxRect.left &&
                nodeRect.right <= boxRect.right &&
                nodeRect.top >= boxRect.top &&
                nodeRect.bottom <= boxRect.bottom) {
                selectedNodes.push(node);
            }
        });

        // Emit selection event
        if (selectedNodes.length > 0 && window.nodeManager) {
            window.nodeManager.selectMultipleNodes(selectedNodes);
        }
    }

    // View Management
    resetView() {
        this.scale = 1;
        this.translateX = 0;
        this.translateY = 0;
        this.updateTransform();
        this.updateGrid();
        this.updateMinimap();

        if (window.notificationManager) {
            window.notificationManager.info('View reset to default', { duration: 2000 });
        }
    }

    fitToView() {
        const nodes = document.querySelectorAll('.workflow-node');
        if (nodes.length === 0) return;

        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

        nodes.forEach(node => {
            const rect = node.getBoundingClientRect();
            const canvasRect = this.canvas.getBoundingClientRect();

            const nodeX = rect.left - canvasRect.left - this.translateX;
            const nodeY = rect.top - canvasRect.top - this.translateY;

            minX = Math.min(minX, nodeX);
            minY = Math.min(minY, nodeY);
            maxX = Math.max(maxX, nodeX + rect.width);
            maxY = Math.max(maxY, nodeY + rect.height);
        });

        const contentWidth = maxX - minX;
        const contentHeight = maxY - minY;
        const canvasRect = this.canvas.getBoundingClientRect();

        const scaleX = (canvasRect.width - 100) / contentWidth;
        const scaleY = (canvasRect.height - 100) / contentHeight;
        this.scale = Math.min(scaleX, scaleY, 1);

        const centerX = (minX + maxX) / 2;
        const centerY = (minY + maxY) / 2;

        this.translateX = canvasRect.width / 2 - centerX * this.scale;
        this.translateY = canvasRect.height / 2 - centerY * this.scale;

        this.updateTransform();
        this.updateGrid();
        this.updateMinimap();

        if (window.notificationManager) {
            window.notificationManager.info('Fitted workflow to view', { duration: 2000 });
        }
    }

    // Override parent methods to include advanced features
    updateTransform() {
        // Enforce Zoom Limits
        if (this.scale < this.MIN_SCALE) this.scale = this.MIN_SCALE;
        if (this.scale > this.MAX_SCALE) this.scale = this.MAX_SCALE;

        super.updateTransform();
        this.updateGrid();
        this.updateMinimap();
        this.updateViewportBounds();

        // Update status bar if available
        const zoomDisplay = document.getElementById('zoom-level');
        if (zoomDisplay) {
            zoomDisplay.textContent = Math.round(this.scale * 100) + '%';
        }
    }

    updateViewportBounds() {
        if (!this.canvas) return;

        const rect = this.canvas.getBoundingClientRect();
        this.viewportBounds = {
            x: -this.translateX / this.scale,
            y: -this.translateY / this.scale,
            width: rect.width / this.scale,
            height: rect.height / this.scale
        };
    }

    // Check if element is in viewport (for performance optimization)
    isInViewport(element) {
        const rect = element.getBoundingClientRect();
        const canvasRect = this.canvas.getBoundingClientRect();

        return !(rect.right < canvasRect.left ||
            rect.left > canvasRect.right ||
            rect.bottom < canvasRect.top ||
            rect.top > canvasRect.bottom);
    }
}

// Add minimap styles
const minimapStyles = document.createElement('style');
minimapStyles.textContent = `
    .minimap-container {
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
        z-index: 1000;
        display: none;
    }
    
    .minimap-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 8px 12px;
        border-bottom: 1px solid #e5e7eb;
        font-size: 12px;
        font-weight: 600;
        color: #374151;
    }
    
    .minimap-toggle {
        background: none;
        border: none;
        color: #6b7280;
        cursor: pointer;
        font-size: 12px;
        padding: 2px;
    }
    
    .minimap-toggle:hover {
        color: #374151;
    }
    
    .minimap-canvas {
        position: relative;
        padding: 8px;
    }
    
    #minimap-canvas {
        border: 1px solid #e5e7eb;
        border-radius: 4px;
        display: block;
    }
    
    .selection-box {
        border: 2px dashed #4f46e5 !important;
        background: rgba(79, 70, 229, 0.1) !important;
    }
`;
document.head.appendChild(minimapStyles);

// Create global instance
window.advancedCanvas = new AdvancedCanvas();