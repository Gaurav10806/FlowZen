/**
 * 🚀 ENHANCED MAIN APPLICATION CONTROLLER
 * 
 * This is the central orchestrator that brings together all the revolutionary features:
 * - Real-time collaboration
 * - AI-powered workflow assistant
 * - Advanced analytics dashboard
 * - Smart node recommendations
 * - Visual templates gallery
 * - Beautiful animations and interactions
 */

class EnhancedMainController {
    constructor() {
        this.isInitialized = false;
        this.modules = new Map();
        this.eventBus = new EventTarget();
        this.shortcuts = new Map();
        this.theme = 'light';
        this.user = null;

        this.init();
    }

    async init() {
        console.log('🚀 Initializing Enhanced Automation Platform...');

        try {
            // Show loading screen
            this.showLoadingScreen();

            // Initialize core modules
            await this.initializeModules();

            // Setup global event handlers
            this.setupGlobalEvents();

            // Setup keyboard shortcuts
            this.setupKeyboardShortcuts();

            // Initialize theme system
            this.initializeTheme();

            // Setup user session
            await this.initializeUser();

            // Create enhanced UI
            this.createEnhancedUI();

            // Hide loading screen
            this.hideLoadingScreen();

            this.isInitialized = true;
            console.log('✅ Enhanced Automation Platform ready!');

            // Show welcome message
            this.showWelcomeMessage();

        } catch (error) {
            console.error('❌ Failed to initialize platform:', error);
            this.showErrorMessage('Failed to initialize platform. Please refresh the page.');
        }
    }

    async initializeModules() {
        const modulePromises = [];

        // Initialize collaboration engine
        if (window.CollaborationEngine) {
            modulePromises.push(this.initModule('collaboration', CollaborationEngine));
        }

        // Initialize AI assistant
        if (window.AIWorkflowAssistant) {
            modulePromises.push(this.initModule('aiAssistant', AIWorkflowAssistant));
        }

        // Initialize analytics dashboard
        if (window.AdvancedAnalyticsDashboard) {
            modulePromises.push(this.initModule('analytics', AdvancedAnalyticsDashboard));
        }

        // Initialize smart node engine
        if (window.SmartNodeEngine) {
            modulePromises.push(this.initModule('smartNodes', SmartNodeEngine));
        }

        // Initialize templates gallery
        if (window.WorkflowTemplatesGallery) {
            modulePromises.push(this.initModule('templates', WorkflowTemplatesGallery));
        }

        // Initialize existing modules
        if (window.AnimationManager) {
            modulePromises.push(this.initModule('animations', AnimationManager));
        }

        if (window.NotificationManager) {
            modulePromises.push(this.initModule('notifications', NotificationManager));
        }

        await Promise.all(modulePromises);
    }

    async initModule(name, ModuleClass) {
        try {
            const instance = new ModuleClass();
            this.modules.set(name, instance);
            console.log(`✅ ${name} module initialized`);
        } catch (error) {
            console.warn(`⚠️ Failed to initialize ${name} module:`, error);
        }
    }

    createEnhancedUI() {
        // Create floating action button for quick access
        this.createFloatingActionButton();

        // Create command palette
        this.createCommandPalette();

        // Create status bar
        this.createStatusBar();

        // Create quick settings panel
        this.createQuickSettings();

        // Setup enhanced tooltips
        this.setupEnhancedTooltips();
    }

    createFloatingActionButton() {
        const fab = document.createElement('div');
        fab.className = 'floating-action-button';
        fab.innerHTML = `
            <div class="fab-main" onclick="enhancedController.toggleFABMenu()">
                <i class="fas fa-magic"></i>
                <div class="fab-pulse"></div>
            </div>
            
            <div class="fab-menu" id="fab-menu">
                <button class="fab-item" onclick="enhancedController.openAIAssistant()" data-tooltip="AI Assistant">
                    <i class="fas fa-robot"></i>
                </button>
                <button class="fab-item" onclick="enhancedController.openAnalytics()" data-tooltip="Analytics">
                    <i class="fas fa-chart-line"></i>
                </button>
                <button class="fab-item" onclick="enhancedController.openTemplates()" data-tooltip="Templates">
                    <i class="fas fa-layer-group"></i>
                </button>
                <button class="fab-item" onclick="enhancedController.openCollaboration()" data-tooltip="Collaboration">
                    <i class="fas fa-users"></i>
                </button>
                <button class="fab-item" onclick="enhancedController.openCommandPalette()" data-tooltip="Commands">
                    <i class="fas fa-terminal"></i>
                </button>
            </div>
        `;

        document.body.appendChild(fab);
        this.setupFABStyles();
    }

    setupFABStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .floating-action-button {
                position: fixed;
                bottom: 30px;
                right: 30px;
                z-index: 9999;
            }
            
            .fab-main {
                width: 60px;
                height: 60px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 24px;
                cursor: pointer;
                box-shadow: 0 8px 25px rgba(102, 126, 234, 0.3);
                transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                position: relative;
                overflow: hidden;
            }
            
            .fab-main:hover {
                transform: scale(1.1) rotate(10deg);
                box-shadow: 0 12px 35px rgba(102, 126, 234, 0.4);
            }
            
            .fab-pulse {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.3);
                animation: fabPulse 2s infinite;
            }
            
            .fab-menu {
                position: absolute;
                bottom: 80px;
                right: 0;
                display: flex;
                flex-direction: column;
                gap: 12px;
                opacity: 0;
                visibility: hidden;
                transform: scale(0.8);
                transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            }
            
            .fab-menu.open {
                opacity: 1;
                visibility: visible;
                transform: scale(1);
            }
            
            .fab-item {
                width: 48px;
                height: 48px;
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(20px);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #667eea;
                font-size: 18px;
                cursor: pointer;
                box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
                transition: all 0.2s ease;
            }
            
            .fab-item:hover {
                background: #667eea;
                color: white;
                transform: scale(1.1);
                box-shadow: 0 6px 20px rgba(102, 126, 234, 0.3);
            }
            
            @keyframes fabPulse {
                0%, 100% {
                    opacity: 0.3;
                    transform: scale(1);
                }
                50% {
                    opacity: 0.8;
                    transform: scale(1.1);
                }
            }
        `;
        document.head.appendChild(style);
    }

    createCommandPalette() {
        const palette = document.createElement('div');
        palette.className = 'command-palette';
        palette.id = 'command-palette';
        palette.innerHTML = `
            <div class="palette-overlay" onclick="enhancedController.closeCommandPalette()"></div>
            <div class="palette-container">
                <div class="palette-header">
                    <i class="fas fa-terminal"></i>
                    <input type="text" id="command-input" placeholder="Type a command or search...">
                </div>
                <div class="palette-content">
                    <div class="command-categories">
                        <div class="command-category">
                            <div class="category-title">Quick Actions</div>
                            <div class="command-item" data-command="new-workflow">
                                <i class="fas fa-plus"></i>
                                <span>Create New Workflow</span>
                                <kbd>Ctrl+N</kbd>
                            </div>
                            <div class="command-item" data-command="save-workflow">
                                <i class="fas fa-save"></i>
                                <span>Save Workflow</span>
                                <kbd>Ctrl+S</kbd>
                            </div>
                            <div class="command-item" data-command="run-workflow">
                                <i class="fas fa-play"></i>
                                <span>Run Workflow</span>
                                <kbd>Ctrl+R</kbd>
                            </div>
                        </div>
                        
                        <div class="command-category">
                            <div class="category-title">AI & Automation</div>
                            <div class="command-item" data-command="ai-assistant">
                                <i class="fas fa-robot"></i>
                                <span>Open AI Assistant</span>
                                <kbd>Ctrl+A</kbd>
                            </div>
                            <div class="command-item" data-command="generate-workflow">
                                <i class="fas fa-magic"></i>
                                <span>Generate Workflow with AI</span>
                                <kbd>Ctrl+G</kbd>
                            </div>
                        </div>
                        
                        <div class="command-category">
                            <div class="category-title">Analytics & Insights</div>
                            <div class="command-item" data-command="analytics">
                                <i class="fas fa-chart-line"></i>
                                <span>Open Analytics Dashboard</span>
                                <kbd>Ctrl+D</kbd>
                            </div>
                            <div class="command-item" data-command="performance">
                                <i class="fas fa-tachometer-alt"></i>
                                <span>Performance Monitor</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(palette);
        this.setupCommandPaletteStyles();
        this.setupCommandPaletteEvents();
    }

    setupCommandPaletteStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .command-palette {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                z-index: 10001;
                opacity: 0;
                visibility: hidden;
                transition: all 0.2s ease;
            }
            
            .command-palette.open {
                opacity: 1;
                visibility: visible;
            }
            
            .palette-overlay {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.5);
                backdrop-filter: blur(5px);
            }
            
            .palette-container {
                position: absolute;
                top: 20%;
                left: 50%;
                transform: translateX(-50%);
                width: 90%;
                max-width: 600px;
                background: rgba(255, 255, 255, 0.98);
                backdrop-filter: blur(20px);
                border-radius: 16px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
                overflow: hidden;
            }
            
            .palette-header {
                padding: 20px;
                border-bottom: 1px solid rgba(0, 0, 0, 0.1);
                display: flex;
                align-items: center;
                gap: 12px;
                background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
            }
            
            .palette-header i {
                color: #667eea;
                font-size: 18px;
            }
            
            #command-input {
                flex: 1;
                border: none;
                background: transparent;
                font-size: 16px;
                color: #1f2937;
                outline: none;
            }
            
            #command-input::placeholder {
                color: #9ca3af;
            }
            
            .palette-content {
                max-height: 400px;
                overflow-y: auto;
                padding: 20px;
            }
            
            .command-category {
                margin-bottom: 24px;
            }
            
            .category-title {
                font-size: 12px;
                font-weight: 600;
                color: #6b7280;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 12px;
            }
            
            .command-item {
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 12px;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.2s ease;
                margin-bottom: 4px;
            }
            
            .command-item:hover {
                background: rgba(102, 126, 234, 0.1);
            }
            
            .command-item i {
                width: 20px;
                color: #667eea;
            }
            
            .command-item span {
                flex: 1;
                color: #374151;
                font-weight: 500;
            }
            
            .command-item kbd {
                background: rgba(0, 0, 0, 0.1);
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 11px;
                color: #6b7280;
            }
        `;
        document.head.appendChild(style);
    }

    setupCommandPaletteEvents() {
        const input = document.getElementById('command-input');

        input.addEventListener('input', (e) => {
            this.filterCommands(e.target.value);
        });

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeCommandPalette();
            } else if (e.key === 'Enter') {
                this.executeSelectedCommand();
            }
        });

        // Command item clicks
        document.addEventListener('click', (e) => {
            if (e.target.closest('.command-item')) {
                const command = e.target.closest('.command-item').dataset.command;
                this.executeCommand(command);
                this.closeCommandPalette();
            }
        });
    }

    setupKeyboardShortcuts() {
        const shortcuts = [
            { key: 'ctrl+k', action: () => this.openCommandPalette() },
            { key: 'ctrl+n', action: () => this.createNewWorkflow() },
            { key: 'ctrl+s', action: () => this.saveWorkflow() },
            { key: 'ctrl+r', action: () => this.runWorkflow() },
            { key: 'ctrl+a', action: () => this.openAIAssistant() },
            { key: 'ctrl+d', action: () => this.openAnalytics() },
            { key: 'ctrl+g', action: () => this.generateWorkflow() },
            { key: 'ctrl+t', action: () => this.openTemplates() },
            { key: 'ctrl+/', action: () => this.showHelp() },
            { key: 'escape', action: () => this.closeAllModals() }
        ];

        shortcuts.forEach(shortcut => {
            this.shortcuts.set(shortcut.key, shortcut.action);
        });

        document.addEventListener('keydown', (e) => {
            const key = this.getKeyString(e);
            const action = this.shortcuts.get(key);

            if (action && !this.isInputFocused()) {
                e.preventDefault();
                action();
            }
        });
    }

    getKeyString(e) {
        const parts = [];
        if (e.ctrlKey) parts.push('ctrl');
        if (e.altKey) parts.push('alt');
        if (e.shiftKey) parts.push('shift');
        parts.push(e.key.toLowerCase());
        return parts.join('+');
    }

    isInputFocused() {
        const activeElement = document.activeElement;
        return activeElement && (
            activeElement.tagName === 'INPUT' ||
            activeElement.tagName === 'TEXTAREA' ||
            activeElement.contentEditable === 'true'
        );
    }

    // Module access methods
    toggleFABMenu() {
        const menu = document.getElementById('fab-menu');
        menu.classList.toggle('open');
    }

    openCommandPalette() {
        const palette = document.getElementById('command-palette');
        palette.classList.add('open');
        document.getElementById('command-input').focus();
    }

    closeCommandPalette() {
        const palette = document.getElementById('command-palette');
        palette.classList.remove('open');
    }

    openAIAssistant() {
        const aiAssistant = this.modules.get('aiAssistant');
        if (aiAssistant) {
            aiAssistant.togglePanel();
        }
    }

    openAnalytics() {
        const analytics = this.modules.get('analytics');
        if (analytics) {
            analytics.showDashboard();
        }
    }

    openTemplates() {
        const templates = this.modules.get('templates');
        if (templates) {
            templates.showGallery();
        }
    }

    openCollaboration() {
        const collaboration = this.modules.get('collaboration');
        if (collaboration) {
            collaboration.togglePanel();
        }
    }

    // Workflow operations
    createNewWorkflow() {
        this.showNotification('Creating new workflow...', 'info');
        // Implement new workflow creation
    }

    saveWorkflow() {
        this.showNotification('Saving workflow...', 'info');
        // Implement workflow saving
    }

    runWorkflow() {
        this.showNotification('Running workflow...', 'info');
        // Implement workflow execution
    }

    generateWorkflow() {
        this.openAIAssistant();
        // Focus on AI generation
    }

    showHelp() {
        this.showNotification('Help system coming soon!', 'info');
    }

    closeAllModals() {
        // Close all open modals and panels
        document.querySelectorAll('.modal, .panel, .overlay').forEach(element => {
            if (element.classList.contains('open') || element.classList.contains('visible')) {
                element.classList.remove('open', 'visible');
            }
        });
    }

    showNotification(message, type = 'info') {
        const notifications = this.modules.get('notifications');
        if (notifications) {
            notifications.show(message, type);
        } else {
            console.log(`[${type.toUpperCase()}] ${message}`);
        }
    }

    showLoadingScreen() {
        const loading = document.getElementById('loading-screen');
        if (loading) {
            loading.style.display = 'flex';
        }
    }

    hideLoadingScreen() {
        const loading = document.getElementById('loading-screen');
        if (loading) {
            setTimeout(() => {
                loading.style.display = 'none';
            }, 500);
        }
    }

    showWelcomeMessage() {
        setTimeout(() => {
            this.showNotification('🎉 Welcome to the Enhanced Automation Platform! Press Ctrl+K for commands.', 'success');
        }, 1000);
    }

    showErrorMessage(message) {
        this.showNotification(message, 'error');
    }

    async initializeUser() {
        // Initialize user session
        this.user = {
            id: 'user_' + Date.now(),
            name: 'User',
            email: 'user@example.com',
            color: '#667eea'
        };

        // Set user in collaboration engine
        const collaboration = this.modules.get('collaboration');
        if (collaboration) {
            collaboration.setCurrentUser(this.user);
        }
    }

    initializeTheme() {
        // Initialize theme system
        const savedTheme = localStorage.getItem('theme') || 'light';
        this.setTheme(savedTheme);
    }

    setTheme(theme) {
        this.theme = theme;
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
    }

    setupGlobalEvents() {
        // Setup global event listeners
        window.addEventListener('error', (e) => {
            console.error('Global error:', e.error);
            this.showNotification('An error occurred. Please check the console.', 'error');
        });

        window.addEventListener('unhandledrejection', (e) => {
            console.error('Unhandled promise rejection:', e.reason);
            this.showNotification('An error occurred. Please check the console.', 'error');
        });
    }

    // Command execution
    executeCommand(command) {
        const commands = {
            'new-workflow': () => this.createNewWorkflow(),
            'save-workflow': () => this.saveWorkflow(),
            'run-workflow': () => this.runWorkflow(),
            'ai-assistant': () => this.openAIAssistant(),
            'generate-workflow': () => this.generateWorkflow(),
            'analytics': () => this.openAnalytics(),
            'performance': () => this.openAnalytics(),
            'templates': () => this.openTemplates(),
            'collaboration': () => this.openCollaboration()
        };

        const action = commands[command];
        if (action) {
            action();
        }
    }

    executeSelectedCommand() {
        // Execute the currently selected command
        const selected = document.querySelector('.command-item.selected');
        if (selected) {
            const command = selected.dataset.command;
            this.executeCommand(command);
            this.closeCommandPalette();
        }
    }

    filterCommands(query) {
        const items = document.querySelectorAll('.command-item');

        items.forEach(item => {
            const text = item.textContent.toLowerCase();
            const matches = text.includes(query.toLowerCase());
            item.style.display = matches ? 'flex' : 'none';
        });
    }
}

// Initialize the enhanced main controller
window.enhancedController = new EnhancedMainController();