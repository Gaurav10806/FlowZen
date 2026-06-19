// Enhanced Main Application - Integrates All Advanced Features
class EnhancedWorkflowApp {
    constructor() {
        this.modules = new Map();
        this.isInitialized = false;
        this.config = {
            enablePerformanceMonitoring: true,
            enableAnimations: true,
            enableTemplates: true,
            enableAdvancedCanvas: true,
            autoSave: true,
            autoSaveInterval: 30000, // 30 seconds
            theme: 'auto' // auto, light, dark
        };

        this.init();
    }

    async init() {
        try {
            console.log('🚀 Initializing Enhanced Workflow Application...');

            // Initialize core modules
            await this.initializeModules();

            // Setup global event handlers
            this.setupGlobalEvents();

            // Setup keyboard shortcuts
            this.setupKeyboardShortcuts();

            // Setup auto-save
            if (this.config.autoSave) {
                this.setupAutoSave();
            }

            // Setup theme system
            this.setupThemeSystem();

            // Initialize UI enhancements
            this.initializeUIEnhancements();

            // Setup error handling
            this.setupErrorHandling();

            // Mark as initialized
            this.isInitialized = true;

            console.log('✅ Enhanced Workflow Application initialized successfully!');

            // Show welcome notification
            if (window.notificationManager) {
                window.notificationManager.success(
                    'Welcome to the Enhanced Workflow Builder!',
                    {
                        title: 'System Ready',
                        duration: 4000,
                        actions: [
                            {
                                label: 'Quick Start',
                                type: 'primary',
                                handler: 'workflowTemplates.showTemplateModal()'
                            }
                        ]
                    }
                );
            }

        } catch (error) {
            console.error('❌ Failed to initialize Enhanced Workflow Application:', error);
            this.handleInitializationError(error);
        }
    }

    async initializeModules() {
        const moduleInitializers = [
            { name: 'animations', init: () => new AnimationManager() },
            { name: 'notifications', init: () => window.notificationManager },
            { name: 'sound', init: () => new SoundManager() }, // Batch 5
            { name: 'interactiveElements', init: () => window.interactiveElements },
            { name: 'advancedCanvas', init: () => window.advancedCanvas },
            { name: 'workflowTemplates', init: () => window.workflowTemplates },
            { name: 'performanceMonitor', init: () => window.performanceMonitor },
            { name: 'history', init: () => new HistoryManager(window.advancedCanvas || new AdvancedCanvas()) }, // Batch 5
            { name: 'confetti', init: () => new ConfettiManager() } // Batch 5
        ];

        for (const module of moduleInitializers) {
            try {
                console.log(`Initializing ${module.name}...`);
                const instance = module.init();
                this.modules.set(module.name, instance);

                // Expose globally
                window[`${module.name}Manager`] = instance;

                console.log(`✅ ${module.name} initialized`);
            } catch (error) {
                console.warn(`⚠️ Failed to initialize ${module.name}:`, error);
            }
        }

        // Post-Init: Link History to Canvas
        if (this.modules.get('history') && this.modules.get('advancedCanvas')) {
            this.modules.get('history').canvasManager = this.modules.get('advancedCanvas');
        }
    }

    setupGlobalEvents() {
        // Window resize handler
        window.addEventListener('resize', this.debounce(() => {
            this.handleWindowResize();
        }, 250));

        // Visibility change handler
        document.addEventListener('visibilitychange', () => {
            this.handleVisibilityChange();
        });

        // Before unload handler
        window.addEventListener('beforeunload', (e) => {
            if (this.hasUnsavedChanges()) {
                e.preventDefault();
                e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
                return e.returnValue;
            }
        });

        // Online/offline handlers
        window.addEventListener('online', () => {
            this.handleOnlineStatusChange(true);
        });

        window.addEventListener('offline', () => {
            this.handleOnlineStatusChange(false);
        });

        // Error handlers
        window.addEventListener('error', (e) => {
            this.handleGlobalError(e);
        });

        window.addEventListener('unhandledrejection', (e) => {
            this.handleUnhandledRejection(e);
        });
    }

    setupKeyboardShortcuts() {
        const shortcuts = {
            // File operations
            'ctrl+s': () => this.saveWorkflow(),
            'ctrl+shift+s': () => this.saveWorkflowAs(),
            'ctrl+o': () => this.openWorkflow(),
            'ctrl+n': () => this.newWorkflow(),

            // Edit operations
            'ctrl+z': () => {
                // Undo
                const history = this.modules.get('history');
                if (history) history.undo();
            },
            'ctrl+y': () => {
                // Redo
                const history = this.modules.get('history');
                if (history) history.redo();
            },
            'ctrl+shift+z': () => {
                // Redo (Alternative)
                const history = this.modules.get('history');
                if (history) history.redo();
            },
            'ctrl+c': () => this.copy(),
            'ctrl+v': () => this.paste(),
            'ctrl+x': () => this.cut(),
            'ctrl+a': () => this.selectAll(),
            'delete': () => this.deleteSelected(),
            'backspace': () => this.deleteSelected(),

            // View operations
            'ctrl+0': () => this.resetView(),
            'ctrl+1': () => this.fitToView(),
            'ctrl+=': () => this.zoomIn(),
            'ctrl+-': () => this.zoomOut(),
            'ctrl+g': () => this.toggleGrid(),
            'ctrl+m': () => this.toggleMinimap(),

            // Workflow operations
            'f5': () => this.runWorkflow(),
            'shift+f5': () => this.stopWorkflow(),
            'f9': () => this.debugWorkflow(),
            'f10': () => this.stepWorkflow(),

            // UI operations
            'ctrl+shift+p': () => this.showCommandPalette(),
            'ctrl+shift+t': () => this.showTemplates(),
            'ctrl+shift+h': () => this.showHelp(),
            'escape': () => this.handleEscape(),

            // Performance
            'ctrl+shift+i': () => this.togglePerformanceMonitor(),
            'ctrl+shift+o': () => this.optimizePerformance()
        };

        document.addEventListener('keydown', (e) => {
            // Skip if typing in input fields
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.contentEditable === 'true') {
                return;
            }

            const key = this.getKeyboardShortcut(e);
            const handler = shortcuts[key];

            if (handler) {
                e.preventDefault();
                try {
                    handler();
                } catch (error) {
                    console.error(`Error executing shortcut ${key}:`, error);
                }
            }
        });
    }

    setupAutoSave() {
        setInterval(() => {
            if (this.hasUnsavedChanges()) {
                this.autoSave();
            }
        }, this.config.autoSaveInterval);

        // Save on visibility change (tab switch, minimize)
        document.addEventListener('visibilitychange', () => {
            if (document.hidden && this.hasUnsavedChanges()) {
                this.autoSave();
            }
        });
    }

    setupThemeSystem() {
        const savedTheme = localStorage.getItem('workflow-theme') || this.config.theme;
        this.setTheme(savedTheme);

        // Listen for system theme changes
        if (window.matchMedia) {
            const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
            mediaQuery.addEventListener('change', (e) => {
                if (this.config.theme === 'auto') {
                    this.applyTheme(e.matches ? 'dark' : 'light');
                }
            });
        }
    }

    initializeUIEnhancements() {
        // Initialize Global Search
        if (typeof GlobalSearch !== 'undefined') {
            this.globalSearch = new GlobalSearch();
        }
        // Add enhanced tooltips to existing elements
        this.enhanceExistingElements();

        // Setup drag and drop enhancements
        this.setupEnhancedDragDrop();

        // Setup context menus
        this.setupContextMenus();

        // Setup loading states
        this.setupLoadingStates();

        // Initialize command palette
        this.initializeCommandPalette();

        // Setup status bar
        this.setupStatusBar();

        // Load Analytics Graph
        this.loadAnalytics();
    }

    setupErrorHandling() {
        // Global error boundary
        window.onerror = (message, source, lineno, colno, error) => {
            this.handleError({
                message,
                source,
                lineno,
                colno,
                error,
                type: 'javascript'
            });
            return false; // Don't prevent default error handling
        };

        // Promise rejection handler
        window.addEventListener('unhandledrejection', (event) => {
            this.handleError({
                message: event.reason?.message || 'Unhandled promise rejection',
                error: event.reason,
                type: 'promise'
            });
        });
    }

    // Keyboard shortcut helpers
    getKeyboardShortcut(e) {
        const parts = [];
        if (e.ctrlKey || e.metaKey) parts.push('ctrl');
        if (e.shiftKey) parts.push('shift');
        if (e.altKey) parts.push('alt');

        let key = e.key.toLowerCase();
        if (key === ' ') key = 'space';
        if (key === 'arrowup') key = 'up';
        if (key === 'arrowdown') key = 'down';
        if (key === 'arrowleft') key = 'left';
        if (key === 'arrowright') key = 'right';

        parts.push(key);
        return parts.join('+');
    }

    // File operations
    async saveWorkflow() {
        try {
            this.showLoadingState('Saving workflow...');

            const workflowData = this.getWorkflowData();
            const result = await this.apiCall('/api/workflows/', {
                method: 'POST',
                body: JSON.stringify(workflowData)
            });

            this.markAsSaved();
            this.hideLoadingState();

            if (window.notificationManager) {
                window.notificationManager.success('Workflow saved successfully!');
            }

            return result;
        } catch (error) {
            this.hideLoadingState();
            this.handleError(error);
            throw error;
        }
    }

    async runWorkflow() {
        try {
            this.showLoadingState('Running workflow...');

            // 1. Save first to get ID and ensure backend has latest graph
            // This fixes the issue where /execute/ was called with body. 
            // The real API requires /ID/run/
            const savedWorkflow = await this.saveWorkflow();
            const workflowId = savedWorkflow.id;

            if (!workflowId) {
                throw new Error("Workflow ID not found after save.");
            }

            // 2. Execute using the ID
            const result = await this.apiCall(`/api/v1/workflows/${workflowId}/run/`, {
                method: 'POST',
                body: JSON.stringify({}) // Run uses the stored graph on backend
            });

            this.hideLoadingState();
            this.handleWorkflowExecution(result);

            return result;
        } catch (error) {
            this.hideLoadingState();
            this.handleError(error);
            throw error;
        }
    }

    // View operations
    resetView() {
        if (this.modules.get('advancedCanvas')) {
            this.modules.get('advancedCanvas').resetView();
        }
    }

    fitToView() {
        if (this.modules.get('advancedCanvas')) {
            this.modules.get('advancedCanvas').fitToView();
        }
    }

    zoomIn() {
        if (this.modules.get('advancedCanvas')) {
            this.modules.get('advancedCanvas').zoom(0.2);
        }
    }

    zoomOut() {
        if (this.modules.get('advancedCanvas')) {
            this.modules.get('advancedCanvas').zoom(-0.2);
        }
    }

    toggleGrid() {
        if (this.modules.get('advancedCanvas')) {
            this.modules.get('advancedCanvas').toggleGrid();
        }
    }

    toggleMinimap() {
        if (this.modules.get('advancedCanvas')) {
            this.modules.get('advancedCanvas').toggleMinimap();
        }
    }

    // UI operations
    showTemplates() {
        if (this.modules.get('workflowTemplates')) {
            this.modules.get('workflowTemplates').showTemplateModal();
        }
    }

    togglePerformanceMonitor() {
        if (this.modules.get('performanceMonitor')) {
            this.modules.get('performanceMonitor').togglePanel();
        }
    }

    optimizePerformance() {
        if (this.modules.get('performanceMonitor')) {
            this.modules.get('performanceMonitor').optimizePerformance();
        }
    }

    // Theme management
    setTheme(theme) {
        this.config.theme = theme;
        localStorage.setItem('workflow-theme', theme);

        if (theme === 'auto') {
            const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
            this.applyTheme(prefersDark ? 'dark' : 'light');
        } else {
            this.applyTheme(theme);
        }
    }

    applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        document.body.className = document.body.className.replace(/theme-\w+/g, '') + ` theme-${theme}`;
    }

    // Event handlers
    handleWindowResize() {
        if (this.modules.get('advancedCanvas')) {
            this.modules.get('advancedCanvas').updateViewportBounds();
        }
    }

    handleVisibilityChange() {
        if (document.hidden) {
            // Page is hidden - pause performance monitoring
            if (this.modules.get('performanceMonitor')) {
                this.modules.get('performanceMonitor').stopFPSMonitoring();
            }
        } else {
            // Page is visible - resume performance monitoring
            if (this.modules.get('performanceMonitor')) {
                this.modules.get('performanceMonitor').startFPSMonitoring();
            }
        }
    }

    handleOnlineStatusChange(isOnline) {
        const message = isOnline ? 'Connection restored' : 'Connection lost - working offline';
        const type = isOnline ? 'success' : 'warning';

        if (window.notificationManager) {
            window.notificationManager[type](message, { duration: 3000 });
        }

        // Update UI to reflect online status
        document.body.classList.toggle('offline', !isOnline);
    }

    handleError(error) {
        console.error('Application error:', error);

        if (window.notificationManager) {
            window.notificationManager.error(
                error.message || 'An unexpected error occurred',
                {
                    title: 'Error',
                    persistent: true,
                    actions: [
                        {
                            label: 'Report Bug',
                            handler: () => this.reportBug(error)
                        }
                    ]
                }
            );
        }
    }

    handleGlobalError(event) {
        console.error('Global error:', event.error || event.message);
        this.handleError({
            message: event.message,
            source: event.filename,
            lineno: event.lineno,
            colno: event.colno,
            error: event.error
        });
    }

    handleUnhandledRejection(event) {
        console.error('Unhandled promise rejection:', event.reason);
        this.handleError({
            message: event.reason?.message || 'Unhandled promise rejection',
            error: event.reason
        });
    }

    handleInitializationError(error) {
        console.error('Initialization error:', error);
        // Don't use notificationManager here as it might not be initialized
        alert(`Failed to initialize application: ${error.message}\n\nPlease refresh the page or contact support.`);
    }

    handleWorkflowExecution(result) {
        if (result.success) {
            if (window.notificationManager) {
                window.notificationManager.success(
                    'Workflow executed successfully!',
                    {
                        duration: 4000,
                        actions: [
                            {
                                label: 'View Results',
                                type: 'primary',
                                handler: () => this.showExecutionResults(result)
                            }
                        ]
                    }
                );
            }
        } else {
            if (window.notificationManager) {
                window.notificationManager.error(
                    result.error || 'Workflow execution failed',
                    { duration: 6000 }
                );
            }
        }
    }

    // Utility methods
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

    async apiCall(url, options = {}) {
        const startTime = performance.now();

        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                credentials: 'same-origin',
                ...options
            });

            if (!response.ok) {
                const error = new Error(`HTTP ${response.status}: ${response.statusText}`);
                error.response = response; // Attach response for parsing
                throw error;
            }

            const data = await response.json();

            // Monitor API performance
            if (this.modules.get('performanceMonitor')) {
                this.modules.get('performanceMonitor').monitorAPICall(url, startTime);
            }

            return data;
        } catch (error) {
            // New: Parse JSON error response if available
            if (error.response && typeof error.response.json === 'function') {
                try {
                    const errorData = await error.response.json();
                    const message = errorData.detail || errorData.error || error.message;
                    const trace = errorData.trace || errorData.traceback;

                    if (window.notificationManager) {
                        const actions = [];

                        if (trace) {
                            actions.push({
                                label: 'View Trace',
                                handler: () => {
                                    // Open trace in new window for readability
                                    const win = window.open("", "Server Trace", "width=900,height=700,scrollbars=yes");
                                    win.document.write(`
                                        <html>
                                            <head>
                                                <title>Server Error Trace</title>
                                                <style>
                                                    body { background: #1a1a1a; color: #ff5555; font-family: monospace; padding: 20px; }
                                                    pre { white-space: pre-wrap; word-wrap: break-word; }
                                                </style>
                                            </head>
                                            <body>
                                                <h2>${message}</h2>
                                                <hr>
                                                <pre>${trace}</pre>
                                            </body>
                                        </html>
                                    `);
                                }
                            });
                        }

                        actions.push({
                            label: 'Report Bug',
                            handler: () => this.reportBug(error)
                        });

                        window.notificationManager.error(message, {
                            title: errorData.error_type || 'Server Error',
                            duration: trace ? 10000 : 5000,
                            persistent: !!trace,
                            actions: actions
                        });
                    }
                    throw new Error(message); // Re-throw with clean message
                } catch (jsonError) {
                    // Fallback if JSON parse fails
                }
            }

            // Monitor failed API calls
            if (this.modules.get('performanceMonitor')) {
                this.modules.get('performanceMonitor').monitorAPICall(url, startTime);
            }
            throw error;
        }
    }

    getCSRFToken() {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                return value;
            }
        }
        return null;
    }

    showLoadingState(message = 'Loading...') {
        // Implementation depends on your UI framework
        console.log('Loading:', message);
    }

    hideLoadingState() {
        // Implementation depends on your UI framework
        console.log('Loading complete');
    }

    getWorkflowData() {
        // Get current workflow data from the canvas
        return {
            name: 'Current Workflow',
            nodes: [],
            edges: []
        };
    }

    hasUnsavedChanges() {
        // Check if there are unsaved changes
        return false; // Implement based on your state management
    }

    markAsSaved() {
        // Mark workflow as saved
        console.log('Workflow marked as saved');
    }

    autoSave() {
        // Perform auto-save
        console.log('Auto-saving workflow...');
    }

    // Enhanced UI methods
    enhanceExistingElements() {
        // Add tooltips to buttons
        document.querySelectorAll('button[title]').forEach(button => {
            button.setAttribute('data-tooltip', button.title);
            button.removeAttribute('title');
        });

        // Add hover effects to interactive elements
        document.querySelectorAll('.node-item, .workflow-node, button').forEach(element => {
            element.classList.add('hover-lift');
        });
    }

    setupEnhancedDragDrop() {
        // Enhanced drag and drop with visual feedback
        document.addEventListener('dragstart', (e) => {
            if (e.target.classList.contains('node-item')) {
                e.target.classList.add('dragging');

                // Create drag preview
                const preview = e.target.cloneNode(true);
                preview.style.opacity = '0.8';
                preview.style.transform = 'rotate(5deg)';
                document.body.appendChild(preview);

                setTimeout(() => {
                    if (preview.parentNode) {
                        preview.parentNode.removeChild(preview);
                    }
                }, 0);
            }
        });

        document.addEventListener('dragend', (e) => {
            if (e.target.classList.contains('node-item')) {
                e.target.classList.remove('dragging');
            }
        });
    }

    setupContextMenus() {
        // Add context menus to workflow nodes
        document.addEventListener('contextmenu', (e) => {
            document.addEventListener('contextmenu', (e) => {
                // Node Context Menu
                if (e.target.closest('.workflow-node')) {
                    e.preventDefault();
                    const node = e.target.closest('.workflow-node');
                    const menuItems = [
                        { icon: 'fas fa-edit', label: 'Edit Node', handler: 'editNode' },
                        { icon: 'fas fa-copy', label: 'Duplicate', handler: 'duplicateNode' },
                        { icon: 'fas fa-play', label: 'Execute', handler: 'executeNode' },
                        { divider: true },
                        { icon: 'fas fa-trash', label: 'Delete', handler: 'deleteNode', type: 'danger' }
                    ];
                    node.setAttribute('data-context-menu', JSON.stringify(menuItems));
                    if (window.interactiveElements) window.interactiveElements.showContextMenu(e, node);
                    return;
                }

                // Canvas Context Menu (Background)
                if (e.target.closest('.canvas-container') || e.target.classList.contains('canvas-content')) {
                    e.preventDefault();
                    const canvas = document.querySelector('.canvas-container');
                    const menuItems = [
                        { icon: 'fas fa-paste', label: 'Paste Node', handler: 'paste' },
                        { divider: true },
                        { icon: 'fas fa-compress-arrows-alt', label: 'Fit to View', handler: 'fitToView' },
                        { icon: 'fas fa-border-all', label: 'Toggle Grid', handler: 'toggleGrid' },
                        { icon: 'fas fa-map', label: 'Toggle Minimap', handler: 'toggleMinimap' }
                    ];
                    canvas.setAttribute('data-context-menu', JSON.stringify(menuItems));
                    if (window.interactiveElements) window.interactiveElements.showContextMenu(e, canvas);
                }
            });
        });
    }

    setupLoadingStates() {
        // Add loading states to buttons
        document.addEventListener('click', (e) => {
            if (e.target.matches('button[data-loading]')) {
                if (window.interactiveElements) {
                    window.interactiveElements.setLoading(e.target, true);

                    // Simulate async operation
                    setTimeout(() => {
                        window.interactiveElements.setLoading(e.target, false);
                    }, 2000);
                }
            }
        });
    }

    initializeCommandPalette() {
        // Command palette for quick actions
        const commands = [
            { name: 'Save Workflow', shortcut: 'Ctrl+S', action: () => this.saveWorkflow() },
            { name: 'Run Workflow', shortcut: 'F5', action: () => this.runWorkflow() },
            { name: 'Show Templates', shortcut: 'Ctrl+Shift+T', action: () => this.showTemplates() },
            { name: 'Toggle Grid', shortcut: 'Ctrl+G', action: () => this.toggleGrid() },
            { name: 'Fit to View', shortcut: 'Ctrl+1', action: () => this.fitToView() },
            { name: 'Performance Monitor', shortcut: 'Ctrl+Shift+I', action: () => this.togglePerformanceMonitor() }
        ];

        // Store commands for later use
        this.commands = commands;
    }

    setupStatusBar() {
        // Create status bar if it doesn't exist
        if (!document.querySelector('.status-bar')) {
            const statusBar = document.createElement('div');
            statusBar.className = 'status-bar';
            statusBar.innerHTML = `
                <div class="status-left">
                    <span class="status-item">Ready</span>
                </div>
                <div class="status-right">
                    <span class="status-item" id="node-count">0 nodes</span>
                    <span class="status-item" id="zoom-level">100%</span>
                    <span class="status-item" id="connection-status">Online</span>
                </div>
            `;
            document.body.appendChild(statusBar);

            // ... styles ...
        }
    }

    // Clipboard Operations
    copy() {
        if (!window.nodeManager) return;
        const selectedNodes = window.nodeManager.getSelectedNodes();
        if (selectedNodes.length === 0) {
            window.Toast.info("Clipboard", "Select nodes to copy");
            return;
        }

        const data = selectedNodes.map(node => window.nodeManager.serializeNode(node));
        localStorage.setItem('flowzen_clipboard', JSON.stringify(data));
        window.Toast.success("Clipboard", `Copied ${selectedNodes.length} node(s)`);
    }

    paste() {
        const dataStr = localStorage.getItem('flowzen_clipboard');
        if (!dataStr) {
            window.Toast.info("Clipboard", "Clipboard is empty");
            return;
        }

        try {
            const nodes = JSON.parse(dataStr);
            if (!Array.isArray(nodes)) return;

            window.nodeManager.clearSelection();

            nodes.forEach(nodeData => {
                // Offset position slightly
                nodeData.position.x += 20;
                nodeData.position.y += 20;
                // Create new ID
                nodeData.id = 'node_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5);

                window.nodeManager.createNode(nodeData);
            });

            window.Toast.success("Clipboard", `Pasted ${nodes.length} node(s)`);
        } catch (e) {
            console.error("Paste error:", e);
            window.Toast.error("Clipboard", "Failed to paste nodes");
        }
    }

    async loadAnalytics() {
        const img = document.getElementById('weekly-analytics-graph');
        const loader = document.getElementById('analytics-loading');
        const error = document.getElementById('analytics-error');

        if (!img) return;

        try {
            loader.style.display = 'flex';
            error.style.display = 'none';
            img.style.display = 'none';

            const data = await this.apiCall('/api/analytics/executions/weekly/');

            if (data.success && data.image) {
                img.src = data.image;
                img.style.display = 'block';
            } else {
                throw new Error('No image data');
            }
        } catch (e) {
            console.error('Analytics load failed:', e);
            error.style.display = 'block';
        } finally {
            loader.style.display = 'none';
        }
    }


    // Public API methods
    getModule(name) {
        return this.modules.get(name);
    }

    isReady() {
        return this.isInitialized;
    }

    getConfig() {
        return { ...this.config };
    }

    updateConfig(updates) {
        this.config = { ...this.config, ...updates };
        localStorage.setItem('workflow-config', JSON.stringify(this.config));
    }
}

// Initialize the enhanced application
document.addEventListener('DOMContentLoaded', () => {
    // Global Helpers for HTML Buttons
    // Global Helpers for HTML Buttons
    // toggleHistory removed to use builder.html implementation

    window.toggleProperties = function () {
        const panel = document.getElementById('properties-panel');
        panel.classList.toggle('collapsed');
    };

    // Initialize
    const app = new EnhancedWorkflowApp();
    window.app = app;
});

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = EnhancedWorkflowApp;
}