// Enhanced Canvas Management - Pan, Zoom, Coordinate System
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
        
        this.minScale = 0.1;
        this.maxScale = 3.0;
        
        this.init();
    }
    
    init() {
        if (!this.canvas) {
            console.warn('Canvas element not found');
            return;
        }
        
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
            const zoomDelta = e.deltaY > 0 ? -0.1 : 0.1;
            this.zoom(zoomDelta, e.clientX, e.clientY);
        });
        
        // Zoom buttons
        const zoomInBtn = document.getElementById('zoom-in');
        const zoomOutBtn = document.getElementById('zoom-out');
        
        if (zoomInBtn) {
            zoomInBtn.addEventListener('click', () => {
                this.zoom(0.2);
            });
        }
        
        if (zoomOutBtn) {
            zoomOutBtn.addEventListener('click', () => {
                this.zoom(-0.2);
            });
        }
        
        // Prevent context menu
        this.canvas.addEventListener('contextmenu', (e) => {
            e.preventDefault();
        });
        
        // Touch support for mobile
        this.setupTouchEvents();
    }
    
    setupTouchEvents() {
        let lastTouchDistance = 0;
        let lastTouchCenter = { x: 0, y: 0 };
        
        this.canvas.addEventListener('touchstart', (e) => {
            if (e.touches.length === 1) {
                // Single touch - start panning
                const touch = e.touches[0];
                this.startPan({ clientX: touch.clientX, clientY: touch.clientY });
            } else if (e.touches.length === 2) {
                // Two touches - prepare for zoom
                const touch1 = e.touches[0];
                const touch2 = e.touches[1];
                
                lastTouchDistance = Math.sqrt(
                    Math.pow(touch2.clientX - touch1.clientX, 2) +
                    Math.pow(touch2.clientY - touch1.clientY, 2)
                );
                
                lastTouchCenter = {
                    x: (touch1.clientX + touch2.clientX) / 2,
                    y: (touch1.clientY + touch2.clientY) / 2
                };
            }
            
            e.preventDefault();
        });
        
        this.canvas.addEventListener('touchmove', (e) => {
            if (e.touches.length === 1 && this.isPanning) {
                // Single touch - pan
                const touch = e.touches[0];
                this.updatePan({ clientX: touch.clientX, clientY: touch.clientY });
            } else if (e.touches.length === 2) {
                // Two touches - zoom
                const touch1 = e.touches[0];
                const touch2 = e.touches[1];
                
                const currentDistance = Math.sqrt(
                    Math.pow(touch2.clientX - touch1.clientX, 2) +
                    Math.pow(touch2.clientY - touch1.clientY, 2)
                );
                
                const currentCenter = {
                    x: (touch1.clientX + touch2.clientX) / 2,
                    y: (touch1.clientY + touch2.clientY) / 2
                };
                
                if (lastTouchDistance > 0) {
                    const zoomDelta = (currentDistance - lastTouchDistance) * 0.01;
                    this.zoom(zoomDelta, currentCenter.x, currentCenter.y);
                }
                
                lastTouchDistance = currentDistance;
                lastTouchCenter = currentCenter;
            }
            
            e.preventDefault();
        });
        
        this.canvas.addEventListener('touchend', () => {
            this.endPan();
            lastTouchDistance = 0;
        });
    }
    
    startPan(e) {
        this.isPanning = true;
        this.canvas.classList.add('panning');
        this.lastPanPoint = { x: e.clientX, y: e.clientY };
        
        // Dispatch custom event
        this.canvas.dispatchEvent(new CustomEvent('panStart', {
            detail: { x: e.clientX, y: e.clientY }
        }));
    }
    
    updatePan(e) {
        if (!this.isPanning) return;
        
        const deltaX = e.clientX - this.lastPanPoint.x;
        const deltaY = e.clientY - this.lastPanPoint.y;
        
        this.translateX += deltaX;
        this.translateY += deltaY;
        
        this.updateTransform();
        
        this.lastPanPoint = { x: e.clientX, y: e.clientY };
        
        // Dispatch custom event
        this.canvas.dispatchEvent(new CustomEvent('panUpdate', {
            detail: { deltaX, deltaY, translateX: this.translateX, translateY: this.translateY }
        }));
    }
    
    endPan() {
        if (!this.isPanning) return;
        
        this.isPanning = false;
        this.canvas.classList.remove('panning');
        
        // Dispatch custom event
        this.canvas.dispatchEvent(new CustomEvent('panEnd', {
            detail: { translateX: this.translateX, translateY: this.translateY }
        }));
    }
    
    zoom(delta, centerX = null, centerY = null) {
        const oldScale = this.scale;
        this.scale = Math.max(this.minScale, Math.min(this.maxScale, this.scale + delta));
        
        if (this.scale === oldScale) return; // No change
        
        // If center point is provided, zoom towards that point
        if (centerX !== null && centerY !== null) {
            const rect = this.canvas.getBoundingClientRect();
            const canvasX = centerX - rect.left;
            const canvasY = centerY - rect.top;
            
            // Calculate the point in canvas coordinates before zoom
            const beforeX = (canvasX - this.translateX) / oldScale;
            const beforeY = (canvasY - this.translateY) / oldScale;
            
            // Calculate the point in canvas coordinates after zoom
            const afterX = beforeX * this.scale;
            const afterY = beforeY * this.scale;
            
            // Adjust translation to keep the zoom center point fixed
            this.translateX = canvasX - afterX;
            this.translateY = canvasY - afterY;
        }
        
        this.updateTransform();
        this.updateZoomIndicator();
        
        // Dispatch custom event
        this.canvas.dispatchEvent(new CustomEvent('zoomChange', {
            detail: { scale: this.scale, delta, centerX, centerY }
        }));
    }
    
    updateTransform() {
        if (!this.nodesLayer || !this.edgesLayer) return;
        
        const transform = `translate(${this.translateX}px, ${this.translateY}px) scale(${this.scale})`;
        
        this.nodesLayer.style.transform = transform;
        this.edgesLayer.style.transform = transform;
        
        // Update grid if present
        const grid = this.canvas.querySelector('#grid');
        if (grid) {
            grid.setAttribute('transform', `translate(${this.translateX}, ${this.translateY}) scale(${this.scale})`);
        }
    }
    
    updateZoomIndicator() {
        const zoomIndicator = document.getElementById('zoom-level');
        if (zoomIndicator) {
            zoomIndicator.textContent = Math.round(this.scale * 100) + '%';
        }
    }
    
    // Convert screen coordinates to canvas coordinates
    screenToCanvas(screenX, screenY) {
        const rect = this.canvas.getBoundingClientRect();
        const canvasX = (screenX - rect.left - this.translateX) / this.scale;
        const canvasY = (screenY - rect.top - this.translateY) / this.scale;
        
        return { x: canvasX, y: canvasY };
    }
    
    // Convert canvas coordinates to screen coordinates
    canvasToScreen(canvasX, canvasY) {
        const rect = this.canvas.getBoundingClientRect();
        const screenX = canvasX * this.scale + this.translateX + rect.left;
        const screenY = canvasY * this.scale + this.translateY + rect.top;
        
        return { x: screenX, y: screenY };
    }
    
    // Get the current viewport bounds in canvas coordinates
    getViewportBounds() {
        const rect = this.canvas.getBoundingClientRect();
        const topLeft = this.screenToCanvas(0, 0);
        const bottomRight = this.screenToCanvas(rect.width, rect.height);
        
        return {
            left: topLeft.x,
            top: topLeft.y,
            right: bottomRight.x,
            bottom: bottomRight.y,
            width: bottomRight.x - topLeft.x,
            height: bottomRight.y - topLeft.y
        };
    }
    
    // Center the canvas on a specific point
    centerOn(x, y) {
        const rect = this.canvas.getBoundingClientRect();
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        
        this.translateX = centerX - x * this.scale;
        this.translateY = centerY - y * this.scale;
        
        this.updateTransform();
    }
    
    // Fit all content in the viewport
    fitToContent(padding = 50) {
        if (!this.nodesLayer) return;
        
        const nodes = this.nodesLayer.querySelectorAll('.workflow-node');
        if (nodes.length === 0) return;
        
        let minX = Infinity, minY = Infinity;
        let maxX = -Infinity, maxY = -Infinity;
        
        nodes.forEach(node => {
            const rect = node.getBoundingClientRect();
            const canvasPos = this.screenToCanvas(rect.left, rect.top);
            
            minX = Math.min(minX, canvasPos.x);
            minY = Math.min(minY, canvasPos.y);
            maxX = Math.max(maxX, canvasPos.x + rect.width / this.scale);
            maxY = Math.max(maxY, canvasPos.y + rect.height / this.scale);
        });
        
        const contentWidth = maxX - minX;
        const contentHeight = maxY - minY;
        
        const canvasRect = this.canvas.getBoundingClientRect();
        const availableWidth = canvasRect.width - padding * 2;
        const availableHeight = canvasRect.height - padding * 2;
        
        const scaleX = availableWidth / contentWidth;
        const scaleY = availableHeight / contentHeight;
        
        this.scale = Math.min(scaleX, scaleY, this.maxScale);
        this.scale = Math.max(this.scale, this.minScale);
        
        const centerX = (minX + maxX) / 2;
        const centerY = (minY + maxY) / 2;
        
        this.centerOn(centerX, centerY);
        this.updateZoomIndicator();
    }
    
    // Reset zoom and pan to default
    resetView() {
        this.scale = 1;
        this.translateX = 0;
        this.translateY = 0;
        
        this.updateTransform();
        this.updateZoomIndicator();
        
        // Dispatch custom event
        this.canvas.dispatchEvent(new CustomEvent('viewReset'));
    }
    
    // Get current transform state
    getTransform() {
        return {
            scale: this.scale,
            translateX: this.translateX,
            translateY: this.translateY
        };
    }
    
    // Set transform state
    setTransform(transform) {
        this.scale = Math.max(this.minScale, Math.min(this.maxScale, transform.scale));
        this.translateX = transform.translateX;
        this.translateY = transform.translateY;
        
        this.updateTransform();
        this.updateZoomIndicator();
    }
    
    // Animation helpers
    animateToTransform(targetTransform, duration = 300) {
        const startTransform = this.getTransform();
        const startTime = performance.now();
        
        const animate = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Easing function (ease-out)
            const easeOut = 1 - Math.pow(1 - progress, 3);
            
            const currentTransform = {
                scale: startTransform.scale + (targetTransform.scale - startTransform.scale) * easeOut,
                translateX: startTransform.translateX + (targetTransform.translateX - startTransform.translateX) * easeOut,
                translateY: startTransform.translateY + (targetTransform.translateY - startTransform.translateY) * easeOut
            };
            
            this.setTransform(currentTransform);
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };
        
        requestAnimationFrame(animate);
    }
    
    // Smooth zoom to a specific scale
    zoomTo(targetScale, centerX = null, centerY = null, duration = 300) {
        const currentTransform = this.getTransform();
        let targetTransform = { ...currentTransform, scale: targetScale };
        
        // If center point is provided, calculate new translation
        if (centerX !== null && centerY !== null) {
            const rect = this.canvas.getBoundingClientRect();
            const canvasX = centerX - rect.left;
            const canvasY = centerY - rect.top;
            
            const beforeX = (canvasX - currentTransform.translateX) / currentTransform.scale;
            const beforeY = (canvasY - currentTransform.translateY) / currentTransform.scale;
            
            const afterX = beforeX * targetScale;
            const afterY = beforeY * targetScale;
            
            targetTransform.translateX = canvasX - afterX;
            targetTransform.translateY = canvasY - afterY;
        }
        
        this.animateToTransform(targetTransform, duration);
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CanvasManager;
}