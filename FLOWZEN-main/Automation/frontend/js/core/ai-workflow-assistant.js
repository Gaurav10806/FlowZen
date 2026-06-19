/**
 * 🤖 AI-POWERED WORKFLOW ASSISTANT
 * 
 * Revolutionary Features:
 * - Natural language workflow generation
 * - Intelligent node suggestions
 * - Auto-completion and optimization
 * - Error detection and fixes
 * - Performance recommendations
 * - Smart documentation generation
 */

class AIWorkflowAssistant {
    constructor() {
        this.isActive = false;
        this.suggestions = [];
        this.currentContext = null;
        this.conversationHistory = [];
        this.isProcessing = false;
        this.panel = null;
        this.voiceRecognition = null;
        this.isListening = false;
        this.lastGeneratedWorkflow = null;
        
        this.init();
    }
    
    init() {
        this.createAssistantUI();
        this.setupEventListeners();
        this.initializeVoiceRecognition();
        this.startContextAnalysis();
        console.log('🤖 AI Workflow Assistant initialized');
    }
    
    createAssistantUI() {
        // Create floating AI assistant
        const assistant = document.createElement('div');
        assistant.className = 'ai-assistant';
        assistant.innerHTML = `
            <div class="ai-assistant-trigger" onclick="aiAssistant.togglePanel()">
                <div class="ai-avatar">
                    <i class="fas fa-robot"></i>
                    <div class="ai-pulse"></div>
                </div>
                <div class="ai-tooltip">AI Assistant</div>
            </div>
            
            <div class="ai-assistant-panel" id="ai-panel">
                <div class="ai-header">
                    <div class="ai-title">
                        <i class="fas fa-magic"></i>
                        <span>AI Workflow Assistant</span>
                        <div class="ai-status ${this.isProcessing ? 'thinking' : 'ready'}"></div>
                    </div>
                    <button class="ai-close" onclick="aiAssistant.togglePanel()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                
                <div class="ai-content">
                    <!-- Quick Actions -->
                    <div class="ai-quick-actions">
                        <button class="quick-action" onclick="aiAssistant.generateWorkflow()">
                            <i class="fas fa-wand-magic-sparkles"></i>
                            Generate Workflow
                        </button>
                        <button class="quick-action" onclick="aiAssistant.optimizeWorkflow()">
                            <i class="fas fa-rocket"></i>
                            Optimize Current
                        </button>
                        <button class="quick-action" onclick="aiAssistant.explainWorkflow()">
                            <i class="fas fa-lightbulb"></i>
                            Explain Workflow
                        </button>
                        <button class="quick-action" onclick="aiAssistant.findErrors()">
                            <i class="fas fa-bug"></i>
                            Find Issues
                        </button>
                    </div>
                    
                    <!-- Chat Interface -->
                    <div class="ai-chat">
                        <div class="ai-messages" id="ai-messages">
                            <div class="ai-message assistant">
                                <div class="message-avatar">
                                    <i class="fas fa-robot"></i>
                                </div>
                                <div class="message-content">
                                    <div class="message-text">
                                        👋 Hi! I'm your AI workflow assistant. I can help you:
                                        <ul>
                                            <li>🎯 Generate workflows from natural language</li>
                                            <li>🔧 Optimize existing workflows</li>
                                            <li>🐛 Find and fix errors</li>
                                            <li>📚 Explain complex workflows</li>
                                            <li>💡 Suggest improvements</li>
                                        </ul>
                                        What would you like to create today?
                                    </div>
                                    <div class="message-time">${this.formatTime(Date.now())}</div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="ai-input-container">
                            <div class="ai-input-wrapper">
                                <textarea 
                                    id="ai-input" 
                                    placeholder="Describe the workflow you want to create..."
                                    rows="3"
                                ></textarea>
                                <div class="ai-input-actions">
                                    <button class="voice-btn ${this.isListening ? 'listening' : ''}" onclick="aiAssistant.toggleVoice()">
                                        <i class="fas fa-microphone"></i>
                                    </button>
                                    <button class="send-btn" onclick="aiAssistant.sendMessage()">
                                        <i class="fas fa-paper-plane"></i>
                                    </button>
                                </div>
                            </div>
                            
                            <!-- Suggestions -->
                            <div class="ai-suggestions" id="ai-suggestions">
                                <div class="suggestion-item" onclick="aiAssistant.useSuggestion(this)">
                                    "Create a workflow that sends welcome emails to new users"
                                </div>
                                <div class="suggestion-item" onclick="aiAssistant.useSuggestion(this)">
                                    "Build an automated data backup system"
                                </div>
                                <div class="suggestion-item" onclick="aiAssistant.useSuggestion(this)">
                                    "Set up customer support ticket routing"
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Smart Suggestions Panel -->
                    <div class="ai-smart-suggestions" id="smart-suggestions">
                        <!-- Dynamic suggestions will appear here -->
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(assistant);
        this.panel = document.getElementById('ai-panel');
        
        this.setupStyles();
    }
    
    setupStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .ai-assistant {
                position: fixed;
                bottom: 30px;
                left: 30px;
                z-index: 10000;
            }
            
            .ai-assistant-trigger {
                position: relative;
                cursor: pointer;
            }
            
            .ai-avatar {
                width: 60px;
                height: 60px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 24px;
                box-shadow: 0 8px 25px rgba(102, 126, 234, 0.3);
                transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                position: relative;
                overflow: hidden;
            }
            
            .ai-avatar:hover {
                transform: scale(1.1) rotate(5deg);
                box-shadow: 0 12px 35px rgba(102, 126, 234, 0.4);
            }
            
            .ai-pulse {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.3);
                animation: aiPulse 2s infinite;
            }
            
            .ai-tooltip {
                position: absolute;
                bottom: 70px;
                left: 50%;
                transform: translateX(-50%);
                background: #1f2937;
                color: white;
                padding: 8px 12px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
                white-space: nowrap;
                opacity: 0;
                visibility: hidden;
                transition: all 0.2s ease;
                pointer-events: none;
            }
            
            .ai-assistant-trigger:hover .ai-tooltip {
                opacity: 1;
                visibility: visible;
                bottom: 75px;
            }
            
            .ai-assistant-panel {
                position: absolute;
                bottom: 80px;
                left: 0;
                width: 400px;
                max-height: 600px;
                background: rgba(255, 255, 255, 0.98);
                backdrop-filter: blur(20px);
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
                border: 1px solid rgba(255, 255, 255, 0.2);
                transform: scale(0.8) translateY(20px);
                opacity: 0;
                visibility: hidden;
                transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                overflow: hidden;
            }
            
            .ai-assistant-panel.open {
                transform: scale(1) translateY(0);
                opacity: 1;
                visibility: visible;
            }
            
            .ai-header {
                padding: 20px;
                border-bottom: 1px solid rgba(0, 0, 0, 0.1);
                display: flex;
                align-items: center;
                justify-content: space-between;
                background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
            }
            
            .ai-title {
                display: flex;
                align-items: center;
                gap: 8px;
                font-weight: 600;
                color: #1f2937;
            }
            
            .ai-status {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                margin-left: 8px;
            }
            
            .ai-status.ready {
                background: #10b981;
                box-shadow: 0 0 10px rgba(16, 185, 129, 0.5);
            }
            
            .ai-status.thinking {
                background: #f59e0b;
                animation: aiThinking 1s infinite;
            }
            
            .ai-close {
                background: none;
                border: none;
                color: #6b7280;
                cursor: pointer;
                padding: 4px;
                border-radius: 4px;
                transition: all 0.2s ease;
            }
            
            .ai-close:hover {
                background: rgba(0, 0, 0, 0.1);
                color: #1f2937;
            }
            
            .ai-content {
                padding: 20px;
                max-height: 500px;
                overflow-y: auto;
            }
            
            .ai-quick-actions {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 8px;
                margin-bottom: 20px;
            }
            
            .quick-action {
                padding: 12px;
                border: 1px solid rgba(102, 126, 234, 0.2);
                border-radius: 8px;
                background: rgba(102, 126, 234, 0.05);
                color: #667eea;
                font-size: 12px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s ease;
                display: flex;
                align-items: center;
                gap: 6px;
            }
            
            .quick-action:hover {
                background: rgba(102, 126, 234, 0.1);
                border-color: #667eea;
                transform: translateY(-1px);
            }
            
            .ai-chat {
                margin-bottom: 20px;
            }
            
            .ai-messages {
                max-height: 300px;
                overflow-y: auto;
                margin-bottom: 16px;
            }
            
            .ai-message {
                display: flex;
                gap: 12px;
                margin-bottom: 16px;
                animation: messageSlideIn 0.3s ease;
            }
            
            .ai-message.user {
                flex-direction: row-reverse;
            }
            
            .message-avatar {
                width: 32px;
                height: 32px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 14px;
                flex-shrink: 0;
            }
            
            .ai-message.assistant .message-avatar {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }
            
            .ai-message.user .message-avatar {
                background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            }
            
            .message-content {
                flex: 1;
                max-width: 280px;
            }
            
            .message-text {
                background: rgba(0, 0, 0, 0.05);
                padding: 12px 16px;
                border-radius: 16px;
                font-size: 14px;
                line-height: 1.4;
                color: #374151;
            }
            
            .ai-message.user .message-text {
                background: #667eea;
                color: white;
            }
            
            .message-text ul {
                margin: 8px 0;
                padding-left: 16px;
            }
            
            .message-text li {
                margin: 4px 0;
            }
            
            .message-time {
                font-size: 11px;
                color: #9ca3af;
                margin-top: 4px;
                text-align: right;
            }
            
            .ai-input-container {
                border-top: 1px solid rgba(0, 0, 0, 0.1);
                padding-top: 16px;
            }
            
            .ai-input-wrapper {
                position: relative;
                background: rgba(0, 0, 0, 0.02);
                border-radius: 12px;
                border: 1px solid rgba(0, 0, 0, 0.1);
                overflow: hidden;
            }
            
            .ai-input-wrapper:focus-within {
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }
            
            #ai-input {
                width: 100%;
                padding: 12px 60px 12px 16px;
                border: none;
                background: transparent;
                resize: none;
                font-size: 14px;
                color: #374151;
                outline: none;
                font-family: inherit;
            }
            
            #ai-input::placeholder {
                color: #9ca3af;
            }
            
            .ai-input-actions {
                position: absolute;
                right: 8px;
                top: 50%;
                transform: translateY(-50%);
                display: flex;
                gap: 4px;
            }
            
            .voice-btn,
            .send-btn {
                width: 32px;
                height: 32px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.2s ease;
                font-size: 12px;
            }
            
            .voice-btn {
                background: rgba(245, 158, 11, 0.1);
                color: #f59e0b;
            }
            
            .voice-btn:hover {
                background: rgba(245, 158, 11, 0.2);
            }
            
            .voice-btn.listening {
                background: #f59e0b;
                color: white;
                animation: voicePulse 1s infinite;
            }
            
            .send-btn {
                background: #667eea;
                color: white;
            }
            
            .send-btn:hover {
                background: #5a67d8;
                transform: scale(1.05);
            }
            
            .ai-suggestions {
                margin-top: 12px;
                display: flex;
                flex-direction: column;
                gap: 6px;
            }
            
            .suggestion-item {
                padding: 8px 12px;
                background: rgba(102, 126, 234, 0.05);
                border: 1px solid rgba(102, 126, 234, 0.1);
                border-radius: 6px;
                font-size: 12px;
                color: #667eea;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            
            .suggestion-item:hover {
                background: rgba(102, 126, 234, 0.1);
                border-color: #667eea;
            }
            
            .ai-smart-suggestions {
                border-top: 1px solid rgba(0, 0, 0, 0.1);
                padding-top: 16px;
            }
            
            .smart-suggestion {
                padding: 12px;
                background: linear-gradient(135deg, rgba(16, 185, 129, 0.05) 0%, rgba(5, 150, 105, 0.05) 100%);
                border: 1px solid rgba(16, 185, 129, 0.2);
                border-radius: 8px;
                margin-bottom: 8px;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            
            .smart-suggestion:hover {
                background: linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(5, 150, 105, 0.1) 100%);
                transform: translateY(-1px);
            }
            
            .suggestion-title {
                font-weight: 500;
                color: #10b981;
                margin-bottom: 4px;
                font-size: 13px;
            }
            
            .suggestion-description {
                font-size: 12px;
                color: #6b7280;
                line-height: 1.3;
            }
            
            @keyframes aiPulse {
                0%, 100% {
                    opacity: 0.3;
                    transform: scale(1);
                }
                50% {
                    opacity: 0.8;
                    transform: scale(1.1);
                }
            }
            
            @keyframes aiThinking {
                0%, 100% {
                    opacity: 1;
                }
                50% {
                    opacity: 0.3;
                }
            }
            
            @keyframes voicePulse {
                0%, 100% {
                    transform: scale(1);
                }
                50% {
                    transform: scale(1.1);
                }
            }
            
            @keyframes messageSlideIn {
                from {
                    transform: translateY(10px);
                    opacity: 0;
                }
                to {
                    transform: translateY(0);
                    opacity: 1;
                }
            }
            
            /* Scrollbar styling */
            .ai-messages::-webkit-scrollbar,
            .ai-content::-webkit-scrollbar {
                width: 4px;
            }
            
            .ai-messages::-webkit-scrollbar-track,
            .ai-content::-webkit-scrollbar-track {
                background: transparent;
            }
            
            .ai-messages::-webkit-scrollbar-thumb,
            .ai-content::-webkit-scrollbar-thumb {
                background: rgba(0, 0, 0, 0.2);
                border-radius: 2px;
            }
        `;
        document.head.appendChild(style);
    }
    
    setupEventListeners() {
        // Enter key to send message
        document.addEventListener('keydown', (e) => {
            if (e.target.id === 'ai-input' && e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Listen for workflow changes to provide suggestions
        document.addEventListener('workflowChanged', (e) => {
            this.analyzeWorkflow(e.detail);
        });
        
        // Listen for node selection to provide context-aware suggestions
        document.addEventListener('nodeSelected', (e) => {
            this.analyzeSelectedNode(e.detail);
        });
    }
    
    initializeVoiceRecognition() {
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.voiceRecognition = new SpeechRecognition();
            
            this.voiceRecognition.continuous = false;
            this.voiceRecognition.interimResults = false;
            this.voiceRecognition.lang = 'en-US';
            
            this.voiceRecognition.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                document.getElementById('ai-input').value = transcript;
                this.isListening = false;
                this.updateVoiceButton();
            };
            
            this.voiceRecognition.onerror = () => {
                this.isListening = false;
                this.updateVoiceButton();
            };
            
            this.voiceRecognition.onend = () => {
                this.isListening = false;
                this.updateVoiceButton();
            };
        }
    }
    
    togglePanel() {
        this.panel.classList.toggle('open');
        this.isActive = this.panel.classList.contains('open');
        
        if (this.isActive) {
            this.startContextAnalysis();
        }
    }
    
    async sendMessage() {
        const input = document.getElementById('ai-input');
        const message = input.value.trim();
        
        if (!message) return;
        
        // Add user message to chat
        this.addMessage(message, 'user');
        input.value = '';
        
        // Show thinking state
        this.setThinkingState(true);
        
        try {
            // Process the message with AI
            const response = await this.processMessage(message);
            
            // Store generated workflow if present
            if (response.workflow) {
                this.lastGeneratedWorkflow = response.workflow;
            }
            
            // Add AI response to chat
            this.addMessage(response.text, 'assistant');
            
            // Execute any actions
            if (response.actions) {
                await this.executeActions(response.actions);
            }
            
        } catch (error) {
            console.error('AI Assistant error:', error);
            this.addMessage('Sorry, I encountered an error. Please try again.', 'assistant');
        } finally {
            this.setThinkingState(false);
        }
    }
    
    async processMessage(message) {
        // Use real backend API for AI processing
        try {
            const response = await fetch('/api/ai/chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    message: message,
                    workflow: this.getCurrentWorkflow()
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                const result = {
                    text: data.message,
                    actions: []
                };
                
                // If workflow was generated, add it to actions
                if (data.workflow) {
                    result.workflow = data.workflow;
                    result.actions.push('load_generated_workflow');
                }
                
                return result;
            } else {
                return {
                    text: data.message || 'Sorry, I encountered an error. Please try again.',
                    actions: []
                };
            }
        } catch (error) {
            console.error('AI API error:', error);
            return {
                text: 'Sorry, I\'m having trouble connecting to the AI service. Please try again later.',
                actions: []
            };
        }
    }
    
    async handleCreateWorkflow(message) {
        const workflows = {
            'email': {
                text: "I'll create an email automation workflow for you! This will include a trigger, email composition, and sending logic.",
                actions: ['create_email_workflow']
            },
            'backup': {
                text: "Perfect! I'll set up an automated backup system with scheduling and error handling.",
                actions: ['create_backup_workflow']
            },
            'api': {
                text: "Great idea! I'll create an API integration workflow with proper error handling and data transformation.",
                actions: ['create_api_workflow']
            }
        };
        
        // Simple keyword matching (replace with proper NLP)
        for (const [key, workflow] of Object.entries(workflows)) {
            if (message.toLowerCase().includes(key)) {
                return workflow;
            }
        }
        
        return {
            text: "I'd love to help you create a workflow! Could you provide more details about what you want to automate? For example:\n\n• Email automation\n• Data processing\n• API integrations\n• File management\n• Notifications",
            actions: []
        };
    }
    
    async handleOptimizeWorkflow(message) {
        const currentWorkflow = this.getCurrentWorkflow();
        
        if (!currentWorkflow || !currentWorkflow.nodes || currentWorkflow.nodes.length === 0) {
            return {
                text: "I don't see any workflow to optimize. Please create or open a workflow first, then I can suggest improvements!",
                actions: []
            };
        }
        
        const suggestions = this.analyzeWorkflowForOptimization(currentWorkflow);
        
        return {
            text: `I've analyzed your workflow and found ${suggestions.length} optimization opportunities:\n\n${suggestions.map((s, i) => `${i + 1}. ${s}`).join('\n')}`,
            actions: ['highlight_optimization_opportunities']
        };
    }
    
    async handleExplainWorkflow(message) {
        const currentWorkflow = this.getCurrentWorkflow();
        
        if (!currentWorkflow || !currentWorkflow.nodes || currentWorkflow.nodes.length === 0) {
            return {
                text: "I don't see any workflow to explain. Please create or open a workflow first!",
                actions: []
            };
        }
        
        const explanation = this.generateWorkflowExplanation(currentWorkflow);
        
        return {
            text: explanation,
            actions: ['highlight_workflow_flow']
        };
    }
    
    async handleFindErrors(message) {
        const currentWorkflow = this.getCurrentWorkflow();
        
        if (!currentWorkflow) {
            return {
                text: "I don't see any workflow to check for errors. Please create or open a workflow first!",
                actions: []
            };
        }
        
        const errors = this.findWorkflowErrors(currentWorkflow);
        
        if (errors.length === 0) {
            return {
                text: "Great news! I didn't find any obvious errors in your workflow. Everything looks good! 🎉",
                actions: []
            };
        }
        
        return {
            text: `I found ${errors.length} potential issues:\n\n${errors.map((e, i) => `${i + 1}. ${e.message} (${e.severity})`).join('\n')}`,
            actions: ['highlight_errors']
        };
    }
    
    async handleGeneralQuery(message) {
        const responses = [
            "I'm here to help you build amazing workflows! What would you like to create?",
            "That's interesting! How can I assist you with your workflow automation?",
            "I'd be happy to help! Could you tell me more about what you're trying to achieve?",
            "Great question! Let me know what specific workflow challenge you're facing."
        ];
        
        return {
            text: responses[Math.floor(Math.random() * responses.length)],
            actions: []
        };
    }
    
    async executeActions(actions) {
        for (const action of actions) {
            switch (action) {
                case 'load_generated_workflow':
                    await this.loadGeneratedWorkflow();
                    break;
                case 'create_email_workflow':
                    await this.createEmailWorkflow();
                    break;
                case 'create_backup_workflow':
                    await this.createBackupWorkflow();
                    break;
                case 'create_api_workflow':
                    await this.createApiWorkflow();
                    break;
                case 'highlight_optimization_opportunities':
                    this.highlightOptimizationOpportunities();
                    break;
                case 'highlight_workflow_flow':
                    this.highlightWorkflowFlow();
                    break;
                case 'highlight_errors':
                    this.highlightErrors();
                    break;
            }
        }
    }
    
    async loadGeneratedWorkflow() {
        // Load the generated workflow from the last response
        if (this.lastGeneratedWorkflow) {
            if (window.workflowManager) {
                window.workflowManager.loadWorkflow(this.lastGeneratedWorkflow);
            } else {
                // Fallback: trigger custom event
                const event = new CustomEvent('loadWorkflow', {
                    detail: this.lastGeneratedWorkflow
                });
                document.dispatchEvent(event);
            }
            
            this.showNotification('✨ Workflow loaded successfully!', 'success');
        }
    }
    
    getCSRFToken() {
        // Get CSRF token from Django
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                return value;
            }
        }
        
        // Fallback: try to get from meta tag
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        if (csrfMeta) {
            return csrfMeta.getAttribute('content');
        }
        
        return '';
    }
    
    async createEmailWorkflow() {
        // Create a sample email workflow
        const workflow = {
            nodes: [
                {
                    id: 'trigger_1',
                    type: 'webhook',
                    position: { x: 100, y: 100 },
                    config: { name: 'New User Trigger' }
                },
                {
                    id: 'email_1',
                    type: 'email',
                    position: { x: 300, y: 100 },
                    config: { 
                        name: 'Welcome Email',
                        subject: 'Welcome to our platform!',
                        template: 'welcome_email'
                    }
                }
            ],
            edges: [
                {
                    source: 'trigger_1',
                    target: 'email_1'
                }
            ]
        };
        
        if (window.workflowManager) {
            window.workflowManager.loadWorkflow(workflow);
        }
        
        this.showNotification('✨ Email workflow created successfully!', 'success');
    }
    
    async createBackupWorkflow() {
        // Create a sample backup workflow
        const workflow = {
            nodes: [
                {
                    id: 'schedule_1',
                    type: 'schedule',
                    position: { x: 100, y: 100 },
                    config: { name: 'Daily Backup', cron: '0 2 * * *' }
                },
                {
                    id: 'backup_1',
                    type: 'backup',
                    position: { x: 300, y: 100 },
                    config: { 
                        name: 'Database Backup',
                        source: 'database',
                        destination: 's3://backups/'
                    }
                }
            ],
            edges: [
                {
                    source: 'schedule_1',
                    target: 'backup_1'
                }
            ]
        };
        
        if (window.workflowManager) {
            window.workflowManager.loadWorkflow(workflow);
        }
        
        this.showNotification('🔄 Backup workflow created successfully!', 'success');
    }
    
    async createApiWorkflow() {
        // Create a sample API integration workflow
        const workflow = {
            nodes: [
                {
                    id: 'webhook_1',
                    type: 'webhook',
                    position: { x: 100, y: 100 },
                    config: { name: 'API Trigger' }
                },
                {
                    id: 'transform_1',
                    type: 'transform',
                    position: { x: 300, y: 100 },
                    config: { 
                        name: 'Data Transform',
                        mapping: { 'user_id': '$.id', 'email': '$.email' }
                    }
                },
                {
                    id: 'http_1',
                    type: 'http_request',
                    position: { x: 500, y: 100 },
                    config: { 
                        name: 'External API Call',
                        method: 'POST',
                        url: 'https://api.example.com/users'
                    }
                }
            ],
            edges: [
                {
                    source: 'webhook_1',
                    target: 'transform_1'
                },
                {
                    source: 'transform_1',
                    target: 'http_1'
                }
            ]
        };
        
        if (window.workflowManager) {
            window.workflowManager.loadWorkflow(workflow);
        }
        
        this.showNotification('🚀 API workflow created successfully!', 'success');
    }
    
    addMessage(text, sender) {
        const messagesContainer = document.getElementById('ai-messages');
        
        const message = document.createElement('div');
        message.className = `ai-message ${sender}`;
        
        const avatar = sender === 'assistant' ? 'fas fa-robot' : 'fas fa-user';
        
        message.innerHTML = `
            <div class="message-avatar">
                <i class="${avatar}"></i>
            </div>
            <div class="message-content">
                <div class="message-text">${text}</div>
                <div class="message-time">${this.formatTime(Date.now())}</div>
            </div>
        `;
        
        messagesContainer.appendChild(message);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
        // Store in conversation history
        this.conversationHistory.push({
            text: text,
            sender: sender,
            timestamp: Date.now()
        });
    }
    
    setThinkingState(thinking) {
        this.isProcessing = thinking;
        const status = document.querySelector('.ai-status');
        if (status) {
            status.className = `ai-status ${thinking ? 'thinking' : 'ready'}`;
        }
    }
    
    toggleVoice() {
        if (!this.voiceRecognition) {
            this.showNotification('Voice recognition not supported in this browser', 'warning');
            return;
        }
        
        if (this.isListening) {
            this.voiceRecognition.stop();
        } else {
            this.voiceRecognition.start();
            this.isListening = true;
            this.updateVoiceButton();
        }
    }
    
    updateVoiceButton() {
        const voiceBtn = document.querySelector('.voice-btn');
        if (voiceBtn) {
            voiceBtn.className = `voice-btn ${this.isListening ? 'listening' : ''}`;
        }
    }
    
    useSuggestion(element) {
        const suggestion = element.textContent.replace(/"/g, '');
        document.getElementById('ai-input').value = suggestion;
    }
    
    async generateWorkflow() {
        this.addMessage("I'll help you generate a workflow! What kind of automation do you need?", 'assistant');
        document.getElementById('ai-input').focus();
    }
    
    async optimizeWorkflow() {
        const currentWorkflow = this.getCurrentWorkflow();
        
        if (!currentWorkflow || !currentWorkflow.nodes || currentWorkflow.nodes.length === 0) {
            this.addMessage("I don't see any workflow to optimize. Please create or open a workflow first!", 'assistant');
            return;
        }
        
        this.addMessage("Let me analyze your workflow for optimization opportunities...", 'assistant');
        
        setTimeout(() => {
            const suggestions = this.analyzeWorkflowForOptimization(currentWorkflow);
            const message = suggestions.length > 0 
                ? `I found ${suggestions.length} ways to optimize your workflow:\n\n${suggestions.map((s, i) => `${i + 1}. ${s}`).join('\n')}`
                : "Your workflow is already well-optimized! Great job! 🎉";
            
            this.addMessage(message, 'assistant');
        }, 2000);
    }
    
    async explainWorkflow() {
        const currentWorkflow = this.getCurrentWorkflow();
        
        if (!currentWorkflow || !currentWorkflow.nodes || currentWorkflow.nodes.length === 0) {
            this.addMessage("I don't see any workflow to explain. Please create or open a workflow first!", 'assistant');
            return;
        }
        
        const explanation = this.generateWorkflowExplanation(currentWorkflow);
        this.addMessage(explanation, 'assistant');
    }
    
    async findErrors() {
        const currentWorkflow = this.getCurrentWorkflow();
        
        if (!currentWorkflow) {
            this.addMessage("I don't see any workflow to check. Please create or open a workflow first!", 'assistant');
            return;
        }
        
        this.addMessage("Let me scan your workflow for potential issues...", 'assistant');
        
        setTimeout(() => {
            const errors = this.findWorkflowErrors(currentWorkflow);
            
            if (errors.length === 0) {
                this.addMessage("Excellent! I didn't find any issues in your workflow. Everything looks perfect! ✨", 'assistant');
            } else {
                const message = `I found ${errors.length} potential issues:\n\n${errors.map((e, i) => `${i + 1}. ${e.message} (${e.severity})`).join('\n')}\n\nWould you like me to help fix these?`;
                this.addMessage(message, 'assistant');
            }
        }, 1500);
    }
    
    getCurrentWorkflow() {
        // Get current workflow from workflow manager
        if (window.workflowManager && window.workflowManager.currentWorkflow) {
            return window.workflowManager.currentWorkflow;
        }
        
        // Fallback: try to get from canvas
        const nodes = document.querySelectorAll('.workflow-node');
        if (nodes.length === 0) return null;
        
        return {
            nodes: Array.from(nodes).map(node => ({
                id: node.id,
                type: node.dataset.nodeType,
                position: {
                    x: parseInt(node.style.left),
                    y: parseInt(node.style.top)
                }
            })),
            edges: [] // Would need to extract from connections
        };
    }
    
    analyzeWorkflowForOptimization(workflow) {
        const suggestions = [];
        
        if (!workflow.nodes || workflow.nodes.length === 0) {
            return suggestions;
        }
        
        // Check for parallel execution opportunities
        if (workflow.nodes.length > 2) {
            suggestions.push("Consider using parallel execution for independent operations to improve performance");
        }
        
        // Check for error handling
        const hasErrorHandling = workflow.nodes.some(node => node.type === 'error_handler');
        if (!hasErrorHandling) {
            suggestions.push("Add error handling nodes to make your workflow more robust");
        }
        
        // Check for caching opportunities
        const hasHttpNodes = workflow.nodes.some(node => node.type === 'http_request');
        if (hasHttpNodes) {
            suggestions.push("Consider adding caching for API calls to reduce latency and costs");
        }
        
        // Check for logging
        const hasLogging = workflow.nodes.some(node => node.type === 'logger');
        if (!hasLogging) {
            suggestions.push("Add logging nodes to help with debugging and monitoring");
        }
        
        return suggestions;
    }
    
    generateWorkflowExplanation(workflow) {
        if (!workflow.nodes || workflow.nodes.length === 0) {
            return "This workflow is empty. Add some nodes to get started!";
        }
        
        const nodeCount = workflow.nodes.length;
        const nodeTypes = [...new Set(workflow.nodes.map(n => n.type))];
        
        let explanation = `This workflow contains ${nodeCount} nodes with the following types: ${nodeTypes.join(', ')}.\n\n`;
        
        explanation += "Here's what it does:\n";
        
        workflow.nodes.forEach((node, index) => {
            explanation += `${index + 1}. ${this.getNodeDescription(node)}\n`;
        });
        
        return explanation;
    }
    
    getNodeDescription(node) {
        const descriptions = {
            webhook: "Receives HTTP requests to trigger the workflow",
            schedule: "Runs the workflow on a scheduled basis",
            email: "Sends email notifications",
            http_request: "Makes API calls to external services",
            transform: "Transforms and processes data",
            condition: "Makes decisions based on conditions",
            logger: "Logs information for debugging"
        };
        
        return descriptions[node.type] || `Performs ${node.type} operations`;
    }
    
    findWorkflowErrors(workflow) {
        const errors = [];
        
        if (!workflow.nodes || workflow.nodes.length === 0) {
            errors.push({
                message: "Workflow is empty",
                severity: "warning"
            });
            return errors;
        }
        
        // Check for disconnected nodes
        const connectedNodes = new Set();
        if (workflow.edges) {
            workflow.edges.forEach(edge => {
                connectedNodes.add(edge.source);
                connectedNodes.add(edge.target);
            });
        }
        
        workflow.nodes.forEach(node => {
            if (!connectedNodes.has(node.id) && workflow.nodes.length > 1) {
                errors.push({
                    message: `Node "${node.id}" is not connected to any other nodes`,
                    severity: "warning"
                });
            }
        });
        
        // Check for missing configurations
        workflow.nodes.forEach(node => {
            if (!node.config || Object.keys(node.config).length === 0) {
                errors.push({
                    message: `Node "${node.id}" is missing configuration`,
                    severity: "error"
                });
            }
        });
        
        return errors;
    }
    
    startContextAnalysis() {
        // Analyze current context and provide smart suggestions
        setInterval(() => {
            if (this.isActive) {
                this.updateSmartSuggestions();
            }
        }, 5000);
    }
    
    updateSmartSuggestions() {
        const suggestionsContainer = document.getElementById('smart-suggestions');
        if (!suggestionsContainer) return;
        
        const currentWorkflow = this.getCurrentWorkflow();
        const suggestions = this.generateSmartSuggestions(currentWorkflow);
        
        suggestionsContainer.innerHTML = '';
        
        suggestions.forEach(suggestion => {
            const item = document.createElement('div');
            item.className = 'smart-suggestion';
            item.innerHTML = `
                <div class="suggestion-title">${suggestion.title}</div>
                <div class="suggestion-description">${suggestion.description}</div>
            `;
            item.onclick = () => suggestion.action();
            suggestionsContainer.appendChild(item);
        });
    }
    
    generateSmartSuggestions(workflow) {
        const suggestions = [];
        
        if (!workflow || !workflow.nodes || workflow.nodes.length === 0) {
            suggestions.push({
                title: "🚀 Start Building",
                description: "Create your first workflow with our AI assistant",
                action: () => this.generateWorkflow()
            });
        } else {
            suggestions.push({
                title: "⚡ Optimize Performance",
                description: "Get AI-powered optimization suggestions",
                action: () => this.optimizeWorkflow()
            });
            
            suggestions.push({
                title: "🔍 Find Issues",
                description: "Scan for potential problems and fixes",
                action: () => this.findErrors()
            });
        }
        
        return suggestions;
    }
    
    analyzeWorkflow(workflowData) {
        // Analyze workflow changes and provide contextual suggestions
        this.currentContext = workflowData;
    }
    
    analyzeSelectedNode(nodeData) {
        // Provide suggestions based on selected node
        if (this.isActive) {
            this.updateSmartSuggestions();
        }
    }
    
    formatTime(timestamp) {
        return new Date(timestamp).toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    }
    
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    showNotification(message, type) {
        if (window.notificationManager) {
            window.notificationManager.show(message, type);
        }
    }
    
    highlightOptimizationOpportunities() {
        // Highlight nodes that can be optimized
        console.log('Highlighting optimization opportunities');
    }
    
    highlightWorkflowFlow() {
        // Animate the workflow flow
        console.log('Highlighting workflow flow');
    }
    
    highlightErrors() {
        // Highlight nodes with errors
        console.log('Highlighting errors');
    }
}

// Initialize AI Assistant
window.aiAssistant = new AIWorkflowAssistant();

// Auto-show AI assistant panel after initialization
setTimeout(() => {
    if (window.aiAssistant) {
        window.aiAssistant.togglePanel();
        // Show welcome message
        setTimeout(() => {
            if (window.aiAssistant.isActive) {
                window.aiAssistant.addMessage("🎉 Welcome! I'm your AI Workflow Assistant. Try saying: 'Create an email automation workflow' or 'Help me build a data backup system'", 'assistant');
            }
        }, 1000);
    }
}, 2000);