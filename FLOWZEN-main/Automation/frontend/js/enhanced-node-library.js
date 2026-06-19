// Enhanced Node Library - Beautiful, Interactive Node Palette
class EnhancedNodeLibrary {
    constructor() {
        // HARD SINGLETON CHECK
        if (document.querySelector('.enhanced-node-library')) {
            console.warn("⚠️ EnhancedNodeLibrary ALREADY EXISTS in DOM. Aborting constructor.");
            return;
        }

        this.nodes = new Map();
        this.categories = new Map();
        this.searchIndex = new Map();
        this.container = null;
        this.isExpanded = true;

        this.init();
    }


    init() {
        this.loadNodeDefinitions();
        this.syncToGlobalRegistry(); // FORCE SYNC TO LEGACY REGISTRY
        this.createLibraryUI();
        this.setupInteractions();
        this.setupSearch();
        this.setupAnimations();
    }

    syncToGlobalRegistry() {
        // Ensure window.NODE_REGISTRY uses our enhanced definitions but formatted for Builder
        this.nodes.forEach((def, type) => {
            // Generate Builder-compatible 'fields' array from 'config' object
            let fields = [];
            if (def.config) {
                fields = Object.entries(def.config).map(([key, conf]) => {
                    const field = { key: key, label: conf.title || key };

                    // Map Types
                    if (conf.type === 'credential_select') {
                        field.type = 'credential';
                        // CORE FIX: Map snake_case credential_type to camelCase credentialType for Builder
                        field.credentialType = conf.credential_type || conf.credentialType;
                    } else if (conf.widget === 'code_editor') {
                        field.type = 'code_editor';
                        field.rows = 15;
                        field.className = 'monaco-editor-target'; // Modern hook
                        field.language = conf.language || 'python';
                        field.placeholder = 'Enter code here...';
                    } else if (conf.type === 'string' && conf.widget === 'textarea') {
                        field.type = 'textarea';
                    } else if (conf.type === 'string') {
                        field.type = 'text';
                    } else if (conf.widget === 'multiselect' || conf.type === 'multiselect') {
                        field.type = 'multiselect';
                        field.options = conf.options || [];
                    } else if (conf.type === 'select') {
                        field.type = 'select';
                        field.options = conf.options || [];
                    } else {
                        field.type = conf.type; // Fallback
                    }

                    // Copy other props
                    if (conf.default !== undefined) field.default = conf.default;
                    if (conf.options) field.options = conf.options;
                    if (conf.placeholder) field.placeholder = conf.placeholder;

                    return field;
                });
            }

            // GLOBAL CONFIG INJECTION (Batch 3: Reliability)
            // Add Retry/Timeout fields to all ACTION nodes (exclude triggers and logic/flow)
            if (def.category !== 'triggers' && def.category !== 'logic' && def.category !== 'utilities') {
                // Actually, let's add to utilities too (like HTTP), but maybe not flow logic
                // Let's exclude ONLY Triggers and Flow Control (If, Switch, Split)
                const excludedTypes = ['manual_trigger', 'webhook_trigger', 'if-condition', 'switch-case', 'merge', 'loop'];
                if (!excludedTypes.includes(type) && !type.endsWith('_trigger')) {
                    fields.push(
                        { key: 'divider_retry', type: 'divider', label: 'Reliability Settings' },
                        { key: 'retryOnFail', type: 'boolean', label: 'Retry On Fail', default: false },
                        { key: 'maxTries', type: 'number', label: 'Max Retries', default: 3 },
                        { key: 'waitBetweenTries', type: 'number', label: 'Retry Delay (ms)', default: 1000 },
                        { key: 'timeout', type: 'number', label: 'Timeout (ms)', default: 30000 }
                    );
                }
            }

            if (!window.NODE_REGISTRY[type]) {
                window.NODE_REGISTRY[type] = {
                    type: type,
                    label: def.name,
                    category: def.category,
                    icon: def.icon,
                    color: def.color,
                    defaultConfig: this.extractDefaultConfig(def.config),
                    fields: fields // Helper for Builder
                };
            } else {
                // Update existing if undefined or stale
                const existing = window.NODE_REGISTRY[type];
                existing.label = def.name;
                // Only overwrite if we have a valid config, otherwise keep existing fields (e.g. from nodes.js)
                if (fields.length > 0) {
                    existing.fields = fields;
                }
            }
        });
        console.log("✅ EnhancedNodeLibrary and Builder Schema synced.");
    }

    extractDefaultConfig(config) {
        if (!config) return {};
        const defaults = {};
        Object.entries(config).forEach(([key, conf]) => {
            defaults[key] = conf.default !== undefined ? conf.default : "";
        });
        return defaults;
    }

    loadNodeDefinitions() {
        // Core Categories
        this.addCategory('triggers', {
            name: 'Triggers',
            icon: 'fas fa-play-circle',
            color: '#10b981',
            description: 'Start your automation flows'
        });

        // Manual Trigger
        this.addNode('manual_trigger', {
            name: 'Manual Trigger',
            category: 'triggers',
            icon: 'fas fa-play',
            color: '#10b981',
            description: 'Manually start this workflow for testing',
            inputs: [],
            outputs: ['trigger_data'],
            config: {
                test_data: { type: 'json', title: 'Test Data JSON', default: '{}' }
            },
            tags: ['start', 'manual', 'test', 'trigger']
        });

        // Code Node (Python)
        this.addNode('code', {
            name: 'Python Code',
            category: 'utilities',
            icon: 'fab fa-python',
            color: '#3b82f6',
            description: 'Execute custom Python code',
            inputs: ['input'],
            outputs: ['result'],
            config: {
                code: {
                    type: 'string',
                    widget: 'code_editor',
                    language: 'python',
                    title: 'Python Code',
                    default: 'return {"message": "Hello World!"}'
                }
            },
            tags: ['python', 'code', 'script', 'custom']
        });

        // Logger Node
        this.addNode('logger', {
            name: 'Debug Log',
            category: 'utilities',
            icon: 'fas fa-bug',
            color: '#6b7280',
            description: 'Log data to the execution history',
            inputs: ['input'],
            outputs: ['output'],
            config: {
                message: { type: 'string', title: 'Log Message', default: 'Debug Info' },
                level: { type: 'select', options: ['info', 'warning', 'error', 'debug'], default: 'info', title: 'Level' },
                include_data: { type: 'boolean', default: true, title: 'Include Input Data' }
            },
            tags: ['log', 'debug', 'print', 'utility']
        });

        // Google Integrations Category
        this.addCategory('integrations', {
            name: 'Google Ecosystem',
            icon: 'fab fa-google',
            color: '#4285F4',
            description: 'Google Sheets, Drive, Calendar and YouTube'
        });

        // Google Sheets
        this.addNode('google_sheets', {
            name: 'Google Sheets',
            category: 'integrations',
            icon: 'fas fa-file-excel',
            color: '#0F9D58',
            description: 'Read, write, and update Google Sheets',
            inputs: ['input'],
            outputs: ['result'],
            config: {
                credential_id: { type: 'credential_select', credential_type: 'google_oauth', title: 'Google Credential' },
                operation: { type: 'select', options: ['append', 'get', 'update', 'clear', 'lookup'], default: 'append', title: 'Operation' },
                spreadsheet_id: { type: 'string', title: 'Spreadsheet ID', placeholder: 'Enter ID from URL' },
                range: { type: 'string', title: 'Range', placeholder: 'Sheet1!A1:B10' },
                values: { type: 'string', widget: 'textarea', title: 'Values (JSON)', placeholder: '[["Row1", "Value"]]' },
                sheet_name: { type: 'string', title: 'Sheet Name', default: 'Sheet1' },
                lookup_column: { type: 'string', title: 'Lookup Column', default: 'A' },
                lookup_value: { type: 'string', title: 'Lookup Value' },
                fail_if_not_found: { type: 'boolean', default: false, title: 'Fail if not found' }
            },
            tags: ['google', 'sheets', 'spreadsheet', 'data']
        });

        // Google Drive
        this.addNode('google_drive', {
            name: 'Google Drive',
            category: 'integrations',
            icon: 'fab fa-google-drive',
            color: '#4285F4',
            description: 'Manage files on Google Drive',
            inputs: ['input'],
            outputs: ['result'],
            config: {
                credential_id: { type: 'credential_select', credential_type: 'google_oauth', title: 'Google Credential' },
                operation: { type: 'select', options: ['upload', 'list', 'create_folder', 'delete'], default: 'upload', title: 'Operation' },
                filename: { type: 'string', title: 'File Name', default: 'file.txt' },
                content: { type: 'string', widget: 'textarea', title: 'Text Content' },
                mime_type: { type: 'string', title: 'MIME Type', default: 'text/plain' },
                parent_id: { type: 'string', title: 'Parent Folder ID' },
                query: { type: 'string', title: 'Search Query' },
                limit: { type: 'number', default: 10, title: 'Limit' },
                folder_name: { type: 'string', title: 'Folder Name' },
                file_id: { type: 'string', title: 'File ID' }
            },
            tags: ['google', 'drive', 'files', 'storage']
        });

        // YouTube
        this.addNode('youtube', {
            name: 'YouTube',
            category: 'integrations',
            icon: 'fab fa-youtube',
            color: '#FF0000',
            description: 'Search, Get Video, and Comment on YouTube',
            inputs: ['input'],
            outputs: ['output'],
            config: {
                credential_id: { type: 'credential_select', credential_type: 'google_oauth', title: 'Google Credential' },
                operation: { type: 'select', options: ['search', 'get_video', 'comment'], default: 'search', title: 'Operation' },
                query: { type: 'string', title: 'Search Query' },
                max_results: { type: 'number', default: 5, title: 'Max Results' },
                video_id: { type: 'string', title: 'Video ID' },
                comment_text: { type: 'string', widget: 'textarea', title: 'Comment Text' }
            },
            tags: ['google', 'youtube', 'video', 'social']
        });

        // Google Calendar
        this.addNode('google_calendar', {
            name: 'Google Calendar',
            category: 'integrations',
            icon: 'fas fa-calendar-alt',
            color: '#4285F4',
            description: 'Manage Google Calendar events',
            inputs: ['input'],
            outputs: ['output'],
            config: {
                credential_id: { type: 'credential_select', credential_type: 'google_calendar', title: 'Calendar Credential' },
                operation: { type: 'select', options: ['create', 'update', 'delete', 'get'], default: 'create', title: 'Operation' },
                calendar_id: { type: 'string', title: 'Calendar ID', default: 'primary' },
                summary: { type: 'string', title: 'Summary' },
                description: { type: 'string', widget: 'textarea', title: 'Description' },
                location: { type: 'string', title: 'Location' },
                start_time: { type: 'string', title: 'Start Time' },
                end_time: { type: 'string', title: 'End Time' },
                timezone: { type: 'string', title: 'Timezone', default: 'UTC' },
                attendees: { type: 'string', title: 'Attendees (Comma-separated)' },
                event_id: { type: 'string', title: 'Event ID' }
            },
            tags: ['google', 'calendar', 'events', 'schedule']
        });

        // AI & Machine Learning Nodes
        this.addCategory('ai', {
            name: 'AI & ML',
            icon: 'fas fa-brain',
            color: '#8b5cf6',
            description: 'Artificial Intelligence and Machine Learning nodes'
        });

        // AI Agent - Enhanced Definition
        this.addNode('ai_agent', {
            name: 'AI Agent',
            category: 'ai',
            icon: 'fas fa-robot',
            color: '#8b5cf6',
            description: 'Autonomous AI agent with tools, memory, and decisions',
            inputs: ['input', 'tools', 'memory'],
            outputs: ['output', 'decision', 'tool_result'],
            tags: ['ai', 'agent', 'automation', 'tools'],
            config: {
                credential_id: { type: 'credential_select', credential_type: 'ai_provider', title: 'AI Provider' },
                model: { type: 'string', default: 'gpt-4', title: 'Model' },
                temperature: { type: 'slider', min: 0, max: 2, default: 0.7, title: 'Temperature' },
                max_tokens: { type: 'number', default: 2000, title: 'Max Tokens' },
                system_prompt: { type: 'string', widget: 'textarea', title: 'System Prompt', default: 'You are a helpful AI assistant.' },
                user_prompt: { type: 'string', widget: 'textarea', title: 'User Prompt', placeholder: '{{ telegram_trigger.json.clean_text }}' },
                tools: { type: 'json', title: 'Tools Configuration', default: '[]' }
            }
        });


        this.addNode('openai-gpt', {
            name: 'OpenAI GPT',
            category: 'ai',
            icon: 'fas fa-robot',
            description: 'Generate text using OpenAI GPT models',
            color: '#10b981',
            inputs: ['prompt', 'context'],
            outputs: ['text', 'usage'],
            config: {
                model: { type: 'select', options: ['gpt-4', 'gpt-3.5-turbo'], default: 'gpt-4' },
                temperature: { type: 'slider', min: 0, max: 2, default: 0.7 },
                max_tokens: { type: 'number', default: 1000 }
            },
            tags: ['ai', 'text', 'generation', 'openai']
        });

        this.addNode('image-generator', {
            name: 'AI Image Generator',
            category: 'ai',
            icon: 'fas fa-image',
            description: 'Generate images using AI models',
            color: '#f59e0b',
            inputs: ['prompt', 'style'],
            outputs: ['image_url', 'metadata'],
            config: {
                model: { type: 'select', options: ['dall-e-3', 'midjourney', 'stable-diffusion'] },
                size: { type: 'select', options: ['256x256', '512x512', '1024x1024'] },
                quality: { type: 'select', options: ['standard', 'hd'] }
            },
            tags: ['ai', 'image', 'generation', 'creative']
        });

        this.addNode('sentiment-analysis', {
            name: 'Sentiment Analysis',
            category: 'ai',
            icon: 'fas fa-heart',
            description: 'Analyze sentiment of text content',
            color: '#ef4444',
            inputs: ['text'],
            outputs: ['sentiment', 'confidence', 'emotions'],
            config: {
                provider: { type: 'select', options: ['openai', 'huggingface', 'aws-comprehend'] },
                language: { type: 'select', options: ['auto', 'en', 'es', 'fr', 'de'] }
            },
            tags: ['ai', 'nlp', 'sentiment', 'analysis']
        });

        // Communication Nodes
        this.addCategory('communication', {
            name: 'Communication',
            icon: 'fas fa-comments',
            color: '#3b82f6',
            description: 'Email, messaging, and communication tools'
        });

        // WhatsApp Nodes
        this.addNode('whatsapp_trigger', {
            name: 'WhatsApp Trigger',
            category: 'triggers',
            icon: 'MessageCircle',
            color: 'green',
            inputs: [],
            outputs: ['message', 'sender', 'data'],
            config: {
                credential_id: { type: 'credential_select', credential_type: 'meta_whatsapp', title: 'WhatsApp Account' }
            },
            tags: ['whatsapp', 'meta', 'trigger', 'chat']
        });

        this.addNode('whatsapp_send', {
            name: 'WhatsApp Send',
            category: 'communication',
            icon: 'fab fa-whatsapp',
            description: 'Send WhatsApp message (Text/Template)',
            color: '#25D366',
            inputs: ['main'],
            outputs: ['output'],
            config: {
                credential_id: { type: 'credential_select', credential_type: 'meta_whatsapp', title: 'WhatsApp Account' },
                recipient_number: { type: 'string', title: 'Recipient Number' },
                message_text: { type: 'string', widget: 'textarea', title: 'Message Text' },
                message_type: { type: 'select', options: ['text', 'template'], default: 'text', title: 'Message Type' },
                template_name: { type: 'string', title: 'Template Name' },
                template_language: { type: 'string', default: 'en_US', title: 'Language' },
                template_params: { type: 'string', widget: 'textarea', title: 'Template Params (CSV/JSON)' }
            },
            tags: ['whatsapp', 'meta', 'send', 'message']
        });

        // Telegram Nodes
        this.addNode('telegram_trigger', {
            name: 'Telegram Trigger',
            category: 'communication',
            icon: 'fab fa-telegram',
            description: 'Triggers on incoming Telegram message/command',
            color: '#0088cc',
            inputs: [],
            outputs: ['message', 'chat_id', 'user'],
            config: {
                credential_id: { type: 'credential_select', credential_type: 'telegram_bot', title: 'Bot Credential' },
                chatbot_mode: { type: 'boolean', default: false, title: 'Chatbot Mode' },
                events: { type: 'multiselect', options: ['message', 'command', 'photo', 'voice'], default: ['message', 'command'], title: 'Events' }
            },
            tags: ['telegram', 'bot', 'trigger', 'chat']
        });

        // Google Calendar Trigger
        this.addNode('google_calendar_trigger', {
            name: 'Google Calendar Trigger',
            category: 'triggers',
            icon: 'fas fa-calendar-check',
            description: 'Triggers on new or updated calendar events',
            color: '#10b981',
            inputs: [],
            outputs: ['events', 'count'],
            config: {
                credential_id: { type: 'credential_select', credential_type: 'google_calendar', title: 'Calendar Credential' },
                calendar_id: { type: 'string', title: 'Calendar ID', default: 'primary' },
                trigger_on: { type: 'select', options: ['event_created', 'event_starting'], default: 'event_created', title: 'Trigger On' },
                poll_interval: { type: 'number', default: 1, title: 'Poll Interval (Min)' }
            },
            tags: ['google', 'calendar', 'trigger', 'events']
        });

        // Discord Node
        this.addNode('discord', {
            name: 'Discord',
            category: 'communication',
            icon: 'fab fa-discord',
            color: '#5865F2',
            description: 'Send messages via Webhook or Bot',
            inputs: ['input'],
            outputs: ['output'],
            config: {
                mode: { type: 'select', options: ['webhook', 'bot'], default: 'webhook', title: 'Mode' },
                credential_id: { type: 'credential_select', credential_type: 'discord_bot', title: 'Bot Token' },
                webhook_url: { type: 'string', title: 'Webhook URL' },
                channel_id: { type: 'string', title: 'Channel ID' },
                message: { type: 'string', widget: 'textarea', title: 'Message' },
                username: { type: 'string', title: 'Username Override' }
            },
            tags: ['discord', 'chat', 'notification', 'bot']
        });

        this.addNode('telegram_send', {
            name: 'Telegram Send',
            category: 'communication',
            icon: 'fab fa-telegram',
            description: 'Send Telegram message',
            color: '#0088cc',
            inputs: ['chat_id', 'text'],
            outputs: ['message_id', 'result'],
            config: {
                credential_id: { type: 'credential_select', credential_type: 'telegram_bot', title: 'Bot Credential' },
                chat_id: { type: 'string', title: 'Chat ID' },
                text: { type: 'string', widget: 'textarea', title: 'Message Text' },
                parse_mode: { type: 'select', options: ['Markdown', 'HTML', 'None'], default: 'Markdown', title: 'Parse Mode' }
            },
            tags: ['telegram', 'bot', 'send', 'message']
        });

        this.addNode('send_email', {
            name: 'Gmail Send',
            category: 'communication',
            icon: 'fab fa-google',
            description: 'Send emails via Gmail',
            color: '#ea4335',
            inputs: ['to', 'subject', 'body', 'attachments'],
            outputs: ['message_id', 'status'],
            config: {
                credential_id: { type: 'credential_select', credential_type: 'email', title: 'Email Credential' },
                to: { type: 'string', title: 'To Email', placeholder: 'recipient@example.com' },
                subject: { type: 'string', title: 'Subject' },
                body: { type: 'string', widget: 'textarea', title: 'Body' },
                is_html: { type: 'boolean', default: false, title: 'Send as HTML' },
                cc: { type: 'string', title: 'CC' },
                bcc: { type: 'string', title: 'BCC' }
            },
            tags: ['email', 'gmail', 'send', 'communication']
        });

        this.addNode('slack_message', {
            name: 'Slack Message',
            category: 'communication',
            icon: 'fab fa-slack',
            description: 'Send messages to Slack channels',
            color: '#4a154b',
            inputs: ['channel', 'message', 'attachments'],
            outputs: ['timestamp', 'status'],
            config: {
                webhook_url: { type: 'url', title: 'Webhook URL', required: true },
                channel: { type: 'string', title: 'Channel Name/ID', placeholder: '#general' },
                message: { type: 'string', widget: 'textarea', title: 'Message Content' },
                username: { type: 'text', title: 'Bot Username' },
                emoji: { type: 'text', title: 'Icon Emoji', default: ':robot_face:' }
            },
            tags: ['slack', 'message', 'team', 'notification']
        });

        // Data Processing Nodes
        this.addCategory('data', {
            name: 'Data Processing',
            icon: 'fas fa-database',
            color: '#06b6d4',
            description: 'Data transformation and processing tools'
        });

        this.addNode('json-processor', {
            name: 'JSON Processor',
            category: 'data',
            icon: 'fas fa-code',
            description: 'Parse, transform, and manipulate JSON data',
            color: '#8b5cf6',
            inputs: ['json_data'],
            outputs: ['processed_data', 'errors'],
            config: {
                operation: { type: 'select', options: ['parse', 'stringify', 'transform', 'filter'] },
                path: { type: 'text', placeholder: '$.data.items' },
                transform_script: { type: 'code', language: 'javascript' }
            },
            tags: ['json', 'data', 'transform', 'parse']
        });

        this.addNode('csv-processor', {
            name: 'CSV Processor',
            category: 'data',
            icon: 'fas fa-table',
            description: 'Process and transform CSV data',
            color: '#10b981',
            inputs: ['csv_data', 'headers'],
            outputs: ['processed_data', 'row_count'],
            config: {
                delimiter: { type: 'text', default: ',' },
                has_headers: { type: 'boolean', default: true },
                encoding: { type: 'select', options: ['utf-8', 'latin1', 'ascii'] }
            },
            tags: ['csv', 'data', 'spreadsheet', 'table']
        });

        // Memory Node
        this.addNode('memory', {
            name: 'Memory (Redis)',
            category: 'data',
            icon: 'fas fa-memory',
            description: 'Store and retrieve data using Redis',
            color: '#dc2626',
            inputs: ['input'],
            outputs: ['result'],
            config: {
                operation: { type: 'select', options: ['set', 'get', 'increment', 'delete'], default: 'set', title: 'Operation' },
                key: { type: 'string', title: 'Key' },
                value: { type: 'string', widget: 'textarea', title: 'Value' },
                delta: { type: 'number', default: 1, title: 'Increment By' },
                scope: { type: 'select', options: ['workflow', 'user', 'global'], default: 'workflow', title: 'Scope' },
                ttl: { type: 'number', default: 86400, title: 'TTL (Seconds)' }
            },
            tags: ['memory', 'redis', 'cache', 'storage']
        });

        // HTTP & API Nodes
        this.addCategory('http', {
            name: 'HTTP & APIs',
            icon: 'fas fa-globe',
            color: '#f59e0b',
            description: 'HTTP requests and API integrations'
        });

        this.addNode('http_request', {
            name: 'HTTP Request',
            category: 'http',
            icon: 'fas fa-exchange-alt',
            description: 'Make HTTP requests to any API',
            color: '#3b82f6',
            inputs: ['url', 'headers', 'body'],
            outputs: ['response', 'status_code', 'headers'],
            config: {
                method: { type: 'select', title: 'Method', options: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH'], default: 'GET' },
                url: { type: 'string', title: 'URL', placeholder: 'https://api.example.com' },
                headers: { type: 'string', widget: 'textarea', title: 'Headers (JSON)', placeholder: '{"Content-Type": "application/json"}' },
                body_type: { type: 'select', title: 'Body Type', options: ['json', 'raw'], default: 'json' },
                body: { type: 'string', widget: 'textarea', title: 'Body (JSON/Text)', placeholder: '{"key": "value"}' },
                timeout: { type: 'number', title: 'Timeout (ms)', default: 30000 },
                follow_redirects: { type: 'boolean', title: 'Follow Redirects', default: true }
            },
            tags: ['http', 'api', 'request', 'web']
        });

        this.addNode('webhook_trigger', {
            name: 'Webhook Trigger',
            category: 'http',
            icon: 'fas fa-bolt',
            description: 'Trigger workflows via HTTP webhooks',
            color: '#ef4444',
            inputs: [],
            outputs: ['body', 'headers', 'query_params'],
            config: {
                path: { type: 'text', title: 'Webhook Path', default: '/webhook' },
                methods: { type: 'multiselect', title: 'Allowed Methods', options: ['GET', 'POST', 'PUT', 'DELETE'] },
                authentication: { type: 'select', title: 'Authentication', options: ['none', 'basic', 'bearer', 'api_key'], default: 'none' }
            },
            tags: ['webhook', 'trigger', 'http', 'automation']
        });

        // Logic & Control Nodes
        this.addCategory('logic', {
            name: 'Logic & Control',
            icon: 'fas fa-sitemap',
            color: '#ef4444',
            description: 'Conditional logic and flow control'
        });

        this.addNode('if_else', {
            name: 'IF Condition',
            category: 'logic',
            icon: 'fas fa-question-circle',
            description: 'Conditional branching based on data',
            color: '#f59e0b',
            inputs: ['condition', 'true_value', 'false_value'],
            outputs: ['result', 'branch_taken'],
            config: {
                operator: { type: 'select', options: ['equals', 'not_equals', 'greater_than', 'less_than', 'contains'] },
                case_sensitive: { type: 'boolean', default: true }
            },
            tags: ['condition', 'if', 'logic', 'branch']
        });

        this.addNode('switch', {
            name: 'Switch Case',
            category: 'logic',
            icon: 'fas fa-code-branch',
            description: 'Multi-way branching logic',
            color: '#8b5cf6',
            inputs: ['input_value'],
            outputs: ['matched_case', 'output_value'],
            config: {
                cases: { type: 'key_value_list' },
                default_case: { type: 'text' },
                match_type: { type: 'select', options: ['exact', 'regex', 'contains'] }
            },
            tags: ['switch', 'case', 'logic', 'branch']
        });

        // Parallel Fork
        this.addNode('parallel_fork', {
            name: 'Parallel Fork',
            category: 'logic',
            icon: 'fas fa-code-branch',
            description: 'Split workflow execution into parallel branches',
            color: '#fbbf24',
            inputs: ['input'],
            outputs: ['branch_1', 'branch_2'],
            config: {
                branch_count: { type: 'number', default: 2, title: 'Number of Branches' },
                branch_names: { type: 'string', title: 'Branch Names (Comma-separated)' },
                execution_mode: { type: 'select', options: ['sync', 'async'], default: 'sync', title: 'Execution Mode' },
                timeout_ms: { type: 'number', default: 60000, title: 'Timeout (ms)' },
                failure_strategy: { type: 'select', options: ['fail_fast', 'continue_on_error', 'wait_for_all'], default: 'fail_fast', title: 'Failure Strategy' }
            },
            tags: ['parallel', 'fork', 'split', 'logic']
        });

        // Parallel Merge
        this.addNode('parallel_merge', {
            name: 'Parallel Merge',
            category: 'logic',
            icon: 'fas fa-layer-group',
            description: 'Merge parallel branches back into one',
            color: '#fbbf24',
            inputs: ['branches'],
            outputs: ['merged_result'],
            config: {
                merge_strategy: { type: 'select', options: ['all', 'first_success', 'majority', 'any'], default: 'all', title: 'Merge Strategy' },
                merge_mode: { type: 'select', options: ['array', 'object', 'flatten', 'first'], default: 'array', title: 'Merge Mode' },
                timeout_ms: { type: 'number', default: 60000, title: 'Timeout (ms)' },
                failure_strategy: { type: 'select', options: ['fail_on_any', 'partial_success', 'ignore_failures'], default: 'fail_on_any', title: 'Failure Strategy' }
            },
            tags: ['parallel', 'merge', 'join', 'logic']
        });

        // Router
        this.addNode('router', {
            name: 'Router / Switch',
            category: 'logic',
            icon: 'fas fa-random',
            description: 'Route execution based on multiple rules',
            color: '#ef4444',
            inputs: ['input'],
            outputs: ['path_1', 'path_2', 'default'],
            config: {
                rules: { type: 'json', title: 'Routing Rules (JSON)', default: '[]' },
                default_path: { type: 'string', default: 'default', title: 'Default Path' },
                case_sensitive: { type: 'boolean', default: true, title: 'Case Sensitive' },
                evaluation_strategy: { type: 'select', options: ['first_match', 'all_matches'], default: 'first_match', title: 'Evaluation Strategy' }
            },
            tags: ['router', 'switch', 'logic', 'routing']
        });

        // Loop
        this.addNode('loop', {
            name: 'Loop (Iterator)',
            category: 'logic',
            icon: 'fas fa-redo',
            description: 'Iterate over a list and run sub-workflow',
            color: '#ec4899',
            inputs: ['items'],
            outputs: ['results'],
            config: {
                items: { type: 'string', title: 'Items to Iterate' },
                sub_workflow: { type: 'string', title: 'Sub-Workflow ID' }
            },
            tags: ['loop', 'iterate', 'foreach', 'logic']
        });

        // Utility Nodes
        this.addCategory('utilities', {
            name: 'Utilities',
            icon: 'fas fa-tools',
            color: '#6b7280',
            description: 'Helper functions and utilities'
        });

        this.addNode('delay', {
            name: 'Delay',
            category: 'utilities',
            icon: 'fas fa-clock',
            description: 'Add delays to workflow execution',
            color: '#6b7280',
            inputs: ['trigger'],
            outputs: ['delayed_output'],
            config: {
                duration: { type: 'number', default: 1000 },
                unit: { type: 'select', options: ['milliseconds', 'seconds', 'minutes'] }
            },
            tags: ['delay', 'wait', 'timing', 'utility']
        });
        // --- BATCH 3 EXPANSION NODES ---

        // Logic Nodes
        this.addNode('switch', {
            name: 'Switch',
            category: 'logic',
            icon: 'fas fa-code-branch',
            description: 'Route based on multiple value matches',
            color: '#8b5cf6',
            inputs: ['input'],
            outputs: ['output'], // Dynamic output handling in future
            config: {
                value: { type: 'string', title: 'Value to Match' },
                cases: { type: 'json', title: 'Cases (JSON Output List)', default: '[]' },
                default_case: { type: 'string', title: 'Default Case Output' }
            },
            tags: ['switch', 'logic', 'route']
        });

        // Utility Nodes
        this.addNode('date_time', {
            name: 'Date & Time',
            category: 'utilities',
            icon: 'far fa-clock',
            description: 'Format, calculate, or get current time',
            color: '#6b7280',
            inputs: ['trigger'],
            outputs: ['date'],
            config: {
                operation: { type: 'select', options: ['current', 'format', 'add'], default: 'current' },
                format: { type: 'string', default: '%Y-%m-%d %H:%M:%S', title: 'Format' },
                timezone: { type: 'string', default: 'UTC', title: 'Timezone' },
                date: { type: 'string', title: 'Input Date' },
                value: { type: 'number', title: 'Value to Add' },
                unit: { type: 'select', options: ['hours', 'days', 'minutes'], default: 'hours' }
            },
            tags: ['date', 'time', 'format', 'utility']
        });

        this.addNode('crypto', {
            name: 'Crypto & Hash',
            category: 'utilities',
            icon: 'fas fa-lock',
            description: 'Hashing (MD5, SHA) and Base64',
            color: '#6b7280',
            inputs: ['input'],
            outputs: ['hash'],
            config: {
                action: { type: 'select', options: ['hash', 'hmac', 'base64_encode', 'base64_decode'], default: 'hash' },
                value: { type: 'string', title: 'Value' },
                algo: { type: 'select', options: ['sha256', 'md5', 'sha512'], default: 'sha256' },
                secret: { type: 'string', title: 'Secret (HMAC)' }
            },
            tags: ['crypto', 'hash', 'security']
        });

        this.addNode('markdown', {
            name: 'Markdown to HTML',
            category: 'utilities',
            icon: 'fab fa-markdown',
            description: 'Convert Markdown text to HTML',
            color: '#6b7280',
            inputs: ['markdown'],
            outputs: ['html'],
            config: {
                content: { type: 'string', widget: 'textarea', title: 'Markdown Content' }
            },
            tags: ['markdown', 'html', 'convert']
        });

        this.addNode('rss_read', {
            name: 'RSS Reader',
            category: 'utilities',
            icon: 'fas fa-rss',
            description: 'Fetch and parse RSS feeds',
            color: '#ea580c',
            inputs: ['trigger'],
            outputs: ['items'],
            config: {
                url: { type: 'string', title: 'Feed URL' }
            },
            tags: ['rss', 'feed', 'ingest']
        });

        this.addNode('inspector', {
            name: 'Payload Inspector',
            category: 'utilities',
            icon: 'fas fa-microscope',
            description: 'Debug: Log and inspect data payload',
            color: '#475569',
            inputs: ['input'],
            outputs: ['output'],
            config: {},
            tags: ['debug', 'inspect', 'log']
        });

        // Sticky Note (Canvas Annotation)
        this.addNode('sticky_note', {
            name: 'Sticky Note',
            category: 'utilities',
            icon: 'fas fa-sticky-note',
            description: 'Add a note to the canvas',
            color: '#facc15', // Yellow
            inputs: [],
            outputs: [],
            config: {
                text: { type: 'string', widget: 'textarea', title: 'Note Text', default: 'My Note' },
                color: { type: 'select', options: ['yellow', 'blue', 'green', 'red'], default: 'yellow' }
            },
            tags: ['note', 'comment', 'annotation']
        });


        this.addNode('random-generator', {
            name: 'Random Generator',
            category: 'utilities',
            icon: 'fas fa-dice',
            description: 'Generate random numbers, strings, or UUIDs',
            color: '#10b981',
            inputs: ['seed'],
            outputs: ['random_value'],
            config: {
                type: { type: 'select', options: ['number', 'string', 'uuid', 'boolean'] },
                min: { type: 'number', default: 0 },
                max: { type: 'number', default: 100 },
                length: { type: 'number', default: 10 }
            },
            tags: ['random', 'generator', 'uuid', 'utility']
        });
    }

    addCategory(id, category) {
        this.categories.set(id, { id, ...category });
    }

    addNode(id, node) {
        const nodeData = { id, ...node };
        this.nodes.set(id, nodeData);

        // Add to search index
        const searchTerms = [
            node.name.toLowerCase(),
            node.description.toLowerCase(),
            ...node.tags.map(tag => tag.toLowerCase())
        ].join(' ');

        this.searchIndex.set(id, searchTerms);
    }

    createLibraryUI() {
        // Create main container
        this.container = document.createElement('div');
        this.container.className = 'enhanced-node-library';
        this.container.innerHTML = `
            <div class="library-header">
                <div class="library-title">
                    <i class="fas fa-cubes"></i>
                    <span>Node Library</span>
                </div>
                <div class="library-controls">
                    <button class="library-search-btn" data-tooltip="Search nodes">
                        <i class="fas fa-search"></i>
                    </button>
                    <button class="library-collapse-btn" data-tooltip="Collapse library">
                        <i class="fas fa-chevron-left"></i>
                    </button>
                </div>
            </div>
            
            <div class="library-search">
                <div class="search-input-container">
                    <i class="fas fa-search"></i>
                    <input type="text" class="search-input" placeholder="Search nodes...">
                    <button class="search-clear">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="search-filters">
                    <button class="filter-btn active" data-category="all">All</button>
                </div>
            </div>
            
            <div class="library-content">
                <div class="node-categories"></div>
            </div>
            
            <div class="library-footer">
                <div class="node-count">
                    <span class="count-number">${this.nodes.size}</span>
                    <span class="count-label">nodes available</span>
                </div>
            </div>
        `;

        // Add to page
        // Add to page
        const existingLibrary = document.querySelector('.node-library, .n8n-sidebar, .sidebar');
        if (existingLibrary) {
            existingLibrary.parentNode.replaceChild(this.container, existingLibrary);
        } else {
            // Fallback: Try to insert after toolbar or at beginning of main content
            const mainContent = document.querySelector('.main-content');
            if (mainContent) {
                mainContent.insertBefore(this.container, mainContent.firstChild);
            } else {
                document.body.appendChild(this.container);
            }
        }

        this.renderCategories();
        this.setupStyles();
    }

    renderCategories() {
        const container = this.container.querySelector('.node-categories');
        const filtersContainer = this.container.querySelector('.search-filters');

        container.innerHTML = '';

        // Add category filters
        this.categories.forEach(category => {
            const filterBtn = document.createElement('button');
            filterBtn.className = 'filter-btn';
            filterBtn.dataset.category = category.id;
            filterBtn.innerHTML = `<i class="${category.icon}"></i> ${category.name}`;
            filtersContainer.appendChild(filterBtn);
        });

        // Render each category
        this.categories.forEach(category => {
            const categoryElement = this.createCategoryElement(category);
            container.appendChild(categoryElement);
        });
    }

    createCategoryElement(category) {
        const categoryNodes = Array.from(this.nodes.values())
            .filter(node => node.category === category.id);

        const element = document.createElement('div');
        element.className = 'node-category';
        element.dataset.category = category.id;

        element.innerHTML = `
            <div class="category-header">
                <div class="category-icon" style="background: ${category.color}20; color: ${category.color}">
                    <i class="${category.icon}"></i>
                </div>
                <div class="category-info">
                    <h3>${category.name}</h3>
                    <p>${category.description}</p>
                </div>
                <button class="category-toggle">
                    <i class="fas fa-chevron-down"></i>
                </button>
            </div>
            <div class="category-nodes">
                ${categoryNodes.map(node => this.createNodeElement(node)).join('')}
            </div>
        `;

        return element;
    }

    createNodeElement(node) {
        return `
            <div class="node-item" 
                 data-node-id="${node.id}" 
                 data-category="${node.category}"
                 draggable="true"
                 data-tooltip="${node.description}"
                 data-tooltip-position="right">
                <div class="node-icon" style="background: ${node.color}20; color: ${node.color}">
                    <i class="${node.icon}"></i>
                </div>
                <div class="node-info">
                    <h4>${node.name}</h4>
                    <p>${node.description}</p>
                    <div class="node-tags">
                        ${node.tags.slice(0, 3).map(tag => `<span class="node-tag">${tag}</span>`).join('')}
                    </div>
                </div>
                <div class="node-actions">
                    <button class="node-action-btn" data-action="info" data-tooltip="Node info">
                        <i class="fas fa-info-circle"></i>
                    </button>
                    <button class="node-action-btn" data-action="favorite" data-tooltip="Add to favorites">
                        <i class="far fa-heart"></i>
                    </button>
                </div>
            </div>
        `;
    }

    setupInteractions() {
        // Category toggle
        this.container.addEventListener('click', (e) => {
            if (e.target.closest('.category-toggle')) {
                const category = e.target.closest('.node-category');
                const nodes = category.querySelector('.category-nodes');
                const icon = e.target.closest('.category-toggle').querySelector('i');

                category.classList.toggle('collapsed');

                if (category.classList.contains('collapsed')) {
                    nodes.style.maxHeight = '0';
                    icon.style.transform = 'rotate(-90deg)';
                } else {
                    nodes.style.maxHeight = nodes.scrollHeight + 'px';
                    icon.style.transform = 'rotate(0deg)';
                }
            }
        });

        // Node actions
        this.container.addEventListener('click', (e) => {
            if (e.target.closest('.node-action-btn')) {
                e.stopPropagation();
                const action = e.target.closest('.node-action-btn').dataset.action;
                const nodeId = e.target.closest('.node-item').dataset.nodeId;

                this.handleNodeAction(action, nodeId);
            }
        });

        // Library controls
        this.container.querySelector('.library-collapse-btn').addEventListener('click', () => {
            this.toggleLibrary();
        });

        this.container.querySelector('.library-search-btn').addEventListener('click', () => {
            this.toggleSearch();
        });

        // Filter buttons
        this.container.addEventListener('click', (e) => {
            if (e.target.classList.contains('filter-btn')) {
                this.setActiveFilter(e.target);
                this.filterNodes(e.target.dataset.category);
            }
        });

        // Drag and drop
        this.setupDragAndDrop();
    }

    setupSearch() {
        const searchInput = this.container.querySelector('.search-input');
        const clearBtn = this.container.querySelector('.search-clear');

        searchInput.addEventListener('input', (e) => {
            this.performSearch(e.target.value);
            clearBtn.style.display = e.target.value ? 'block' : 'none';
        });

        clearBtn.addEventListener('click', () => {
            searchInput.value = '';
            this.performSearch('');
            clearBtn.style.display = 'none';
            searchInput.focus();
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'k') {
                e.preventDefault();
                searchInput.focus();
            }
        });
    }

    setupDragAndDrop() {
        this.container.addEventListener('dragstart', (e) => {
            if (e.target.closest('.node-item')) {
                const item = e.target.closest('.node-item');
                const nodeId = item.dataset.nodeId;
                const node = this.nodes.get(nodeId);

                // Payload for builder compatibility
                e.dataTransfer.setData('text/plain', nodeId);

                // Extended payload
                e.dataTransfer.setData('application/json', JSON.stringify({
                    type: 'node',
                    nodeId: nodeId,
                    nodeData: node
                }));

                item.classList.add('dragging');
                this.createDragPreview(item, e);
            }
        });

        this.container.addEventListener('dragend', (e) => {
            if (e.target.classList.contains('node-item')) {
                e.target.classList.remove('dragging');
                this.removeDragPreview();
            }
        });
    }

    createDragPreview(element, event) {
        const preview = element.cloneNode(true);
        preview.className = 'node-drag-preview';
        preview.style.cssText = `
            position: fixed;
            top: ${event.clientY - 30}px;
            left: ${event.clientX - 100}px;
            width: 200px;
            opacity: 0.8;
            transform: rotate(5deg);
            pointer-events: none;
            z-index: 10000;
            transition: all 0.2s ease;
        `;

        document.body.appendChild(preview);
        this.dragPreview = preview;

        // Animate preview
        requestAnimationFrame(() => {
            preview.style.transform = 'rotate(0deg) scale(0.9)';
        });
    }

    removeDragPreview() {
        if (this.dragPreview) {
            this.dragPreview.style.opacity = '0';
            this.dragPreview.style.transform = 'scale(0.8)';

            setTimeout(() => {
                if (this.dragPreview && this.dragPreview.parentNode) {
                    this.dragPreview.parentNode.removeChild(this.dragPreview);
                }
                this.dragPreview = null;
            }, 200);
        }
    }

    performSearch(query) {
        const normalizedQuery = query.toLowerCase().trim();

        if (!normalizedQuery) {
            this.showAllNodes();
            return;
        }

        const matchingNodes = [];

        this.searchIndex.forEach((searchTerms, nodeId) => {
            if (searchTerms.includes(normalizedQuery)) {
                matchingNodes.push(nodeId);
            }
        });

        this.showSearchResults(matchingNodes, query);
    }

    showSearchResults(nodeIds, query) {
        const categories = this.container.querySelectorAll('.node-category');

        categories.forEach(category => {
            const nodes = category.querySelectorAll('.node-item');
            let hasVisibleNodes = false;

            nodes.forEach(node => {
                const nodeId = node.dataset.nodeId;
                const isMatch = nodeIds.includes(nodeId);

                node.style.display = isMatch ? 'flex' : 'none';

                if (isMatch) {
                    hasVisibleNodes = true;
                    this.highlightSearchTerms(node, query);
                }
            });

            category.style.display = hasVisibleNodes ? 'block' : 'none';

            // Expand categories with results
            if (hasVisibleNodes) {
                category.classList.remove('collapsed');
                const nodesContainer = category.querySelector('.category-nodes');
                nodesContainer.style.maxHeight = nodesContainer.scrollHeight + 'px';
            }
        });

        // Update count
        this.updateNodeCount(nodeIds.length);
    }

    showAllNodes() {
        const categories = this.container.querySelectorAll('.node-category');
        const nodes = this.container.querySelectorAll('.node-item');

        categories.forEach(category => {
            category.style.display = 'block';
        });

        nodes.forEach(node => {
            node.style.display = 'flex';
            this.removeHighlights(node);
        });

        this.updateNodeCount(this.nodes.size);
    }

    highlightSearchTerms(node, query) {
        const title = node.querySelector('h4');
        const description = node.querySelector('p');

        [title, description].forEach(element => {
            if (element) {
                const text = element.textContent;
                const regex = new RegExp(`(${query})`, 'gi');
                element.innerHTML = text.replace(regex, '<mark>$1</mark>');
            }
        });
    }

    removeHighlights(node) {
        const highlighted = node.querySelectorAll('mark');
        highlighted.forEach(mark => {
            mark.outerHTML = mark.textContent;
        });
    }

    filterNodes(category) {
        if (category === 'all') {
            this.showAllNodes();
            return;
        }

        const categories = this.container.querySelectorAll('.node-category');

        categories.forEach(cat => {
            const isMatch = cat.dataset.category === category;
            cat.style.display = isMatch ? 'block' : 'none';

            if (isMatch) {
                cat.classList.remove('collapsed');
                const nodesContainer = cat.querySelector('.category-nodes');
                nodesContainer.style.maxHeight = nodesContainer.scrollHeight + 'px';
            }
        });

        const categoryNodes = Array.from(this.nodes.values())
            .filter(node => node.category === category);

        this.updateNodeCount(categoryNodes.length);
    }

    setActiveFilter(button) {
        this.container.querySelectorAll('.filter-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        button.classList.add('active');
    }

    updateNodeCount(count) {
        const countElement = this.container.querySelector('.count-number');
        if (countElement) {
            countElement.textContent = count;
        }
    }

    handleNodeAction(action, nodeId) {
        const node = this.nodes.get(nodeId);

        switch (action) {
            case 'info':
                this.showNodeInfo(node);
                break;
            case 'favorite':
                this.toggleFavorite(nodeId);
                break;
        }
    }

    showNodeInfo(node) {
        if (window.notificationManager) {
            const content = `
                <div class="node-info-modal">
                    <div class="node-info-header">
                        <div class="node-info-icon" style="background: ${node.color}20; color: ${node.color}">
                            <i class="${node.icon}"></i>
                        </div>
                        <div>
                            <h3>${node.name}</h3>
                            <p>${node.description}</p>
                        </div>
                    </div>
                    <div class="node-info-details">
                        <div class="info-section">
                            <h4>Inputs</h4>
                            <ul>${node.inputs.map(input => `<li>${input}</li>`).join('')}</ul>
                        </div>
                        <div class="info-section">
                            <h4>Outputs</h4>
                            <ul>${node.outputs.map(output => `<li>${output}</li>`).join('')}</ul>
                        </div>
                        <div class="info-section">
                            <h4>Tags</h4>
                            <div class="tag-list">
                                ${node.tags.map(tag => `<span class="tag">${tag}</span>`).join('')}
                            </div>
                        </div>
                    </div>
                </div>
            `;

            window.notificationManager.modal(content, {
                title: 'Node Information',
                size: 'large'
            });
        }
    }

    toggleFavorite(nodeId) {
        const favorites = JSON.parse(localStorage.getItem('favorite-nodes') || '[]');
        const index = favorites.indexOf(nodeId);

        if (index > -1) {
            favorites.splice(index, 1);
        } else {
            favorites.push(nodeId);
        }

        localStorage.setItem('favorite-nodes', JSON.stringify(favorites));
        this.updateFavoriteUI(nodeId, index === -1);
    }

    updateFavoriteUI(nodeId, isFavorite) {
        const nodeElement = this.container.querySelector(`[data-node-id="${nodeId}"]`);
        const favoriteBtn = nodeElement.querySelector('[data-action="favorite"] i');

        favoriteBtn.className = isFavorite ? 'fas fa-heart' : 'far fa-heart';
        favoriteBtn.style.color = isFavorite ? '#ef4444' : '';
    }

    toggleLibrary() {
        this.isExpanded = !this.isExpanded;
        this.container.classList.toggle('collapsed', !this.isExpanded);

        const icon = this.container.querySelector('.library-collapse-btn i');
        icon.className = this.isExpanded ? 'fas fa-chevron-left' : 'fas fa-chevron-right';
    }

    toggleSearch() {
        const searchContainer = this.container.querySelector('.library-search');
        const isVisible = searchContainer.style.display !== 'none';

        searchContainer.style.display = isVisible ? 'none' : 'block';

        if (!isVisible) {
            this.container.querySelector('.search-input').focus();
        }
    }

    setupStyles() {
        const style = document.createElement('style');
        style.textContent = `
            /* NUCLEAR OPTION: Hide all legacy sidebars */
            .sidebar:not(.enhanced-node-library) {
                display: none !important;
                width: 0 !important;
                visibility: hidden !important;
                opacity: 0 !important;
                pointer-events: none !important;
                position: absolute !important;
                z-index: -100 !important;
            }

            .enhanced-node-library {
                width: 260px;
                background: rgba(15, 23, 42, 0.95);
                backdrop-filter: blur(12px);
                border-right: 1px solid rgba(255, 255, 255, 0.1);
                display: flex;
                flex-direction: column;
                height: 100%;
                flex-shrink: 0;
                position: relative;
                z-index: 100;
                color: #f1f5f9;
                font-family: 'Outfit', sans-serif;
            }
            
            .enhanced-node-library.collapsed {
                width: 60px;
            }
            
            .enhanced-node-library.collapsed .library-header span,
            .enhanced-node-library.collapsed .library-search,
            .enhanced-node-library.collapsed .library-content,
            .enhanced-node-library.collapsed .library-footer {
                display: none;
            }
            
            .library-header {
                padding: 16px 20px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                display: flex;
                align-items: center;
                justify-content: space-between;
            }
            
            .library-title {
                display: flex;
                align-items: center;
                gap: 10px;
                font-weight: 700;
                font-size: 14px;
                color: #f8fafc;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            .library-title i {
                color: #6366f1;
            }
            
            .library-controls {
                display: flex;
                gap: 4px;
            }
            
            .library-search-btn,
            .library-collapse-btn {
                background: none;
                border: none;
                color: #94a3b8;
                cursor: pointer;
                padding: 6px;
                border-radius: 6px;
                transition: all 0.2s ease;
            }
            
            .library-search-btn:hover,
            .library-collapse-btn:hover {
                background: rgba(255, 255, 255, 0.1);
                color: #f1f5f9;
            }
            
            .library-search {
                padding: 12px 16px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                display: none;
                flex-direction: column;
                gap: 10px;
            }
            
            .library-search.active {
                display: flex;
            }
            
            .search-input-container {
                position: relative;
            }
            
            .search-input-container i {
                position: absolute;
                left: 12px;
                top: 50%;
                transform: translateY(-50%);
                color: #94a3b8;
                font-size: 14px;
            }
            
            .search-input {
                width: 100%;
                padding: 10px 12px 10px 36px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                font-size: 14px;
                background: rgba(0, 0, 0, 0.3);
                color: white;
                transition: all 0.2s ease;
            }
            
            .search-input:focus {
                outline: none;
                border-color: #6366f1;
                background: rgba(0, 0, 0, 0.5);
                box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
            }
            
            .search-clear {
                position: absolute;
                right: 8px;
                top: 50%;
                transform: translateY(-50%);
                background: none;
                border: none;
                color: #94a3b8;
                cursor: pointer;
                padding: 4px;
                border-radius: 4px;
                display: none;
            }
            
            .search-clear:hover {
                background: rgba(255, 255, 255, 0.1);
                color: white;
            }
            
            .search-filters {
                display: flex;
                gap: 6px;
                flex-wrap: wrap;
            }
            
            .filter-btn {
                padding: 4px 10px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 16px;
                font-size: 11px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s ease;
                background: rgba(255, 255, 255, 0.05);
                color: #94a3b8;
                display: flex;
                align-items: center;
                gap: 6px;
            }
            
            .filter-btn:hover {
                background: rgba(255, 255, 255, 0.1);
                color: white;
            }
            
            .filter-btn.active {
                background: #6366f1;
                border-color: #6366f1;
                color: white;
            }
            
            .library-content {
                flex: 1;
                overflow-y: auto;
                padding: 8px 0;
            }
             /* Scrollbar Polish (Dark) */
            .library-content::-webkit-scrollbar {
                width: 6px;
            }
            .library-content::-webkit-scrollbar-track {
                background: transparent;
            }
            .library-content::-webkit-scrollbar-thumb {
                background: rgba(255, 255, 255, 0.1);
                border-radius: 3px;
            }
            .library-content::-webkit-scrollbar-thumb:hover {
                background: rgba(255, 255, 255, 0.2);
            }
            
            .node-category {
                margin-bottom: 2px;
            }
            
            .category-header {
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 10px 20px;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            
            .category-header:hover {
                background: rgba(255, 255, 255, 0.05);
            }
            
            .category-icon {
                width: 28px;
                height: 28px;
                border-radius: 6px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 12px;
            }
            
            .category-info {
                flex: 1;
            }
            
            .category-info h3 {
                margin: 0 0 2px 0;
                font-size: 13px;
                font-weight: 600;
                color: #e2e8f0;
            }
            
            .category-info p {
                margin: 0;
                font-size: 10px;
                color: #64748b;
            }
            
            .category-toggle {
                background: none;
                border: none;
                color: #64748b;
                cursor: pointer;
                padding: 4px;
                transition: all 0.2s ease;
            }
            
            .category-toggle i {
                transition: transform 0.2s ease;
            }
            
            .category-nodes {
                overflow: hidden;
                transition: max-height 0.3s ease;
            }
            
            .node-item {
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 8px 20px 8px 30px; /* Indented */
                cursor: grab;
                transition: all 0.2s ease;
                border-left: 3px solid transparent;
                position: relative;
            }
            
            .node-item:hover {
                background: rgba(255, 255, 255, 0.08);
                border-left-color: #6366f1;
            }
            
            .node-item.dragging {
                opacity: 0.5;
                background: rgba(99, 102, 241, 0.2);
                border: 1px dashed #6366f1;
            }
            
            .node-icon {
                width: 32px;
                height: 32px;
                border-radius: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 14px;
                flex-shrink: 0;
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }
            
            .node-info {
                flex: 1;
                min-width: 0;
            }
            
            .node-info h4 {
                margin: 0 0 2px 0;
                font-size: 13px;
                font-weight: 500;
                color: #cbd5e1;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            
            .node-info p {
                margin: 0 0 4px 0;
                font-size: 10px;
                color: #64748b;
                line-height: 1.2;
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
                overflow: hidden;
            }
            
            .node-tags {
                display: flex;
                gap: 4px;
                flex-wrap: wrap;
            }
            
            .node-tag {
                padding: 2px 6px;
                background: rgba(255, 255, 255, 0.05);
                color: #94a3b8;
                font-size: 9px;
                font-weight: 500;
                border-radius: 4px;
                text-transform: uppercase;
                letter-spacing: 0.3px;
            }
            
            .node-actions {
                display: flex;
                gap: 4px;
                opacity: 0;
                transition: opacity 0.2s ease;
            }
            
            .node-item:hover .node-actions {
                opacity: 1;
            }
            
            .node-action-btn {
                background: none;
                border: none;
                padding: 6px;
                border-radius: 4px;
                color: #64748b;
                cursor: pointer;
                transition: all 0.2s ease;
                font-size: 12px;
            }
            
            .node-action-btn:hover {
                background: rgba(255, 255, 255, 0.1);
                color: white;
            }
            
            .library-footer {
                padding: 12px 20px;
                border-top: 1px solid rgba(255, 255, 255, 0.1);
                background: rgba(0, 0, 0, 0.2);
                text-align: center;
            }
            
            .node-count {
                display: flex;
                flex-direction: column;
                align-items: center;
            }
            
            .count-number {
                font-size: 18px;
                font-weight: 700;
                color: #6366f1;
            }
            
            .count-label {
                font-size: 10px;
                color: #64748b;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            /* Search highlights */
            mark {
                background: rgba(251, 191, 36, 0.2);
                color: #fbbf24;
                padding: 0 2px;
                border-radius: 2px;
            }
            
            /* Drag preview */
            .node-drag-preview {
                box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
                border-radius: 8px;
                background: white;
                border: 2px solid #4f46e5;
            }
            
            /* Node info modal styles */
            .node-info-modal {
                max-width: 500px;
            }
            
            .node-info-header {
                display: flex;
                align-items: center;
                gap: 16px;
                margin-bottom: 20px;
            }
            
            .node-info-icon {
                width: 48px;
                height: 48px;
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 20px;
            }
            
            .node-info-header h3 {
                margin: 0 0 4px 0;
                font-size: 18px;
                font-weight: 600;
            }
            
            .node-info-header p {
                margin: 0;
                color: #6b7280;
            }
            
            .info-section {
                margin-bottom: 16px;
            }
            
            .info-section h4 {
                margin: 0 0 8px 0;
                font-size: 14px;
                font-weight: 600;
                color: #374151;
            }
            
            .info-section ul {
                margin: 0;
                padding-left: 20px;
                color: #6b7280;
            }
            
            .tag-list {
                display: flex;
                gap: 6px;
                flex-wrap: wrap;
            }
            
            .tag {
                padding: 4px 8px;
                background: #f3f4f6;
                color: #6b7280;
                font-size: 11px;
                font-weight: 500;
                border-radius: 12px;
                text-transform: uppercase;
                letter-spacing: 0.3px;
            }
        `;
        document.head.appendChild(style);
    }
}

// Initialize the enhanced node library with AGGRESSIVE placement & SINGLETON check
document.addEventListener('DOMContentLoaded', () => {
    // Singleton check
    if (window.enhancedLibraryInitialized) {
        console.warn("Enhanced Node Library already initialized. Skipping.");
        return;
    }
    window.enhancedLibraryInitialized = true;

    // Delayed init to ensure DOM readiness and cleanup
    setTimeout(() => {
        // Remove ALL existing sidebars, including previous instances of THIS library
        const existingSidebars = document.querySelectorAll('.sidebar, .n8n-sidebar, .node-library, .enhanced-node-library');
        existingSidebars.forEach(el => el.remove());

        // Init new one
        console.log("Initializing Enhanced Node Library (Singleton)...");
        window.enhancedNodeLibrary = new EnhancedNodeLibrary();
    }, 100);
});