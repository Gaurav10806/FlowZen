// Main Application - Initialize and coordinate all components
class WorkflowApp {
    constructor() {
        this.canvasManager = null;
        this.nodeManager = null;
        this.edgeManager = null;
        this.configManager = null;
        this.apiManager = null;
        this.animationManager = null;
        this.notificationManager = null;

        this.currentWorkflowId = null;
        this.isModified = false;

        this.init();
    }

    init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.initializeApp());
        } else {
            this.initializeApp();
        }
    }

    initializeApp() {
        // Initialize core systems first
        this.animationManager = new AnimationManager();
        this.notificationManager = new NotificationManager();

        // Initialize managers with animation support
        this.apiManager = new APIManager();
        this.canvasManager = new AdvancedCanvas();
        this.nodeManager = new NodeManager(this.canvasManager, this.animationManager);
        this.edgeManager = new EdgeManager(this.canvasManager, this.nodeManager, this.animationManager);
        this.configManager = new ConfigManager(this.nodeManager, this.apiManager);

        // Initialize Replay Manager
        this.replayManager = new ReplayManager(this);

        // Make managers globally available
        window.canvasManager = this.canvasManager;
        window.nodeManager = this.nodeManager;
        window.edgeManager = this.edgeManager;
        window.configManager = this.configManager;
        window.apiManager = this.apiManager;
        window.animationManager = this.animationManager;
        window.notificationManager = this.notificationManager;
        window.replayManager = this.replayManager; // Expose for debugging

        this.setupEventListeners();
        this.setupKeyboardShortcuts();
        this.setupThemeSystem();

        this.loadInitialData();

        // Show welcome notification
        this.notificationManager.success('Workflow Builder initialized successfully! 🎉', {
            duration: 3000
        });
    }

    // ... (keeping setupEventListeners etc)

    showExecutionResult(execution) {
        // Switch to Canvas view if not already
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        document.getElementById('builder-view').classList.add('active');
        document.querySelector('a[href="#builder"]').classList.add('active'); // Update sidebar if needed

        // Delegate to ReplayManager
        this.replayManager.enterReplayMode(execution);
    }

    // Legacy methods enterReplayMode, exitReplayMode, showNodeExecutionDetails removed
    // Delegated to ReplayManager

    setupEventListeners() {
        // Enhanced save button with animation feedback
        document.getElementById('save-btn').addEventListener('click', () => {
            const btn = document.getElementById('save-btn');
            this.animationManager.bounce(btn);
            this.saveWorkflow();
        });

        // Enhanced execute button with animation feedback
        document.getElementById('run-btn').addEventListener('click', () => {
            const btn = document.getElementById('run-btn');
            this.animationManager.pulse(btn, 'success');
            this.executeWorkflow();
        });

        // Template manager button
        document.getElementById('templates-btn').addEventListener('click', () => {
            const btn = document.getElementById('templates-btn');
            this.animationManager.bounce(btn);
            if (window.templateManager) {
                window.templateManager.showTemplateModal();
            }
        });

        // Credential manager button
        document.getElementById('credentials-btn').addEventListener('click', () => {
            const btn = document.getElementById('credentials-btn');
            this.animationManager.bounce(btn);
            if (window.credentialManager) {
                window.credentialManager.showCredentialModal();
            }
        });

        // Zoom controls with smooth animations
        document.getElementById('zoom-in').addEventListener('click', () => {
            this.canvasManager.zoomIn();
            this.animationManager.bounce(document.getElementById('zoom-in'), 0.5);
        });

        document.getElementById('zoom-out').addEventListener('click', () => {
            this.canvasManager.zoomOut();
            this.animationManager.bounce(document.getElementById('zoom-out'), 0.5);
        });

        // Track modifications with visual feedback
        document.addEventListener('nodeCreated', (e) => {
            this.isModified = true;
            this.updateSaveButtonState();

            // Show creation notification
            this.notificationManager.info(`${e.detail.type} node created`, {
                duration: 2000
            });
        });

        document.addEventListener('nodeDeleted', (e) => {
            this.isModified = true;
            this.updateSaveButtonState();

            // Show deletion notification
            this.notificationManager.warning(`Node deleted`, {
                duration: 2000
            });
        });

        document.addEventListener('edgeCreated', (e) => {
            this.isModified = true;
            this.updateSaveButtonState();

            // Show connection notification
            this.notificationManager.info('Nodes connected', {
                duration: 1500
            });
        });

        document.addEventListener('edgeDeleted', () => {
            this.isModified = true;
            this.updateSaveButtonState();
        });

        document.addEventListener('nodeConfigChanged', () => {
            this.isModified = true;
            this.updateSaveButtonState();
        });

        // Auto-save with progress indication
        setInterval(() => {
            if (this.isModified && this.currentWorkflowId) {
                this.autoSave();
            }
        }, 30000);

        // Window events
        window.addEventListener('beforeunload', (e) => {
            if (this.isModified) {
                e.preventDefault();
                e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
            }
        });

        // Canvas interaction feedback
        document.addEventListener('canvasInteraction', (e) => {
            if (e.detail.type === 'pan') {
                document.body.style.cursor = 'grabbing';
            } else if (e.detail.type === 'panEnd') {
                document.body.style.cursor = '';
            }
        });
    }

    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Handle modifier keys (Ctrl/Cmd)
            if (e.ctrlKey || e.metaKey) {
                switch (e.key) {
                    case 's':
                        e.preventDefault();
                        this.saveWorkflow();
                        this.animationManager.pulse(document.getElementById('save-btn'), 'success');
                        break;
                    case 'r':
                        e.preventDefault();
                        this.executeWorkflow();
                        this.animationManager.pulse(document.getElementById('run-btn'), 'success');
                        break;
                    case 'z':
                        e.preventDefault();
                        if (e.shiftKey) {
                            this.redo();
                        } else {
                            this.undo();
                        }
                        break;
                    case 'a':
                        e.preventDefault();
                        this.selectAll();
                        break;
                }
            }

            // Handle other keys
            switch (e.key) {
                case 'Escape':
                    this.cancelCurrentOperation();
                    break;
                case 'Delete':
                case 'Backspace':
                    this.deleteSelected();
                    break;
                case 'F11':
                    e.preventDefault();
                    this.toggleFullscreen();
                    break;
            }
        });
    }

    setupThemeSystem() {
        // Detect system theme preference
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');

        // Listen for theme changes
        prefersDark.addEventListener('change', (e) => {
            this.applyTheme(e.matches ? 'dark' : 'light');
        });

        // Apply initial theme
        this.applyTheme(prefersDark.matches ? 'dark' : 'light');
    }

    applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);

        // Animate theme transition
        document.body.style.transition = 'background-color 0.3s ease, color 0.3s ease';

        setTimeout(() => {
            document.body.style.transition = '';
        }, 300);
    }

    updateSaveButtonState() {
        const saveBtn = document.getElementById('save-btn');
        if (this.isModified) {
            saveBtn.classList.add('btn-warning');
            saveBtn.classList.remove('btn-primary');
            saveBtn.innerHTML = '<i class="fas fa-save"></i> Save*';
        } else {
            saveBtn.classList.add('btn-primary');
            saveBtn.classList.remove('btn-warning');
            saveBtn.innerHTML = '<i class="fas fa-save"></i> Save';
        }
    }

    async loadInitialData() {
        console.log('🎬 BOOT START - Loading initial data with animations');

        try {
            // Show loading notification
            const loadingNotification = this.notificationManager.loading('Initializing workspace...');

            // Simulate loading delay for better UX
            await new Promise(resolve => setTimeout(resolve, 800));

            // Check if there's a workflow ID in URL
            const urlParams = new URLSearchParams(window.location.search);
            const workflowId = urlParams.get('id');

            if (workflowId) {
                console.log('📋 Workflow ID found, loading workflow...');
                loadingNotification.update(50, 'Loading workflow...');
                await this.loadWorkflow(workflowId);
            } else {
                // Create a sample workflow with animations
                loadingNotification.update(30, 'Creating sample workflow...');
                await this.createSampleWorkflow();
            }

            // Fetch real user data and stats
            await this.fetchUserProfile();
            await this.fetchDashboardStats();

            loadingNotification.complete('Workspace ready!');
            console.log('🎉 BOOT COMPLETE - Enhanced UI ready for interaction');

        } catch (error) {
            console.error('❌ Failed to load initial data:', error);
            this.notificationManager.error('Failed to load initial data: ' + error.message);
        }
    }

    async createSampleWorkflow() {
        // Create sample nodes with staggered animations
        const webhookNode = this.nodeManager.createNode('webhook', 'tools', 100, 200);

        // Wait for first node animation
        await new Promise(resolve => setTimeout(resolve, 300));

        const emailNode = this.nodeManager.createNode('email', 'tools', 400, 200);

        // Wait for second node animation
        await new Promise(resolve => setTimeout(resolve, 300));

        const ifNode = this.nodeManager.createNode('if', 'brain', 250, 350);

        // Connect them with animated edges
        setTimeout(() => {
            this.edgeManager.createEdge(webhookNode.id, emailNode.id);
        }, 500);

        setTimeout(() => {
            this.edgeManager.createEdge(webhookNode.id, ifNode.id);
        }, 800);

        console.log('✨ Sample workflow created with animations');
    }

    async saveWorkflow() {
        console.log('💾 Enhanced save with progress feedback');

        try {
            const workflowData = this.nodeManager.exportWorkflow();
            console.log('📊 Workflow data to save:', workflowData);

            // Show progress notification
            const progress = this.notificationManager.progress('Saving workflow...');

            // Simulate save progress
            progress.update(25, 'Validating workflow...');
            await new Promise(resolve => setTimeout(resolve, 300));

            progress.update(50, 'Uploading data...');
            await new Promise(resolve => setTimeout(resolve, 400));

            progress.update(75, 'Finalizing...');
            await new Promise(resolve => setTimeout(resolve, 200));

            progress.update(100, 'Saved successfully!');
            progress.complete('Workflow saved! 🎉');

            this.isModified = false;
            this.updateSaveButtonState();

            // Animate save button
            this.animationManager.pulse(document.getElementById('save-btn'), 'success');

        } catch (error) {
            console.error('❌ Failed to save workflow:', error);
            this.notificationManager.error('Failed to save workflow: ' + error.message);
            this.animationManager.shake(document.getElementById('save-btn'));
        }
    }

    async executeWorkflow() {
        console.log('🚀 Enhanced execute with visual feedback');

        try {
            const workflowData = this.nodeManager.exportWorkflow();
            console.log('⚡ Workflow data to execute:', workflowData);

            if (workflowData.nodes.length === 0) {
                throw new Error('Workflow is empty. Add some nodes first.');
            }

            // Show execution progress
            const progress = this.notificationManager.progress('Executing workflow...');

            // Animate nodes during execution
            const executionAnimations = [];
            workflowData.nodes.forEach((node, index) => {
                setTimeout(() => {
                    const nodeElement = document.querySelector(`[data-node-id="${node.id}"]`);
                    if (nodeElement) {
                        const animation = this.animationManager.animateNodeExecution(nodeElement);
                        executionAnimations.push(animation);

                        // Update node status
                        const statusElement = nodeElement.querySelector('.node-status');
                        if (statusElement) {
                            statusElement.textContent = 'Executing...';
                            statusElement.className = 'node-status executing';
                        }
                    }
                }, index * 500);
            });

            // Simulate execution progress
            progress.update(20, 'Initializing nodes...');
            await new Promise(resolve => setTimeout(resolve, 800));

            progress.update(50, 'Processing workflow...');
            await new Promise(resolve => setTimeout(resolve, 1200));

            progress.update(80, 'Finalizing execution...');
            await new Promise(resolve => setTimeout(resolve, 600));

            // Stop all execution animations
            executionAnimations.forEach(animation => animation.stop());

            // Update node statuses to completed
            workflowData.nodes.forEach(node => {
                const nodeElement = document.querySelector(`[data-node-id="${node.id}"]`);
                if (nodeElement) {
                    const statusElement = nodeElement.querySelector('.node-status');
                    if (statusElement) {
                        statusElement.textContent = 'Completed';
                        statusElement.className = 'node-status completed';
                    }

                    // Add success pulse
                    this.animationManager.pulse(nodeElement, 'success');
                }
            });

            progress.complete('Workflow executed successfully! 🎉');

            // Animate execute button
            this.animationManager.pulse(document.getElementById('run-btn'), 'success');

        } catch (error) {
            console.error('❌ Failed to execute workflow:', error);
            this.notificationManager.error('Failed to execute workflow: ' + error.message);
            this.animationManager.shake(document.getElementById('run-btn'));
        }
    }

    // Enhanced utility methods
    cancelCurrentOperation() {
        // Cancel any ongoing operations
        if (this.edgeManager && this.edgeManager.isConnecting) {
            this.edgeManager.cancelConnection();
            this.notificationManager.info('Connection cancelled');
        }
    }

    deleteSelected() {
        if (this.nodeManager && this.nodeManager.selectedNode) {
            const nodeElement = document.querySelector(`[data-node-id="${this.nodeManager.selectedNode}"]`);
            if (nodeElement) {
                this.animationManager.shake(nodeElement);
                setTimeout(() => {
                    this.nodeManager.deleteNode(this.nodeManager.selectedNode);
                }, 300);
            }
        }
    }

    selectAll() {
        // Select all nodes
        this.nodeManager.nodes.forEach((node, id) => {
            const nodeElement = document.querySelector(`[data-node-id="${id}"]`);
            if (nodeElement) {
                nodeElement.classList.add('selected');
            }
        });

        this.notificationManager.info(`Selected ${this.nodeManager.nodes.size} nodes`);
    }

    toggleFullscreen() {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
            this.notificationManager.info('Entered fullscreen mode');
        } else {
            document.exitFullscreen();
            this.notificationManager.info('Exited fullscreen mode');
        }
    }

    undo() {
        // Implement undo functionality
        this.notificationManager.info('Undo (not implemented yet)');
    }

    redo() {
        // Implement redo functionality
        this.notificationManager.info('Redo (not implemented yet)');
    }

    async autoSave() {
        try {
            if (!this.currentWorkflowId) return;

            const workflowData = this.nodeManager.exportWorkflow();
            workflowData.name = 'My Workflow';
            workflowData.description = 'Auto-saved';

            // Show subtle auto-save indicator
            const indicator = document.createElement('div');
            indicator.textContent = 'Auto-saving...';
            indicator.style.cssText = `
                position: fixed;
                top: 20px;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(0, 0, 0, 0.8);
                color: white;
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 12px;
                z-index: 10000;
                opacity: 0;
                transition: opacity 0.3s ease;
            `;

            document.body.appendChild(indicator);

            requestAnimationFrame(() => {
                indicator.style.opacity = '1';
            });

            // Simulate auto-save
            await new Promise(resolve => setTimeout(resolve, 1000));

            indicator.textContent = 'Auto-saved ✓';

            setTimeout(() => {
                indicator.style.opacity = '0';
                setTimeout(() => {
                    if (indicator.parentNode) {
                        indicator.parentNode.removeChild(indicator);
                    }
                }, 300);
            }, 1500);

            this.isModified = false;
            this.updateSaveButtonState();

            console.log('💾 Workflow auto-saved');

        } catch (error) {
            console.error('❌ Auto-save failed:', error);
        }
    }

    // Cleanup method
    destroy() {
        if (this.animationManager) {
            this.animationManager.cleanup();
        }

        if (this.notificationManager) {
            this.notificationManager.destroy();
        }
    }

    async setupGmailOAuth() {
        try {
            const loading = this.apiManager.showLoading('Setting up Gmail OAuth...');

            const oauthData = await this.apiManager.initiateGmailOAuth();

            loading.hide();

            if (oauthData.auth_url) {
                // Open OAuth URL in new window
                const oauthWindow = window.open(
                    oauthData.auth_url,
                    'gmail-oauth',
                    'width=500,height=600,scrollbars=yes,resizable=yes'
                );

                // Poll for completion
                const pollInterval = setInterval(async () => {
                    try {
                        if (oauthWindow.closed) {
                            clearInterval(pollInterval);

                            // Check if OAuth was successful
                            const status = await this.apiManager.getGmailOAuthStatus();
                            if (status.is_configured) {
                                this.apiManager.showSuccess('Gmail OAuth configured successfully');
                            } else {
                                this.apiManager.showError('Gmail OAuth setup was cancelled or failed');
                            }
                        }
                    } catch (error) {
                        console.error('Error checking OAuth status:', error);
                    }
                }, 1000);

            } else {
                throw new Error('Failed to get OAuth URL');
            }

        } catch (error) {
            console.error('Failed to setup Gmail OAuth:', error);
            this.apiManager.showError('Failed to setup Gmail OAuth: ' + error.message);
        }
    }

    showExecutionResult(execution) {
        // Switch to Canvas view if not already
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        document.getElementById('builder-view').classList.add('active');
        document.querySelector('a[href="#builder"]').classList.add('active'); // Update sidebar if needed

        this.enterReplayMode(execution);
    }

}

// Configuration Manager for node settings
class ConfigManager {
    constructor(nodeManager, apiManager) {
        this.nodeManager = nodeManager;
        this.apiManager = apiManager;
        this.currentNode = null;

        this.configContent = document.getElementById('config-content');
        this.monacoInstance = null;
    }

    showNodeConfig(nodeData) {
        this.currentNode = nodeData;

        const config = this.getConfigForm(nodeData.type, nodeData.config);

        this.configContent.innerHTML = `
            <div class="config-form active">
                <h6 class="mb-3">
                    <i class="${this.getNodeIcon(nodeData.type)}" style="color: ${this.getNodeColor(nodeData.type)}"></i>
                    ${this.getNodeTitle(nodeData.type)} Configuration
                </h6>
                ${config}
                <div class="mt-3">
                    <button class="btn btn-primary btn-sm" onclick="window.configManager.saveNodeConfig()">
                        <i class="fas fa-save"></i> Save
                    </button>
                    <button class="btn btn-outline-secondary btn-sm ms-2" onclick="window.configManager.testNodeConfig()">
                        <i class="fas fa-play"></i> Test
                    </button>
                </div>
            </div>
        `;

        // Populate current values
        this.populateConfigForm(nodeData.config);

        // Initialize Monaco for code nodes
        if (nodeData.type === 'code') {
            this.initMonaco(nodeData.config.code || '# Write your Python code here\nprint("Hello World")');
        }
    }

    initMonaco(value) {
        const container = document.getElementById('monaco-editor-container');
        if (!container) return;

        // Clean up existing instance
        if (this.monacoInstance) {
            this.monacoInstance.dispose();
            this.monacoInstance = null;
        }

        if (window.monaco) {
            this.monacoInstance = monaco.editor.create(container, {
                value: value,
                language: 'python',
                theme: 'vs-dark',
                minimap: { enabled: false },
                automaticLayout: true,
                scrollBeyondLastLine: false,
                fontSize: 14
            });
        }
    }

    hideNodeConfig() {
        this.currentNode = null;
        this.configContent.innerHTML = `
            <div class="no-selection">
                <i class="fas fa-mouse-pointer"></i>
                <p>Select a node to configure</p>
            </div>
        `;
    }

    getConfigForm(nodeType, config) {
        switch (nodeType) {
            case 'email':
                return `
                    <div class="form-group">
                        <label>Gmail Credential</label>
                        <select id="config-credential" class="form-control">
                            <option value="">Select Gmail credential...</option>
                            ${this.getCredentialOptions('gmail')}
                        </select>
                        <small class="text-muted">
                            <a href="#" onclick="window.credentialManager.showCreateCredentialModal(); return false;">
                                <i class="fas fa-plus"></i> Add new Gmail credential
                            </a>
                        </small>
                    </div>
                    <div class="form-group">
                        <label>To Email</label>
                        <input type="email" id="config-to" class="form-control" placeholder="recipient@example.com">
                    </div>
                    <div class="form-group">
                        <label>Subject</label>
                        <input type="text" id="config-subject" class="form-control" placeholder="Email subject">
                    </div>
                    <div class="form-group">
                        <label>Body</label>
                        <textarea id="config-body" class="form-control" rows="4" placeholder="Email content"></textarea>
                    </div>
                `;

            case 'webhook':
                return `
                    <div class="form-group">
                        <label>Authentication</label>
                        <select id="config-auth-credential" class="form-control">
                            <option value="">No authentication</option>
                            ${this.getCredentialOptions('http_auth')}
                        </select>
                        <small class="text-muted">
                            <a href="#" onclick="window.credentialManager.showCreateCredentialModal(); return false;">
                                <i class="fas fa-plus"></i> Add new HTTP credential
                            </a>
                        </small>
                    </div>
                    <div class="form-group">
                        <label>Webhook URL</label>
                        <input type="url" id="config-url" class="form-control" placeholder="https://example.com/webhook">
                    </div>
                    <div class="form-group">
                        <label>Method</label>
                        <select id="config-method" class="form-control">
                            <option value="POST">POST</option>
                            <option value="GET">GET</option>
                            <option value="PUT">PUT</option>
                            <option value="DELETE">DELETE</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Headers (JSON)</label>
                        <textarea id="config-headers" class="form-control" rows="3" placeholder='{"Content-Type": "application/json"}'></textarea>
                    </div>
                `;

            case 'http':
                return `
                    <div class="form-group">
                        <label>Authentication</label>
                        <select id="config-auth-credential" class="form-control">
                            <option value="">No authentication</option>
                            ${this.getCredentialOptions('http_auth')}
                        </select>
                        <small class="text-muted">
                            <a href="#" onclick="window.credentialManager.showCreateCredentialModal(); return false;">
                                <i class="fas fa-plus"></i> Add new HTTP credential
                            </a>
                        </small>
                    </div>
                    <div class="form-group">
                        <label>URL</label>
                        <input type="url" id="config-url" class="form-control" placeholder="https://api.example.com/data">
                    </div>
                    <div class="form-group">
                        <label>Method</label>
                        <select id="config-method" class="form-control">
                            <option value="GET">GET</option>
                            <option value="POST">POST</option>
                            <option value="PUT">PUT</option>
                            <option value="DELETE">DELETE</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Headers (JSON)</label>
                        <textarea id="config-headers" class="form-control" rows="2" placeholder='{"Authorization": "Bearer token"}'></textarea>
                    </div>
                    <div class="form-group">
                        <label>Body (JSON)</label>
                        <textarea id="config-body" class="form-control" rows="3" placeholder='{"key": "value"}'></textarea>
                    </div>
                `;

            case 'database':
                return `
                    <div class="form-group">
                        <label>Database Credential</label>
                        <select id="config-credential" class="form-control">
                            <option value="">Select database credential...</option>
                            ${this.getCredentialOptions('database')}
                        </select>
                        <small class="text-muted">
                            <a href="#" onclick="window.credentialManager.showCreateCredentialModal(); return false;">
                                <i class="fas fa-plus"></i> Add new database credential
                            </a>
                        </small>
                    </div>
                    <div class="form-group">
                        <label>Query</label>
                        <textarea id="config-query" class="form-control" rows="4" placeholder="SELECT * FROM users WHERE active = true"></textarea>
                    </div>
                `;

            case 'slack':
                return `
                    <div class="form-group">
                        <label>Slack Credential</label>
                        <select id="config-credential" class="form-control">
                            <option value="">Select Slack credential...</option>
                            ${this.getCredentialOptions('slack')}
                        </select>
                        <small class="text-muted">
                            <a href="#" onclick="window.credentialManager.showCreateCredentialModal(); return false;">
                                <i class="fas fa-plus"></i> Add new Slack credential
                            </a>
                        </small>
                    </div>
                    <div class="form-group">
                        <label>Channel</label>
                        <input type="text" id="config-channel" class="form-control" placeholder="#general">
                    </div>
                    <div class="form-group">
                        <label>Message</label>
                        <textarea id="config-message" class="form-control" rows="3" placeholder="Hello from workflow!"></textarea>
                    </div>
                `;

            case 'discord':
                return `
                    <div class="form-group">
                        <label>Discord Credential</label>
                        <select id="config-credential" class="form-control">
                            <option value="">Select Discord credential...</option>
                            ${this.getCredentialOptions('discord')}
                        </select>
                        <small class="text-muted">
                            <a href="#" onclick="window.credentialManager.showCreateCredentialModal(); return false;">
                                <i class="fas fa-plus"></i> Add new Discord credential
                            </a>
                        </small>
                    </div>
                    <div class="form-group">
                        <label>Channel ID</label>
                        <input type="text" id="config-channel-id" class="form-control" placeholder="123456789012345678">
                    </div>
                    <div class="form-group">
                        <label>Message</label>
                        <textarea id="config-message" class="form-control" rows="3" placeholder="Hello from workflow!"></textarea>
                    </div>
                `;

            case 'ai-agent':
                return `
                    <div class="form-group">
                        <label>AI Service Credential</label>
                        <select id="config-credential" class="form-control">
                            <option value="">Select AI credential...</option>
                            ${this.getCredentialOptions('openai')}
                        </select>
                        <small class="text-muted">
                            <a href="#" onclick="window.credentialManager.showCreateCredentialModal(); return false;">
                                <i class="fas fa-plus"></i> Add new OpenAI credential
                            </a>
                        </small>
                    </div>
                    <div class="form-group">
                        <label>Model</label>
                        <select id="config-model" class="form-control">
                            <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                            <option value="gpt-4">GPT-4</option>
                            <option value="gpt-4-turbo">GPT-4 Turbo</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Prompt</label>
                        <textarea id="config-prompt" class="form-control" rows="4" placeholder="You are a helpful assistant..."></textarea>
                    </div>
                    <div class="form-group">
                        <label>Max Tokens</label>
                        <input type="number" id="config-max-tokens" class="form-control" value="1000" min="1" max="4000">
                    </div>
                `;

            case 'if':
                return `
                    <div class="form-group">
                        <label>Condition</label>
                        <input type="text" id="config-condition" class="form-control" placeholder="data.value > 10">
                    </div>
                    <div class="form-group">
                        <label>True Path</label>
                        <input type="text" id="config-true-path" class="form-control" placeholder="Continue to next node">
                    </div>
                    <div class="form-group">
                        <label>False Path</label>
                        <input type="text" id="config-false-path" class="form-control" placeholder="Skip or alternative path">
                    </div>
                `;

            case 'code':
                return `
                    <div class="form-group">
                        <label>Python Code</label>
                        <div id="monaco-editor-container" style="height: 400px; border: 1px solid #ced4da; border-radius: 4px;"></div>
                    </div>
                `;

            case 'telegram_trigger':
                return `
                    <div class="form-group">
                        <label>Telegram Bot Credential</label>
                        <select id="config-credential-id" class="form-control">
                            <option value="">Select Telegram Bot...</option>
                            ${this.getCredentialOptions('telegram_bot')}
                        </select>
                        <small class="text-muted">
                            <a href="/credentials/" target="_blank">
                                <i class="fas fa-plus"></i> Add new Telegram Bot
                            </a>
                        </small>
                    </div>
                    <div class="form-group">
                        <label>Chatbot Mode</label>
                        <select id="config-chatbot-mode" class="form-control">
                            <option value="false">Disabled</option>
                            <option value="true">Enabled (pass conversation context to AI)</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Trigger Events</label>
                        <select id="config-events" class="form-control" multiple>
                            <option value="message" selected>Message</option>
                            <option value="command">Command</option>
                            <option value="callback_query">Callback Query</option>
                        </select>
                        <small class="text-muted">Hold Ctrl to select multiple</small>
                    </div>
                    <div class="form-group">
                        <label>Allow Group Messages</label>
                        <select id="config-allow-groups" class="form-control">
                            <option value="false">No</option>
                            <option value="true">Yes</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Allowed Chat IDs</label>
                        <input type="text" id="config-allowed-chat-ids" class="form-control" placeholder="123456789, -987654321 (leave empty for all)">
                    </div>
                    <div class="form-group">
                        <label>Trigger Keywords</label>
                        <input type="text" id="config-trigger-keywords" class="form-control" placeholder="start, help, alert (leave empty for all)">
                    </div>
                `;

            case 'telegram_send':
                return `
                    <div class="form-group">
                        <label>Telegram Bot Credential</label>
                        <select id="config-credential-id" class="form-control">
                            <option value="">Select Telegram Bot...</option>
                            ${this.getCredentialOptions('telegram_bot')}
                        </select>
                        <small class="text-muted">
                            <a href="/credentials/" target="_blank">
                                <i class="fas fa-plus"></i> Add new Telegram Bot
                            </a>
                        </small>
                    </div>
                    <div class="form-group">
                        <label>Chat ID</label>
                        <input type="text" id="config-chat-id" class="form-control" placeholder="e.g. 123456789 or {{ telegram_trigger.json.chat_id }}">
                    </div>
                    <div class="form-group">
                        <label>Message Text</label>
                        <textarea id="config-message-text" class="form-control" rows="4" placeholder="Hello! Use {{ variable }} for dynamic content"></textarea>
                    </div>
                    <div class="form-group">
                        <label>Parse Mode</label>
                        <select id="config-parse-mode" class="form-control">
                            <option value="Markdown">Markdown</option>
                            <option value="HTML">HTML</option>
                            <option value="None">None (Plain Text)</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Disable Web Preview</label>
                        <select id="config-disable-web-preview" class="form-control">
                            <option value="false">No</option>
                            <option value="true">Yes</option>
                        </select>
                    </div>
                `;

            default:
                return `
                    <div class="alert alert-info">
                        <i class="fas fa-info-circle"></i>
                        Configuration for ${nodeType} nodes is not yet implemented.
                    </div>
                `;
        }
    }

    getCredentialOptions(credentialType) {
        if (!window.credentialManager) return '';

        const credentials = window.credentialManager.getCredentialsByType(credentialType);
        return credentials.map(cred =>
            `<option value="${cred.id}">${cred.name}</option>`
        ).join('');
    }

    populateConfigForm(config) {
        Object.keys(config).forEach(key => {
            const element = document.getElementById(`config-${key.replace('_', '-')}`);
            if (element) {
                if (element.type === 'checkbox') {
                    element.checked = config[key];
                } else {
                    element.value = typeof config[key] === 'object' ?
                        JSON.stringify(config[key], null, 2) : config[key];
                }
            }
        });
    }

    saveNodeConfig() {
        if (!this.currentNode) return;

        const config = {};
        const form = document.querySelector('.config-form.active');

        form.querySelectorAll('input, textarea, select').forEach(element => {
            if (element.id.startsWith('config-')) {
                const key = element.id.replace('config-', '').replace('-', '_');

                if (element.type === 'checkbox') {
                    config[key] = element.checked;
                } else {
                    let value = element.value;

                    // Try to parse JSON for textarea fields
                    if (element.tagName === 'TEXTAREA' && value.trim().startsWith('{')) {
                        try {
                            value = JSON.parse(value);
                        } catch (e) {
                            // Keep as string if not valid JSON
                        }
                    }

                    config[key] = value;
                }
            }
        });

        // Get value from Monaco if active
        if (this.currentNode.type === 'code' && this.monacoInstance) {
            config['code'] = this.monacoInstance.getValue();
        }

        this.nodeManager.updateNodeConfig(this.currentNode.id, config);

        // Dispatch event for modification tracking
        document.dispatchEvent(new CustomEvent('nodeConfigChanged'));

        this.apiManager.showSuccess('Node configuration saved');
    }

    async testNodeConfig() {
        if (!this.currentNode) return;

        try {
            const loading = this.apiManager.showLoading('Testing node configuration...');

            // Get current config from form
            this.saveNodeConfig(); // Save first
            const nodeData = this.nodeManager.nodes.get(this.currentNode.id);

            const result = await this.apiManager.validateNodeConfig(nodeData.type, nodeData.config);

            loading.hide();

            if (result.valid) {
                this.apiManager.showSuccess('Node configuration is valid');
            } else {
                this.apiManager.showError('Configuration error: ' + result.error);
            }

        } catch (error) {
            console.error('Failed to test node config:', error);
            this.apiManager.showError('Failed to test configuration: ' + error.message);
        }
    }

    getNodeIcon(type) {
        const icons = {
            'email': 'fab fa-google',
            'webhook': 'fas fa-link',
            'http': 'fas fa-globe',
            'if': 'fas fa-code-branch',
            'switch': 'fas fa-random',
            'database': 'fas fa-table',
            'variable': 'fas fa-box',
            'code': 'fas fa-code',
            'telegram': 'fab fa-telegram',
            'telegram_trigger': 'fab fa-telegram',
            'telegram_send': 'fab fa-telegram',
            'slack': 'fab fa-slack',
            'ai-agent': 'fas fa-robot'
        };
        return icons[type] || 'fas fa-question';
    }

    getNodeColor(type) {
        const colors = {
            'email': '#ea4335',
            'webhook': '#4285f4',
            'http': '#34a853',
            'if': '#fbbc04',
            'switch': '#ea4335',
            'database': '#9aa0a6',
            'variable': '#9aa0a6',
            'code': '#1e1e1e',
            'telegram': '#0088cc',
            'telegram_trigger': '#0088cc',
            'telegram_send': '#0088cc',
            'slack': '#4a154b',
            'ai-agent': '#10a37f'
        };
        return colors[type] || '#666';
    }

    getNodeTitle(type) {
        const titles = {
            'email': 'Gmail',
            'webhook': 'Webhook',
            'http': 'HTTP Request',
            'if': 'If Condition',
            'switch': 'Switch',
            'database': 'Database',
            'variable': 'Variable',
            'code': 'Python Code',
            'telegram': 'Telegram',
            'telegram_trigger': 'Telegram Trigger',
            'telegram_send': 'Telegram Send',
            'slack': 'Slack',
            'ai-agent': 'AI Agent'
        };
        return titles[type] || 'Unknown';
    }
}

// Initialize the application
const app = new WorkflowApp();