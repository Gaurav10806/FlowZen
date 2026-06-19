// Performance Monitoring & Optimization System
class PerformanceMonitor {
    constructor() {
        this.metrics = new Map();
        this.observers = new Map();
        this.isMonitoring = false;
        this.performanceData = {
            fps: [],
            memory: [],
            renderTime: [],
            apiCalls: [],
            nodeCount: 0,
            edgeCount: 0
        };
        
        this.thresholds = {
            fps: 30,
            memory: 100 * 1024 * 1024, // 100MB
            renderTime: 16, // 16ms for 60fps
            apiResponseTime: 1000 // 1 second
        };
        
        this.init();
    }
    
    init() {
        this.setupPerformanceObservers();
        this.setupFPSMonitor();
        this.setupMemoryMonitor();
        this.setupRenderTimeMonitor();
        this.createPerformancePanel();
    }
    
    setupPerformanceObservers() {
        // Performance Observer for navigation timing
        if ('PerformanceObserver' in window) {
            const observer = new PerformanceObserver((list) => {
                list.getEntries().forEach(entry => {
                    this.recordMetric(entry.entryType, entry);
                });
            });
            
            observer.observe({ entryTypes: ['navigation', 'resource', 'measure'] });
            this.observers.set('performance', observer);
        }
        
        // Intersection Observer for viewport optimization
        if ('IntersectionObserver' in window) {
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    const element = entry.target;
                    if (entry.isIntersecting) {
                        element.classList.add('in-viewport');
                        this.optimizeElement(element);
                    } else {
                        element.classList.remove('in-viewport');
                        this.deoptimizeElement(element);
                    }
                });
            }, { threshold: 0.1 });
            
            this.observers.set('intersection', observer);
        }
        
        // Mutation Observer for DOM changes
        if ('MutationObserver' in window) {
            const observer = new MutationObserver((mutations) => {
                mutations.forEach(mutation => {
                    if (mutation.type === 'childList') {
                        this.handleDOMChanges(mutation);
                    }
                });
            });
            
            observer.observe(document.body, {
                childList: true,
                subtree: true
            });
            
            this.observers.set('mutation', observer);
        }
    }
    
    setupFPSMonitor() {
        let lastTime = performance.now();
        let frameCount = 0;
        
        const measureFPS = (currentTime) => {
            frameCount++;
            
            if (currentTime - lastTime >= 1000) {
                const fps = Math.round((frameCount * 1000) / (currentTime - lastTime));
                this.recordFPS(fps);
                
                frameCount = 0;
                lastTime = currentTime;
            }
            
            if (this.isMonitoring) {
                requestAnimationFrame(measureFPS);
            }
        };
        
        this.startFPSMonitoring = () => {
            this.isMonitoring = true;
            requestAnimationFrame(measureFPS);
        };
        
        this.stopFPSMonitoring = () => {
            this.isMonitoring = false;
        };
    }
    
    setupMemoryMonitor() {
        this.memoryInterval = setInterval(() => {
            if (performance.memory) {
                const memory = {
                    used: performance.memory.usedJSHeapSize,
                    total: performance.memory.totalJSHeapSize,
                    limit: performance.memory.jsHeapSizeLimit,
                    timestamp: Date.now()
                };
                
                this.recordMemory(memory);
                
                // Check for memory leaks
                if (memory.used > this.thresholds.memory) {
                    this.handleMemoryWarning(memory);
                }
            }
        }, 5000); // Check every 5 seconds
    }
    
    setupRenderTimeMonitor() {
        const originalRequestAnimationFrame = window.requestAnimationFrame;
        
        window.requestAnimationFrame = (callback) => {
            const startTime = performance.now();
            
            return originalRequestAnimationFrame(() => {
                const endTime = performance.now();
                const renderTime = endTime - startTime;
                
                this.recordRenderTime(renderTime);
                
                if (renderTime > this.thresholds.renderTime) {
                    this.handleSlowRender(renderTime);
                }
                
                callback();
            });
        };
    }
    
    createPerformancePanel() {
        const panel = document.createElement('div');
        panel.className = 'performance-panel';
        panel.innerHTML = `
            <div class="performance-header">
                <span>Performance Monitor</span>
                <button class="performance-toggle" onclick="performanceMonitor.togglePanel()">
                    <i class="fas fa-chart-line"></i>
                </button>
            </div>
            <div class="performance-content">
                <div class="performance-metric">
                    <label>FPS</label>
                    <span class="fps-value">--</span>
                    <div class="fps-chart"></div>
                </div>
                <div class="performance-metric">
                    <label>Memory</label>
                    <span class="memory-value">--</span>
                    <div class="memory-chart"></div>
                </div>
                <div class="performance-metric">
                    <label>Render Time</label>
                    <span class="render-value">--</span>
                    <div class="render-chart"></div>
                </div>
                <div class="performance-metric">
                    <label>Nodes</label>
                    <span class="nodes-value">0</span>
                </div>
                <div class="performance-metric">
                    <label>Edges</label>
                    <span class="edges-value">0</span>
                </div>
                <div class="performance-actions">
                    <button onclick="performanceMonitor.optimizePerformance()" class="btn-optimize">
                        <i class="fas fa-rocket"></i> Optimize
                    </button>
                    <button onclick="performanceMonitor.clearMetrics()" class="btn-clear">
                        <i class="fas fa-trash"></i> Clear
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(panel);
        this.panel = panel;
        
        this.setupPanelStyles();
    }
    
    setupPanelStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .performance-panel {
                position: fixed;
                top: 20px;
                left: 20px;
                background: rgba(0, 0, 0, 0.9);
                color: white;
                border-radius: 8px;
                padding: 0;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                z-index: 10000;
                min-width: 200px;
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                transform: translateX(-180px);
                transition: transform 0.3s ease;
            }
            
            .performance-panel.open {
                transform: translateX(0);
            }
            
            .performance-header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 8px 12px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                font-weight: bold;
            }
            
            .performance-toggle {
                background: none;
                border: none;
                color: white;
                cursor: pointer;
                padding: 4px;
                border-radius: 4px;
                transition: background 0.2s ease;
            }
            
            .performance-toggle:hover {
                background: rgba(255, 255, 255, 0.1);
            }
            
            .performance-content {
                padding: 12px;
                display: none;
            }
            
            .performance-panel.open .performance-content {
                display: block;
            }
            
            .performance-metric {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 8px;
                padding: 4px 0;
            }
            
            .performance-metric label {
                font-weight: bold;
                min-width: 60px;
            }
            
            .fps-value.good { color: #10b981; }
            .fps-value.warning { color: #f59e0b; }
            .fps-value.critical { color: #ef4444; }
            
            .memory-value.good { color: #10b981; }
            .memory-value.warning { color: #f59e0b; }
            .memory-value.critical { color: #ef4444; }
            
            .render-value.good { color: #10b981; }
            .render-value.warning { color: #f59e0b; }
            .render-value.critical { color: #ef4444; }
            
            .performance-chart {
                width: 60px;
                height: 20px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 2px;
                position: relative;
                overflow: hidden;
            }
            
            .chart-bar {
                position: absolute;
                bottom: 0;
                width: 2px;
                background: #4f46e5;
                transition: height 0.3s ease;
            }
            
            .performance-actions {
                margin-top: 12px;
                display: flex;
                gap: 8px;
            }
            
            .btn-optimize, .btn-clear {
                background: rgba(79, 70, 229, 0.8);
                border: none;
                color: white;
                padding: 6px 12px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 11px;
                transition: background 0.2s ease;
                flex: 1;
            }
            
            .btn-optimize:hover, .btn-clear:hover {
                background: rgba(79, 70, 229, 1);
            }
            
            .btn-clear {
                background: rgba(239, 68, 68, 0.8);
            }
            
            .btn-clear:hover {
                background: rgba(239, 68, 68, 1);
            }
        `;
        document.head.appendChild(style);
    }
    
    recordFPS(fps) {
        this.performanceData.fps.push({ value: fps, timestamp: Date.now() });
        
        // Keep only last 60 measurements
        if (this.performanceData.fps.length > 60) {
            this.performanceData.fps.shift();
        }
        
        this.updateFPSDisplay(fps);
    }
    
    recordMemory(memory) {
        this.performanceData.memory.push(memory);
        
        // Keep only last 60 measurements
        if (this.performanceData.memory.length > 60) {
            this.performanceData.memory.shift();
        }
        
        this.updateMemoryDisplay(memory);
    }
    
    recordRenderTime(time) {
        this.performanceData.renderTime.push({ value: time, timestamp: Date.now() });
        
        // Keep only last 60 measurements
        if (this.performanceData.renderTime.length > 60) {
            this.performanceData.renderTime.shift();
        }
        
        this.updateRenderTimeDisplay(time);
    }
    
    recordMetric(type, entry) {
        this.metrics.set(`${type}_${Date.now()}`, entry);
    }
    
    updateFPSDisplay(fps) {
        const fpsElement = this.panel.querySelector('.fps-value');
        if (fpsElement) {
            fpsElement.textContent = fps;
            
            // Color coding
            fpsElement.className = 'fps-value';
            if (fps >= 50) fpsElement.classList.add('good');
            else if (fps >= 30) fpsElement.classList.add('warning');
            else fpsElement.classList.add('critical');
        }
        
        this.updateChart('.fps-chart', this.performanceData.fps, 60);
    }
    
    updateMemoryDisplay(memory) {
        const memoryElement = this.panel.querySelector('.memory-value');
        if (memoryElement) {
            const mb = Math.round(memory.used / 1024 / 1024);
            memoryElement.textContent = `${mb}MB`;
            
            // Color coding
            memoryElement.className = 'memory-value';
            if (memory.used < this.thresholds.memory * 0.7) memoryElement.classList.add('good');
            else if (memory.used < this.thresholds.memory) memoryElement.classList.add('warning');
            else memoryElement.classList.add('critical');
        }
        
        this.updateChart('.memory-chart', this.performanceData.memory.map(m => ({
            value: m.used / 1024 / 1024,
            timestamp: m.timestamp
        })), 200);
    }
    
    updateRenderTimeDisplay(time) {
        const renderElement = this.panel.querySelector('.render-value');
        if (renderElement) {
            renderElement.textContent = `${Math.round(time)}ms`;
            
            // Color coding
            renderElement.className = 'render-value';
            if (time <= 16) renderElement.classList.add('good');
            else if (time <= 33) renderElement.classList.add('warning');
            else renderElement.classList.add('critical');
        }
        
        this.updateChart('.render-chart', this.performanceData.renderTime, 50);
    }
    
    updateChart(selector, data, maxValue) {
        const chart = this.panel.querySelector(selector);
        if (!chart || data.length === 0) return;
        
        chart.innerHTML = '';
        
        const maxDataValue = Math.max(...data.map(d => d.value), maxValue);
        const barWidth = chart.offsetWidth / Math.min(data.length, 30);
        
        data.slice(-30).forEach((point, index) => {
            const bar = document.createElement('div');
            bar.className = 'chart-bar';
            bar.style.left = `${index * barWidth}px`;
            bar.style.width = `${barWidth - 1}px`;
            bar.style.height = `${(point.value / maxDataValue) * 100}%`;
            
            // Color based on performance
            if (selector.includes('fps')) {
                bar.style.background = point.value >= 50 ? '#10b981' : 
                                     point.value >= 30 ? '#f59e0b' : '#ef4444';
            } else if (selector.includes('memory')) {
                bar.style.background = point.value < maxValue * 0.7 ? '#10b981' : 
                                     point.value < maxValue ? '#f59e0b' : '#ef4444';
            } else {
                bar.style.background = point.value <= 16 ? '#10b981' : 
                                     point.value <= 33 ? '#f59e0b' : '#ef4444';
            }
            
            chart.appendChild(bar);
        });
    }
    
    updateNodeCount(count) {
        this.performanceData.nodeCount = count;
        const element = this.panel.querySelector('.nodes-value');
        if (element) {
            element.textContent = count;
        }
    }
    
    updateEdgeCount(count) {
        this.performanceData.edgeCount = count;
        const element = this.panel.querySelector('.edges-value');
        if (element) {
            element.textContent = count;
        }
    }
    
    togglePanel() {
        this.panel.classList.toggle('open');
        
        if (this.panel.classList.contains('open')) {
            this.startFPSMonitoring();
        } else {
            this.stopFPSMonitoring();
        }
    }
    
    optimizePerformance() {
        // Viewport culling for nodes
        this.optimizeViewport();
        
        // Debounce expensive operations
        this.setupDebouncing();
        
        // Optimize DOM updates
        this.optimizeDOM();
        
        // Clean up unused resources
        this.cleanupResources();
        
        if (window.notificationManager) {
            window.notificationManager.success('Performance optimizations applied', {
                duration: 3000
            });
        }
    }
    
    optimizeViewport() {
        const nodes = document.querySelectorAll('.workflow-node');
        const observer = this.observers.get('intersection');
        
        nodes.forEach(node => {
            if (observer) {
                observer.observe(node);
            }
        });
    }
    
    optimizeElement(element) {
        // Enable GPU acceleration for visible elements
        element.style.willChange = 'transform';
        element.style.transform = 'translateZ(0)';
    }
    
    deoptimizeElement(element) {
        // Remove GPU acceleration for hidden elements
        element.style.willChange = 'auto';
        element.style.transform = '';
    }
    
    setupDebouncing() {
        // Debounce pan and zoom operations
        if (window.advancedCanvas) {
            const originalUpdateTransform = window.advancedCanvas.updateTransform;
            window.advancedCanvas.updateTransform = this.debounce(originalUpdateTransform.bind(window.advancedCanvas), 16);
        }
    }
    
    optimizeDOM() {
        // Use document fragments for batch DOM updates
        this.createDocumentFragment = () => document.createDocumentFragment();
        
        // Minimize reflows and repaints
        this.batchDOMUpdates = (updates) => {
            const fragment = document.createDocumentFragment();
            updates.forEach(update => update(fragment));
            document.body.appendChild(fragment);
        };
    }
    
    cleanupResources() {
        // Clear old performance data
        const cutoff = Date.now() - 300000; // 5 minutes
        
        this.performanceData.fps = this.performanceData.fps.filter(d => d.timestamp > cutoff);
        this.performanceData.memory = this.performanceData.memory.filter(d => d.timestamp > cutoff);
        this.performanceData.renderTime = this.performanceData.renderTime.filter(d => d.timestamp > cutoff);
        
        // Clear old metrics
        this.metrics.forEach((value, key) => {
            if (value.startTime && value.startTime < cutoff) {
                this.metrics.delete(key);
            }
        });
        
        // Force garbage collection if available
        if (window.gc) {
            window.gc();
        }
    }
    
    clearMetrics() {
        this.performanceData = {
            fps: [],
            memory: [],
            renderTime: [],
            apiCalls: [],
            nodeCount: 0,
            edgeCount: 0
        };
        
        this.metrics.clear();
        
        // Update displays
        this.updateFPSDisplay(0);
        this.updateMemoryDisplay({ used: 0, timestamp: Date.now() });
        this.updateRenderTimeDisplay(0);
    }
    
    handleMemoryWarning(memory) {
        console.warn('High memory usage detected:', memory);
        
        if (window.notificationManager) {
            window.notificationManager.warning(
                `High memory usage: ${Math.round(memory.used / 1024 / 1024)}MB`,
                { duration: 5000 }
            );
        }
    }
    
    handleSlowRender(renderTime) {
        console.warn('Slow render detected:', renderTime);
        
        if (renderTime > 100) { // Very slow
            if (window.notificationManager) {
                window.notificationManager.warning(
                    `Slow rendering detected: ${Math.round(renderTime)}ms`,
                    { duration: 3000 }
                );
            }
        }
    }
    
    handleDOMChanges(mutation) {
        // Update node/edge counts
        if (mutation.addedNodes.length > 0) {
            const nodes = document.querySelectorAll('.workflow-node').length;
            const edges = document.querySelectorAll('.workflow-edge').length;
            
            this.updateNodeCount(nodes);
            this.updateEdgeCount(edges);
        }
    }
    
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
    
    // API call monitoring
    monitorAPICall(url, startTime) {
        const endTime = performance.now();
        const duration = endTime - startTime;
        
        this.performanceData.apiCalls.push({
            url,
            duration,
            timestamp: Date.now()
        });
        
        if (duration > this.thresholds.apiResponseTime) {
            console.warn(`Slow API call: ${url} took ${duration}ms`);
        }
    }
    
    // Get performance report
    getPerformanceReport() {
        const avgFPS = this.performanceData.fps.length > 0 
            ? this.performanceData.fps.reduce((sum, d) => sum + d.value, 0) / this.performanceData.fps.length 
            : 0;
        
        const avgRenderTime = this.performanceData.renderTime.length > 0
            ? this.performanceData.renderTime.reduce((sum, d) => sum + d.value, 0) / this.performanceData.renderTime.length
            : 0;
        
        const currentMemory = this.performanceData.memory.length > 0
            ? this.performanceData.memory[this.performanceData.memory.length - 1]
            : { used: 0 };
        
        return {
            fps: {
                average: Math.round(avgFPS),
                current: this.performanceData.fps.length > 0 
                    ? this.performanceData.fps[this.performanceData.fps.length - 1].value 
                    : 0,
                status: avgFPS >= 50 ? 'good' : avgFPS >= 30 ? 'warning' : 'critical'
            },
            memory: {
                current: Math.round(currentMemory.used / 1024 / 1024),
                status: currentMemory.used < this.thresholds.memory * 0.7 ? 'good' : 
                       currentMemory.used < this.thresholds.memory ? 'warning' : 'critical'
            },
            renderTime: {
                average: Math.round(avgRenderTime),
                status: avgRenderTime <= 16 ? 'good' : avgRenderTime <= 33 ? 'warning' : 'critical'
            },
            nodes: this.performanceData.nodeCount,
            edges: this.performanceData.edgeCount
        };
    }
}

// Create global instance
window.performanceMonitor = new PerformanceMonitor();