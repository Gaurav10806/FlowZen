// User Interface Main Application
class UserWorkflowApp {
    constructor() {
        this.apiManager = null;
        this.currentView = 'dashboard';
        this.workflows = [];
        this.notifications = [];
        
        this.init();
    }
    
    init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.initializeApp());
        } else {
            this.initializeApp();
        }
    }
    
    initializeApp() {
        console.log('🌟 USER MODE - Initializing User Workflow Dashboard');
        
        // Initialize API manager
        this.apiManager = new APIManager();
        
        // Make globally available
        window.userApp = this;
        window.apiManager = this.apiManager;
        
        this.setupNavigation();
        this.setupEventListeners();
        this.setupSearch();
        this.setupNotifications();
        this.loadInitialData();
        
        console.log('✅ User interface initialized successfully');
        this.showToast('Welcome to Workflow Hub! 👋', 'success');
    }
    
    setupNavigation() {
        // Sidebar navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const view = item.getAttribute('href').substring(1);
                this.switchView(view);
                
                // Update active state
                document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
                item.classList.add('active');
            });
        });
    }
    
    setupEventListeners() {
        // Create workflow buttons
        document.querySelectorAll('[data-action="create-workflow"]').forEach(btn => {
            btn.addEventListener('click', () => this.createNewWorkflow());
        });
        
        // FAB button
        const fab = document.getElementById('create-workflow-fab');
        if (fab) {
            fab.addEventListener('click', () => this.createNewWorkflow());
        }
        
        // Workflow actions
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-action="run-workflow"]')) {
                const workflowId = e.target.dataset.workflowId;
                this.runWorkflow(workflowId);
            }
            
            if (e.target.matches('[data-action="edit-workflow"]')) {
                const workflowId = e.target.dataset.workflowId;
                this.editWorkflow(workflowId);
            }
            
            if (e.target.matches('[data-action="pause-workflow"]')) {
                const workflowId = e.target.dataset.workflowId;
                this.pauseWorkflow(workflowId);
            }
            
            if (e.target.matches('[data-action="resume-workflow"]')) {
                const workflowId = e.target.dataset.workflowId;
                this.resumeWorkflow(workflowId);
            }
            
            if (e.target.matches('[data-action="use-template"]')) {
                const templateId = e.target.dataset.templateId;
                this.useTemplate(templateId);
            }
        });
        
        // Profile dropdown
        const userProfile = document.querySelector('.user-profile');
        if (userProfile) {
            userProfile.addEventListener('click', () => this.toggleProfileMenu());
        }
        
        // Notification bell
        const notificationBtn = document.querySelector('[data-action="notifications"]');
        if (notificationBtn) {
            notificationBtn.addEventListener('click', () => this.showNotifications());
        }
    }
    
    setupSearch() {
        const searchInput = document.getElementById('global-search');
        if (searchInput) {
            let searchTimeout;
            
            searchInput.addEventListener('input', (e) => {
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => {
                    this.performSearch(e.target.value);
                }, 300);
            });
            
            searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    this.performSearch(e.target.value);
                }
            });
        }
    }
    
    setupNotifications() {
        // Load notifications
        this.notifications = [
            {
                id: 1,
                type: 'success',
                title: 'Workflow Completed',
                message: 'Email Campaign workflow finished successfully',
                time: '2 minutes ago',
                read: false
            },
            {
                id: 2,
                type: 'warning',
                title: 'Action Required',
                message: 'Data Sync workflow needs attention',
                time: '15 minutes ago',
                read: false
            },
            {
                id: 3,
                type: 'info',
                title: 'New Template',
                message: 'Social Media Automation template available',
                time: '1 hour ago',
                read: true
            }
        ];
        
        this.updateNotificationBadge();
    }
    
    switchView(viewName) {
        // Hide all views
        document.querySelectorAll('.view').forEach(view => {
            view.classList.remove('active');
        });
        
        // Show selected view
        const targetView = document.getElementById(`${viewName}-view`);
        if (targetView) {
            targetView.classList.add('active');
            this.currentView = viewName;
            
            // Load view-specific data
            this.loadViewData(viewName);
        }
    }
    
    async loadViewData(viewName) {
        switch (viewName) {
            case 'dashboard':
                await this.loadDashboardData();
                break;
            case 'workflows':
                await this.loadWorkflowsData();
                break;
            case 'templates':
                await this.loadTemplatesData();
                break;
            case 'history':
                await this.loadHistoryData();
                break;
            case 'integrations':
                await this.loadIntegrationsData();
                break;
        }
    }
    
    async loadDashboardData() {
        try {
            // Load dashboard statistics
            const stats = await this.apiManager.getDashboardStats();
            this.updateDashboardStats(stats);
            
            // Load recent activity
            const activity = await this.apiManager.getRecentActivity();
            this.updateRecentActivity(activity);
            
        } catch (error) {
            console.error('Failed to load dashboard data:', error);
            this.showToast('Failed to load dashboard data', 'error');
        }
    }
    
    async loadWorkflowsData() {
        try {
            const workflows = await this.apiManager.getUserWorkflows();
            this.workflows = workflows;
            this.renderWorkflows(workflows);
            
        } catch (error) {
            console.error('Failed to load workflows:', error);
            this.showToast('Failed to load workflows', 'error');
        }
    }
    
    async loadTemplatesData() {
        try {
            const templates = await this.apiManager.getWorkflowTemplates();
            this.renderTemplates(templates);
            
        } catch (error) {
            console.error('Failed to load templates:', error);
            this.showToast('Failed to load templates', 'error');
        }
    }
    
    async loadHistoryData() {
        try {
            const history = await this.apiManager.getExecutionHistory();
            this.renderExecutionHistory(history);
            
        } catch (error) {
            console.error('Failed to load history:', error);
            this.showToast('Failed to load execution history', 'error');
        }
    }
    
    async loadIntegrationsData() {
        try {
            const integrations = await this.apiManager.getAvailableIntegrations();
            this.renderIntegrations(integrations);
            
        } catch (error) {
            console.error('Failed to load integrations:', error);
            this.showToast('Failed to load integrations', 'error');
        }
    }
    
    updateDashboardStats(stats) {
        // Update stat cards with real data
        const statCards = document.querySelectorAll('.stat-card');
        if (statCards.length >= 4 && stats) {
            // Successful runs
            const successCard = statCards[0];
            successCard.querySelector('h3').textContent = stats.successfulRuns || 156;
            successCard.querySelector('.stat-change').textContent = stats.successChange || '+12% from last week';
            
            // Pending tasks
            const pendingCard = statCards[1];
            pendingCard.querySelector('h3').textContent = stats.pendingTasks || 23;
            pendingCard.querySelector('.stat-change').textContent = stats.pendingNote || '2 require attention';
            
            // Active workflows
            const activeCard = statCards[2];
            activeCard.querySelector('h3').textContent = stats.activeWorkflows || 8;
            activeCard.querySelector('.stat-change').textContent = stats.activeChange || '+2 this week';
            
            // Failed runs
            const failedCard = statCards[3];
            failedCard.querySelector('h3').textContent = stats.failedRuns || 3;
            failedCard.querySelector('.stat-change').textContent = stats.failedNote || 'Needs review';
        }
    }
    
    updateRecentActivity(activities) {
        const activityList = document.querySelector('.activity-list');
        if (!activityList || !activities) return;
        
        activityList.innerHTML = activities.map(activity => `
            <div class="activity-item">
                <div class="activity-icon ${activity.type}">
                    <i class="fas fa-${this.getActivityIcon(activity.type)}"></i>
                </div>
                <div class="activity-content">
                    <h4>${activity.title}</h4>
                    <p>${activity.message}</p>
                    <span class="activity-time">${activity.time}</span>
                </div>
                <div class="activity-actions">
                    <button class="user-btn secondary small" onclick="userApp.handleActivityAction('${activity.id}', '${activity.action}')">
                        ${activity.actionLabel}
                    </button>
                </div>
            </div>
        `).join('');
    }
    
    renderWorkflows(workflows) {
        const workflowsGrid = document.querySelector('.workflows-grid');
        if (!workflowsGrid) return;
        
        workflowsGrid.innerHTML = workflows.map(workflow => `
            <div class="workflow-card">
                <div class="workflow-header">
                    <div class="workflow-status ${workflow.status}">
                        <i class="fas fa-${this.getStatusIcon(workflow.status)}"></i>
                        ${workflow.status.charAt(0).toUpperCase() + workflow.status.slice(1)}
                    </div>
                    <div class="workflow-menu" onclick="userApp.showWorkflowMenu('${workflow.id}')">
                        <i class="fas fa-ellipsis-h"></i>
                    </div>
                </div>
                <div class="workflow-content">
                    <h3>${workflow.name}</h3>
                    <p>${workflow.description}</p>
                    <div class="workflow-stats">
                        <span class="stat">
                            <i class="fas fa-play"></i>
                            ${workflow.executions} runs
                        </span>
                        <span class="stat">
                            <i class="fas fa-clock"></i>
                            Last run: ${workflow.lastRun}
                        </span>
                    </div>
                </div>
                <div class="workflow-actions">
                    ${this.getWorkflowActions(workflow)}
                </div>
            </div>
        `).join('');
    }
    
    getWorkflowActions(workflow) {
        switch (workflow.status) {
            case 'active':
                return `
                    <button class="user-btn secondary small" data-action="run-workflow" data-workflow-id="${workflow.id}">
                        <i class="fas fa-play"></i> Run Now
                    </button>
                    <button class="user-btn secondary small" data-action="edit-workflow" data-workflow-id="${workflow.id}">
                        <i class="fas fa-edit"></i> Edit
                    </button>
                `;
            case 'paused':
                return `
                    <button class="user-btn primary small" data-action="resume-workflow" data-workflow-id="${workflow.id}">
                        <i class="fas fa-play"></i> Resume
                    </button>
                    <button class="user-btn secondary small" data-action="edit-workflow" data-workflow-id="${workflow.id}">
                        <i class="fas fa-edit"></i> Edit
                    </button>
                `;
            case 'error':
                return `
                    <button class="user-btn warning small" data-action="fix-workflow" data-workflow-id="${workflow.id}">
                        <i class="fas fa-wrench"></i> Fix Issues
                    </button>
                    <button class="user-btn secondary small" data-action="edit-workflow" data-workflow-id="${workflow.id}">
                        <i class="fas fa-edit"></i> Edit
                    </button>
                `;
            default:
                return `
                    <button class="user-btn secondary small" data-action="edit-workflow" data-workflow-id="${workflow.id}">
                        <i class="fas fa-edit"></i> Edit
                    </button>
                `;
        }
    }
    
    async createNewWorkflow() {
        this.showToast('Opening workflow builder...', 'info');
        
        // Switch to builder view
        this.switchView('builder');
        
        // Update navigation
        document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
    }
    
    async runWorkflow(workflowId) {
        try {
            this.showToast('Starting workflow execution...', 'info');
            
            const result = await this.apiManager.executeWorkflow(null, workflowId);
            
            this.showToast('Workflow started successfully! 🚀', 'success');
            
            // Refresh workflow data
            if (this.currentView === 'workflows') {
                await this.loadWorkflowsData();
            }
            
        } catch (error) {
            console.error('Failed to run workflow:', error);
            this.showToast('Failed to start workflow: ' + error.message, 'error');
        }
    }
    
    async editWorkflow(workflowId) {
        this.showToast('Opening workflow editor...', 'info');
        
        // In a real implementation, this would open the workflow in the builder
        // For now, we'll just show a message
        setTimeout(() => {
            this.showToast('Workflow editor opened', 'success');
        }, 1000);
    }
    
    async pauseWorkflow(workflowId) {
        try {
            await this.apiManager.pauseWorkflow(workflowId);
            this.showToast('Workflow paused', 'success');
            
            if (this.currentView === 'workflows') {
                await this.loadWorkflowsData();
            }
            
        } catch (error) {
            this.showToast('Failed to pause workflow', 'error');
        }
    }
    
    async resumeWorkflow(workflowId) {
        try {
            await this.apiManager.resumeWorkflow(workflowId);
            this.showToast('Workflow resumed', 'success');
            
            if (this.currentView === 'workflows') {
                await this.loadWorkflowsData();
            }
            
        } catch (error) {
            this.showToast('Failed to resume workflow', 'error');
        }
    }
    
    async useTemplate(templateId) {
        try {
            this.showToast('Creating workflow from template...', 'info');
            
            const workflow = await this.apiManager.createFromTemplate(templateId);
            
            this.showToast('Workflow created from template! 🎉', 'success');
            
            // Switch to workflows view to show the new workflow
            this.switchView('workflows');
            
        } catch (error) {
            this.showToast('Failed to create workflow from template', 'error');
        }
    }
    
    performSearch(query) {
        if (!query.trim()) return;
        
        this.showToast(`Searching for "${query}"...`, 'info');
        
        // Implement search functionality
        // This would filter workflows, templates, etc. based on the query
        
        setTimeout(() => {
            this.showToast(`Found results for "${query}"`, 'success');
        }, 500);
    }
    
    showNotifications() {
        // Create and show notifications panel
        const unreadCount = this.notifications.filter(n => !n.read).length;
        
        if (unreadCount > 0) {
            this.showToast(`You have ${unreadCount} unread notifications`, 'info');
        } else {
            this.showToast('No new notifications', 'info');
        }
    }
    
    updateNotificationBadge() {
        const badge = document.querySelector('.notification-badge');
        const unreadCount = this.notifications.filter(n => !n.read).length;
        
        if (badge) {
            badge.textContent = unreadCount;
            badge.style.display = unreadCount > 0 ? 'block' : 'none';
        }
    }
    
    toggleProfileMenu() {
        this.showToast('Profile menu clicked', 'info');
        // Implement profile menu dropdown
    }
    
    showWorkflowMenu(workflowId) {
        this.showToast(`Workflow menu for ${workflowId}`, 'info');
        // Implement workflow context menu
    }
    
    handleActivityAction(activityId, action) {
        this.showToast(`Handling action: ${action}`, 'info');
        // Implement activity action handling
    }
    
    getActivityIcon(type) {
        const icons = {
            success: 'check',
            warning: 'exclamation',
            error: 'times',
            info: 'info'
        };
        return icons[type] || 'info';
    }
    
    getStatusIcon(status) {
        const icons = {
            active: 'circle',
            paused: 'pause',
            error: 'exclamation-triangle',
            draft: 'edit'
        };
        return icons[status] || 'circle';
    }
    
    showToast(message, type = 'info', duration = 3000) {
        const toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            console.log(`[${type.toUpperCase()}] ${message}`);
            return;
        }
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icon = this.getToastIcon(type);
        toast.innerHTML = `
            <i class="fas fa-${icon}"></i>
            <div class="toast-content">
                <div class="toast-message">${message}</div>
            </div>
            <button class="toast-close" onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        toastContainer.appendChild(toast);
        
        // Auto-remove after duration
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, duration);
    }
    
    getToastIcon(type) {
        const icons = {
            success: 'check-circle',
            error: 'exclamation-circle',
            warning: 'exclamation-triangle',
            info: 'info-circle'
        };
        return icons[type] || 'info-circle';
    }
    
    async loadInitialData() {
        // Load initial dashboard data
        await this.loadDashboardData();
        
        // Simulate some sample data for demo
        this.workflows = [
            {
                id: '1',
                name: 'Customer Email Sequence',
                description: 'Automated welcome email series for new customers',
                status: 'active',
                executions: 45,
                lastRun: '2h ago'
            },
            {
                id: '2',
                name: 'Lead Scoring System',
                description: 'Automatically score and route leads based on behavior',
                status: 'paused',
                executions: 128,
                lastRun: '1d ago'
            },
            {
                id: '3',
                name: 'Social Media Posting',
                description: 'Schedule and post content across social platforms',
                status: 'active',
                executions: 89,
                lastRun: '30m ago'
            },
            {
                id: '4',
                name: 'Inventory Management',
                description: 'Monitor stock levels and reorder automatically',
                status: 'error',
                executions: 67,
                lastRun: '4h ago'
            }
        ];
        
        console.log('✅ Initial data loaded');
    }
}

// Enhanced API Manager for User Interface
class UserAPIManager extends APIManager {
    async getDashboardStats() {
        // Simulate API call
        return {
            successfulRuns: 156,
            successChange: '+12% from last week',
            pendingTasks: 23,
            pendingNote: '2 require attention',
            activeWorkflows: 8,
            activeChange: '+2 this week',
            failedRuns: 3,
            failedNote: 'Needs review'
        };
    }
    
    async getRecentActivity() {
        // Simulate API call
        return [
            {
                id: '1',
                type: 'success',
                title: 'Email Campaign Completed',
                message: 'Successfully sent 1,250 emails to subscribers',
                time: '2 minutes ago',
                action: 'view-details',
                actionLabel: 'View Details'
            },
            {
                id: '2',
                type: 'warning',
                title: 'Data Sync Warning',
                message: 'Some records failed to sync with CRM system',
                time: '15 minutes ago',
                action: 'fix-issues',
                actionLabel: 'Fix Issues'
            },
            {
                id: '3',
                type: 'info',
                title: 'New Template Available',
                message: 'Social Media Automation template is now available',
                time: '1 hour ago',
                action: 'explore',
                actionLabel: 'Explore'
            }
        ];
    }
    
    async getUserWorkflows() {
        // Return sample workflows
        return [
            {
                id: '1',
                name: 'Customer Email Sequence',
                description: 'Automated welcome email series for new customers',
                status: 'active',
                executions: 45,
                lastRun: '2h ago'
            },
            {
                id: '2',
                name: 'Lead Scoring System',
                description: 'Automatically score and route leads based on behavior',
                status: 'paused',
                executions: 128,
                lastRun: '1d ago'
            }
        ];
    }
    
    async pauseWorkflow(workflowId) {
        // Simulate API call
        return { success: true };
    }
    
    async resumeWorkflow(workflowId) {
        // Simulate API call
        return { success: true };
    }
    
    async createFromTemplate(templateId) {
        // Simulate API call
        return { id: 'new-workflow-id', name: 'New Workflow from Template' };
    }
}

// Initialize the user application
const userApp = new UserWorkflowApp();