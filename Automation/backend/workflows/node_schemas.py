"""
Unified Node Schemas for Workflow Builder UI.
This module provides a single source of truth for node categories, icons, and fields.
"""

FULL_NODE_SCHEMAS = {
    # --- TRIGGERS ---
    "manual_trigger": { "category": "Triggers", "icon": "fas fa-play", "label": "Manual Trigger", "description": "Start flow manually", 
        "inputs": [], "outputs": ["output"],
        "fields": [] 
    },
    "webhook_trigger": { "category": "Triggers", "icon": "fas fa-bolt", "label": "Webhook", "description": "Start flow via URL",
        "inputs": [], "outputs": ["output"],
        "fields": [
            { "key": "path", "label": "URL Path", "type": "text", "placeholder": "/my-hook", "required": True },
            { "key": "method", "label": "Method", "type": "select", "options": ["GET", "POST"], "default": "POST" },
            { "key": "authentication", "label": "Authentication", "type": "boolean", "default": False },
            { "key": "secret_token", "label": "Secret Token", "type": "text", "displayOptions": { "show": { "authentication": [True] } } }
        ]
    },
    "schedule_trigger": { "category": "Triggers", "icon": "fas fa-clock", "label": "Schedule", "description": "Run on cron timer",
        "inputs": [], "outputs": ["output"],
        "fields": [
            { "key": "cron_expression", "label": "Cron Expression", "type": "text", "placeholder": "* * * * *", "required": True },
            { "key": "timezone", "label": "Timezone", "type": "select", "options": ["UTC", "Asia/Kolkata", "America/New_York", "Europe/London"], "default": "UTC" }
        ]
    },
    "telegram_trigger": { "category": "Triggers", "icon": "fab fa-telegram", "label": "Telegram", "description": "On new message",
        "inputs": [], "outputs": ["output"],
        "fields": [
             { "key": "credential_id", "label": "Telegram Bot", "type": "credential_select", "credential_type": "telegram_bot", "required": True },
             { "key": "chatbot_mode", "label": "Chatbot Mode", "type": "boolean", "default": False },
             { "key": "events", "label": "Events", "type": "select", "options": ["message", "command", "callback_query"], "multiple": True, "default": ["message"] },
             { "key": "allow_groups", "label": "Allow Group Messages", "type": "boolean", "default": False },
             { "key": "allowed_chat_ids", "label": "Allowed Chat IDs", "type": "text", "placeholder": "123456, 789012" },
             { "key": "trigger_keywords", "label": "Trigger Keywords", "type": "text", "placeholder": "hello, help, alert" }
        ]
    },
    "gmail_trigger": { "category": "Triggers", "icon": "fab fa-google", "label": "Gmail Trigger", "description": "On new email",
        "inputs": [], "outputs": ["output"],
        "fields": [
            { "key": "credential", "label": "Credential", "type": "credential_select", "credential_type": "gmail_oauth", "required": True },
            { "key": "watch_type", "label": "Watch Type", "type": "select", "options": ["inbox", "sent", "label"], "default": "inbox" },
            { "key": "label_name", "label": "Label Name", "type": "text", "placeholder": "INBOX", "displayOptions": { "show": { "watch_type": ["label"] } } }
        ]
    },
    "youtube_trigger": { "category": "Triggers", "icon": "fab fa-youtube", "label": "YouTube Trigger", "description": "On new video",
        "inputs": [], "outputs": ["output"],
        "fields": [
            { "key": "credential", "label": "Credential", "type": "credential_select", "credential_type": "google_oauth", "required": True },
            { "key": "trigger_type", "label": "Trigger Type", "type": "select", "options": ["channel", "playlist", "search"], "default": "channel" },
            { "key": "channel_id", "label": "Channel ID", "type": "text", "displayOptions": { "show": { "trigger_type": ["channel"] } } }
        ]
    },
    "whatsapp_trigger": { "category": "Triggers", "icon": "fab fa-whatsapp", "label": "WhatsApp Trigger", "description": "Triggers on new WhatsApp message",
        "inputs": [], "outputs": ["output"],
        "fields": [
            { "key": "credential_id", "label": "WhatsApp Account", "type": "credential_select", "credential_type": "meta_whatsapp", "required": True }
        ]
    },

    # --- MESSAGING ---
    "telegram_send": { "category": "Messaging", "icon": "fab fa-telegram", "label": "Telegram Send", "description": "Send message to chat",
        "inputs": ["main"], "outputs": ["output"],
        "fields": [
            { "key": "credential_id", "label": "Telegram Bot", "type": "credential_select", "credential_type": "telegram_bot", "required": True },
            { "key": "chat_id", "label": "Chat ID", "type": "text", "required": True },
            { "key": "message_text", "label": "Message Text", "type": "textarea" },
            { "key": "parse_mode", "label": "Parse Mode", "type": "select", "options": ["Markdown", "HTML", "None"], "default": "Markdown" },
            { "key": "disable_web_preview", "label": "Disable Web Preview", "type": "boolean", "default": False }
        ]
    },
    "telegram_reply": { "category": "Messaging", "icon": "fab fa-telegram", "label": "Telegram Reply", "description": "Reply to incoming message",
        "inputs": ["main"], "outputs": ["output"],
        "fields": [
            { "key": "credential_id", "label": "Telegram Bot", "type": "credential_select", "credential_type": "telegram_bot", "required": True },
            { "key": "message_text", "label": "Reply Text", "type": "textarea", "required": True, "placeholder": "{{ $json.response }}" },
            { "key": "parse_mode", "label": "Parse Mode", "type": "select", "options": ["Markdown", "HTML", "None"], "default": "Markdown" },
            { "key": "disable_web_preview", "label": "Disable Web Preview", "type": "boolean", "default": False }
        ]
    },
    "telegram_send_buttons": { "category": "Messaging", "icon": "fab fa-telegram", "label": "Telegram Buttons", "description": "Send inline keyboard buttons",
        "inputs": ["main"], "outputs": ["output"],
        "fields": [
            { "key": "credential_id", "label": "Telegram Bot", "type": "credential_select", "credential_type": "telegram_bot", "required": True },
            { "key": "chat_id", "label": "Chat ID", "type": "text", "required": True, "placeholder": "{{ $json.chat_id }}" },
            { "key": "message_text", "label": "Message Text", "type": "textarea", "required": True },
            { "key": "buttons", "label": "Buttons (JSON)", "type": "textarea", "required": True, "placeholder": "[[{\"text\": \"Yes\", \"callback_data\": \"yes\"}, {\"text\": \"No\", \"callback_data\": \"no\"}]]" },
            { "key": "parse_mode", "label": "Parse Mode", "type": "select", "options": ["Markdown", "HTML", "None"], "default": "Markdown" }
        ]
    },
    "telegram_set_commands": { "category": "Messaging", "icon": "fab fa-telegram", "label": "Telegram Set Commands", "description": "Register bot commands menu",
        "inputs": ["main"], "outputs": ["output"],
        "fields": [
            { "key": "credential_id", "label": "Telegram Bot", "type": "credential_select", "credential_type": "telegram_bot", "required": True },
            { "key": "commands", "label": "Commands (JSON)", "type": "textarea", "required": True, "placeholder": "[{\"command\": \"start\", \"description\": \"Start the bot\"}, {\"command\": \"help\", \"description\": \"Get help\"}]" }
        ]
    },
    "whatsapp_send": { "category": "Messaging", "icon": "fab fa-whatsapp", "label": "WhatsApp Send", "description": "Send template/text",
        "inputs": ["main"], "outputs": ["output"],
        "fields": [
            { "key": "credential_id", "label": "WhatsApp Account", "type": "credential_select", "credential_type": "meta_whatsapp", "required": True },
            { "key": "recipient_number", "label": "Recipient Number", "type": "text", "required": True },
            { "key": "message_type", "label": "Message Type", "type": "select", "options": ["text", "template"], "default": "text" },
            { "key": "message_text", "label": "Message Text", "type": "textarea", "displayOptions": { "show": { "message_type": ["text"] } } },
            { "key": "template_name", "label": "Template Name", "type": "text", "description": "Used in Template mode OR as fallback for 24h window errors.", "displayOptions": { "show": { "message_type": ["template", "text"] } } },
            { "key": "template_language", "label": "Template Language", "type": "text", "default": "en_US", "displayOptions": { "show": { "message_type": ["template", "text"] } } },
            { "key": "template_params", "label": "Template Params (JSON Array/CSV)", "type": "textarea", "placeholder": '["Value 1", "Value 2"]', "displayOptions": { "show": { "message_type": ["template", "text"] } } }
        ]
    },
    "send_email": { "category": "Messaging", "icon": "fas fa-envelope", "label": "Send Email", "description": "Via Gmail/SMTP",
        "inputs": ["main"], "outputs": ["output"],
        "fields": [
            { "key": "credential", "label": "Credential", "type": "credential_select", "credential_type": "email", "required": True },
            { "key": "to_email", "label": "To Email", "type": "text", "required": True },
            { "key": "subject", "label": "Subject", "type": "text", "required": True },
            { "key": "body", "label": "Email Body", "type": "textarea", "required": True }
        ]
    },

    # --- AI ---
    "ai_chat": { "category": "AI", "icon": "fas fa-brain", "label": "AI Chat", "description": "Simple LLM Chat",
        "inputs": ["main"], "outputs": ["output"],
        "fields": [
            { "key": "model", "label": "Model", "type": "select", "options": ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"], "default": "gpt-4o" },
            { "key": "system_prompt", "label": "System Prompt", "type": "textarea" },
            { "key": "user_prompt", "label": "User Prompt", "type": "textarea", "required": True },
            { "key": "temperature", "label": "Temperature", "type": "slider", "min": 0, "max": 1, "step": 0.1, "default": 0.7 },
            { "key": "max_tokens", "label": "Max Tokens", "type": "number", "default": 1000 }
        ]
    },
    "ai_agent": { "category": "AI", "icon": "fas fa-robot", "label": "AI Agent", "description": "Autonomous AI Agent (Ollama / OpenAI)",
        "inputs": ["main"], "outputs": ["output"],
        "fields": [
            { "key": "credential_id", "label": "Brain (AI Credential)", "type": "credential_select", "credential_type": "ai_offline", "required": True },
            { "key": "user_prompt", "label": "User Prompt", "type": "textarea", "required": True, "placeholder": "{{ $json.clean_text }}" },
            { "key": "system_prompt", "label": "System Prompt", "type": "textarea", "default": "You are a helpful AI assistant." },
            { "key": "agent_name", "label": "Agent Name", "type": "text", "default": "AI Agent" }
        ]
    },

    # --- LOGIC ---
    "if_else": { "category": "Logic", "icon": "fas fa-code-branch", "label": "If / Else", "description": "Conditional branching",
        "inputs": ["main"],
        "fields": [
            { "key": "condition_expression", "label": "Condition Expression", "type": "text", "placeholder": "{{ $json.value }} > 10", "required": True },
            { "key": "comparison_type", "label": "Comparison Type", "type": "select", "options": ["Expression", "Equals", "Contains", "Regex"], "default": "Expression" },
            { "key": "true_label", "label": "True Label", "type": "text", "default": "True" },
            { "key": "false_label", "label": "False Label", "type": "text", "default": "False" }
        ],
        "outputs": ["true", "false"]
    },
    "loop": { "category": "Logic", "icon": "fas fa-sync", "label": "Loop", "description": "Iterate over items",
        "inputs": ["main"],
        "fields": [
            { "key": "loop_over", "label": "Loop Over (Array/JSON)", "type": "text", "placeholder": "{{ $json.items }}", "required": True },
            { "key": "max_iterations", "label": "Max Iterations", "type": "number", "default": 100 },
            { "key": "break_condition", "label": "Break Condition", "type": "text" },
            { "key": "sub_workflow", "label": "Sub Workflow ID", "type": "workflow_select", "required": True }
        ],
        "outputs": ["output"]
    },
    "delay": { "category": "Logic", "icon": "fas fa-hourglass-half", "label": "Delay", "description": "Pause execution",
        "inputs": ["main"],
        "fields": [
            { "key": "delay_seconds", "label": "Seconds", "type": "number", "default": 0 },
            { "key": "delay_minutes", "label": "Minutes", "type": "number", "default": 0 },
            { "key": "delay_until_datetime", "label": "Until Datetime (ISO)", "type": "text" }
        ],
        "outputs": ["output"]
    },
    "switch": { "category": "Logic", "icon": "fas fa-random", "label": "Switch", "description": "Multi-path routing",
        "inputs": ["main"],
        "outputs": [],
        "fields": [
            { "key": "switch_expression", "label": "Switch Value", "type": "text", "required": True },
            { "key": "cases", "label": "Cases (JSON List)", "type": "json", "placeholder": "[{\"value\": \"email\", \"label\": \"Email Path\"}]" },
            { "key": "default_path", "label": "Default Path", "type": "toggle", "default": True }
        ],
        "dynamicOutputs": True
    },

    # --- DATA ---
    "google_sheets": { "category": "Data", "icon": "fas fa-table", "label": "Google Sheets", "description": "Read/Write Sheet Rows",
        "inputs": ["main"], "outputs": ["output"],
        "fields": [
            { "key": "credential", "label": "Google Credential", "type": "credential_select", "credential_type": "google_sheets", "required": True },
            { "key": "spreadsheet_id", "label": "Spreadsheet ID", "type": "text", "required": True },
            { "key": "sheet_name", "label": "Sheet Name", "type": "text", "required": True },
            { "key": "operation", "label": "Operation", "type": "select", "options": ["Read", "Append", "Update", "Clear"], "default": "Read" },
            { "key": "values_mapping", "label": "Values Mapping (JSON)", "type": "json" }
        ]
    },
    "database_query": { "category": "Data", "icon": "fas fa-database", "label": "Database Query", "description": "Execute SQL",
        "inputs": ["main"], "outputs": ["output"],
        "fields": [
            { "key": "db_connection", "label": "Connection String", "type": "text", "required": True },
            { "key": "sql_query", "label": "SQL Query", "type": "textarea", "required": True },
            { "key": "output_mode", "label": "Output Mode", "type": "select", "options": ["Rows", "JSON"], "default": "Rows" }
        ]
    },
    "bigquery": { 
        "category": "DATA", 
        "icon": "fas fa-search-dollar", 
        "label": "Google BigQuery", 
        "description": "Execute queries",
        "title": "Google BigQuery",
        "inputs": ["main"], "outputs": ["output"],
        "properties": [
            { "name": "credential", "label": "Google OAuth Credential", "type": "credential_select", "credential_type": "google_bigquery", "required": True },
            { "name": "project_id", "label": "Project ID", "type": "text", "required": True },
            { "name": "operation", "label": "Operation", "type": "select", "default": "run_query", "options": [
                {"label": "Run Query", "value": "run_query"},
                {"label": "Insert Rows", "value": "insert_rows"},
                {"label": "List Tables", "value": "list_tables"}
            ]},
            { "name": "sql_query", "label": "SQL Query", "type": "textarea", "displayOptions": { "show": { "operation": ["run_query"] } } },
            { "name": "dataset_id", "label": "Dataset ID", "type": "text", "displayOptions": { "show": { "operation": ["insert_rows", "list_tables"] } } },
            { "name": "table_id", "label": "Table ID", "type": "text", "displayOptions": { "show": { "operation": ["insert_rows"] } } },
            { "name": "rows_json", "label": "Rows (JSON)", "type": "textarea", "displayOptions": { "show": { "operation": ["insert_rows"] } } }
        ]
    },
    "file_storage": { 
        "category": "DATA", 
        "icon": "fas fa-hdd", 
        "label": "File Storage", 
        "description": "Read/Write Files",
        "title": "File Storage",
        "inputs": ["main"], "outputs": ["output"],
        "properties": [
            { "name": "operation", "label": "Operation", "type": "select", "options": [
                {"label": "Read", "value": "read"},
                {"label": "Write", "value": "write"},
                {"label": "Append", "value": "append"},
                {"label": "Delete", "value": "delete"}
            ], "default": "read" },
            { "name": "file_path", "label": "File Path", "type": "text", "required": True },
            { "name": "encoding", "label": "Encoding", "type": "select", "default": "utf-8", "options": [
                {"label": "UTF-8", "value": "utf-8"},
                {"label": "ASCII", "value": "ascii"},
                {"label": "Binary (Base64)", "value": "base64"}
            ], "displayOptions": { "show": { "operation": ["read", "write", "append"] } } },
            { "name": "content", "label": "Content (Write/Append)", "type": "textarea", "displayOptions": { "show": { "operation": ["write", "append"] } } },
            { "name": "overwrite", "label": "Overwrite", "type": "toggle", "default": True, "displayOptions": { "show": { "operation": ["write"] } } }
        ]
    },
    "google_calendar": {
        "display_name": "Google Calendar",
        "category": "DATA",
        "icon": "fas fa-calendar-alt",
        "description": "Create, update, list, and delete calendar events",
        "inputs": ["main"],
        "outputs": ["output"],
        "fields": [
            {
                "key": "credential",
                "label": "Google Credential",
                "type": "credential_select",
                "credential_type": "google_calendar",
                "required": True
            },
            {
                "name": "operation",
                "label": "Operation",
                "type": "select",
                "options": [
                    {"label": "List Events", "value": "list_events"},
                    {"label": "Create Event", "value": "create_event"},
                    {"label": "Update Event", "value": "update_event"},
                    {"label": "Delete Event", "value": "delete_event"}
                ],
                "default": "list_events",
                "required": True
            },
            {
                "name": "calendar_id",
                "label": "Calendar ID",
                "type": "string",
                "default": "primary",
                "required": True
            },
            {
                "name": "summary",
                "label": "Event Title",
                "type": "string",
                "required": True,
                "displayOptions": {
                    "show": {"operation": ["create_event", "update_event"]}
                }
            },
            {
                "name": "start_datetime",
                "label": "Start Time (ISO)",
                "type": "string",
                "required": True,
                "placeholder": "2024-05-10T10:00:00Z",
                "displayOptions": {
                    "show": {"operation": ["create_event", "update_event"]}
                }
            },
            {
                "name": "end_datetime",
                "label": "End Time (ISO)",
                "type": "string",
                "required": True,
                "placeholder": "2024-05-10T11:00:00Z",
                "displayOptions": {
                    "show": {"operation": ["create_event", "update_event"]}
                }
            },
            {
                "name": "event_id",
                "label": "Event ID",
                "type": "string",
                "required": True,
                "displayOptions": {
                    "show": {"operation": ["delete_event", "update_event"]}
                }
            },
            {
                "name": "max_results",
                "label": "Max Results",
                "type": "number",
                "default": 10,
                "displayOptions": {
                    "show": {"operation": ["list_events"]}
                }
            }
        ]
    },

    # --- DEBUG ---
    "debug": { "category": "Utilities", "icon": "fas fa-bug", "label": "Debug", "description": "Inspect JSON",
        "inputs": ["main"], "outputs": ["output"],
        "fields": [
            { "key": "log_level", "label": "Log Level", "type": "select", "options": ["Info", "Error", "Full"], "default": "Info" },
            { "key": "show_payload", "label": "Show Full Payload", "type": "toggle", "default": True }
        ]
    }
}
