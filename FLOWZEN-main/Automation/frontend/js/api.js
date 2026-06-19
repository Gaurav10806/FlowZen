// API Integration - Real Django Backend Connectivity
class APIManager {
    constructor() {
        this.baseURL = '/api';
        this.csrfToken = this.getCSRFToken();
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

        try {
            const response = await fetch(url, mergedOptions);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API Request failed:', error);
            throw error;
        }
    }

    // Workflow operations
    async saveWorkflow(workflowData, workflowId = null) {
        const payload = {
            name: workflowData.name || 'Untitled Workflow',
            description: workflowData.description || '',
            nodes: workflowData.nodes,
            edges: workflowData.edges,
            is_active: true
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

    async executeWorkflow(workflowId, inputData = {}) {
        return await this.request(`/workflows/${workflowId}/execute/`, {
            method: 'POST',
            body: JSON.stringify({
                input_data: inputData
            })
        });
    }

    async getWorkflows() {
        return await this.request('/workflows/');
    }

    async deleteWorkflow(workflowId) {
        return await this.request(`/workflows/${workflowId}/`, {
            method: 'DELETE'
        });
    }

    // Execution operations
    async getExecution(executionId) {
        return await this.request(`/executions/${executionId}/`);
    }

    async getExecutions(workflowId = null) {
        const endpoint = workflowId ? `/workflows/${workflowId}/executions/` : '/executions/';
        return await this.request(endpoint);
    }

    // Node operations
    async getNodeTypes() {
        return await this.request('/node-types/');
    }

    async validateNodeConfig(nodeType, config) {
        return await this.request('/nodes/validate/', {
            method: 'POST',
            body: JSON.stringify({
                type: nodeType,
                config: config
            })
        });
    }

    // OAuth operations (for Gmail)
    async initiateGmailOAuth() {
        return await this.request('/oauth/gmail/initiate/', {
            method: 'POST'
        });
    }

    async getGmailOAuthStatus() {
        return await this.request('/oauth/gmail/status/');
    }

    async testGmailConnection() {
        return await this.request('/oauth/gmail/test/', {
            method: 'POST'
        });
    }

    // Utility methods
    showError(message) {
        if (window.Toast) {
            window.Toast.error("Error", message);
            return;
        }
        console.error("API Error:", message);
        alert(message); // Fallback
    }

    showSuccess(message) {
        if (window.Toast) {
            window.Toast.success("Success", message);
            return;
        }
        console.log("API Success:", message);
        alert(message); // Fallback
    }

    showLoading(message = 'Loading...') {
        // Create loading modal
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = 'loading-modal';
        modal.setAttribute('data-bs-backdrop', 'static');
        modal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content">
                    <div class="modal-body text-center py-4">
                        <div class="spinner-border text-primary mb-3" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                        <p class="mb-0">${message}</p>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();

        return {
            hide: () => {
                bsModal.hide();
                modal.addEventListener('hidden.bs.modal', () => {
                    modal.remove();
                });
            }
        };
    }
}

// Export for use in other modules
window.APIManager = APIManager;