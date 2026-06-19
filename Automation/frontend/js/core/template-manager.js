// Enhanced Template Manager with Creation and Management
class TemplateManager {
    constructor() {
        this.templates = new Map();
        this.categories = new Map();
        this.templateModal = null;
        this.createModal = null;
        this.animationManager = null;
        
        this.init();
    }
    
    init() {
        this.setupAnimationManager();
        this.loadDefaultTemplates();
        this.setupTemplateModal();
        this.setupCreateModal();
        this.setupStyles();
        this.createQuickStartButton();
    }
    
    setupAnimationManager() {
        if (window.AnimationManager) {
            this.animationManager = new AnimationManager();
        }
    }
    
    setupStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .template-manager-modal {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.6);
                backdrop-filter: blur(8px);
                z-index: 10000;
                display: flex;
                align-items: center;
                justify-content: center;
                opacity: 0;
                visibility: hidden;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }
            
            .template-manager-modal.show {
                opacity: 1;
                visibility: visible;
            }
            
            .template-modal-content {
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(20px);
                border-radius: 20px;
                box-shadow: 0 25px 50px rgba(0, 0, 0, 0.25);
                width: 95%;
                max-width: 1200px;
                max-height: 85vh;
                overflow: hidden;
                transform: scale(0.9) translateY(-30px);
                transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            
            .template-manager-modal.show .template-modal-content {
                transform: scale(1) translateY(0);
            }
            
            .template-modal-header {
                padding: 32px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.2);
                background: linear-gradient(135deg, rgba(79, 70, 229, 0.1), rgba(124, 58, 237, 0.1));
                display: flex;
                align-items: center;
                justify-content: space-between;
            }
            
            .template-modal-title {
                font-size: 24px;
                font-weight: 700;
                color: var(--text-primary);
                margin: 0;
                display: flex;
                align-items: center;
                gap: 12px;
            }
            
            .template-modal-actions {
                display: flex;
                gap: 12px;
            }
            
            .template-btn {
                padding: 10px 20px;
                border: none;
                border-radius: 10px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            
            .template-btn-primary {
                background: linear-gradient(135deg, var(--primary-color), var(--primary-hover));
                color: white;
            }
            
            .template-btn-primary:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 25px rgba(79, 70, 229, 0.3);
            }
            
            .template-btn-secondary {
                background: rgba(255, 255, 255, 0.8);
                color: var(--text-secondary);
                border: 1px solid rgba(255, 255, 255, 0.3);
            }
            
            .template-btn-secondary:hover {
                background: rgba(255, 255, 255, 1);
                transform: translateY(-1px);
            }
            
            .template-modal-close {
                background: rgba(255, 255, 255, 0.8);
                border: none;
                color: var(--text-secondary);
                cursor: pointer;
                font-size: 20px;
                padding: 12px;
                border-radius: 10px;
                transition: all 0.2s ease;
            }
            
            .template-modal-close:hover {
                background: rgba(255, 255, 255, 1);
                color: var(--text-primary);
                transform: scale(1.1);
            }
            
            .template-modal-body {
                display: flex;
                height: calc(85vh - 120px);
            }
            
            .template-sidebar {
                width: 280px;
                background: rgba(255, 255, 255, 0.5);
                border-right: 1px solid rgba(255, 255, 255, 0.2);
                padding: 24px;
                overflow-y: auto;
            }
            
            .template-search {
                margin-bottom: 24px;
            }
            
            .template-search-input {
                width: 100%;
                padding: 12px 16px;
                border: 2px solid rgba(255, 255, 255, 0.3);
                border-radius: 12px;
                font-size: 14px;
                background: rgba(255, 255, 255, 0.8);
                backdrop-filter: blur(10px);
                transition: all 0.3s ease;
            }
            
            .template-search-input:focus {
                outline: none;
                border-color: var(--primary-color);
                box-shadow: 0 0 0 4px rgba(79, 70, 229, 0.1);
                background: rgba(255, 255, 255, 1);
            }
            
            .template-categories {
                margin-bottom: 24px;
            }
            
            .template-categories h6 {
                font-size: 12px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                color: var(--text-secondary);
                margin-bottom: 12px;
            }
            
            .template-category {
                padding: 12px 16px;
                cursor: pointer;
                font-weight: 500;
                color: var(--text-secondary);
                border-radius: 10px;
                margin-bottom: 4px;
                transition: all 0.2s ease;
                display: flex;
                align-items: center;
                gap: 12px;
            }
            
            .template-category:hover {
                background: rgba(255, 255, 255, 0.8);
                color: var(--text-primary);
                transform: translateX(4px);
            }
            
            .template-category.active {
                background: linear-gradient(135deg, var(--primary-color), var(--primary-hover));
                color: white;
                transform: translateX(8px);
            }
            
            .template-category i {
                width: 16px;
                text-align: center;
            }
            
            .template-content {
                flex: 1;
                padding: 24px;
                overflow-y: auto;
            }
            
            .template-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
                gap: 24px;
            }
            
            .template-card {
                background: rgba(255, 255, 255, 0.8);
                backdrop-filter: blur(20px);
                border: 2px solid rgba(255, 255, 255, 0.3);
                border-radius: 16px;
                overflow: hidden;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                cursor: pointer;
                position: relative;
            }
            
            .template-card::before {
                content: '';
                position: absolute;
                top: 0;
                left: -100%;
                width: 100%;
                height: 100%;
                background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.4), transparent);
                transition: left 0.5s;
            }
            
            .template-card:hover::before {
                left: 100%;
            }
            
            .template-card:hover {
                border-color: var(--primary-color);
                box-shadow: 0 12px 40px rgba(79, 70, 229, 0.2);
                transform: translateY(-4px) scale(1.02);
            }
            
            .template-card-header {
                height: 140px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                position: relative;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-size: 32px;
                overflow: hidden;
            }
            
            .template-card-header::after {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: linear-gradient(45deg, rgba(255, 255, 255, 0.1), transparent);
            }
            
            .template-card-content {
                padding: 20px;
            }
            
            .template-card-title {
                font-size: 18px;
                font-weight: 700;
                color: var(--text-primary);
                margin: 0 0 8px 0;
            }
            
            .template-card-description {
                font-size: 14px;
                color: var(--text-secondary);
                line-height: 1.5;
                margin: 0 0 16px 0;
            }
            
            .template-card-meta {
                display: flex;
                align-items: center;
                justify-content: space-between;
                font-size: 12px;
                color: var(--text-secondary);
            }
            
            .template-card-nodes {
                display: flex;
                align-items: center;
                gap: 6px;
                font-weight: 600;
            }
            
            .template-card-difficulty {
                padding: 4px 12px;
                border-radius: 20px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                font-size: 10px;
            }
            
            .template-card-difficulty.beginner {
                background: rgba(16, 185, 129, 0.1);
                color: #059669;
            }
            
            .template-card-difficulty.intermediate {
                background: rgba(245, 158, 11, 0.1);
                color: #d97706;
            }
            
            .template-card-difficulty.advanced {
                background: rgba(239, 68, 68, 0.1);
                color: #dc2626;
            }
            
            .template-empty {
                text-align: center;
                padding: 80px 24px;
                color: var(--text-secondary);
            }
            
            .template-empty i {
                font-size: 64px;
                margin-bottom: 20px;
                opacity: 0.5;
                color: var(--primary-color);
            }
            
            .template-empty h3 {
                font-size: 20px;
                font-weight: 600;
                margin-bottom: 8px;
                color: var(--text-primary);
            }
            
            .quick-start-fab {
                position: fixed;
                bottom: 30px;
                right: 30px;
                background: linear-gradient(135deg, var(--primary-color), var(--primary-hover));
                color: white;
                border: none;
                border-radius: 50%;
                width: 64px;
                height: 64px;
                font-size: 24px;
                cursor: pointer;
                box-shadow: 0 8px 25px rgba(79, 70, 229, 0.3);
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                z-index: 1000;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .quick-start-fab:hover {
                transform: translateY(-4px) scale(1.1);
                box-shadow: 0 12px 35px rgba(79, 70, 229, 0.4);
            }
            
            .quick-start-fab:active {
                transform: translateY(-2px) scale(1.05);
            }
            
            /* Create Template Modal */
            .create-template-modal {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.6);
                backdrop-filter: blur(8px);
                z-index: 10001;
                display: flex;
                align-items: center;
                justify-content: center;
                opacity: 0;
                visibility: hidden;
                transition: all 0.3s ease;
            }
            
            .create-template-modal.show {
                opacity: 1;
                visibility: visible;
            }
            
            .create-template-content {
                background: rgba(255, 255, 255, 0.95);
                backdrop-filter: blur(20px);
                border-radius: 20px;
                width: 90%;
                max-width: 800px;
                max-height: 90vh;
                overflow: hidden;
                transform: scale(0.9);
                transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            }
            
            .create-template-modal.show .create-template-content {
                transform: scale(1);
            }
            
            .create-template-header {
                padding: 24px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.2);
                background: linear-gradient(135deg, rgba(79, 70, 229, 0.1), rgba(124, 58, 237, 0.1));
            }
            
            .create-template-body {
                padding: 24px;
                max-height: 60vh;
                overflow-y: auto;
            }
            
            .create-template-form {
                display: grid;
                gap: 20px;
            }
            
            .form-group {
                display: flex;
                flex-direction: column;
                gap: 8px;
            }
            
            .form-group label {
                font-weight: 600;
                color: var(--text-primary);
                font-size: 14px;
            }
            
            .form-group input,
            .form-group textarea,
            .form-group select {
                padding: 12px 16px;
                border: 2px solid rgba(255, 255, 255, 0.3);
                border-radius: 10px;
                background: rgba(255, 255, 255, 0.8);
                backdrop-filter: blur(10px);
                transition: all 0.3s ease;
                font-size: 14px;
            }
            
            .form-group input:focus,
            .form-group textarea:focus,
            .form-group select:focus {
                outline: none;
                border-color: var(--primary-color);
                box-shadow: 0 0 0 4px rgba(79, 70, 229, 0.1);
                background: rgba(255, 255, 255, 1);
            }
            
            .form-group textarea {
                resize: vertical;
                min-height: 100px;
            }
            
            .form-row {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
            }
            
            .create-template-footer {
                padding: 24px;
                border-top: 1px solid rgba(255, 255, 255, 0.2);
                display: flex;
                justify-content: flex-end;
                gap: 12px;
            }
        `;
        document.head.appendChild(style);
    }
    
    loadDefaultTemplates() {
        // Load comprehensive template library
        this.addCategory('ai', 'AI & Automation', 'fas fa-robot');
        this.addCategory('marketing', 'Marketing', 'fas fa-bullhorn');
        this.addCategory('data', 'Data Processing', 'fas fa-database');
        this.addCategory('social', 'Social Media', 'fas fa-share-alt');
        this.addCategory('ecommerce', 'E-commerce', 'fas fa-shopping-cart');
        this.addCategory('productivity', 'Productivity', 'fas fa-tasks');
        this.addCategory('communication', 'Communication', 'fas fa-comments');
        this.addCategory('monitoring', 'Monitoring', 'fas fa-chart-line');
        this.addCategory('finance', 'Finance & Accounting', 'fas fa-dollar-sign');
        this.addCategory('security', 'Security & Compliance', 'fas fa-shield-alt');
        this.addCategory('devops', 'DevOps & Infrastructure', 'fas fa-server');
        this.addCategory('hr', 'Human Resources', 'fas fa-users');
        
        // AI Templates
        this.addTemplate('ai-content-generator', {
            name: 'AI Content Generator',
            description: 'Generate blog posts, social media content, and marketing copy using OpenAI GPT models with customizable prompts and output formatting.',
            category: 'ai',
            difficulty: 'beginner',
            nodes: 4,
            icon: 'fas fa-robot',
            tags: ['ai', 'content', 'openai', 'writing'],
            workflow: this.createSampleWorkflow('ai-content')
        });
        
        this.addTemplate('ai-image-generator', {
            name: 'AI Image Generator',
            description: 'Create stunning images using DALL-E or Midjourney APIs with automated prompt enhancement and style variations.',
            category: 'ai',
            difficulty: 'intermediate',
            nodes: 5,
            icon: 'fas fa-image',
            tags: ['ai', 'image', 'dalle', 'midjourney'],
            workflow: this.createSampleWorkflow('ai-image')
        });
        
        this.addTemplate('ai-chatbot', {
            name: 'AI Chatbot Assistant',
            description: 'Intelligent chatbot with natural language processing, context awareness, and multi-platform integration.',
            category: 'ai',
            difficulty: 'advanced',
            nodes: 8,
            icon: 'fas fa-comments',
            tags: ['ai', 'chatbot', 'nlp', 'assistant'],
            workflow: this.createSampleWorkflow('ai-chatbot')
        });
        
        this.addTemplate('ai-data-analysis', {
            name: 'AI Data Analysis',
            description: 'Automated data analysis with machine learning insights, pattern recognition, and predictive analytics.',
            category: 'ai',
            difficulty: 'advanced',
            nodes: 10,
            icon: 'fas fa-brain',
            tags: ['ai', 'analytics', 'ml', 'insights'],
            workflow: this.createSampleWorkflow('ai-data-analysis')
        });
        
        // Marketing Templates
        this.addTemplate('email-campaign', {
            name: 'Email Marketing Campaign',
            description: 'Automated email campaigns with personalization, A/B testing, and performance tracking across multiple platforms.',
            category: 'marketing',
            difficulty: 'intermediate',
            nodes: 8,
            icon: 'fas fa-envelope',
            tags: ['email', 'marketing', 'automation', 'personalization'],
            workflow: this.createSampleWorkflow('email-campaign')
        });
        
        this.addTemplate('lead-scoring', {
            name: 'Lead Scoring System',
            description: 'Intelligent lead scoring based on user behavior, demographics, and engagement patterns with CRM integration.',
            category: 'marketing',
            difficulty: 'advanced',
            nodes: 10,
            icon: 'fas fa-chart-line',
            tags: ['leads', 'scoring', 'crm', 'analytics'],
            workflow: this.createSampleWorkflow('lead-scoring')
        });
        
        this.addTemplate('marketing-attribution', {
            name: 'Marketing Attribution',
            description: 'Track and analyze marketing touchpoints across channels to determine campaign effectiveness and ROI.',
            category: 'marketing',
            difficulty: 'advanced',
            nodes: 12,
            icon: 'fas fa-funnel-dollar',
            tags: ['attribution', 'analytics', 'roi', 'tracking'],
            workflow: this.createSampleWorkflow('marketing-attribution')
        });
        
        this.addTemplate('sms-marketing', {
            name: 'SMS Marketing Automation',
            description: 'Automated SMS campaigns with segmentation, scheduling, and compliance management.',
            category: 'marketing',
            difficulty: 'intermediate',
            nodes: 6,
            icon: 'fas fa-sms',
            tags: ['sms', 'marketing', 'automation', 'mobile'],
            workflow: this.createSampleWorkflow('sms-marketing')
        });
        
        // Data Processing Templates
        this.addTemplate('etl-pipeline', {
            name: 'ETL Data Pipeline',
            description: 'Extract, transform, and load data from multiple sources with error handling, validation, and monitoring.',
            category: 'data',
            difficulty: 'advanced',
            nodes: 12,
            icon: 'fas fa-database',
            tags: ['etl', 'data', 'pipeline', 'transformation'],
            workflow: this.createSampleWorkflow('etl-pipeline')
        });
        
        this.addTemplate('real-time-analytics', {
            name: 'Real-time Analytics',
            description: 'Process and analyze streaming data in real-time with dashboards and alerting.',
            category: 'data',
            difficulty: 'advanced',
            nodes: 9,
            icon: 'fas fa-stream',
            tags: ['realtime', 'analytics', 'streaming', 'dashboard'],
            workflow: this.createSampleWorkflow('real-time-analytics')
        });
        
        this.addTemplate('data-quality', {
            name: 'Data Quality Monitoring',
            description: 'Monitor data quality with automated validation, cleansing, and anomaly detection.',
            category: 'data',
            difficulty: 'intermediate',
            nodes: 7,
            icon: 'fas fa-check-circle',
            tags: ['quality', 'validation', 'cleansing', 'monitoring'],
            workflow: this.createSampleWorkflow('data-quality')
        });
        
        // Social Media Templates
        this.addTemplate('social-scheduler', {
            name: 'Social Media Scheduler',
            description: 'Schedule and publish content across multiple social media platforms with optimal timing and engagement tracking.',
            category: 'social',
            difficulty: 'intermediate',
            nodes: 6,
            icon: 'fas fa-calendar',
            tags: ['social', 'scheduling', 'automation', 'engagement'],
            workflow: this.createSampleWorkflow('social-scheduler')
        });
        
        this.addTemplate('social-listening', {
            name: 'Social Media Listening',
            description: 'Monitor brand mentions, sentiment analysis, and competitor tracking across social platforms.',
            category: 'social',
            difficulty: 'intermediate',
            nodes: 8,
            icon: 'fas fa-ear-listen',
            tags: ['listening', 'sentiment', 'monitoring', 'brand'],
            workflow: this.createSampleWorkflow('social-listening')
        });
        
        this.addTemplate('influencer-outreach', {
            name: 'Influencer Outreach',
            description: 'Automated influencer identification, outreach, and campaign management with performance tracking.',
            category: 'social',
            difficulty: 'advanced',
            nodes: 10,
            icon: 'fas fa-star',
            tags: ['influencer', 'outreach', 'campaign', 'tracking'],
            workflow: this.createSampleWorkflow('influencer-outreach')
        });
        
        // E-commerce Templates
        this.addTemplate('inventory-sync', {
            name: 'Inventory Synchronization',
            description: 'Keep inventory levels synchronized across multiple sales channels with automated reordering and alerts.',
            category: 'ecommerce',
            difficulty: 'intermediate',
            nodes: 7,
            icon: 'fas fa-boxes',
            tags: ['inventory', 'sync', 'ecommerce', 'automation'],
            workflow: this.createSampleWorkflow('inventory-sync')
        });
        
        this.addTemplate('price-optimization', {
            name: 'Dynamic Price Optimization',
            description: 'Automated pricing strategies based on competition, demand, and inventory levels.',
            category: 'ecommerce',
            difficulty: 'advanced',
            nodes: 9,
            icon: 'fas fa-tags',
            tags: ['pricing', 'optimization', 'competition', 'dynamic'],
            workflow: this.createSampleWorkflow('price-optimization')
        });
        
        this.addTemplate('order-fulfillment', {
            name: 'Order Fulfillment Automation',
            description: 'Streamline order processing from payment to shipping with multi-warehouse support.',
            category: 'ecommerce',
            difficulty: 'intermediate',
            nodes: 11,
            icon: 'fas fa-shipping-fast',
            tags: ['orders', 'fulfillment', 'shipping', 'automation'],
            workflow: this.createSampleWorkflow('order-fulfillment')
        });
        
        this.addTemplate('abandoned-cart', {
            name: 'Abandoned Cart Recovery',
            description: 'Recover lost sales with personalized email sequences and targeted offers.',
            category: 'ecommerce',
            difficulty: 'beginner',
            nodes: 5,
            icon: 'fas fa-shopping-cart',
            tags: ['cart', 'recovery', 'email', 'conversion'],
            workflow: this.createSampleWorkflow('abandoned-cart')
        });
        
        // Productivity Templates
        this.addTemplate('task-automation', {
            name: 'Task Automation Suite',
            description: 'Automate repetitive tasks with file processing, email management, and workflow orchestration.',
            category: 'productivity',
            difficulty: 'intermediate',
            nodes: 8,
            icon: 'fas fa-tasks',
            tags: ['tasks', 'automation', 'productivity', 'workflow'],
            workflow: this.createSampleWorkflow('task-automation')
        });
        
        this.addTemplate('document-processing', {
            name: 'Document Processing',
            description: 'Automated document parsing, data extraction, and classification with OCR support.',
            category: 'productivity',
            difficulty: 'advanced',
            nodes: 9,
            icon: 'fas fa-file-alt',
            tags: ['documents', 'ocr', 'extraction', 'classification'],
            workflow: this.createSampleWorkflow('document-processing')
        });
        
        this.addTemplate('meeting-scheduler', {
            name: 'Smart Meeting Scheduler',
            description: 'Intelligent meeting scheduling with calendar integration and availability optimization.',
            category: 'productivity',
            difficulty: 'intermediate',
            nodes: 6,
            icon: 'fas fa-calendar-alt',
            tags: ['meetings', 'scheduling', 'calendar', 'optimization'],
            workflow: this.createSampleWorkflow('meeting-scheduler')
        });
        
        // Communication Templates
        this.addTemplate('customer-support', {
            name: 'Customer Support Bot',
            description: 'Automated customer support with AI-powered responses, ticket routing, and escalation management.',
            category: 'communication',
            difficulty: 'advanced',
            nodes: 9,
            icon: 'fas fa-headset',
            tags: ['support', 'chatbot', 'ai', 'tickets'],
            workflow: this.createSampleWorkflow('customer-support')
        });
        
        this.addTemplate('notification-system', {
            name: 'Multi-Channel Notifications',
            description: 'Send notifications across email, SMS, Slack, and push notifications with smart routing.',
            category: 'communication',
            difficulty: 'intermediate',
            nodes: 7,
            icon: 'fas fa-bell',
            tags: ['notifications', 'multichannel', 'alerts', 'routing'],
            workflow: this.createSampleWorkflow('notification-system')
        });
        
        this.addTemplate('survey-automation', {
            name: 'Survey & Feedback Automation',
            description: 'Automated survey distribution, response collection, and analysis with follow-up actions.',
            category: 'communication',
            difficulty: 'intermediate',
            nodes: 8,
            icon: 'fas fa-poll',
            tags: ['survey', 'feedback', 'automation', 'analysis'],
            workflow: this.createSampleWorkflow('survey-automation')
        });
        
        // Monitoring Templates
        this.addTemplate('system-monitoring', {
            name: 'System Health Monitoring',
            description: 'Monitor system performance, uptime, and resource usage with automated alerting.',
            category: 'monitoring',
            difficulty: 'intermediate',
            nodes: 8,
            icon: 'fas fa-heartbeat',
            tags: ['monitoring', 'health', 'performance', 'alerts'],
            workflow: this.createSampleWorkflow('system-monitoring')
        });
        
        this.addTemplate('log-analysis', {
            name: 'Log Analysis & Alerting',
            description: 'Automated log parsing, error detection, and intelligent alerting with pattern recognition.',
            category: 'monitoring',
            difficulty: 'advanced',
            nodes: 10,
            icon: 'fas fa-file-code',
            tags: ['logs', 'analysis', 'errors', 'patterns'],
            workflow: this.createSampleWorkflow('log-analysis')
        });
        
        this.addTemplate('security-monitoring', {
            name: 'Security Event Monitoring',
            description: 'Monitor security events, detect threats, and automate incident response procedures.',
            category: 'security',
            difficulty: 'advanced',
            nodes: 12,
            icon: 'fas fa-shield-alt',
            tags: ['security', 'threats', 'incidents', 'response'],
            workflow: this.createSampleWorkflow('security-monitoring')
        });
        
        // Finance Templates
        this.addTemplate('expense-tracking', {
            name: 'Expense Tracking & Reporting',
            description: 'Automated expense categorization, approval workflows, and financial reporting.',
            category: 'finance',
            difficulty: 'intermediate',
            nodes: 7,
            icon: 'fas fa-receipt',
            tags: ['expenses', 'tracking', 'approval', 'reporting'],
            workflow: this.createSampleWorkflow('expense-tracking')
        });
        
        this.addTemplate('invoice-automation', {
            name: 'Invoice Processing Automation',
            description: 'Automated invoice generation, sending, and payment tracking with reminders.',
            category: 'finance',
            difficulty: 'intermediate',
            nodes: 9,
            icon: 'fas fa-file-invoice',
            tags: ['invoices', 'billing', 'payments', 'automation'],
            workflow: this.createSampleWorkflow('invoice-automation')
        });
        
        this.addTemplate('financial-reporting', {
            name: 'Financial Reporting Dashboard',
            description: 'Automated financial reports with KPI tracking, variance analysis, and forecasting.',
            category: 'finance',
            difficulty: 'advanced',
            nodes: 11,
            icon: 'fas fa-chart-pie',
            tags: ['reporting', 'kpi', 'forecasting', 'analysis'],
            workflow: this.createSampleWorkflow('financial-reporting')
        });
        
        // DevOps Templates
        this.addTemplate('ci-cd-pipeline', {
            name: 'CI/CD Pipeline',
            description: 'Automated build, test, and deployment pipeline with quality gates and rollback capabilities.',
            category: 'devops',
            difficulty: 'advanced',
            nodes: 13,
            icon: 'fas fa-code-branch',
            tags: ['cicd', 'deployment', 'testing', 'automation'],
            workflow: this.createSampleWorkflow('ci-cd-pipeline')
        });
        
        this.addTemplate('infrastructure-provisioning', {
            name: 'Infrastructure Provisioning',
            description: 'Automated cloud infrastructure provisioning with configuration management and scaling.',
            category: 'devops',
            difficulty: 'advanced',
            nodes: 10,
            icon: 'fas fa-cloud',
            tags: ['infrastructure', 'provisioning', 'cloud', 'scaling'],
            workflow: this.createSampleWorkflow('infrastructure-provisioning')
        });
        
        this.addTemplate('backup-automation', {
            name: 'Backup & Recovery Automation',
            description: 'Automated backup scheduling, verification, and disaster recovery procedures.',
            category: 'devops',
            difficulty: 'intermediate',
            nodes: 8,
            icon: 'fas fa-hdd',
            tags: ['backup', 'recovery', 'disaster', 'automation'],
            workflow: this.createSampleWorkflow('backup-automation')
        });
        
        // HR Templates
        this.addTemplate('employee-onboarding', {
            name: 'Employee Onboarding',
            description: 'Streamlined employee onboarding with document collection, account setup, and training scheduling.',
            category: 'hr',
            difficulty: 'intermediate',
            nodes: 9,
            icon: 'fas fa-user-plus',
            tags: ['onboarding', 'employees', 'training', 'documents'],
            workflow: this.createSampleWorkflow('employee-onboarding')
        });
        
        this.addTemplate('performance-review', {
            name: 'Performance Review Automation',
            description: 'Automated performance review cycles with feedback collection and goal tracking.',
            category: 'hr',
            difficulty: 'intermediate',
            nodes: 8,
            icon: 'fas fa-star',
            tags: ['performance', 'reviews', 'feedback', 'goals'],
            workflow: this.createSampleWorkflow('performance-review')
        });
        
        this.addTemplate('recruitment-pipeline', {
            name: 'Recruitment Pipeline',
            description: 'Automated candidate screening, interview scheduling, and hiring workflow management.',
            category: 'hr',
            difficulty: 'advanced',
            nodes: 11,
            icon: 'fas fa-search',
            tags: ['recruitment', 'hiring', 'screening', 'interviews'],
            workflow: this.createSampleWorkflow('recruitment-pipeline')
        });
    }
    
    createSampleWorkflow(type) {
        // Create sample workflow structures for different template types
        const workflows = {
            'ai-content': {
                nodes: [
                    { id: 'trigger', type: 'webhook', position: { x: 100, y: 200 } },
                    { id: 'openai', type: 'openai', position: { x: 300, y: 200 } },
                    { id: 'format', type: 'json', position: { x: 500, y: 200 } },
                    { id: 'response', type: 'http_response', position: { x: 700, y: 200 } }
                ],
                edges: [
                    { source: 'trigger', target: 'openai' },
                    { source: 'openai', target: 'format' },
                    { source: 'format', target: 'response' }
                ]
            },
            'ai-image': {
                nodes: [
                    { id: 'trigger', type: 'webhook', position: { x: 100, y: 200 } },
                    { id: 'enhance', type: 'ai-agent', position: { x: 300, y: 200 } },
                    { id: 'dalle', type: 'dalle', position: { x: 500, y: 200 } },
                    { id: 'storage', type: 's3', position: { x: 700, y: 200 } },
                    { id: 'response', type: 'http_response', position: { x: 900, y: 200 } }
                ],
                edges: [
                    { source: 'trigger', target: 'enhance' },
                    { source: 'enhance', target: 'dalle' },
                    { source: 'dalle', target: 'storage' },
                    { source: 'storage', target: 'response' }
                ]
            },
            'ai-chatbot': {
                nodes: [
                    { id: 'webhook', type: 'webhook', position: { x: 100, y: 200 } },
                    { id: 'nlp', type: 'ai-agent', position: { x: 300, y: 200 } },
                    { id: 'context', type: 'memory', position: { x: 500, y: 200 } },
                    { id: 'response', type: 'ai-agent', position: { x: 700, y: 200 } },
                    { id: 'format', type: 'json', position: { x: 900, y: 200 } },
                    { id: 'send', type: 'http_response', position: { x: 1100, y: 200 } }
                ],
                edges: [
                    { source: 'webhook', target: 'nlp' },
                    { source: 'nlp', target: 'context' },
                    { source: 'context', target: 'response' },
                    { source: 'response', target: 'format' },
                    { source: 'format', target: 'send' }
                ]
            },
            'email-campaign': {
                nodes: [
                    { id: 'schedule', type: 'schedule', position: { x: 100, y: 200 } },
                    { id: 'database', type: 'database', position: { x: 300, y: 200 } },
                    { id: 'segment', type: 'condition', position: { x: 500, y: 150 } },
                    { id: 'personalize', type: 'ai-agent', position: { x: 700, y: 200 } },
                    { id: 'send', type: 'email', position: { x: 900, y: 200 } },
                    { id: 'track', type: 'http', position: { x: 1100, y: 200 } }
                ],
                edges: [
                    { source: 'schedule', target: 'database' },
                    { source: 'database', target: 'segment' },
                    { source: 'segment', target: 'personalize' },
                    { source: 'personalize', target: 'send' },
                    { source: 'send', target: 'track' }
                ]
            },
            'lead-scoring': {
                nodes: [
                    { id: 'webhook', type: 'webhook', position: { x: 100, y: 200 } },
                    { id: 'enrich', type: 'http', position: { x: 300, y: 200 } },
                    { id: 'score', type: 'ai-agent', position: { x: 500, y: 200 } },
                    { id: 'condition', type: 'condition', position: { x: 700, y: 200 } },
                    { id: 'crm-hot', type: 'salesforce', position: { x: 900, y: 150 } },
                    { id: 'crm-cold', type: 'salesforce', position: { x: 900, y: 250 } },
                    { id: 'notify', type: 'slack', position: { x: 1100, y: 200 } }
                ],
                edges: [
                    { source: 'webhook', target: 'enrich' },
                    { source: 'enrich', target: 'score' },
                    { source: 'score', target: 'condition' },
                    { source: 'condition', target: 'crm-hot' },
                    { source: 'condition', target: 'crm-cold' },
                    { source: 'crm-hot', target: 'notify' }
                ]
            },
            'etl-pipeline': {
                nodes: [
                    { id: 'schedule', type: 'schedule', position: { x: 100, y: 200 } },
                    { id: 'extract-db', type: 'database', position: { x: 300, y: 150 } },
                    { id: 'extract-api', type: 'http', position: { x: 300, y: 250 } },
                    { id: 'validate', type: 'condition', position: { x: 500, y: 200 } },
                    { id: 'transform', type: 'json', position: { x: 700, y: 200 } },
                    { id: 'load', type: 'database', position: { x: 900, y: 200 } },
                    { id: 'notify', type: 'email', position: { x: 1100, y: 200 } }
                ],
                edges: [
                    { source: 'schedule', target: 'extract-db' },
                    { source: 'schedule', target: 'extract-api' },
                    { source: 'extract-db', target: 'validate' },
                    { source: 'extract-api', target: 'validate' },
                    { source: 'validate', target: 'transform' },
                    { source: 'transform', target: 'load' },
                    { source: 'load', target: 'notify' }
                ]
            },
            'social-scheduler': {
                nodes: [
                    { id: 'schedule', type: 'schedule', position: { x: 100, y: 200 } },
                    { id: 'content', type: 'database', position: { x: 300, y: 200 } },
                    { id: 'optimize', type: 'ai-agent', position: { x: 500, y: 200 } },
                    { id: 'twitter', type: 'twitter', position: { x: 700, y: 150 } },
                    { id: 'facebook', type: 'facebook', position: { x: 700, y: 200 } },
                    { id: 'linkedin', type: 'linkedin', position: { x: 700, y: 250 } },
                    { id: 'analytics', type: 'http', position: { x: 900, y: 200 } }
                ],
                edges: [
                    { source: 'schedule', target: 'content' },
                    { source: 'content', target: 'optimize' },
                    { source: 'optimize', target: 'twitter' },
                    { source: 'optimize', target: 'facebook' },
                    { source: 'optimize', target: 'linkedin' },
                    { source: 'twitter', target: 'analytics' },
                    { source: 'facebook', target: 'analytics' },
                    { source: 'linkedin', target: 'analytics' }
                ]
            },
            'inventory-sync': {
                nodes: [
                    { id: 'schedule', type: 'schedule', position: { x: 100, y: 200 } },
                    { id: 'shopify', type: 'shopify', position: { x: 300, y: 150 } },
                    { id: 'amazon', type: 'amazon', position: { x: 300, y: 250 } },
                    { id: 'sync', type: 'json', position: { x: 500, y: 200 } },
                    { id: 'update', type: 'database', position: { x: 700, y: 200 } },
                    { id: 'alert', type: 'email', position: { x: 900, y: 200 } }
                ],
                edges: [
                    { source: 'schedule', target: 'shopify' },
                    { source: 'schedule', target: 'amazon' },
                    { source: 'shopify', target: 'sync' },
                    { source: 'amazon', target: 'sync' },
                    { source: 'sync', target: 'update' },
                    { source: 'update', target: 'alert' }
                ]
            },
            'customer-support': {
                nodes: [
                    { id: 'webhook', type: 'webhook', position: { x: 100, y: 200 } },
                    { id: 'classify', type: 'ai-agent', position: { x: 300, y: 200 } },
                    { id: 'route', type: 'condition', position: { x: 500, y: 200 } },
                    { id: 'ai-response', type: 'ai-agent', position: { x: 700, y: 150 } },
                    { id: 'human-queue', type: 'zendesk', position: { x: 700, y: 250 } },
                    { id: 'respond', type: 'http_response', position: { x: 900, y: 200 } }
                ],
                edges: [
                    { source: 'webhook', target: 'classify' },
                    { source: 'classify', target: 'route' },
                    { source: 'route', target: 'ai-response' },
                    { source: 'route', target: 'human-queue' },
                    { source: 'ai-response', target: 'respond' },
                    { source: 'human-queue', target: 'respond' }
                ]
            },
            'system-monitoring': {
                nodes: [
                    { id: 'schedule', type: 'schedule', position: { x: 100, y: 200 } },
                    { id: 'check-cpu', type: 'http', position: { x: 300, y: 150 } },
                    { id: 'check-memory', type: 'http', position: { x: 300, y: 200 } },
                    { id: 'check-disk', type: 'http', position: { x: 300, y: 250 } },
                    { id: 'analyze', type: 'condition', position: { x: 500, y: 200 } },
                    { id: 'alert', type: 'slack', position: { x: 700, y: 200 } },
                    { id: 'log', type: 'database', position: { x: 900, y: 200 } }
                ],
                edges: [
                    { source: 'schedule', target: 'check-cpu' },
                    { source: 'schedule', target: 'check-memory' },
                    { source: 'schedule', target: 'check-disk' },
                    { source: 'check-cpu', target: 'analyze' },
                    { source: 'check-memory', target: 'analyze' },
                    { source: 'check-disk', target: 'analyze' },
                    { source: 'analyze', target: 'alert' },
                    { source: 'analyze', target: 'log' }
                ]
            },
            'ci-cd-pipeline': {
                nodes: [
                    { id: 'git-trigger', type: 'webhook', position: { x: 100, y: 200 } },
                    { id: 'checkout', type: 'git', position: { x: 300, y: 200 } },
                    { id: 'test', type: 'shell', position: { x: 500, y: 150 } },
                    { id: 'build', type: 'shell', position: { x: 500, y: 250 } },
                    { id: 'quality-gate', type: 'condition', position: { x: 700, y: 200 } },
                    { id: 'deploy-staging', type: 'kubernetes', position: { x: 900, y: 150 } },
                    { id: 'deploy-prod', type: 'kubernetes', position: { x: 900, y: 250 } },
                    { id: 'notify', type: 'slack', position: { x: 1100, y: 200 } }
                ],
                edges: [
                    { source: 'git-trigger', target: 'checkout' },
                    { source: 'checkout', target: 'test' },
                    { source: 'checkout', target: 'build' },
                    { source: 'test', target: 'quality-gate' },
                    { source: 'build', target: 'quality-gate' },
                    { source: 'quality-gate', target: 'deploy-staging' },
                    { source: 'quality-gate', target: 'deploy-prod' },
                    { source: 'deploy-staging', target: 'notify' },
                    { source: 'deploy-prod', target: 'notify' }
                ]
            }
        };
        
        return workflows[type] || workflows['ai-content'];
    }
    
    addTemplate(id, template) {
        this.templates.set(id, {
            id,
            ...template,
            createdAt: new Date(),
            isCustom: false
        });
    }
    
    addCategory(id, name, icon) {
        this.categories.set(id, { id, name, icon });
    }
    
    setupTemplateModal() {
        const modal = document.createElement('div');
        modal.className = 'template-manager-modal';
        modal.innerHTML = `
            <div class="template-modal-content">
                <div class="template-modal-header">
                    <h2 class="template-modal-title">
                        <i class="fas fa-layer-group"></i>
                        Workflow Templates
                    </h2>
                    <div class="template-modal-actions">
                        <button class="template-btn template-btn-primary" id="create-template-btn">
                            <i class="fas fa-plus"></i>
                            Create Template
                        </button>
                        <button class="template-modal-close">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                </div>
                <div class="template-modal-body">
                    <div class="template-sidebar">
                        <div class="template-search">
                            <input type="text" class="template-search-input" placeholder="Search templates...">
                        </div>
                        <div class="template-categories">
                            <h6>Categories</h6>
                            <div class="template-category active" data-category="all">
                                <i class="fas fa-th-large"></i>
                                All Templates
                            </div>
                        </div>
                    </div>
                    <div class="template-content">
                        <div class="template-grid"></div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        this.templateModal = modal;
        
        this.setupTemplateModalEvents();
        this.renderCategories();
        this.renderTemplates();
    }
    
    setupTemplateModalEvents() {
        const modal = this.templateModal;
        
        // Close modal
        modal.querySelector('.template-modal-close').addEventListener('click', () => {
            this.hideTemplateModal();
        });
        
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.hideTemplateModal();
            }
        });
        
        // Search functionality
        modal.querySelector('.template-search-input').addEventListener('input', (e) => {
            this.filterTemplates(e.target.value);
        });
        
        // Create template button
        modal.querySelector('#create-template-btn').addEventListener('click', () => {
            this.showCreateTemplateModal();
        });
        
        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.classList.contains('show')) {
                this.hideTemplateModal();
            }
        });
    }
    
    setupCreateModal() {
        const modal = document.createElement('div');
        modal.className = 'create-template-modal';
        modal.innerHTML = `
            <div class="create-template-content">
                <div class="create-template-header">
                    <h3>Create New Template</h3>
                    <p>Save your current workflow as a reusable template</p>
                </div>
                <div class="create-template-body">
                    <form class="create-template-form" id="create-template-form">
                        <div class="form-row">
                            <div class="form-group">
                                <label for="template-name">Template Name *</label>
                                <input type="text" id="template-name" name="name" required placeholder="My Awesome Template">
                            </div>
                            <div class="form-group">
                                <label for="template-category">Category *</label>
                                <select id="template-category" name="category" required>
                                    <option value="">Select category...</option>
                                </select>
                            </div>
                        </div>
                        <div class="form-group">
                            <label for="template-description">Description *</label>
                            <textarea id="template-description" name="description" required placeholder="Describe what this template does and when to use it..."></textarea>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label for="template-difficulty">Difficulty Level</label>
                                <select id="template-difficulty" name="difficulty">
                                    <option value="beginner">Beginner</option>
                                    <option value="intermediate" selected>Intermediate</option>
                                    <option value="advanced">Advanced</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="template-icon">Icon Class</label>
                                <input type="text" id="template-icon" name="icon" placeholder="fas fa-cog" value="fas fa-cog">
                            </div>
                        </div>
                        <div class="form-group">
                            <label for="template-tags">Tags (comma-separated)</label>
                            <input type="text" id="template-tags" name="tags" placeholder="automation, email, ai">
                        </div>
                    </form>
                </div>
                <div class="create-template-footer">
                    <button type="button" class="template-btn template-btn-secondary" id="cancel-create-template">
                        Cancel
                    </button>
                    <button type="submit" form="create-template-form" class="template-btn template-btn-primary">
                        <i class="fas fa-save"></i>
                        Create Template
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        this.createModal = modal;
        
        this.setupCreateModalEvents();
    }
    
    setupCreateModalEvents() {
        const modal = this.createModal;
        
        // Populate category dropdown
        const categorySelect = modal.querySelector('#template-category');
        this.categories.forEach(category => {
            const option = document.createElement('option');
            option.value = category.id;
            option.textContent = category.name;
            categorySelect.appendChild(option);
        });
        
        // Close modal
        modal.querySelector('#cancel-create-template').addEventListener('click', () => {
            this.hideCreateTemplateModal();
        });
        
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.hideCreateTemplateModal();
            }
        });
        
        // Form submission
        modal.querySelector('#create-template-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.createTemplateFromForm(e.target);
        });
    }
    
    renderCategories() {
        const container = this.templateModal.querySelector('.template-categories');
        const existingCategories = container.querySelectorAll('.template-category:not([data-category="all"])');
        existingCategories.forEach(cat => cat.remove());
        
        this.categories.forEach(category => {
            const categoryEl = document.createElement('div');
            categoryEl.className = 'template-category';
            categoryEl.dataset.category = category.id;
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
        
        if (categoryFilter && categoryFilter !== 'all') {
            filteredTemplates = filteredTemplates.filter(t => t.category === categoryFilter);
        }
        
        if (searchFilter) {
            const search = searchFilter.toLowerCase();
            filteredTemplates = filteredTemplates.filter(t => 
                t.name.toLowerCase().includes(search) ||
                t.description.toLowerCase().includes(search) ||
                (t.tags && t.tags.some(tag => tag.toLowerCase().includes(search)))
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
        
        filteredTemplates.forEach((template, index) => {
            const card = document.createElement('div');
            card.className = 'template-card';
            card.style.animationDelay = `${index * 0.1}s`;
            card.innerHTML = `
                <div class="template-card-header">
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
            
            // Animate card appearance
            if (this.animationManager) {
                setTimeout(() => {
                    this.animationManager.animateNodeCreation(card);
                }, index * 100);
            }
        });
    }
    
    selectCategory(categoryId) {
        // Update active category
        this.templateModal.querySelectorAll('.template-category').forEach(cat => {
            cat.classList.remove('active');
        });
        
        const categoryEl = this.templateModal.querySelector(`[data-category="${categoryId}"]`);
        if (categoryEl) {
            categoryEl.classList.add('active');
        }
        
        this.renderTemplates(categoryId);
    }
    
    filterTemplates(search) {
        const activeCategory = this.templateModal.querySelector('.template-category.active');
        const categoryId = activeCategory ? activeCategory.dataset.category : 'all';
        
        this.renderTemplates(categoryId === 'all' ? null : categoryId, search);
    }
    
    showTemplateModal() {
        this.templateModal.classList.add('show');
        this.renderTemplates();
        
        if (this.animationManager) {
            this.animationManager.animatePanelOpen(this.templateModal);
        }
    }
    
    hideTemplateModal() {
        this.templateModal.classList.remove('show');
    }
    
    showCreateTemplateModal() {
        // Check if there's a current workflow
        if (!window.nodeManager || window.nodeManager.nodes.size === 0) {
            if (window.notifications) {
                window.notifications.warning('Create a workflow first before saving it as a template');
            }
            return;
        }
        
        this.createModal.classList.add('show');
        
        if (this.animationManager) {
            this.animationManager.animatePanelOpen(this.createModal);
        }
    }
    
    hideCreateTemplateModal() {
        this.createModal.classList.remove('show');
        this.createModal.querySelector('#create-template-form').reset();
    }
    
    createTemplateFromForm(form) {
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());
        
        // Get current workflow
        const workflow = window.nodeManager ? window.nodeManager.exportWorkflow() : null;
        if (!workflow || workflow.nodes.length === 0) {
            if (window.notifications) {
                window.notifications.error('No workflow to save as template');
            }
            return;
        }
        
        // Create template
        const templateId = `custom_${Date.now()}`;
        const template = {
            name: data.name,
            description: data.description,
            category: data.category,
            difficulty: data.difficulty,
            icon: data.icon || 'fas fa-cog',
            tags: data.tags ? data.tags.split(',').map(tag => tag.trim()) : [],
            nodes: workflow.nodes.length,
            workflow: workflow,
            isCustom: true
        };
        
        this.addTemplate(templateId, template);
        
        // Hide modal and show success
        this.hideCreateTemplateModal();
        
        if (window.notifications) {
            window.notifications.success(`Template "${data.name}" created successfully!`, {
                duration: 3000
            });
        }
        
        // Refresh template list if modal is open
        if (this.templateModal.classList.contains('show')) {
            this.renderTemplates();
        }
    }
    
    useTemplate(template) {
        this.hideTemplateModal();
        
        // Clear current workflow
        if (window.nodeManager) {
            window.nodeManager.clearWorkflow();
        }
        
        // Load template workflow
        if (template.workflow && window.nodeManager) {
            this.loadWorkflow(template.workflow);
        }
        
        // Show success notification
        if (window.notifications) {
            window.notifications.success(
                `Template "${template.name}" loaded successfully!`,
                { duration: 3000 }
            );
        }
    }
    
    loadWorkflow(workflow) {
        // Create nodes with staggered animation
        workflow.nodes.forEach((nodeData, index) => {
            setTimeout(() => {
                if (window.nodeManager) {
                    window.nodeManager.createNode(nodeData.type, nodeData.category, nodeData.position.x, nodeData.position.y);
                }
            }, index * 200);
        });
        
        // Create connections after nodes are created
        setTimeout(() => {
            if (workflow.edges && window.edgeManager) {
                workflow.edges.forEach((edgeData, index) => {
                    setTimeout(() => {
                        window.edgeManager.createEdge(edgeData.source, edgeData.target);
                    }, index * 300);
                });
            }
        }, workflow.nodes.length * 200 + 500);
    }
    
    createQuickStartButton() {
        const button = document.createElement('button');
        button.className = 'quick-start-fab';
        button.innerHTML = '<i class="fas fa-magic"></i>';
        button.title = 'Quick Start Templates';
        
        button.addEventListener('click', () => {
            this.showTemplateModal();
            
            if (this.animationManager) {
                this.animationManager.bounce(button);
            }
        });
        
        document.body.appendChild(button);
        return button;
    }
    
    // Export/Import functionality
    exportTemplate(templateId) {
        const template = this.templates.get(templateId);
        if (!template) return null;
        
        const exportData = {
            ...template,
            exportedAt: new Date().toISOString(),
            version: '1.0'
        };
        
        const blob = new Blob([JSON.stringify(exportData, null, 2)], {
            type: 'application/json'
        });
        
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${template.name.replace(/[^a-z0-9]/gi, '_').toLowerCase()}_template.json`;
        a.click();
        
        URL.revokeObjectURL(url);
    }
    
    importTemplate(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                try {
                    const templateData = JSON.parse(e.target.result);
                    
                    // Validate template structure
                    if (!templateData.name || !templateData.workflow) {
                        throw new Error('Invalid template format');
                    }
                    
                    // Add imported template
                    const templateId = `imported_${Date.now()}`;
                    this.addTemplate(templateId, {
                        ...templateData,
                        isCustom: true,
                        importedAt: new Date()
                    });
                    
                    resolve(templateId);
                } catch (error) {
                    reject(error);
                }
            };
            reader.readAsText(file);
        });
    }
    
    // Template sharing and marketplace functionality
    shareTemplate(templateId) {
        const template = this.templates.get(templateId);
        if (!template) return;
        
        // Create shareable link
        const shareData = {
            template: template,
            sharedAt: new Date().toISOString(),
            shareId: this.generateShareId()
        };
        
        // Store in localStorage for demo (in production, would use API)
        localStorage.setItem(`shared_template_${shareData.shareId}`, JSON.stringify(shareData));
        
        const shareUrl = `${window.location.origin}${window.location.pathname}?template=${shareData.shareId}`;
        
        // Copy to clipboard
        navigator.clipboard.writeText(shareUrl).then(() => {
            if (window.notifications) {
                window.notifications.success('Template share link copied to clipboard!');
            }
        });
        
        return shareUrl;
    }
    
    loadSharedTemplate(shareId) {
        const sharedData = localStorage.getItem(`shared_template_${shareId}`);
        if (!sharedData) return null;
        
        try {
            const data = JSON.parse(sharedData);
            return data.template;
        } catch (error) {
            console.error('Error loading shared template:', error);
            return null;
        }
    }
    
    generateShareId() {
        return Math.random().toString(36).substr(2, 9);
    }
    
    // Template versioning
    createTemplateVersion(templateId, changes) {
        const template = this.templates.get(templateId);
        if (!template) return null;
        
        const version = {
            id: `${templateId}_v${Date.now()}`,
            parentId: templateId,
            version: template.version ? template.version + 1 : 2,
            changes: changes,
            createdAt: new Date(),
            ...template
        };
        
        this.addTemplate(version.id, version);
        return version.id;
    }
    
    getTemplateVersions(templateId) {
        return Array.from(this.templates.values())
            .filter(t => t.parentId === templateId || t.id === templateId)
            .sort((a, b) => (b.version || 1) - (a.version || 1));
    }
    
    // Template analytics and usage tracking
    trackTemplateUsage(templateId) {
        const template = this.templates.get(templateId);
        if (!template) return;
        
        template.usageCount = (template.usageCount || 0) + 1;
        template.lastUsed = new Date();
        
        // Store usage analytics
        const analytics = JSON.parse(localStorage.getItem('template_analytics') || '{}');
        analytics[templateId] = {
            count: template.usageCount,
            lastUsed: template.lastUsed,
            name: template.name
        };
        localStorage.setItem('template_analytics', JSON.stringify(analytics));
    }
    
    getPopularTemplates(limit = 5) {
        const analytics = JSON.parse(localStorage.getItem('template_analytics') || '{}');
        
        return Array.from(this.templates.values())
            .map(template => ({
                ...template,
                usageCount: analytics[template.id]?.count || 0
            }))
            .sort((a, b) => b.usageCount - a.usageCount)
            .slice(0, limit);
    }
    
    getRecentTemplates(limit = 5) {
        const analytics = JSON.parse(localStorage.getItem('template_analytics') || '{}');
        
        return Array.from(this.templates.values())
            .filter(template => analytics[template.id]?.lastUsed)
            .map(template => ({
                ...template,
                lastUsed: new Date(analytics[template.id].lastUsed)
            }))
            .sort((a, b) => b.lastUsed - a.lastUsed)
            .slice(0, limit);
    }
    
    // Template validation and quality scoring
    validateTemplate(template) {
        const issues = [];
        const score = { total: 100, deductions: [] };
        
        // Check basic structure
        if (!template.workflow || !template.workflow.nodes || template.workflow.nodes.length === 0) {
            issues.push({ type: 'error', message: 'Template must have at least one node' });
            score.deductions.push({ reason: 'No nodes', points: 50 });
        }
        
        // Check for disconnected nodes
        if (template.workflow.nodes && template.workflow.edges) {
            const connectedNodes = new Set();
            template.workflow.edges.forEach(edge => {
                connectedNodes.add(edge.source);
                connectedNodes.add(edge.target);
            });
            
            const disconnectedNodes = template.workflow.nodes.filter(node => 
                !connectedNodes.has(node.id) && template.workflow.nodes.length > 1
            );
            
            if (disconnectedNodes.length > 0) {
                issues.push({ 
                    type: 'warning', 
                    message: `${disconnectedNodes.length} disconnected nodes found` 
                });
                score.deductions.push({ 
                    reason: 'Disconnected nodes', 
                    points: disconnectedNodes.length * 5 
                });
            }
        }
        
        // Check description quality
        if (!template.description || template.description.length < 50) {
            issues.push({ type: 'warning', message: 'Description should be more detailed' });
            score.deductions.push({ reason: 'Poor description', points: 10 });
        }
        
        // Check tags
        if (!template.tags || template.tags.length === 0) {
            issues.push({ type: 'info', message: 'Consider adding tags for better discoverability' });
            score.deductions.push({ reason: 'No tags', points: 5 });
        }
        
        // Calculate final score
        const finalScore = Math.max(0, score.total - score.deductions.reduce((sum, d) => sum + d.points, 0));
        
        return {
            isValid: issues.filter(i => i.type === 'error').length === 0,
            score: finalScore,
            issues: issues,
            grade: this.getTemplateGrade(finalScore)
        };
    }
    
    getTemplateGrade(score) {
        if (score >= 90) return 'A';
        if (score >= 80) return 'B';
        if (score >= 70) return 'C';
        if (score >= 60) return 'D';
        return 'F';
    }
    
    // Template search and filtering
    searchTemplates(query, filters = {}) {
        let results = Array.from(this.templates.values());
        
        // Text search
        if (query) {
            const searchTerms = query.toLowerCase().split(' ');
            results = results.filter(template => {
                const searchText = `${template.name} ${template.description} ${template.tags?.join(' ')}`.toLowerCase();
                return searchTerms.every(term => searchText.includes(term));
            });
        }
        
        // Category filter
        if (filters.category && filters.category !== 'all') {
            results = results.filter(template => template.category === filters.category);
        }
        
        // Difficulty filter
        if (filters.difficulty) {
            results = results.filter(template => template.difficulty === filters.difficulty);
        }
        
        // Node count filter
        if (filters.minNodes) {
            results = results.filter(template => template.nodes >= filters.minNodes);
        }
        if (filters.maxNodes) {
            results = results.filter(template => template.nodes <= filters.maxNodes);
        }
        
        // Custom templates filter
        if (filters.customOnly) {
            results = results.filter(template => template.isCustom);
        }
        
        // Sort results
        if (filters.sortBy) {
            switch (filters.sortBy) {
                case 'name':
                    results.sort((a, b) => a.name.localeCompare(b.name));
                    break;
                case 'created':
                    results.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
                    break;
                case 'popularity':
                    const analytics = JSON.parse(localStorage.getItem('template_analytics') || '{}');
                    results.sort((a, b) => (analytics[b.id]?.count || 0) - (analytics[a.id]?.count || 0));
                    break;
                case 'difficulty':
                    const difficultyOrder = { 'beginner': 1, 'intermediate': 2, 'advanced': 3 };
                    results.sort((a, b) => difficultyOrder[a.difficulty] - difficultyOrder[b.difficulty]);
                    break;
            }
        }
        
        return results;
    }
    
    // Template recommendations
    getRecommendedTemplates(currentTemplate, limit = 3) {
        if (!currentTemplate) return this.getPopularTemplates(limit);
        
        const recommendations = Array.from(this.templates.values())
            .filter(template => template.id !== currentTemplate.id)
            .map(template => ({
                ...template,
                similarity: this.calculateTemplateSimilarity(currentTemplate, template)
            }))
            .sort((a, b) => b.similarity - a.similarity)
            .slice(0, limit);
        
        return recommendations;
    }
    
    calculateTemplateSimilarity(template1, template2) {
        let similarity = 0;
        
        // Category match
        if (template1.category === template2.category) {
            similarity += 0.4;
        }
        
        // Tag overlap
        if (template1.tags && template2.tags) {
            const commonTags = template1.tags.filter(tag => template2.tags.includes(tag));
            similarity += (commonTags.length / Math.max(template1.tags.length, template2.tags.length)) * 0.3;
        }
        
        // Difficulty similarity
        const difficultyScore = { 'beginner': 1, 'intermediate': 2, 'advanced': 3 };
        const diffDiff = Math.abs(difficultyScore[template1.difficulty] - difficultyScore[template2.difficulty]);
        similarity += (1 - diffDiff / 2) * 0.2;
        
        // Node count similarity
        const nodeDiff = Math.abs(template1.nodes - template2.nodes);
        similarity += Math.max(0, 1 - nodeDiff / 10) * 0.1;
        
        return similarity;
    }
    
    // Bulk operations
    exportAllTemplates() {
        const allTemplates = Array.from(this.templates.values());
        const exportData = {
            templates: allTemplates,
            exportedAt: new Date().toISOString(),
            version: '1.0',
            count: allTemplates.length
        };
        
        const blob = new Blob([JSON.stringify(exportData, null, 2)], {
            type: 'application/json'
        });
        
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `workflow_templates_${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        
        URL.revokeObjectURL(url);
    }
    
    importTemplateCollection(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => {
                try {
                    const data = JSON.parse(e.target.result);
                    
                    if (!data.templates || !Array.isArray(data.templates)) {
                        throw new Error('Invalid template collection format');
                    }
                    
                    const imported = [];
                    data.templates.forEach(templateData => {
                        if (templateData.name && templateData.workflow) {
                            const templateId = `imported_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`;
                            this.addTemplate(templateId, {
                                ...templateData,
                                isCustom: true,
                                importedAt: new Date()
                            });
                            imported.push(templateId);
                        }
                    });
                    
                    resolve(imported);
                } catch (error) {
                    reject(error);
                }
            };
            reader.readAsText(file);
        });
    }
    
    deleteTemplate(templateId) {
        const template = this.templates.get(templateId);
        if (!template || !template.isCustom) {
            if (window.notifications) {
                window.notifications.error('Cannot delete built-in templates');
            }
            return false;
        }
        
        this.templates.delete(templateId);
        
        // Remove from analytics
        const analytics = JSON.parse(localStorage.getItem('template_analytics') || '{}');
        delete analytics[templateId];
        localStorage.setItem('template_analytics', JSON.stringify(analytics));
        
        if (window.notifications) {
            window.notifications.success('Template deleted successfully');
        }
        
        return true;
    }
    
    duplicateTemplate(templateId) {
        const template = this.templates.get(templateId);
        if (!template) return null;
        
        const duplicateId = `duplicate_${Date.now()}`;
        const duplicate = {
            ...template,
            name: `${template.name} (Copy)`,
            isCustom: true,
            createdAt: new Date()
        };
        
        this.addTemplate(duplicateId, duplicate);
        
        if (window.notifications) {
            window.notifications.success('Template duplicated successfully');
        }
        
        return duplicateId;
    }
}

// Export for use in other modules
window.TemplateManager = TemplateManager;