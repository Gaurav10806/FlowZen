// Real-time Execution Monitor - Live Workflow Execution Tracking
class ExecutionMonitor {
    constructor() {
        this.executions = new Map();
        this.activeExecution = null;
        this.panel = null;
        this.isVisible = false;
        this.websocket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        
        this.init();
    }
    
    init() {
        this.createPanel();
        this.setupStyles();
        this.setupEventListeners();
        this.connectWebSocket();
    }
    
    createPanel() {
        this.panel = document.createElement('div');
        this.panel.className = 'execution-monitor';
        this.panel.innerHTML = `
            <div class="monitor-header">
                <div class="monitor-title">
                    <i class="fas fa-play-circle"></i>
                    <span>Execution Monitor</span>
                </div>
                <div class="monitor-controls">
                    <button class="monitor-btn" onclick="executionMonitor.toggleAutoScroll()" data-tooltip="Auto-scroll">
                        <i class="fas fa-arrows-alt-v"></i>
                    </button>
                    <button class="monitor-btn" onclick="executionMonitor.clearHistory()" data-tooltip="Clear History">
                        <i class="fas fa-trash"></i>
                    </button>
                    <button class="monitor-btn" onclick="executionMonitor.togglePanel()" data-tooltip="Close Monitor">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
            
            <div class="monitor-tabs">
                <button class="tab-btn active" data-tab="current">
                    <i class="fas fa-play"></i>
                    Current
                </button>
                <button class="tab-btn" data-tab="history">
                    <i class="fas fa-history"></i>
                    History
                </button>
                <button class="tab-btn" data-tab="logs">
                    <i class="fas fa-file-alt"></i>
                    Logs
                </button>
                <button class="tab-btn" data-tab="performance">
                    <i class="fas fa-chart-line"></i>
                    Performance
                </button>
            </div>
            
            <div class="monitor-content">
                <div class="tab-pane active" id="current-tab">
                    <div class="execution-status" id="execution-status">
                        <div class="status-indicator idle">
                            <div class="status-dot"></div>
                            <span>No active execution</span>
                        </div>
                    </div>
                    
                    <div class="execution-flow" id="execution-flow">
                        <div class="flow-placeholder">
                            <i class="fas fa-play-circle"></i>
                            <h3>Ready to Execute</h3>
                            <p>Start a workflow to see real-time execution progress</p>
                        </div>
                    </div>
                    
                    <div class="execution-data" id="execution-data">
                        <div class="data-viewer">
                            <div class="data-header">
                                <h4>Node Data</h4>
                                <div class="data-controls">
                                    <button class="data-btn" onclick="executionMonitor.formatJson()">
                                        <i class="fas fa-code"></i>
                                        Format
                                    </button>
                                    <button class="data-btn" onclick="executionMonitor.copyData()">
                                        <i class="fas fa-copy"></i>
                                        Copy
                                    </button>
                                </div>
                            </div>
                            <div class="data-content" id="data-content">
                                <div class="data-placeholder">Select a node to view its data</div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="tab-pane" id="history-tab">
                    <div class="history-controls">
                        <div class="search-container">
                            <i class="fas fa-search"></i>
                            <input type="text" placeholder="Search executions..." id="history-search">
                        </div>
                        <div class="filter-controls">
                            <select id="status-filter">
                                <option value="">All Status</option>
                                <option value="success">Success</option>
                                <option value="failed">Failed</option>
                                <option value="cancelled">Cancelled</option>
                            </select>
                            <select id="time-filter">
                                <option value="today">Today</option>
                                <option value="week">This Week</option>
                                <option value="month">This Month</option>
                                <option value="all">All Time</option>
                            </select>
                        </div>
                    </div>
                    
                    <div class="execution-history" id="execution-history">
                        <!-- History items will be populated here -->
                    </div>
                </div>
                
                <div class="tab-pane" id="logs-tab">
                    <div class="logs-controls">
                        <div class="log-filters">
                            <button class="log-filter active" data-level="all">All</button>
                            <button class="log-filter" data-level="info">Info</button>
                            <button class="log-filter" data-level="warning">Warning</button>
                            <button class="log-filter" data-level="error">Error</button>
                        </div>
                        <div class="log-actions">
                            <button class="log-btn" onclick="executionMonitor.downloadLogs()">
                                <i class="fas fa-download"></i>
                                Download
                            </button>
                            <button class="log-btn" onclick="executionMonitor.clearLogs()">
                                <i class="fas fa-trash"></i>
                                Clear
                            </button>
                        </div>
                    </div>
                    
                    <div class="logs-container" id="logs-container">
                        <!-- Log entries will be populated here -->
                    </div>
                </div>
                
                <div class="tab-pane" id="performance-tab">
                    <div class="performance-metrics">
                        <div class="metric-card">
                            <div class="metric-icon">
                                <i class="fas fa-clock"></i>
                            </div>
                            <div class="metric-info">
                                <h4>Execution Time</h4>
                                <span class="metric-value" id="execution-time">--</span>
                            </div>
                        </div>
                        
                        <div class="metric-card">
                            <div class="metric-icon">
                                <i class="fas fa-memory"></i>
                            </div>
                            <div class="metric-info">
                                <h4>Memory Usage</h4>
                                <span class="metric-value" id="memory-usage">--</span>
                            </div>
                        </div>
                        
                        <div class="metric-card">
                            <div class="metric-icon">
                                <i class="fas fa-network-wired"></i>
                            </div>
                            <div class="metric-info">
                                <h4>API Calls</h4>
                                <span class="metric-value" id="api-calls">--</span>
                            </div>
                        </div>
                        
                        <div class="metric-card">
                            <div class="metric-icon">
                                <i class="fas fa-database"></i>
                            </div>
                            <div class="metric-info">
                                <h4>Data Processed</h4>
                                <span class="metric-value" id="data-processed">--</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="performance-charts">
                        <div class="chart-container">
                            <h4>Execution Timeline</h4>
                            <canvas id="timeline-chart" width="400" height="200"></canvas>
                        </div>
                        
                        <div class="chart-container">
                            <h4>Node Performance</h4>
                            <canvas id="performance-chart" width="400" height="200"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(this.panel);
    }
    
    setupStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .execution-monitor {
                position: fixed;
                bottom: -400px;
                left: 0;
                right: 0;
                height: 400px;
                background: white;
                border-top: 1px solid #e5e7eb;
                box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.1);
                z-index: 1000;
                display: flex;
                flex-direction: column;
                transition: bottom 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }
            
            .execution-monitor.visible {
                bottom: 0;
            }
            
            .monitor-header {
                padding: 12px 20px;
                border-bottom: 1px solid #e5e7eb;
                background: #f9fafb;
                display: flex;
                align-items: center;
                justify-content: space-between;
                min-height: 48px;
            }
            
            .monitor-title {
                display: flex;
                align-items: center;
                gap: 8px;
                font-weight: 600;
                color: #1f2937;
                font-size: 14px;
            }
            
            .monitor-title i {
                color: #4f46e5;
                font-size: 16px;
            }
            
            .monitor-controls {
                display: flex;
                gap: 4px;
            }
            
            .monitor-btn {
                width: 28px;
                height: 28px;
                border: none;
                border-radius: 4px;
                background: #f3f4f6;
                color: #6b7280;
                cursor: pointer;
                transition: all 0.2s ease;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 12px;
            }
            
            .monitor-btn:hover {
                background: #e5e7eb;
                color: #374151;
            }
            
            .monitor-tabs {
                display: flex;
                border-bottom: 1px solid #e5e7eb;
                background: #f9fafb;
            }
            
            .tab-btn {
                padding: 8px 16px;
                border: none;
                background: none;
                color: #6b7280;
                font-size: 12px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s ease;
                display: flex;
                align-items: center;
                gap: 6px;
                border-bottom: 2px solid transparent;
            }
            
            .tab-btn:hover {
                color: #374151;
                background: #f3f4f6;
            }
            
            .tab-btn.active {
                color: #4f46e5;
                border-bottom-color: #4f46e5;
                background: white;
            }
            
            .monitor-content {
                flex: 1;
                overflow: hidden;
            }
            
            .tab-pane {
                display: none;
                height: 100%;
                overflow-y: auto;
            }
            
            .tab-pane.active {
                display: flex;
                flex-direction: column;
            }
            
            .execution-status {
                padding: 16px 20px;
                border-bottom: 1px solid #e5e7eb;
                background: #f9fafb;
            }
            
            .status-indicator {
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 13px;
                font-weight: 500;
            }
            
            .status-indicator.idle {
                color: #6b7280;
            }
            
            .status-indicator.running {
                color: #3b82f6;
            }
            
            .status-indicator.success {
                color: #10b981;
            }
            
            .status-indicator.failed {
                color: #ef4444;
            }
            
            .status-dot {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background: currentColor;
            }
            
            .status-indicator.running .status-dot {
                animation: pulse 1.5s infinite;
            }
            
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
            
            .execution-flow {
                flex: 1;
                padding: 20px;
                display: flex;
                flex-direction: column;
                min-height: 200px;
            }
            
            .flow-placeholder {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100%;
                color: #6b7280;
                text-align: center;
            }
            
            .flow-placeholder i {
                font-size: 48px;
                margin-bottom: 16px;
                opacity: 0.5;
            }
            
            .flow-placeholder h3 {
                margin: 0 0 8px 0;
                font-size: 18px;
                font-weight: 600;
            }
            
            .flow-placeholder p {
                margin: 0;
                font-size: 14px;
                opacity: 0.8;
            }
            
            .execution-steps {
                display: flex;
                flex-direction: column;
                gap: 8px;
            }
            
            .execution-step {
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 12px;
                border-radius: 8px;
                background: #f9fafb;
                border-left: 3px solid #e5e7eb;
                transition: all 0.3s ease;
            }
            
            .execution-step.active {
                background: #eff6ff;
                border-left-color: #3b82f6;
            }
            
            .execution-step.success {
                background: #ecfdf5;
                border-left-color: #10b981;
            }
            
            .execution-step.failed {
                background: #fef2f2;
                border-left-color: #ef4444;
            }
            
            .step-icon {
                width: 24px;
                height: 24px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 10px;
                background: #e5e7eb;
                color: #6b7280;
            }
            
            .execution-step.active .step-icon {
                background: #3b82f6;
                color: white;
                animation: spin 1s linear infinite;
            }
            
            .execution-step.success .step-icon {
                background: #10b981;
                color: white;
            }
            
            .execution-step.failed .step-icon {
                background: #ef4444;
                color: white;
            }
            
            @keyframes spin {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
            }
            
            .step-info {
                flex: 1;
            }
            
            .step-name {
                font-size: 13px;
                font-weight: 500;
                color: #1f2937;
                margin-bottom: 2px;
            }
            
            .step-details {
                font-size: 11px;
                color: #6b7280;
            }
            
            .step-duration {
                font-size: 11px;
                color: #6b7280;
                font-weight: 500;
            }
            
            .execution-data {
                border-top: 1px solid #e5e7eb;
                background: #f9fafb;
            }
            
            .data-viewer {
                height: 200px;
                display: flex;
                flex-direction: column;
            }
            
            .data-header {
                padding: 12px 20px;
                border-bottom: 1px solid #e5e7eb;
                display: flex;
                align-items: center;
                justify-content: space-between;
                background: white;
            }
            
            .data-header h4 {
                margin: 0;
                font-size: 13px;
                font-weight: 600;
                color: #1f2937;
            }
            
            .data-controls {
                display: flex;
                gap: 4px;
            }
            
            .data-btn {
                padding: 4px 8px;
                border: none;
                border-radius: 4px;
                background: #f3f4f6;
                color: #6b7280;
                font-size: 11px;
                cursor: pointer;
                transition: all 0.2s ease;
                display: flex;
                align-items: center;
                gap: 4px;
            }
            
            .data-btn:hover {
                background: #e5e7eb;
                color: #374151;
            }
            
            .data-content {
                flex: 1;
                padding: 16px 20px;
                font-family: 'Monaco', 'Menlo', monospace;
                font-size: 11px;
                overflow-y: auto;
                background: white;
            }
            
            .data-placeholder {
                display: flex;
                align-items: center;
                justify-content: center;
                height: 100%;
                color: #9ca3af;
                font-style: italic;
            }
            
            .history-controls {
                padding: 16px 20px;
                border-bottom: 1px solid #e5e7eb;
                background: #f9fafb;
                display: flex;
                align-items: center;
                gap: 16px;
            }
            
            .search-container {
                position: relative;
                flex: 1;
                max-width: 300px;
            }
            
            .search-container i {
                position: absolute;
                left: 8px;
                top: 50%;
                transform: translateY(-50%);
                color: #9ca3af;
                font-size: 12px;
            }
            
            .search-container input {
                width: 100%;
                padding: 6px 8px 6px 28px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                font-size: 12px;
                background: white;
            }
            
            .filter-controls {
                display: flex;
                gap: 8px;
            }
            
            .filter-controls select {
                padding: 6px 8px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                font-size: 12px;
                background: white;
            }
            
            .execution-history {
                flex: 1;
                overflow-y: auto;
                padding: 8px;
            }
            
            .history-item {
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 12px 16px;
                margin-bottom: 4px;
                border-radius: 6px;
                background: white;
                border: 1px solid #e5e7eb;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            
            .history-item:hover {
                border-color: #4f46e5;
                background: #f0f9ff;
            }
            
            .history-status {
                width: 8px;
                height: 8px;
                border-radius: 50%;
            }
            
            .history-status.success {
                background: #10b981;
            }
            
            .history-status.failed {
                background: #ef4444;
            }
            
            .history-status.cancelled {
                background: #6b7280;
            }
            
            .history-info {
                flex: 1;
            }
            
            .history-name {
                font-size: 13px;
                font-weight: 500;
                color: #1f2937;
                margin-bottom: 2px;
            }
            
            .history-details {
                font-size: 11px;
                color: #6b7280;
            }
            
            .history-time {
                font-size: 11px;
                color: #6b7280;
                text-align: right;
            }
            
            .logs-controls {
                padding: 16px 20px;
                border-bottom: 1px solid #e5e7eb;
                background: #f9fafb;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }
            
            .log-filters {
                display: flex;
                gap: 4px;
            }
            
            .log-filter {
                padding: 4px 12px;
                border: none;
                border-radius: 16px;
                font-size: 11px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s ease;
                background: #e5e7eb;
                color: #6b7280;
            }
            
            .log-filter:hover {
                background: #d1d5db;
            }
            
            .log-filter.active {
                background: #4f46e5;
                color: white;
            }
            
            .log-actions {
                display: flex;
                gap: 8px;
            }
            
            .log-btn {
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
                background: #f3f4f6;
                color: #6b7280;
                font-size: 11px;
                cursor: pointer;
                transition: all 0.2s ease;
                display: flex;
                align-items: center;
                gap: 4px;
            }
            
            .log-btn:hover {
                background: #e5e7eb;
                color: #374151;
            }
            
            .logs-container {
                flex: 1;
                overflow-y: auto;
                padding: 8px;
                font-family: 'Monaco', 'Menlo', monospace;
                font-size: 11px;
                background: #1f2937;
                color: #f9fafb;
            }
            
            .log-entry {
                padding: 4px 8px;
                margin-bottom: 2px;
                border-radius: 4px;
                display: flex;
                align-items: flex-start;
                gap: 8px;
            }
            
            .log-entry.info {
                background: rgba(59, 130, 246, 0.1);
                border-left: 2px solid #3b82f6;
            }
            
            .log-entry.warning {
                background: rgba(245, 158, 11, 0.1);
                border-left: 2px solid #f59e0b;
            }
            
            .log-entry.error {
                background: rgba(239, 68, 68, 0.1);
                border-left: 2px solid #ef4444;
            }
            
            .log-timestamp {
                color: #9ca3af;
                font-size: 10px;
                min-width: 80px;
            }
            
            .log-level {
                min-width: 50px;
                font-weight: 600;
                text-transform: uppercase;
            }
            
            .log-level.info { color: #3b82f6; }
            .log-level.warning { color: #f59e0b; }
            .log-level.error { color: #ef4444; }
            
            .log-message {
                flex: 1;
            }
            
            .performance-metrics {
                padding: 20px;
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 16px;
                border-bottom: 1px solid #e5e7eb;
            }
            
            .metric-card {
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 16px;
                display: flex;
                align-items: center;
                gap: 12px;
            }
            
            .metric-icon {
                width: 40px;
                height: 40px;
                border-radius: 8px;
                background: #f0f9ff;
                color: #3b82f6;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 16px;
            }
            
            .metric-info h4 {
                margin: 0 0 4px 0;
                font-size: 12px;
                font-weight: 500;
                color: #6b7280;
            }
            
            .metric-value {
                font-size: 18px;
                font-weight: 700;
                color: #1f2937;
            }
            
            .performance-charts {
                padding: 20px;
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
            }
            
            .chart-container {
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 16px;
            }
            
            .chart-container h4 {
                margin: 0 0 16px 0;
                font-size: 14px;
                font-weight: 600;
                color: #1f2937;
            }
        `;
        document.head.appendChild(style);
    }
    
    setupEventListeners() {
        // Tab switching
        this.panel.addEventListener('click', (e) => {
            if (e.target.classList.contains('tab-btn')) {
                this.switchTab(e.target.dataset.tab);
            }
        });
        
        // Log level filtering
        this.panel.addEventListener('click', (e) => {
            if (e.target.classList.contains('log-filter')) {
                this.filterLogs(e.target.dataset.level);
            }
        });
        
        // History search
        const historySearch = this.panel.querySelector('#history-search');
        if (historySearch) {
            historySearch.addEventListener('input', (e) => {
                this.filterHistory(e.target.value);
            });
        }
    }
    
    connectWebSocket() {
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws/executions/`;
            
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                console.log('Execution monitor WebSocket connected');
                this.reconnectAttempts = 0;
            };
            
            this.websocket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            };
            
            this.websocket.onclose = () => {
                console.log('Execution monitor WebSocket disconnected');
                this.attemptReconnect();
            };
            
            this.websocket.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
        } catch (error) {
            console.error('Failed to connect WebSocket:', error);
        }
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            setTimeout(() => {
                console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
                this.connectWebSocket();
            }, 2000 * this.reconnectAttempts);
        }
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'execution_started':
                this.onExecutionStarted(data.execution);
                break;
            case 'execution_progress':
                this.onExecutionProgress(data.execution, data.step);
                break;
            case 'execution_completed':
                this.onExecutionCompleted(data.execution);
                break;
            case 'execution_failed':
                this.onExecutionFailed(data.execution, data.error);
                break;
            case 'node_data':
                this.onNodeData(data.nodeId, data.data);
                break;
            case 'log_entry':
                this.onLogEntry(data.log);
                break;
        }
    }
    
    showPanel() {
        this.isVisible = true;
        this.panel.classList.add('visible');
    }
    
    hidePanel() {
        this.isVisible = false;
        this.panel.classList.remove('visible');
    }
    
    togglePanel() {
        if (this.isVisible) {
            this.hidePanel();
        } else {
            this.showPanel();
        }
    }
    
    switchTab(tabName) {
        // Update tab buttons
        this.panel.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        this.panel.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
        
        // Update tab panes
        this.panel.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.remove('active');
        });
        this.panel.querySelector(`#${tabName}-tab`).classList.add('active');
        
        // Load tab-specific data
        switch (tabName) {
            case 'history':
                this.loadExecutionHistory();
                break;
            case 'logs':
                this.loadLogs();
                break;
            case 'performance':
                this.loadPerformanceData();
                break;
        }
    }
    
    onExecutionStarted(execution) {
        this.activeExecution = execution;
        
        // Update status
        const statusElement = this.panel.querySelector('#execution-status');
        statusElement.innerHTML = `
            <div class="status-indicator running">
                <div class="status-dot"></div>
                <span>Executing: ${execution.workflow_name}</span>
            </div>
        `;
        
        // Clear previous execution flow
        const flowElement = this.panel.querySelector('#execution-flow');
        flowElement.innerHTML = '<div class="execution-steps" id="execution-steps"></div>';
        
        // Show panel if not visible
        if (!this.isVisible) {
            this.showPanel();
        }
        
        // Add to history
        this.addToHistory(execution);
        
        // Log entry
        this.addLogEntry('info', `Execution started: ${execution.workflow_name}`);
    }
    
    onExecutionProgress(execution, step) {
        const stepsContainer = this.panel.querySelector('#execution-steps');
        if (!stepsContainer) return;
        
        // Find or create step element
        let stepElement = stepsContainer.querySelector(`[data-step-id="${step.id}"]`);
        if (!stepElement) {
            stepElement = document.createElement('div');
            stepElement.className = 'execution-step';
            stepElement.dataset.stepId = step.id;
            stepElement.innerHTML = `
                <div class="step-icon">
                    <i class="fas fa-circle"></i>
                </div>
                <div class="step-info">
                    <div class="step-name">${step.name}</div>
                    <div class="step-details">${step.type}</div>
                </div>
                <div class="step-duration">--</div>
            `;
            stepsContainer.appendChild(stepElement);
        }
        
        // Update step status
        stepElement.className = `execution-step ${step.status}`;
        
        const icon = stepElement.querySelector('.step-icon i');
        const duration = stepElement.querySelector('.step-duration');
        
        switch (step.status) {
            case 'running':
                icon.className = 'fas fa-spinner';
                duration.textContent = 'Running...';
                break;
            case 'success':
                icon.className = 'fas fa-check';
                duration.textContent = `${step.duration}ms`;
                break;
            case 'failed':
                icon.className = 'fas fa-times';
                duration.textContent = 'Failed';
                break;
        }
        
        // Auto-scroll to active step
        stepElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        
        // Log entry
        this.addLogEntry('info', `Step ${step.status}: ${step.name}`);
    }
    
    onExecutionCompleted(execution) {
        this.activeExecution = null;
        
        // Update status
        const statusElement = this.panel.querySelector('#execution-status');
        statusElement.innerHTML = `
            <div class="status-indicator success">
                <div class="status-dot"></div>
                <span>Completed: ${execution.workflow_name} (${execution.duration}ms)</span>
            </div>
        `;
        
        // Update performance metrics
        this.updatePerformanceMetrics(execution);
        
        // Log entry
        this.addLogEntry('info', `Execution completed: ${execution.workflow_name} in ${execution.duration}ms`);
        
        // Show success notification
        if (window.notificationManager) {
            window.notificationManager.success(
                `Workflow "${execution.workflow_name}" completed successfully!`,
                { duration: 4000 }
            );
        }
    }
    
    onExecutionFailed(execution, error) {
        this.activeExecution = null;
        
        // Update status
        const statusElement = this.panel.querySelector('#execution-status');
        statusElement.innerHTML = `
            <div class="status-indicator failed">
                <div class="status-dot"></div>
                <span>Failed: ${execution.workflow_name}</span>
            </div>
        `;
        
        // Log error
        this.addLogEntry('error', `Execution failed: ${error.message}`);
        
        // Show error notification
        if (window.notificationManager) {
            window.notificationManager.error(
                `Workflow "${execution.workflow_name}" failed: ${error.message}`,
                { duration: 6000 }
            );
        }
    }
    
    onNodeData(nodeId, data) {
        // Update data viewer if this node is selected
        const dataContent = this.panel.querySelector('#data-content');
        if (dataContent && this.selectedNodeId === nodeId) {
            dataContent.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
        }
    }
    
    onLogEntry(log) {
        this.addLogEntry(log.level, log.message, log.timestamp);
    }
    
    addLogEntry(level, message, timestamp = null) {
        const logsContainer = this.panel.querySelector('#logs-container');
        if (!logsContainer) return;
        
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry ${level}`;
        
        const time = timestamp ? new Date(timestamp) : new Date();
        const timeStr = time.toLocaleTimeString();
        
        logEntry.innerHTML = `
            <div class="log-timestamp">${timeStr}</div>
            <div class="log-level ${level}">${level}</div>
            <div class="log-message">${message}</div>
        `;
        
        logsContainer.appendChild(logEntry);
        
        // Auto-scroll to bottom
        logsContainer.scrollTop = logsContainer.scrollHeight;
        
        // Limit log entries to prevent memory issues
        const entries = logsContainer.querySelectorAll('.log-entry');
        if (entries.length > 1000) {
            entries[0].remove();
        }
    }
    
    addToHistory(execution) {
        const historyContainer = this.panel.querySelector('#execution-history');
        if (!historyContainer) return;
        
        const historyItem = document.createElement('div');
        historyItem.className = 'history-item';
        historyItem.innerHTML = `
            <div class="history-status ${execution.status}"></div>
            <div class="history-info">
                <div class="history-name">${execution.workflow_name}</div>
                <div class="history-details">ID: ${execution.id} • ${execution.nodes_count} nodes</div>
            </div>
            <div class="history-time">
                <div>${new Date(execution.started_at).toLocaleTimeString()}</div>
                <div>${execution.duration ? execution.duration + 'ms' : 'Running...'}</div>
            </div>
        `;
        
        historyItem.addEventListener('click', () => {
            this.loadExecutionDetails(execution.id);
        });
        
        // Insert at the beginning
        historyContainer.insertBefore(historyItem, historyContainer.firstChild);
    }
    
    loadExecutionHistory() {
        // Mock history data - replace with actual API call
        const history = [
            {
                id: 1,
                workflow_name: 'AI Content Generator',
                status: 'success',
                started_at: new Date(Date.now() - 3600000).toISOString(),
                duration: 2340,
                nodes_count: 5
            },
            {
                id: 2,
                workflow_name: 'Email Campaign',
                status: 'failed',
                started_at: new Date(Date.now() - 7200000).toISOString(),
                duration: null,
                nodes_count: 8
            }
        ];
        
        const historyContainer = this.panel.querySelector('#execution-history');
        historyContainer.innerHTML = '';
        
        history.forEach(execution => {
            this.addToHistory(execution);
        });
    }
    
    loadLogs() {
        // Mock log data - replace with actual API call
        const logs = [
            { level: 'info', message: 'Workflow execution started', timestamp: new Date() },
            { level: 'info', message: 'Node "HTTP Request" completed successfully', timestamp: new Date() },
            { level: 'warning', message: 'Rate limit approaching for API calls', timestamp: new Date() },
            { level: 'error', message: 'Authentication failed for Gmail node', timestamp: new Date() }
        ];
        
        const logsContainer = this.panel.querySelector('#logs-container');
        logsContainer.innerHTML = '';
        
        logs.forEach(log => {
            this.addLogEntry(log.level, log.message, log.timestamp);
        });
    }
    
    loadPerformanceData() {
        // Update performance metrics
        this.panel.querySelector('#execution-time').textContent = '2.34s';
        this.panel.querySelector('#memory-usage').textContent = '45MB';
        this.panel.querySelector('#api-calls').textContent = '12';
        this.panel.querySelector('#data-processed').textContent = '1.2MB';
        
        // Draw charts (simplified - use Chart.js or similar in production)
        this.drawPerformanceCharts();
    }
    
    drawPerformanceCharts() {
        const timelineCanvas = this.panel.querySelector('#timeline-chart');
        const performanceCanvas = this.panel.querySelector('#performance-chart');
        
        if (timelineCanvas && performanceCanvas) {
            // Simple canvas drawing - replace with proper charting library
            const timelineCtx = timelineCanvas.getContext('2d');
            const performanceCtx = performanceCanvas.getContext('2d');
            
            // Clear canvases
            timelineCtx.clearRect(0, 0, timelineCanvas.width, timelineCanvas.height);
            performanceCtx.clearRect(0, 0, performanceCanvas.width, performanceCanvas.height);
            
            // Draw simple placeholder charts
            timelineCtx.fillStyle = '#4f46e5';
            timelineCtx.fillRect(50, 50, 300, 100);
            timelineCtx.fillStyle = 'white';
            timelineCtx.font = '14px Arial';
            timelineCtx.fillText('Timeline Chart', 150, 105);
            
            performanceCtx.fillStyle = '#10b981';
            performanceCtx.fillRect(50, 50, 300, 100);
            performanceCtx.fillStyle = 'white';
            performanceCtx.font = '14px Arial';
            performanceCtx.fillText('Performance Chart', 140, 105);
        }
    }
    
    updatePerformanceMetrics(execution) {
        this.panel.querySelector('#execution-time').textContent = `${execution.duration}ms`;
        this.panel.querySelector('#memory-usage').textContent = `${execution.memory_usage || 0}MB`;
        this.panel.querySelector('#api-calls').textContent = execution.api_calls || 0;
        this.panel.querySelector('#data-processed').textContent = `${execution.data_processed || 0}KB`;
    }
    
    filterLogs(level) {
        // Update active filter
        this.panel.querySelectorAll('.log-filter').forEach(btn => {
            btn.classList.remove('active');
        });
        this.panel.querySelector(`[data-level="${level}"]`).classList.add('active');
        
        // Filter log entries
        const logEntries = this.panel.querySelectorAll('.log-entry');
        logEntries.forEach(entry => {
            if (level === 'all' || entry.classList.contains(level)) {
                entry.style.display = 'flex';
            } else {
                entry.style.display = 'none';
            }
        });
    }
    
    filterHistory(searchTerm) {
        const historyItems = this.panel.querySelectorAll('.history-item');
        historyItems.forEach(item => {
            const name = item.querySelector('.history-name').textContent.toLowerCase();
            if (name.includes(searchTerm.toLowerCase())) {
                item.style.display = 'flex';
            } else {
                item.style.display = 'none';
            }
        });
    }
    
    // Panel action methods
    toggleAutoScroll() {
        // Toggle auto-scroll functionality
        console.log('Toggle auto-scroll');
    }
    
    clearHistory() {
        if (window.notificationManager) {
            window.notificationManager.confirm(
                'Clear all execution history?',
                'Clear History'
            ).then(confirmed => {
                if (confirmed) {
                    this.panel.querySelector('#execution-history').innerHTML = '';
                }
            });
        }
    }
    
    clearLogs() {
        this.panel.querySelector('#logs-container').innerHTML = '';
    }
    
    downloadLogs() {
        const logs = Array.from(this.panel.querySelectorAll('.log-entry')).map(entry => {
            const timestamp = entry.querySelector('.log-timestamp').textContent;
            const level = entry.querySelector('.log-level').textContent;
            const message = entry.querySelector('.log-message').textContent;
            return `${timestamp} [${level}] ${message}`;
        }).join('\n');
        
        const blob = new Blob([logs], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `workflow-logs-${new Date().toISOString().split('T')[0]}.txt`;
        a.click();
        URL.revokeObjectURL(url);
    }
    
    formatJson() {
        const dataContent = this.panel.querySelector('#data-content');
        if (dataContent && dataContent.textContent) {
            try {
                const data = JSON.parse(dataContent.textContent);
                dataContent.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
            } catch (e) {
                console.error('Invalid JSON:', e);
            }
        }
    }
    
    copyData() {
        const dataContent = this.panel.querySelector('#data-content');
        if (dataContent && dataContent.textContent) {
            navigator.clipboard.writeText(dataContent.textContent).then(() => {
                if (window.notificationManager) {
                    window.notificationManager.success('Data copied to clipboard');
                }
            });
        }
    }
    
    loadExecutionDetails(executionId) {
        console.log('Loading execution details:', executionId);
        // Implement execution details loading
    }
    
    selectNode(nodeId) {
        this.selectedNodeId = nodeId;
        // Load node data if available
    }
}

// Create global instance
window.executionMonitor = new ExecutionMonitor();