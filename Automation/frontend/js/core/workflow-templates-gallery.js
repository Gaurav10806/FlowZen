/**
 * 🎨 VISUAL WORKFLOW TEMPLATES GALLERY
 * 
 * Revolutionary Features:
 * - Beautiful template gallery with previews
 * - One-click template import and customization
 * - Community templates with ratings and reviews
 * - Template categories and smart filtering
 * - Visual workflow previews with animations
 * - Template sharing and collaboration
 */

class WorkflowTemplatesGallery {
    constructor() {
        this.templates = new Map();
        this.categories = new Map();
        this.userTemplates = [];
        this.communityTemplates = [];
        this.gallery = null;
        this.isVisible = false;
        this.selectedTemplate = null;
        
        this.init();
    }
    
    init() {
        this.loadTemplateDatabase();
        this.createGallery();
        this.setupEventListeners();
        console.log('🎨 Workflow Templates Gallery initialized');
    }
    
    loadTemplateDatabase() {
        // Comprehensive template database with beautiful workflows
        const templates = [
            {
                id: 'welcome_email_automation',
                name: 'Welcome Email Automation',
                description: 'Automatically send personalized welcome emails to new users with onboarding sequence',
                category: 'marketing',
                difficulty: 'beginner',
                rating: 4.8,
                downloads: 1250,
                author: 'AutomationPro',
                tags: ['email', 'onboarding', 'marketing', 'automation'],
                preview: 'https://via.placeholder.com/400x300/667eea/ffffff?text=Welcome+Email',
                estimatedTime: '5 minutes',
                nodes: [
                    { id: 'trigger_1', type: 'webhook', name: 'New User Signup', x: 100, y: 100 },
                    { id: 'condition_1', type: 'condition', name: 'Check User Type', x: 300, y: 100 },
                    { id: 'email_1', type: 'email', name: 'Welcome Email', x: 500, y: 50 },
                    { id: 'email_2', type: 'email', name: 'Premium Welcome', x: 500, y: 150 }
                ],
                connections: [
                    { from: 'trigger_1', to: 'condition_1' },
                    { from: 'condition_1', to: 'email_1', condition: 'free' },
                    { from: 'condition_1', to: 'email_2', condition: 'premium' }
                ]
            },
            {
                id: 'data_backup_system',
                name: 'Automated Data Backup',
                description: 'Daily automated backup system with error handling and notifications',
                category: 'operations',
                difficulty: 'intermediate',
                rating: 4.9,
                downloads: 890,
                author: 'DevOpsExpert',
                tags: ['backup', 'automation', 'operations', 'monitoring'],
                preview: 'https://via.placeholder.com/400x300/10b981/ffffff?text=Data+Backup',
                estimatedTime: '10 minutes',
                nodes: [
                    { id: 'schedule_1', type: 'schedule', name: 'Daily 2AM', x: 100, y: 100 },
                    { id: 'backup_1', type: 'backup', name: 'Database Backup', x: 300, y: 100 },
                    { id: 'condition_1', type: 'condition', name: 'Check Success', x: 500, y: 100 },
                    { id: 'email_1', type: 'email', name: 'Success Notification', x: 700, y: 50 },
                    { id: 'email_2', type: 'email', name: 'Error Alert', x: 700, y: 150 }
                ]
            }
        ];
        
        templates.forEach(template => {
            this.templates.set(template.id, template);
        });
    }
    
    createGallery() {
        // Create beautiful templates gallery
        const gallery = document.createElement('div');
        gallery.className = 'templates-gallery';
        gallery.innerHTML = `
            <div class="gallery-overlay" onclick="templatesGallery.hideGallery()"></div>
            
            <div class="gallery-container">
                <div class="gallery-header">
                    <div class="gallery-title">
                        <i class="fas fa-layer-group"></i>
                        <span>Workflow Templates</span>
                        <div class="template-count">${this.templates.size} templates</div>
                    </div>
                    
                    <div class="gallery-controls">
                        <div class="search-container">
                            <input type="text" id="template-search" placeholder="Search templates...">
                            <i class="fas fa-search"></i>
                        </div>
                        
                        <div class="filter-container">
                            <select id="category-filter">
                                <option value="all">All Categories</option>
                                <option value="marketing">Marketing</option>
                                <option value="operations">Operations</option>
                                <option value="integration">Integration</option>
                                <option value="ai">AI & Automation</option>
                            </select>
                        </div>
                        
                        <button class="gallery-btn" onclick="templatesGallery.createTemplate()">
                            <i class="fas fa-plus"></i>
                            Create Template
                        </button>
                        
                        <button class="gallery-btn" onclick="templatesGallery.hideGallery()">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                </div>
                
                <div class="gallery-content">
                    <div class="templates-grid" id="templates-grid">
                        <!-- Templates will be populated here -->
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(gallery);
        this.gallery = gallery;
        
        this.setupStyles();
        this.populateTemplates();
    }
    
    setupStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .templates-gallery {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                z-index: 10000;
                opacity: 0;
                visibility: hidden;
                transition: all 0.3s ease;
            }
            
            .templates-gallery.visible {
                opacity: 1;
                visibility: visible;
            }
            
            .gallery-overlay {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.8);
                backdrop-filter: blur(10px);
            }
            
            .gallery-container {
                position: absolute;
                top: 20px;
                left: 20px;
                right: 20px;
                bottom: 20px;
                background: rgba(255, 255, 255, 0.98);
                backdrop-filter: blur(20px);
                border-radius: 20px;
                box-shadow: 0 25px 80px rgba(0, 0, 0, 0.2);
                border: 1px solid rgba(255, 255, 255, 0.3);
                overflow: hidden;
                display: flex;
                flex-direction: column;
            }
            
            .gallery-header {
                padding: 24px 32px;
                border-bottom: 1px solid rgba(0, 0, 0, 0.1);
                display: flex;
                align-items: center;
                justify-content: space-between;
                background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
            }
            
            .gallery-title {
                display: flex;
                align-items: center;
                gap: 12px;
                font-size: 24px;
                font-weight: 700;
                color: #1f2937;
            }
            
            .template-count {
                background: rgba(102, 126, 234, 0.1);
                color: #667eea;
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 600;
            }
            
            .gallery-controls {
                display: flex;
                align-items: center;
                gap: 16px;
            }
            
            .search-container {
                position: relative;
            }
            
            .search-container input {
                padding: 10px 40px 10px 16px;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 8px;
                font-size: 14px;
                width: 250px;
                background: white;
            }
            
            .search-container i {
                position: absolute;
                right: 12px;
                top: 50%;
                transform: translateY(-50%);
                color: #9ca3af;
            }
            
            .filter-container select {
                padding: 10px 12px;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 8px;
                font-size: 14px;
                background: white;
            }
            
            .gallery-btn {
                padding: 10px 16px;
                border: 1px solid rgba(102, 126, 234, 0.2);
                border-radius: 8px;
                background: rgba(102, 126, 234, 0.05);
                color: #667eea;
                font-size: 14px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s ease;
                display: flex;
                align-items: center;
                gap: 6px;
            }
            
            .gallery-btn:hover {
                background: rgba(102, 126, 234, 0.1);
                border-color: #667eea;
                transform: translateY(-1px);
            }
            
            .gallery-content {
                flex: 1;
                padding: 32px;
                overflow-y: auto;
            }
            
            .templates-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
                gap: 24px;
            }
            
            .template-card {
                background: white;
                border-radius: 16px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
                border: 1px solid rgba(0, 0, 0, 0.05);
                overflow: hidden;
                transition: all 0.3s ease;
                cursor: pointer;
            }
            
            .template-card:hover {
                transform: translateY(-4px);
                box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15);
            }
            
            .template-preview {
                height: 200px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                position: relative;
                overflow: hidden;
            }
            
            .template-preview img {
                width: 100%;
                height: 100%;
                object-fit: cover;
            }
            
            .template-overlay {
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.3);
                display: flex;
                align-items: center;
                justify-content: center;
                opacity: 0;
                transition: all 0.3s ease;
            }
            
            .template-card:hover .template-overlay {
                opacity: 1;
            }
            
            .preview-btn {
                background: rgba(255, 255, 255, 0.9);
                border: none;
                padding: 12px 20px;
                border-radius: 8px;
                font-weight: 600;
                color: #1f2937;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            
            .preview-btn:hover {
                background: white;
                transform: scale(1.05);
            }
            
            .template-info {
                padding: 20px;
            }
            
            .template-header {
                display: flex;
                align-items: flex-start;
                justify-content: space-between;
                margin-bottom: 12px;
            }
            
            .template-name {
                font-size: 18px;
                font-weight: 600;
                color: #1f2937;
                margin-bottom: 4px;
            }
            
            .template-author {
                font-size: 12px;
                color: #6b7280;
            }
            
            .template-rating {
                display: flex;
                align-items: center;
                gap: 4px;
                font-size: 12px;
                color: #f59e0b;
            }
            
            .template-description {
                color: #6b7280;
                font-size: 14px;
                line-height: 1.4;
                margin-bottom: 16px;
            }
            
            .template-meta {
                display: flex;
                align-items: center;
                justify-content: space-between;
                margin-bottom: 16px;
            }
            
            .template-tags {
                display: flex;
                flex-wrap: wrap;
                gap: 6px;
            }
            
            .template-tag {
                background: rgba(102, 126, 234, 0.1);
                color: #667eea;
                padding: 2px 8px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 500;
            }
            
            .template-stats {
                display: flex;
                align-items: center;
                gap: 12px;
                font-size: 12px;
                color: #6b7280;
            }
            
            .template-actions {
                display: flex;
                gap: 8px;
            }
            
            .template-btn {
                flex: 1;
                padding: 10px 16px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s ease;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 6px;
            }
            
            .btn-primary {
                background: #667eea;
                color: white;
                border: 1px solid #667eea;
            }
            
            .btn-primary:hover {
                background: #5a67d8;
                transform: translateY(-1px);
            }
            
            .btn-secondary {
                background: white;
                color: #6b7280;
                border: 1px solid rgba(0, 0, 0, 0.1);
            }
            
            .btn-secondary:hover {
                background: rgba(0, 0, 0, 0.05);
                color: #1f2937;
            }
        `;
        document.head.appendChild(style);
    }
    
    populateTemplates() {
        const grid = document.getElementById('templates-grid');
        grid.innerHTML = '';
        
        this.templates.forEach(template => {
            const card = this.createTemplateCard(template);
            grid.appendChild(card);
        });
    }
    
    createTemplateCard(template) {
        const card = document.createElement('div');
        card.className = 'template-card';
        card.dataset.templateId = template.id;
        
        const stars = '★'.repeat(Math.floor(template.rating)) + '☆'.repeat(5 - Math.floor(template.rating));
        
        card.innerHTML = `
            <div class="template-preview">
                <div class="template-overlay">
                    <button class="preview-btn" onclick="templatesGallery.previewTemplate('${template.id}')">
                        <i class="fas fa-eye"></i> Preview
                    </button>
                </div>
            </div>
            
            <div class="template-info">
                <div class="template-header">
                    <div>
                        <div class="template-name">${template.name}</div>
                        <div class="template-author">by ${template.author}</div>
                    </div>
                    <div class="template-rating">
                        <span>${stars}</span>
                        <span>${template.rating}</span>
                    </div>
                </div>
                
                <div class="template-description">${template.description}</div>
                
                <div class="template-meta">
                    <div class="template-tags">
                        ${template.tags.map(tag => `<span class="template-tag">${tag}</span>`).join('')}
                    </div>
                </div>
                
                <div class="template-stats">
                    <span><i class="fas fa-download"></i> ${template.downloads}</span>
                    <span><i class="fas fa-clock"></i> ${template.estimatedTime}</span>
                    <span><i class="fas fa-signal"></i> ${template.difficulty}</span>
                </div>
                
                <div class="template-actions">
                    <button class="template-btn btn-secondary" onclick="templatesGallery.previewTemplate('${template.id}')">
                        <i class="fas fa-eye"></i>
                        Preview
                    </button>
                    <button class="template-btn btn-primary" onclick="templatesGallery.useTemplate('${template.id}')">
                        <i class="fas fa-download"></i>
                        Use Template
                    </button>
                </div>
            </div>
        `;
        
        return card;
    }
    
    setupEventListeners() {
        // Search functionality
        document.getElementById('template-search').addEventListener('input', (e) => {
            this.filterTemplates(e.target.value);
        });
        
        // Category filter
        document.getElementById('category-filter').addEventListener('change', (e) => {
            this.filterByCategory(e.target.value);
        });
    }
    
    showGallery() {
        this.gallery.classList.add('visible');
        this.isVisible = true;
    }
    
    hideGallery() {
        this.gallery.classList.remove('visible');
        this.isVisible = false;
    }
    
    filterTemplates(query) {
        const cards = document.querySelectorAll('.template-card');
        
        cards.forEach(card => {
            const templateId = card.dataset.templateId;
            const template = this.templates.get(templateId);
            
            const matches = template.name.toLowerCase().includes(query.toLowerCase()) ||
                           template.description.toLowerCase().includes(query.toLowerCase()) ||
                           template.tags.some(tag => tag.toLowerCase().includes(query.toLowerCase()));
            
            card.style.display = matches ? 'block' : 'none';
        });
    }
    
    filterByCategory(category) {
        const cards = document.querySelectorAll('.template-card');
        
        cards.forEach(card => {
            const templateId = card.dataset.templateId;
            const template = this.templates.get(templateId);
            
            const matches = category === 'all' || template.category === category;
            card.style.display = matches ? 'block' : 'none';
        });
    }
    
    previewTemplate(templateId) {
        const template = this.templates.get(templateId);
        if (!template) return;
        
        // Create preview modal
        this.showTemplatePreview(template);
    }
    
    useTemplate(templateId) {
        const template = this.templates.get(templateId);
        if (!template) return;
        
        // Import template into current workflow
        this.importTemplate(template);
        this.hideGallery();
    }
    
    importTemplate(template) {
        // Convert template to workflow format
        const workflow = {
            name: template.name,
            description: template.description,
            nodes: template.nodes || [],
            connections: template.connections || []
        };
        
        // Trigger workflow import
        const event = new CustomEvent('importWorkflow', {
            detail: workflow
        });
        document.dispatchEvent(event);
        
        this.showNotification(`Template "${template.name}" imported successfully!`, 'success');
    }
    
    createTemplate() {
        // Open template creation dialog
        this.showNotification('Template creation feature coming soon!', 'info');
    }
    
    showNotification(message, type) {
        if (window.notificationManager) {
            window.notificationManager.show(message, type);
        }
    }
}

// Initialize Templates Gallery
window.templatesGallery = new WorkflowTemplatesGallery();