// Comprehensive Workflow Management System
class WorkflowManager {
    constructor() {
        this.workflows = new Map();
        this.currentWorkflow = null;
        this.isModified = false;
        this.autoSaveInterval = null;
        this.versionHistory = [];
        this.collaborators = new Map();
        
        this.init();
    }
    
    init() {
        this.setupAutoSave();
        this.setupKeyboardShortcuts();
        this.setupBeforeUnload();
        this.loadWorkflowList();
    }
    
    setupAutoSave() {
        this.autoSaveInterval = setInterval(() => {
            if (this.isModified && this.currentWorkflow) {
                this.autoSave();
            }
        }, 30000); // Auto-save every 30 seconds
    }
    
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }
            
            if (e.ctrlKey || e.metaKey) {
                switch (e.key) {
                    case 's':
                        e.preventDefault();
                        this.saveWorkflow();
                        break;
                    case 'n':
                        e.preventDefault();
                        this.createNewWorkflow();
                        break;
                    case 'o':
                        e.preventDefault();
                        this.showOpenDialog();
                        break;
                    case 'z':
                        e.preventDefault();
                        if (e.shiftKey) {
                            this.redo();
                        } else {
                            this.undo();
                        }
                        break;
                    case 'y':
                        e.preventDefault();
                        this.redo();
                        break;
                }
            }
        });
    }
    
    setupBeforeUnload() {
        window.addEventListener('beforeunload', (e) => {
            if (this.isModified) {
                e.preventDefault();
                e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
                return e.returnValue;
            }
        });
    }
    
    async createNewWorkflow(template = null) {
        try {
            // Check for unsaved changes
            if (this.isModified) {
                const shouldSave = await this.confirmSaveChanges();
                if (shouldSave === null) return; // User cancelled
                if (shouldSave) await this.saveWorkflow();
            }
            
            const workflow = {
                id: this.generateId(),
                name: 'Untitled Workflow',
                description: '',
                nodes: [],
                edges: [],
                variables: {},
                settings: {
                    timeout: 300,
                    retryOnFailure: false,
                    continueOnFailure: false,
                    saveDataExecution: true
                },
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
                version: 1,
                status: 'draft'
            };
            
            // Apply template if provided
            if (template) {
                workflow.name = template.name;
                workflow.description = template.description;
                workflow.nodes = [...template.nodes];
                workflow.edges = [...template.edges];
                workflow.variables = { ...template.variables };
            }
            
            this.currentWorkflow = workflow;
            this.workflows.set(workflow.id, workflow);
            this.isModified = false;
            
            // Clear canvas and load workflow
            this.clearCanvas();
            this.loadWorkflowToCanvas(workflow);
            
            // Update UI
            this.updateWorkflowTitle();
            this.updateWorkflowStatus();
            
            // Show success notification
            if (window.notificationManager) {
                window.notificationManager.success(
                    template ? `Workflow created from template: ${template.name}` : 'New workflow created',
                    { duration: 3000 }
                );
            }
            
            return workflow;
        } catch (error) {
            console.error('Failed to create new workflow:', error);
            if (window.notificationManager) {
                window.notificationManager.error('Failed to create new workflow: ' + error.message);
            }
            throw error;
        }
    }
    
    async saveWorkflow(saveAs = false) {
        try {
            if (!this.currentWorkflow) {
                throw new Error('No workflow to save');
            }
            
            // Show loading state
            this.showSaveProgress('Saving workflow...');
            
            // Collect current workflow data from canvas
            const workflowData = this.collectWorkflowData();
            
            // Update workflow object
            Object.assign(this.currentWorkflow, workflowData, {
                updated_at: new Date().toISOString(),
                version: this.currentWorkflow.version + 1
            });
            
            // Save to backend
            const response = await this.apiCall('/api/workflows/', {
                method: this.currentWorkflow.id ? 'PUT' : 'POST',
                body: JSON.stringify(this.currentWorkflow)
            });
            
            // Update workflow with server response
            if (response.id) {
                this.currentWorkflow.id = response.id;
            }
            
            this.isModified = false;
            
            // Update UI
            this.updateWorkflowTitle();
            this.updateWorkflowStatus();
            this.hideSaveProgress();
            
            // Add to version history
            this.addToVersionHistory();
            
            // Show success notification
            if (window.notificationManager) {
                window.notificationManager.success('Workflow saved successfully!', {
                    duration: 3000,
                    actions: [
                        {
                            label: 'View History',
                            handler: 'workflowManager.showVersionHistory()'
                        }
                    ]
                });
            }
            
            return this.currentWorkflow;
        } catch (error) {
            this.hideSaveProgress();
            console.error('Failed to save workflow:', error);
            if (window.notificationManager) {
                window.notificationManager.error('Failed to save workflow: ' + error.message);
            }
            throw error;
        }
    }
    
    async loadWorkflow(workflowId) {
        try {
            // Check for unsaved changes
            if (this.isModified) {
                const shouldSave = await this.confirmSaveChanges();
                if (shouldSave === null) return; // User cancelled
                if (shouldSave) await this.saveWorkflow();
            }
            
            // Show loading state
            this.showLoadProgress('Loading workflow...');
            
            // Load from backend
            const workflow = await this.apiCall(`/api/workflows/${workflowId}/`);
            
            this.currentWorkflow = workflow;
            this.workflows.set(workflow.id, workflow);
            this.isModified = false;
            
            // Load workflow to canvas
            this.clearCanvas();
            this.loadWorkflowToCanvas(workflow);
            
            // Update UI
            this.updateWorkflowTitle();
            this.updateWorkflowStatus();
            this.hideLoadProgress();
            
            // Load version history
            this.loadVersionHistory(workflowId);
            
            // Show success notification
            if (window.notificationManager) {
                window.notificationManager.success(`Workflow "${workflow.name}" loaded successfully!`);
            }
            
            return workflow;
        } catch (error) {
            this.hideLoadProgress();
            console.error('Failed to load workflow:', error);
            if (window.notificationManager) {
                window.notificationManager.error('Failed to load workflow: ' + error.message);
            }
            throw error;
        }
    }
    
    async duplicateWorkflow(workflowId = null) {
        try {
            const sourceWorkflow = workflowId ? 
                await this.apiCall(`/api/workflows/${workflowId}/`) : 
                this.currentWorkflow;
            
            if (!sourceWorkflow) {
                throw new Error('No workflow to duplicate');
            }
            
            const duplicatedWorkflow = {
                ...sourceWorkflow,
                id: this.generateId(),
                name: `${sourceWorkflow.name} (Copy)`,
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
                version: 1,
                status: 'draft'
            };
            
            // Remove server-specific fields
            delete duplicatedWorkflow.id;
            
            this.currentWorkflow = duplicatedWorkflow;
            this.workflows.set(duplicatedWorkflow.id, duplicatedWorkflow);
            this.isModified = true;
            
            // Load to canvas
            this.clearCanvas();
            this.loadWorkflowToCanvas(duplicatedWorkflow);
            
            // Update UI
            this.updateWorkflowTitle();
            this.updateWorkflowStatus();
            
            if (window.notificationManager) {
                window.notificationManager.success('Workflow duplicated successfully!');
            }
            
            return duplicatedWorkflow;
        } catch (error) {
            console.error('Failed to duplicate workflow:', error);
            if (window.notificationManager) {
                window.notificationManager.error('Failed to duplicate workflow: ' + error.message);
            }
            throw error;
        }
    }
    
    async deleteWorkflow(workflowId) {
        try {
            const workflow = this.workflows.get(workflowId) || 
                await this.apiCall(`/api/workflows/${workflowId}/`);
            
            const confirmed = await window.notificationManager?.confirm(
                `Are you sure you want to delete "${workflow.name}"? This action cannot be undone.`,
                'Delete Workflow'
            );
            
            if (!confirmed) return;
            
            // Delete from backend
            await this.apiCall(`/api/workflows/${workflowId}/`, {
                method: 'DELETE'
            });
            
            // Remove from local storage
            this.workflows.delete(workflowId);
            
            // If this is the current workflow, create a new one
            if (this.currentWorkflow?.id === workflowId) {
                await this.createNewWorkflow();
            }
            
            if (window.notificationManager) {
                window.notificationManager.success('Workflow deleted successfully!');
            }
            
            // Refresh workflow list
            this.loadWorkflowList();
            
        } catch (error) {
            console.error('Failed to delete workflow:', error);
            if (window.notificationManager) {
                window.notificationManager.error('Failed to delete workflow: ' + error.message);
            }
            throw error;
        }
    }
    
    async executeWorkflow(workflowId = null) {
        try {
            const workflow = workflowId ? 
                this.workflows.get(workflowId) || await this.apiCall(`/api/workflows/${workflowId}/`) :
                this.currentWorkflow;
            
            if (!workflow) {
                throw new Error('No workflow to execute');
            }
            
            // Validate workflow before execution
            const validation = this.validateWorkflow(workflow);
            if (!validation.isValid) {
                throw new Error(`Workflow validation failed: ${validation.errors.join(', ')}`);
            }
            
            // Show execution monitor
            if (window.executionMonitor) {
                window.executionMonitor.showPanel();
            }
            
            // Start execution
            const execution = await this.apiCall('/api/executions/', {
                method: 'POST',
                body: JSON.stringify({
                    workflow_id: workflow.id,
                    trigger_data: {}
                })
            });
            
            if (window.notificationManager) {
                window.notificationManager.success(
                    `Workflow "${workflow.name}" execution started!`,
                    {
                        duration: 4000,
                        actions: [
                            {
                                label: 'View Progress',
                                handler: 'executionMonitor.showPanel()'
                            }
                        ]
                    }
                );
            }
            
            return execution;
        } catch (error) {
            console.error('Failed to execute workflow:', error);
            if (window.notificationManager) {
                window.notificationManager.error('Failed to execute workflow: ' + error.message);
            }
            throw error;
        }
    }
    
    validateWorkflow(workflow) {
        const errors = [];
        
        // Check for nodes
        if (!workflow.nodes || workflow.nodes.length === 0) {
            errors.push('Workflow must contain at least one node');
        }
        
        // Check for trigger nodes
        const triggerNodes = workflow.nodes.filter(node => 
            node.type === 'webhook' || node.type === 'schedule' || node.type === 'manual'
        );
        
        if (triggerNodes.length === 0) {
            errors.push('Workflow must contain at least one trigger node');
        }
        
        // Check for disconnected nodes
        const connectedNodes = new Set();
        workflow.edges.forEach(edge => {
            connectedNodes.add(edge.source);
            connectedNodes.add(edge.target);
        });
        
        const disconnectedNodes = workflow.nodes.filter(node => 
            !connectedNodes.has(node.id) && !triggerNodes.includes(node)
        );
        
        if (disconnectedNodes.length > 0) {
            errors.push(`${disconnectedNodes.length} nodes are not connected to the workflow`);
        }
        
        // Validate node configurations
        workflow.nodes.forEach(node => {
            const nodeValidation = this.validateNode(node);
            if (!nodeValidation.isValid) {
                errors.push(`Node "${node.name}": ${nodeValidation.errors.join(', ')}`);
            }
        });
        
        return {
            isValid: errors.length === 0,
            errors
        };
    }
    
    validateNode(node) {
        const errors = [];
        
        // Check required fields
        if (!node.name || node.name.trim() === '') {
            errors.push('Node name is required');
        }
        
        if (!node.type) {
            errors.push('Node type is required');
        }
        
        // Type-specific validation
        switch (node.type) {
            case 'http':
                if (!node.config?.url) {
                    errors.push('URL is required for HTTP nodes');
                }
                break;
            case 'gmail':
                if (!node.config?.credentials) {
                    errors.push('Credentials are required for Gmail nodes');
                }
                break;
            case 'openai':
                if (!node.config?.prompt) {
                    errors.push('Prompt is required for OpenAI nodes');
                }
                break;
        }
        
        return {
            isValid: errors.length === 0,
            errors
        };
    }
    
    collectWorkflowData() {
        // Collect nodes from canvas
        const nodes = [];
        if (window.nodeManager) {
            window.nodeManager.nodes.forEach(node => {
                nodes.push({
                    id: node.id,
                    name: node.name,
                    type: node.type,
                    position: node.position,
                    config: node.config || {},
                    credentials: node.credentials,
                    notes: node.notes || ''
                });
            });
        }
        
        // Collect edges from canvas
        const edges = [];
        if (window.edgeManager) {
            window.edgeManager.edges.forEach(edge => {
                edges.push({
                    id: edge.id,
                    source: edge.sourceNode,
                    target: edge.targetNode,
                    sourcePort: edge.sourcePort || 'output',
                    targetPort: edge.targetPort || 'input',
                    condition: edge.condition || 'always'
                });
            });
        }
        
        return {
            nodes,
            edges,
            name: this.getWorkflowName(),
            description: this.getWorkflowDescription()
        };
    }
    
    loadWorkflowToCanvas(workflow) {
        // Load nodes
        if (window.nodeManager && workflow.nodes) {
            workflow.nodes.forEach(nodeData => {
                window.nodeManager.createNode(nodeData.type, nodeData);
            });
        }
        
        // Load edges (with delay to ensure nodes are created)
        if (window.edgeManager && workflow.edges) {
            setTimeout(() => {
                workflow.edges.forEach(edgeData => {
                    window.edgeManager.createEdge(
                        edgeData.source,
                        edgeData.target,
                        edgeData.condition
                    );
                });
            }, 100);
        }
        
        // Fit to view
        setTimeout(() => {
            if (window.advancedCanvas) {
                window.advancedCanvas.fitToView();
            }
        }, 200);
    }
    
    clearCanvas() {
        // Clear nodes
        if (window.nodeManager) {
            window.nodeManager.clearAll();
        }
        
        // Clear edges
        if (window.edgeManager) {
            window.edgeManager.clearAll();
        }
    }
    
    async loadWorkflowList() {
        try {
            const workflows = await this.apiCall('/api/workflows/');
            
            workflows.forEach(workflow => {
                this.workflows.set(workflow.id, workflow);
            });
            
            // Update workflow selector if it exists
            this.updateWorkflowSelector();
            
        } catch (error) {
            console.error('Failed to load workflow list:', error);
        }
    }
    
    updateWorkflowSelector() {
        const selector = document.querySelector('#workflow-selector');
        if (!selector) return;
        
        selector.innerHTML = '<option value="">Select a workflow...</option>';
        
        this.workflows.forEach(workflow => {
            const option = document.createElement('option');
            option.value = workflow.id;
            option.textContent = workflow.name;
            option.selected = this.currentWorkflow?.id === workflow.id;
            selector.appendChild(option);
        });
    }
    
    showOpenDialog() {
        if (window.notificationManager) {
            const workflowList = Array.from(this.workflows.values())
                .sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at))
                .slice(0, 10)
                .map(workflow => `
                    <div class="workflow-item" onclick="workflowManager.loadWorkflow('${workflow.id}')">
                        <div class="workflow-info">
                            <h4>${workflow.name}</h4>
                            <p>${workflow.description || 'No description'}</p>
                            <small>Updated: ${new Date(workflow.updated_at).toLocaleDateString()}</small>
                        </div>
                        <div class="workflow-actions">
                            <button onclick="event.stopPropagation(); workflowManager.duplicateWorkflow('${workflow.id}')">
                                <i class="fas fa-copy"></i>
                            </button>
                            <button onclick="event.stopPropagation(); workflowManager.deleteWorkflow('${workflow.id}')">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                `).join('');
            
            window.notificationManager.modal(`
                <div class="open-workflow-dialog">
                    <h3>Open Workflow</h3>
                    <div class="workflow-list">
                        ${workflowList || '<p>No workflows found</p>'}
                    </div>
                </div>
            `, {
                title: 'Open Workflow',
                size: 'large',
                buttons: [
                    { label: 'Cancel', type: 'secondary' }
                ]
            });
        }
    }
    
    async confirmSaveChanges() {
        if (window.notificationManager) {
            return await window.notificationManager.modal(`
                <div class="save-changes-dialog">
                    <i class="fas fa-exclamation-triangle" style="font-size: 48px; color: #f59e0b; margin-bottom: 16px;"></i>
                    <h3>Unsaved Changes</h3>
                    <p>You have unsaved changes in your workflow. What would you like to do?</p>
                </div>
            `, {
                title: 'Unsaved Changes',
                buttons: [
                    { label: 'Discard Changes', type: 'secondary', value: false },
                    { label: 'Cancel', type: 'secondary', value: null },
                    { label: 'Save Changes', type: 'primary', value: true }
                ]
            }).then(result => result?.value);
        }
        return false;
    }
    
    async autoSave() {
        try {
            if (!this.currentWorkflow) return;
            
            const workflowData = this.collectWorkflowData();
            
            // Save to localStorage as backup
            localStorage.setItem('workflow_autosave', JSON.stringify({
                ...this.currentWorkflow,
                ...workflowData,
                autosaved_at: new Date().toISOString()
            }));
            
            // Show subtle auto-save indicator
            this.showAutoSaveIndicator();
            
        } catch (error) {
            console.error('Auto-save failed:', error);
        }
    }
    
    loadAutoSave() {
        try {
            const autosaved = localStorage.getItem('workflow_autosave');
            if (autosaved) {
                const workflow = JSON.parse(autosaved);
                
                if (window.notificationManager) {
                    window.notificationManager.modal(`
                        <div class="autosave-recovery">
                            <i class="fas fa-history" style="font-size: 48px; color: #3b82f6; margin-bottom: 16px;"></i>
                            <h3>Auto-saved Workflow Found</h3>
                            <p>We found an auto-saved version of "${workflow.name}" from ${new Date(workflow.autosaved_at).toLocaleString()}.</p>
                            <p>Would you like to restore it?</p>
                        </div>
                    `, {
                        title: 'Restore Auto-save',
                        buttons: [
                            { label: 'Ignore', type: 'secondary' },
                            { label: 'Restore', type: 'primary' }
                        ]
                    }).then(result => {
                        if (result && result.label === 'Restore') {
                            this.currentWorkflow = workflow;
                            this.loadWorkflowToCanvas(workflow);
                            this.updateWorkflowTitle();
                            this.isModified = true;
                        }
                        localStorage.removeItem('workflow_autosave');
                    });
                }
            }
        } catch (error) {
            console.error('Failed to load auto-save:', error);
        }
    }
    
    // Version History Management
    addToVersionHistory() {
        if (!this.currentWorkflow) return;
        
        const version = {
            id: this.generateId(),
            workflow_id: this.currentWorkflow.id,
            version: this.currentWorkflow.version,
            name: this.currentWorkflow.name,
            created_at: new Date().toISOString(),
            data: JSON.stringify(this.currentWorkflow)
        };
        
        this.versionHistory.unshift(version);
        
        // Keep only last 20 versions
        if (this.versionHistory.length > 20) {
            this.versionHistory = this.versionHistory.slice(0, 20);
        }
    }
    
    async loadVersionHistory(workflowId) {
        try {
            this.versionHistory = await this.apiCall(`/api/workflows/${workflowId}/versions/`);
        } catch (error) {
            console.error('Failed to load version history:', error);
        }
    }
    
    showVersionHistory() {
        if (window.notificationManager) {
            const historyList = this.versionHistory.map(version => `
                <div class="version-item" onclick="workflowManager.restoreVersion('${version.id}')">
                    <div class="version-info">
                        <h4>Version ${version.version}</h4>
                        <p>${version.name}</p>
                        <small>${new Date(version.created_at).toLocaleString()}</small>
                    </div>
                    <div class="version-actions">
                        <button onclick="event.stopPropagation(); workflowManager.compareVersion('${version.id}')">
                            <i class="fas fa-code-branch"></i>
                        </button>
                    </div>
                </div>
            `).join('');
            
            window.notificationManager.modal(`
                <div class="version-history-dialog">
                    <h3>Version History</h3>
                    <div class="version-list">
                        ${historyList || '<p>No version history available</p>'}
                    </div>
                </div>
            `, {
                title: 'Version History',
                size: 'large',
                buttons: [
                    { label: 'Close', type: 'secondary' }
                ]
            });
        }
    }
    
    async restoreVersion(versionId) {
        try {
            const version = this.versionHistory.find(v => v.id === versionId);
            if (!version) throw new Error('Version not found');
            
            const confirmed = await window.notificationManager?.confirm(
                `Restore to version ${version.version}? Current changes will be lost.`,
                'Restore Version'
            );
            
            if (!confirmed) return;
            
            const workflowData = JSON.parse(version.data);
            this.currentWorkflow = workflowData;
            this.loadWorkflowToCanvas(workflowData);
            this.updateWorkflowTitle();
            this.isModified = true;
            
            if (window.notificationManager) {
                window.notificationManager.success(`Restored to version ${version.version}`);
            }
            
        } catch (error) {
            console.error('Failed to restore version:', error);
            if (window.notificationManager) {
                window.notificationManager.error('Failed to restore version: ' + error.message);
            }
        }
    }
    
    // Undo/Redo functionality
    undo() {
        // Implement undo functionality
        console.log('Undo operation');
    }
    
    redo() {
        // Implement redo functionality
        console.log('Redo operation');
    }
    
    // UI Update Methods
    updateWorkflowTitle() {
        const titleElements = document.querySelectorAll('.workflow-name, #workflow-name');
        titleElements.forEach(element => {
            if (element.tagName === 'INPUT') {
                element.value = this.currentWorkflow?.name || 'Untitled Workflow';
                if (this.isModified) {
                    element.value += ' *';
                }
            } else {
                element.textContent = this.currentWorkflow?.name || 'Untitled Workflow';
                if (this.isModified) {
                    element.textContent += ' *';
                }
            }
        });
    }
    
    updateWorkflowStatus() {
        const statusElements = document.querySelectorAll('.workflow-status');
        statusElements.forEach(element => {
            if (this.currentWorkflow) {
                element.textContent = this.isModified ? 'Modified' : 'Saved';
                element.className = `workflow-status ${this.isModified ? 'modified' : 'saved'}`;
            } else {
                element.textContent = 'No workflow';
                element.className = 'workflow-status empty';
            }
        });
    }
    
    showSaveProgress(message) {
        // Show save progress indicator
        const indicator = document.createElement('div');
        indicator.className = 'save-progress';
        indicator.innerHTML = `
            <div class="spinner"></div>
            <span>${message}</span>
        `;
        document.body.appendChild(indicator);
    }
    
    hideSaveProgress() {
        const indicator = document.querySelector('.save-progress');
        if (indicator) {
            indicator.remove();
        }
    }
    
    showLoadProgress(message) {
        this.showSaveProgress(message);
    }
    
    hideLoadProgress() {
        this.hideSaveProgress();
    }
    
    showAutoSaveIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'autosave-indicator';
        indicator.innerHTML = '<i class="fas fa-check"></i> Auto-saved';
        document.body.appendChild(indicator);
        
        setTimeout(() => {
            indicator.classList.add('fade-out');
            setTimeout(() => indicator.remove(), 300);
        }, 2000);
    }
    
    // Utility Methods
    generateId() {
        return 'wf_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    
    getWorkflowName() {
        const nameInput = document.querySelector('.workflow-name, #workflow-name');
        return nameInput ? nameInput.value.replace(' *', '') : 'Untitled Workflow';
    }
    
    getWorkflowDescription() {
        const descInput = document.querySelector('#workflow-description');
        return descInput ? descInput.value : '';
    }
    
    async apiCall(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken()
            },
            credentials: 'same-origin'
        };
        
        const mergedOptions = {
            ...defaultOptions,
            ...options,
            headers: {
                ...defaultOptions.headers,
                ...options.headers
            }
        };
        
        const response = await fetch(url, mergedOptions);
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
        }
        
        return response.json();
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
    
    // Public API Methods
    markAsModified() {
        this.isModified = true;
        this.updateWorkflowTitle();
        this.updateWorkflowStatus();
    }
    
    getCurrentWorkflow() {
        return this.currentWorkflow;
    }
    
    getWorkflowList() {
        return Array.from(this.workflows.values());
    }
    
    isWorkflowModified() {
        return this.isModified;
    }
}

// Create global instance
window.workflowManager = new WorkflowManager();

// Load auto-save on page load
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        window.workflowManager.loadAutoSave();
    }, 1000);
});