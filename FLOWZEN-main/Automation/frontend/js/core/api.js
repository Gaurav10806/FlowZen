// Enhanced API Integration - Real Django Backend Connectivity
class APIManager {
    constructor() {
        this.baseURL = '/api/v1';
        this.csrfToken = this.getCSRFToken();
        this.requestQueue = [];
        this.isOnline = navigator.onLine;
        
        this.setupNetworkMonitoring();
    }
    
    getCSRFToken() {
        // Try multiple methods to get CSRF token
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'csrftoken') {
                return value;
            }
        }
        
        // Try meta tag
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag) {
            return metaTag.getAttribute('content');
        }
        
        // Try hidden input
        const hiddenInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (hiddenInput) {
            return hiddenInput.value;
        }
        
        return null;
    }
    
    setupNetworkMonitoring() {
        window.addEventListener('online', () => {
            this.isOnline = true;
            this.processQueuedRequests();
        });
        
        window.addEventListener('offline', () => {
            this.isOnline = false;
        });
    }
    
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
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
        
        // Queue request if offline
        if (!this.isOnline && options.method !== 'GET') {
            return this.queueRequest(endpoint, mergedOptions);
        }
        
        try {
            const response = await fetch(url, mergedOptions);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new APIError(
                    errorData.detail || `HTTP ${response.status}: ${response.statusText}`,
                    response.status,
                    errorData
                );
            }
            
            const data = await response.json();
            return data;
            
        } catch (error) {
            if (error instanceof APIError) {
                throw error;
            }
            
            console.error('API Request failed:', error);
            throw new APIError('Network error: ' + error.message, 0, { originalError: error });
        }
    }
    
    queueRequest(endpoint, options) {
        return new Promise((resolve, reject) => {
            this.requestQueue.push({
                endpoint,
                options,
                resolve,
                reject,
                timestamp: Date.now()
            });
        });
    }
    
    async processQueuedRequests() {
        const queue = [...this.requestQueue];
        this.requestQueue = [];
        
        for (const queuedRequest of queue) {
            try {
                const result = await this.request(queuedRequest.endpoint, queuedRequest.options);
                queuedRequest.resolve(result);
            } catch (error) {
                queuedRequest.reject(error);
            }
        }
    }
    
    // Workflow operations
    async saveWorkflow(workflowData, workflowId = null) {
        const payload = {
            name: workflowData.name || 'Untitled Workflow',
            description: workflowData.description || '',
            graph: {
                nodes: workflowData.nodes || [],
                edges: workflowData.edges || []
            },
            is_active: workflowData.is_active !== undefined ? workflowData.is_active : true,
            metadata: workflowData.metadata || {}
        };
        
        if (workflowId) {
            // Update existing workflow
            return await this.request(`/workflows/${workflowId}/`, {
                method: 'PUT',
                body: JSON.stringify(payload)
            });
        } else {
            // Create new workflow
            return await this.request('/workflows/', {
                method: 'POST',
                body: JSON.stringify(payload)
            });
        }
    }
    
    async loadWorkflow(workflowId) {
        return await this.request(`/workflows/${workflowId}/`);
    }
    
    async deleteWorkflow(workflowId) {
        return await this.request(`/workflows/${workflowId}/`, {
            method: 'DELETE'
        });
    }
    
    async listWorkflows(filters = {}) {
        const params = new URLSearchParams(filters);
        return await this.request(`/workflows/?${params}`);
    }
    
    async duplicateWorkflow(workflowId) {
        return await this.request(`/workflows/${workflowId}/duplicate/`, {
            method: 'POST'
        });
    }
    
    // Execution operations
    async executeWorkflow(workflowData = null, workflowId = null, inputData = {}) {
        if (workflowId) {
            // Execute existing workflow
            return await this.request(`/workflows/${workflowId}/execute/`, {
                method: 'POST',
                body: JSON.stringify({
                    input_data: inputData,
                    execution_mode: 'async'
                })
            });
        } else if (workflowData) {
            // Execute workflow data directly
            return await this.request('/workflows/execute/', {
                method: 'POST',
                body: JSON.stringify({
                    workflow_data: workflowData,
                    input_data: inputData,
                    execution_mode: 'async'
                })
            });
        } else {
            throw new APIError('Either workflowId or workflowData must be provided', 400);
        }
    }
    
    async getExecutionStatus(executionId) {
        return await this.request(`/executions/${executionId}/`);
    }
    
    async getExecutionLogs(executionId) {
        return await this.request(`/executions/${executionId}/logs/`);
    }
    
    async cancelExecution(executionId) {
        return await this.request(`/executions/${executionId}/cancel/`, {
            method: 'POST'
        });
    }
    
    async listExecutions(workflowId = null, filters = {}) {
        const params = new URLSearchParams(filters);
        if (workflowId) {
            params.append('workflow', workflowId);
        }
        return await this.request(`/executions/?${params}`);
    }
    
    // Template operations
    async getWorkflowTemplates(category = null) {
        const params = category ? `?category=${category}` : '';
        return await this.request(`/templates/${params}`);
    }
    
    async createFromTemplate(templateId, customizations = {}) {
        return await this.request(`/templates/${templateId}/create/`, {
            method: 'POST',
            body: JSON.stringify(customizations)
        });
    }
    
    async saveAsTemplate(workflowId, templateData) {
        return await this.request(`/workflows/${workflowId}/save-as-template/`, {
            method: 'POST',
            body: JSON.stringify(templateData)
        });
    }
    
    // Credential operations
    async listCredentials(type = null) {
        const params = type ? `?type=${type}` : '';
        return await this.request(`/credentials/${params}`);
    }
    
    async createCredential(credentialData) {
        return await this.request('/credentials/', {
            method: 'POST',
            body: JSON.stringify(credentialData)
        });
    }
    
    async updateCredential(credentialId, credentialData) {
        return await this.request(`/credentials/${credentialId}/`, {
            method: 'PUT',
            body: JSON.stringify(credentialData)
        });
    }
    
    async deleteCredential(credentialId) {
        return await this.request(`/credentials/${credentialId}/`, {
            method: 'DELETE'
        });
    }
    
    async testCredential(credentialId) {
        return await this.request(`/credentials/${credentialId}/test/`, {
            method: 'POST'
        });
    }
    
    // Node configuration and validation
    async validateNodeConfig(nodeType, config) {
        return await this.request('/nodes/validate/', {
            method: 'POST',
            body: JSON.stringify({
                node_type: nodeType,
                config: config
            })
        });
    }
    
    async getNodeSchema(nodeType) {
        return await this.request(`/nodes/${nodeType}/schema/`);
    }
    
    async testNodeExecution(nodeType, config, inputData = {}) {
        return await this.request('/nodes/test/', {
            method: 'POST',
            body: JSON.stringify({
                node_type: nodeType,
                config: config,
                input_data: inputData
            })
        });
    }
    
    // Dashboard and analytics
    async getDashboardStats(timeRange = '7d') {
        return await this.request(`/dashboard/stats/?range=${timeRange}`);
    }
    
    async getRecentActivity(limit = 10) {
        return await this.request(`/dashboard/activity/?limit=${limit}`);
    }
    
    async getExecutionMetrics(workflowId = null, timeRange = '7d') {
        const params = new URLSearchParams({ range: timeRange });
        if (workflowId) {
            params.append('workflow', workflowId);
        }
        return await this.request(`/dashboard/metrics/?${params}`);
    }
    
    // Organization and team operations (if applicable)
    async getOrganizationInfo() {
        return await this.request('/organizations/current/');
    }
    
    async listTeamMembers() {
        return await this.request('/teams/members/');
    }
    
    async inviteTeamMember(email, role = 'member') {
        return await this.request('/teams/invite/', {
            method: 'POST',
            body: JSON.stringify({ email, role })
        });
    }
    
    // File upload operations
    async uploadFile(file, purpose = 'workflow') {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('purpose', purpose);
        
        return await this.request('/files/upload/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': this.csrfToken
                // Don't set Content-Type for FormData
            },
            body: formData
        });
    }
    
    // Webhook operations
    async createWebhook(workflowId, config = {}) {
        return await this.request(`/workflows/${workflowId}/webhook/`, {
            method: 'POST',
            body: JSON.stringify(config)
        });
    }
    
    async getWebhookUrl(workflowId) {
        const response = await this.request(`/workflows/${workflowId}/webhook/`);
        return response.webhook_url;
    }
    
    // Search operations
    async searchWorkflows(query, filters = {}) {
        const params = new URLSearchParams({ q: query, ...filters });
        return await this.request(`/search/workflows/?${params}`);
    }
    
    async searchTemplates(query, filters = {}) {
        const params = new URLSearchParams({ q: query, ...filters });
        return await this.request(`/search/templates/?${params}`);
    }
    
    // Batch operations
    async batchExecuteWorkflows(workflowIds, inputData = {}) {
        return await this.request('/workflows/batch-execute/', {
            method: 'POST',
            body: JSON.stringify({
                workflow_ids: workflowIds,
                input_data: inputData
            })
        });
    }
    
    async batchDeleteWorkflows(workflowIds) {
        return await this.request('/workflows/batch-delete/', {
            method: 'POST',
            body: JSON.stringify({
                workflow_ids: workflowIds
            })
        });
    }
    
    // Real-time updates (WebSocket simulation)
    subscribeToUpdates(workflowId, callback) {
        // Simulate real-time updates with polling
        const pollInterval = setInterval(async () => {
            try {
                const status = await this.getExecutionStatus(workflowId);
                callback(status);
                
                if (status.status === 'completed' || status.status === 'failed') {
                    clearInterval(pollInterval);
                }
            } catch (error) {
                console.error('Failed to poll execution status:', error);
            }
        }, 2000);
        
        return () => clearInterval(pollInterval);
    }
    
    // Utility methods
    async healthCheck() {
        try {
            const response = await fetch('/api/health/', {
                method: 'GET',
                credentials: 'same-origin'
            });
            return response.ok;
        } catch (error) {
            return false;
        }
    }
    
    async getSystemInfo() {
        return await this.request('/system/info/');
    }
    
    // Error handling helpers
    handleError(error) {
        if (error instanceof APIError) {
            switch (error.status) {
                case 401:
                    // Unauthorized - redirect to login
                    window.location.href = '/accounts/login/';
                    break;
                case 403:
                    // Forbidden - show permission error
                    this.showError('You do not have permission to perform this action');
                    break;
                case 404:
                    // Not found
                    this.showError('The requested resource was not found');
                    break;
                case 429:
                    // Rate limited
                    this.showError('Too many requests. Please try again later');
                    break;
                case 500:
                    // Server error
                    this.showError('Server error. Please try again later');
                    break;
                default:
                    this.showError(error.message);
            }
        } else {
            this.showError('An unexpected error occurred');
        }
    }
    
    showError(message) {
        // Dispatch custom event for error display
        document.dispatchEvent(new CustomEvent('apiError', {
            detail: { message }
        }));
    }
    
    // Cache management
    clearCache() {
        // Clear any cached data
        if ('caches' in window) {
            caches.delete('api-cache');
        }
    }
    
    // Request retry logic
    async requestWithRetry(endpoint, options = {}, maxRetries = 3) {
        let lastError;
        
        for (let attempt = 0; attempt <= maxRetries; attempt++) {
            try {
                return await this.request(endpoint, options);
            } catch (error) {
                lastError = error;
                
                if (attempt < maxRetries && this.shouldRetry(error)) {
                    const delay = Math.pow(2, attempt) * 1000; // Exponential backoff
                    await new Promise(resolve => setTimeout(resolve, delay));
                    continue;
                }
                
                break;
            }
        }
        
        throw lastError;
    }
    
    shouldRetry(error) {
        // Retry on network errors or 5xx server errors
        return error.status === 0 || (error.status >= 500 && error.status < 600);
    }
}

// Custom API Error class
class APIError extends Error {
    constructor(message, status = 0, data = {}) {
        super(message);
        this.name = 'APIError';
        this.status = status;
        this.data = data;
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { APIManager, APIError };
}