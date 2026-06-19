// Workflow Templates & Quick Start System
class WorkflowTemplates {
    constructor() {
        this.templates = new Map();
        this.categories = new Map();
        this.templateModal = null;
        
        this.init();
    }
    
    init() {
        this.loadDefaultTemplates();
        this.setupTemplateModal();
        this.setupStyles();
    }
    
    setupStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .template-modal {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.5);
                z-index: 10000;
                display: flex;
                align-items: center;
                justify-content: center;
                opacity: 0;
                visibility: hidden;
                transition: all 0.3s ease;
            }
            
            .template-modal.show {
                opacity: 1;
                visibility: visible;
            }
            
            .template-modal-content {
                background: white;
                border-radius: 12px;
                box-shadow: 0 25px 50px rgba(0, 0, 0, 0.25);
                width: 90%;
                max-width: 1000px;
                max-height: 80vh;
                overflow: hidden;
                transform: scale(0.9) translateY(-20px);
                transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            }
            
            .template-modal.show .template-modal-content {
                transform: scale(1) translateY(0);
            }
            
            .template-modal-header {
                padding: 24px;
                border-bottom: 1px solid #e5e7eb;
                display: flex;
                align-items: center;
                justify-content: space-between;
            }
            
            .template-modal-title {
                font-size: 20px;
                font-weight: 600;
                color: #1f2937;
                margin: 0;
            }
            
            .template-modal-close {
                background: none;
                border: none;
                color: #6b7280;
                cursor: pointer;
                font-size: 24px;
                padding: 4px;
                border-radius: 4px;
                transition: all 0.2s ease;
            }
            
            .template-modal-close:hover {
                background: #f3f4f6;
                color: #374151;
            }
            
            .template-modal-body {
                padding: 0;
                max-height: 60vh;
                overflow-y: auto;
            }
            
            .template-categories {
                display: flex;
                border-bottom: 1px solid #e5e7eb;
                background: #f9fafb;
            }
            
            .template-category {
                padding: 16px 24px;
                cursor: pointer;
                font-weight: 500;
                color: #6b7280;
                border-bottom: 2px solid transparent;
                transition: all 0.2s ease;
            }
            
            .template-category:hover {
                color: #374151;
                background: #f3f4f6;
            }
            
            .template-category.active {
                color: #4f46e5;
                border-bottom-color: #4f46e5;
                background: white;
            }
            
            .template-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 20px;
                padding: 24px;
            }
            
            .template-card {
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                overflow: hidden;
                transition: all 0.2s ease;
                cursor: pointer;
                background: white;
            }
            
            .template-card:hover {
                border-color: #4f46e5;
                box-shadow: 0 4px 12px rgba(79, 70, 229, 0.15);
                transform: translateY(-2px);
            }
            
            .template-card-image {
                height: 120px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                position: relative;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 24px;
            }
            
            .template-card-content {
                padding: 16px;
            }
            
            .template-card-title {
                font-size: 16px;
                font-weight: 600;
                color: #1f2937;
                margin: 0 0 8px 0;
            }
            
            .template-card-description {
                font-size: 14px;
                color: #6b7280;
                line-height: 1.4;
                margin: 0 0 12px 0;
            }
            
            .template-card-meta {
                display: flex;
                align-items: center;
                justify-content: space-between;
                font-size: 12px;
                color: #9ca3af;
            }
            
            .template-card-nodes {
                display: flex;
                align-items: center;
                gap: 4px;
            }
            
            .template-card-difficulty {
                padding: 2px 8px;
                border-radius: 12px;
                font-weight: 500;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            .template-card-difficulty.beginner {
                background: #d1fae5;
                color: #065f46;
            }
            
            .template-card-difficulty.intermediate {
                background: #fef3c7;
                color: #92400e;
            }
            
            .template-card-difficulty.advanced {
                background: #fee2e2;
                color: #991b1b;
            }
            
            .template-search {
                padding: 16px 24px;
                border-bottom: 1px solid #e5e7eb;
                background: #f9fafb;
            }
            
            .template-search-input {
                width: 100%;
                padding: 12px 16px;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                font-size: 14px;
                background: white;
                transition: all 0.2s ease;
            }
            
            .template-search-input:focus {
                outline: none;
                border-color: #4f46e5;
                box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
            }
            
            .template-empty {
                text-align: center;
                padding: 60px 24px;
                color: #6b7280;
            }
            
            .template-empty i {
                font-size: 48px;
                margin-bottom: 16px;
                opacity: 0.5;
            }
            
            .quick-start-button {
                position: fixed;
                bottom: 30px;
                left: 30px;
                background: #4f46e5;
                color: white;
                border: none;
                border-radius: 50px;
                padding: 16px 24px;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                box-shadow: 0 8px 25px rgba(79, 70, 229, 0.3);
                transition: all 0.3s ease;
                z-index: 1000;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            .quick-start-button:hover {
                background: #4338ca;
                transform: translateY(-2px);
                box-shadow: 0 12px 35px rgba(79, 70, 229, 0.4);
            }
            
            .quick-start-button i {
                font-size: 16px;
            }
        `;
        document.head.appendChild(style);
    }
    
    loadDefaultTemplates() {
        // AI & Automation Templates
        this.addTemplate('ai-content-generator', {
            name: 'AI Content Generator',
            description: 'Generate blog posts, social media content, and marketing copy using OpenAI',
            category: 'ai',
            difficulty: 'beginner',
            nodes: 4,
            icon: 'fas fa-robot',
            workflow: {
                nodes: [
                    {
                        id: 'trigger',
                        type: 'webhook',
                        position: { x: 100, y: 200 },
                        config: { method: 'POST', path: '/generate-content' }
                    },
                    {
                        id: 'openai',
                        type: 'openai',
                        position: { x: 300, y: 200 },
                        config: { 
                            model: 'gpt-4',
                            prompt: 'Generate engaging content about: {{input.topic}}',
                            temperature: 0.7
                        }
                    },
                    {
                        id: 'format',
                        type: 'json',
                        position: { x: 500, y: 200 },
                        config: { operation: 'format' }
                    },
                    {
                        id: 'response',
                        type: 'http_response',
                        position: { x: 700, y: 200 },
                        config: { status: 200 }
                    }
                ],
                edges: [
                    { source: 'trigger', target: 'openai' },
                    { source: 'openai', target: 'format' },
                    { source: 'format', target: 'response' }
                ]
            }
        });
        
        this.addTemplate('email-automation', {
            name: 'Email Marketing Automation',
            description: 'Automated email campaigns with personalization and tracking',
            category: 'marketing',
            difficulty: 'intermediate',
            nodes: 6,
            icon: 'fas fa-envelope',
            workflow: {
                nodes: [
                    {
                        id: 'schedule',
                        type: 'schedule',
                        position: { x: 100, y: 200 },
                        config: { cron: '0 9 * * 1' }
                    },
                    {
                        id: 'database',
                        type: 'postgres',
                        position: { x: 300, y: 200 },
                        config: { query: 'SELECT * FROM subscribers WHERE active = true' }
                    },
                    {
                        id: 'personalize',
                        type: 'openai',
                        position: { x: 500, y: 200 },
                        config: { 
                            model: 'gpt-3.5-turbo',
                            prompt: 'Personalize this email for {{name}}: {{template}}'
                        }
                    },
                    {
                        id: 'send_email',
                        type: 'gmail',
                        position: { x: 700, y: 200 },
                        config: { subject: 'Weekly Newsletter' }
                    },
                    {
                        id: 'track',
                        type: 'http',
                        position: { x: 900, y: 200 },
                        config: { url: '/api/track-email', method: 'POST' }
                    },
                    {
                        id: 'log',
                        type: 'json',
                        position: { x: 1100, y: 200 },
                        config: { operation: 'log' }
                    }
                ],
                edges: [
                    { source: 'schedule', target: 'database' },
                    { source: 'database', target: 'personalize' },
                    { source: 'personalize', target: 'send_email' },
                    { source: 'send_email', target: 'track' },
                    { source: 'track', target: 'log' }
                ]
            }
        });
        
        this.addTemplate('data-processing', {
            name: 'Data Processing Pipeline',
            description: 'Extract, transform, and load data from multiple sources',
            category: 'data',
            difficulty: 'advanced',
            nodes: 8,
            icon: 'fas fa-database',
            workflow: {
                nodes: [
                    {
                        id: 'webhook',
                        type: 'webhook',
                        position: { x: 100, y: 200 },
                        config: { method: 'POST', path: '/process-data' }
                    },
                    {
                        id: 'validate',
                        type: 'if',
                        position: { x: 300, y: 200 },
                        config: { condition: 'data.length > 0' }
                    },
                    {
                        id: 'extract',
                        type: 'json',
                        position: { x: 500, y: 150 },
                        config: { operation: 'extract', fields: ['id', 'name', 'email'] }
                    },
                    {
                        id: 'transform',
                        type: 'json',
                        position: { x: 700, y: 150 },
                        config: { operation: 'transform' }
                    },
                    {
                        id: 'enrich',
                        type: 'http',
                        position: { x: 900, y: 150 },
                        config: { url: '/api/enrich-data', method: 'POST' }
                    },
                    {
                        id: 'store',
                        type: 'postgres',
                        position: { x: 1100, y: 150 },
                        config: { query: 'INSERT INTO processed_data VALUES (...)' }
                    },
                    {
                        id: 'error',
                        type: 'http_response',
                        position: { x: 500, y: 250 },
                        config: { status: 400, message: 'Invalid data' }
                    },
                    {
                        id: 'success',
                        type: 'http_response',
                        position: { x: 1300, y: 150 },
                        config: { status: 200, message: 'Data processed successfully' }
                    }
                ],
                edges: [
                    { source: 'webhook', target: 'validate' },
                    { source: 'validate', target: 'extract', condition: 'success' },
                    { source: 'validate', target: 'error', condition: 'error' },
                    { source: 'extract', target: 'transform' },
                    { source: 'transform', target: 'enrich' },
                    { source: 'enrich', target: 'store' },
                    { source: 'store', target: 'success' }
                ]
            }
        });
        
        this.addTemplate('social-media-bot', {
            name: 'Social Media Bot',
            description: 'Automated social media posting with AI-generated content',
            category: 'social',
            difficulty: 'intermediate',
            nodes: 5,
            icon: 'fas fa-share-alt',
            workflow: {
                nodes: [
                    {
                        id: 'schedule',
                        type: 'schedule',
                        position: { x: 100, y: 200 },
                        config: { cron: '0 */4 * * *' }
                    },
                    {
                        id: 'generate',
                        type: 'openai',
                        position: { x: 300, y: 200 },
                        config: { 
                            model: 'gpt-4',
                            prompt: 'Generate an engaging social media post about {{topic}}'
                        }
                    },
                    {
                        id: 'image',
                        type: 'http',
                        position: { x: 500, y: 200 },
                        config: { url: '/api/generate-image', method: 'POST' }
                    },
                    {
                        id: 'post',
                        type: 'http',
                        position: { x: 700, y: 200 },
                        config: { url: '/api/social-media/post', method: 'POST' }
                    },
                    {
                        id: 'analytics',
                        type: 'http',
                        position: { x: 900, y: 200 },
                        config: { url: '/api/analytics/track', method: 'POST' }
                    }
                ],
                edges: [
                    { source: 'schedule', target: 'generate' },
                    { source: 'generate', target: 'image' },
                    { source: 'image', target: 'post' },
                    { source: 'post', target: 'analytics' }
                ]
            }
        });
        
        // Add categories
        this.addCategory('ai', 'AI & Machine Learning', 'fas fa-brain');
        this.addCategory('marketing', 'Marketing Automation', 'fas fa-bullhorn');
        this.addCategory('data', 'Data Processing', 'fas fa-database');
        this.addCategory('social', 'Social Media', 'fas fa-share-alt');
        this.addCategory('ecommerce', 'E-commerce', 'fas fa-shopping-cart');
        this.addCategory('productivity', 'Productivity', 'fas fa-tasks');
    }
    
    addTemplate(id, template) {
        this.templates.set(id, {
            id,
            ...template,
            createdAt: new Date()
        });
    }
    
    addCategory(id, name, icon) {
        this.categories.set(id, { id, name, icon });
    }
    
    setupTemplateModal() {
        const modal = document.createElement('div');
        modal.className = 'template-modal';
        modal.innerHTML = `
            <div class="template-modal-content">
                <div class="template-modal-header">
                    <h2 class="template-modal-title">
                        <i class="fas fa-layer-group"></i>
                        Workflow Templates
                    </h2>
                    <button class="template-modal-close">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="template-search">
                    <input type="text" class="template-search-input" placeholder="Search templates...">
                </div>
                <div class="template-categories"></div>
                <div class="template-modal-body">
                    <div class="template-grid"></div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        this.templateModal = modal;
        
        // Setup event listeners
        modal.querySelector('.template-modal-close').addEventListener('click', () => {
            this.hideTemplateModal();
        });
        
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.hideTemplateModal();
            }
        });
        
        modal.querySelector('.template-search-input').addEventListener('input', (e) => {
            this.filterTemplates(e.target.value);
        });
        
        this.renderCategories();
        this.renderTemplates();
    }
    
    renderCategories() {
        const container = this.templateModal.querySelector('.template-categories');
        container.innerHTML = '';
        
        // Add "All" category
        const allCategory = document.createElement('div');
        allCategory.className = 'template-category active';
        allCategory.textContent = 'All Templates';
        allCategory.addEventListener('click', () => {
            this.selectCategory(null);
        });
        container.appendChild(allCategory);
        
        // Add other categories
        this.categories.forEach(category => {
            const categoryEl = document.createElement('div');
            categoryEl.className = 'template-category';
            categoryEl.innerHTML = `
                <i class="${category.icon}"></i>
                ${category.name}
            `;
            categoryEl.addEventListener('click', () => {
                this.selectCategory(category.id);
            });
            container.appendChild(categoryEl);
        });
    }
    
    renderTemplates(categoryFilter = null, searchFilter = '') {
        const container = this.templateModal.querySelector('.template-grid');
        container.innerHTML = '';
        
        let filteredTemplates = Array.from(this.templates.values());
        
        if (categoryFilter) {
            filteredTemplates = filteredTemplates.filter(t => t.category === categoryFilter);
        }
        
        if (searchFilter) {
            const search = searchFilter.toLowerCase();
            filteredTemplates = filteredTemplates.filter(t => 
                t.name.toLowerCase().includes(search) ||
                t.description.toLowerCase().includes(search)
            );
        }
        
        if (filteredTemplates.length === 0) {
            container.innerHTML = `
                <div class="template-empty">
                    <i class="fas fa-search"></i>
                    <h3>No templates found</h3>
                    <p>Try adjusting your search or category filter</p>
                </div>
            `;
            return;
        }
        
        filteredTemplates.forEach(template => {
            const card = document.createElement('div');
            card.className = 'template-card';
            card.innerHTML = `
                <div class="template-card-image">
                    <i class="${template.icon}"></i>
                </div>
                <div class="template-card-content">
                    <h3 class="template-card-title">${template.name}</h3>
                    <p class="template-card-description">${template.description}</p>
                    <div class="template-card-meta">
                        <div class="template-card-nodes">
                            <i class="fas fa-circle"></i>
                            ${template.nodes} nodes
                        </div>
                        <div class="template-card-difficulty ${template.difficulty}">
                            ${template.difficulty}
                        </div>
                    </div>
                </div>
            `;
            
            card.addEventListener('click', () => {
                this.useTemplate(template);
            });
            
            container.appendChild(card);
        });
    }
    
    selectCategory(categoryId) {
        // Update active category
        this.templateModal.querySelectorAll('.template-category').forEach(cat => {
            cat.classList.remove('active');
        });
        
        if (categoryId) {
            const categoryEl = Array.from(this.templateModal.querySelectorAll('.template-category'))
                .find(el => el.textContent.includes(this.categories.get(categoryId).name));
            if (categoryEl) categoryEl.classList.add('active');
        } else {
            this.templateModal.querySelector('.template-category').classList.add('active');
        }
        
        this.renderTemplates(categoryId);
    }
    
    filterTemplates(search) {
        const activeCategory = this.templateModal.querySelector('.template-category.active');
        const categoryId = activeCategory && activeCategory.textContent !== 'All Templates' 
            ? Array.from(this.categories.values()).find(c => 
                activeCategory.textContent.includes(c.name))?.id 
            : null;
        
        this.renderTemplates(categoryId, search);
    }
    
    showTemplateModal() {
        this.templateModal.classList.add('show');
        this.renderTemplates();
    }
    
    hideTemplateModal() {
        this.templateModal.classList.remove('show');
    }
    
    useTemplate(template) {
        this.hideTemplateModal();
        
        // Clear current workflow
        if (window.nodeManager) {
            window.nodeManager.clearWorkflow();
        }
        
        // Load template workflow
        if (template.workflow) {
            this.loadWorkflow(template.workflow);
        }
        
        // Show success notification
        if (window.notificationManager) {
            window.notificationManager.success(
                `Template "${template.name}" loaded successfully!`,
                { duration: 3000 }
            );
        }
    }
    
    loadWorkflow(workflow) {
        // Create nodes
        workflow.nodes.forEach(nodeData => {
            if (window.nodeManager) {
                window.nodeManager.createNode(nodeData.type, nodeData);
            }
        });
        
        // Create connections
        setTimeout(() => {
            workflow.edges.forEach(edgeData => {
                if (window.edgeManager) {
                    window.edgeManager.createEdge(
                        edgeData.source,
                        edgeData.target,
                        edgeData.condition
                    );
                }
            });
        }, 100);
        
        // Fit to view
        setTimeout(() => {
            if (window.advancedCanvas) {
                window.advancedCanvas.fitToView();
            }
        }, 200);
    }
    
    createQuickStartButton() {
        const button = document.createElement('button');
        button.className = 'quick-start-button';
        button.innerHTML = `
            <i class="fas fa-magic"></i>
            Quick Start
        `;
        
        button.addEventListener('click', () => {
            this.showTemplateModal();
        });
        
        document.body.appendChild(button);
        return button;
    }
    
    // Export workflow as template
    saveAsTemplate(name, description, category = 'custom') {
        if (!window.nodeManager) return;
        
        const nodes = Array.from(window.nodeManager.nodes.values()).map(node => ({
            id: node.id,
            type: node.type,
            position: node.position,
            config: node.config
        }));
        
        const edges = window.edgeManager ? 
            Array.from(window.edgeManager.edges.values()).map(edge => ({
                source: edge.sourceNode,
                target: edge.targetNode,
                condition: edge.condition
            })) : [];
        
        const template = {
            name,
            description,
            category,
            difficulty: 'custom',
            nodes: nodes.length,
            icon: 'fas fa-user',
            workflow: { nodes, edges }
        };
        
        const templateId = `custom_${Date.now()}`;
        this.addTemplate(templateId, template);
        
        if (window.notificationManager) {
            window.notificationManager.success(
                `Template "${name}" saved successfully!`,
                { duration: 3000 }
            );
        }
        
        return templateId;
    }
}

// Create global instance
window.workflowTemplates = new WorkflowTemplates();

// Create quick start button
document.addEventListener('DOMContentLoaded', () => {
    window.workflowTemplates.createQuickStartButton();
});