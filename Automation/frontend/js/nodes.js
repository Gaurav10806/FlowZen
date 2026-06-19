
// ✅ SAFETY: Ensure global node registries always exist
window.NODE_REGISTRY = window.NODE_REGISTRY || {};
window.NodeConfigs = window.NodeConfigs || {};

// AI Agent Definition (n8n-style)
window.NODE_REGISTRY["ai_agent"] = {
    label: "AI Agent",
    category: "AI",
    icon: "fas fa-robot",
    color: "#8b5cf6",
    type: "ai_agent", // Ensure type matches what builder expects
    action_type: "ai_agent",

    inputs: ["main", "chat_model", "memory", "tools"],
    outputs: ["main"],

    defaultConfig: {
        credential_id: "",
        system_prompt: "You are a helpful AI agent.",
        user_prompt: "{{ input.json.text }}",
        model: "gpt-4o",
        temperature: 0.7,
        max_tokens: 1024,
        max_steps: 5,
        response_mode: "text",
        tools: []
    },

    config: { // Legacy builder compatibility field structure
        credential_id: { type: "credential", credential_type: "ai_provider", title: "AI Credential" },
        system_prompt: { type: "textarea", title: "System Prompt" },
        user_prompt: { type: "textarea", title: "User Prompt" },
        model: { type: "select", options: ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"], title: "Model" },
        temperature: { type: "number", min: 0, max: 2, step: 0.1, title: "Temperature" },
        max_tokens: { type: "number", title: "Max Tokens" },
        max_steps: { type: "number", title: "Max Steps" },
        response_mode: { type: "select", options: ["text", "json"], title: "Response Mode" },
        tools: { type: "multiselect", options: ["http", "email", "calendar"], title: "Tools" }
    },

    fields: [ // New field structure
        { key: "credential_id", type: "credential", label: "AI Credential", credential_type: "ai_provider" },
        { key: "system_prompt", type: "textarea", label: "System Prompt" },
        { key: "user_prompt", type: "textarea", label: "User Prompt" },
        { key: "model", type: "select", options: ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"], label: "Model" },
        { key: "temperature", type: "number", min: 0, max: 2, step: 0.1, label: "Temperature" },
        { key: "max_tokens", type: "number", label: "Max Tokens" },
        { key: "max_steps", type: "number", label: "Max Steps" },
        { key: "response_mode", type: "select", options: ["text", "json"], label: "Response Mode" },
        { key: "tools", type: "multiselect", options: ["http", "email", "calendar"], label: "Tools" }
    ]
};

// Also ensure it's in NodeConfigs for enhanced-node-library compatibility
window.NodeConfigs.ai_agent = window.NODE_REGISTRY["ai_agent"];

// OpenAI Model Node
window.NODE_REGISTRY["model_openai"] = {
    label: "OpenAI Chat Model",
    category: "AI",
    icon: "fas fa-brain",
    color: "#10a37f",
    type: "model_openai",
    action_type: "model_openai",
    inputs: [],
    outputs: ["chat_model"],
    defaultConfig: {
        credential_id: "",
        model: "gpt-4o",
        temperature: 0.7
    },
    fields: [
        { key: "credential_id", type: "credential", label: "Credential", credential_type: "ai_provider" },
        { key: "model", type: "select", options: ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"], label: "Model" },
        { key: "temperature", type: "number", min: 0, max: 2, step: 0.1, label: "Temperature" }
    ]
};
window.NodeConfigs.model_openai = window.NODE_REGISTRY["model_openai"];

// Web Search Tool Node
window.NODE_REGISTRY["tool_websearch"] = {
    label: "Web Search Tool",
    category: "Tools",
    icon: "fas fa-search",
    color: "#f59e0b",
    type: "tool_websearch",
    action_type: "tool_websearch",
    inputs: [],
    outputs: ["tools"],
    defaultConfig: {
        provider: "google",
        limit: 5
    },
    fields: [
        { key: "provider", type: "select", options: ["google", "bing", "duckduckgo"], label: "Search Provider" },
        { key: "limit", type: "number", label: "Results Limit" }
    ]
};
window.NodeConfigs.tool_websearch = window.NODE_REGISTRY["tool_websearch"];

// Telegram Trigger Node
window.NODE_REGISTRY["telegram_trigger"] = {
    label: "Telegram Trigger",
    category: "Triggers",
    icon: "fab fa-telegram",
    color: "#0088cc",
    type: "telegram_trigger",
    action_type: "telegram_trigger",
    inputs: [],
    outputs: ["main"],
    defaultConfig: {
        credential_id: "",
        chatbot_mode: false,
        events: ["message"],
        allow_groups: false
    },
    fields: [
        { key: "credential_id", type: "credential", label: "Telegram Bot", credentialType: "telegram_bot" },
        { key: "chatbot_mode", type: "boolean", label: "Chatbot Mode (Pass context to AI)" },
        { key: "events", type: "multiselect", options: ["message", "command"], label: "Trigger On" },
        { key: "allow_groups", type: "boolean", label: "Allow Group Messages" }
    ]
};
window.NodeConfigs.telegram_trigger = window.NODE_REGISTRY["telegram_trigger"];

// Telegram Send Node
window.NODE_REGISTRY["telegram_send"] = {
    label: "Telegram Send",
    category: "Messaging",
    icon: "fab fa-telegram",
    color: "#0088cc",
    type: "telegram_send",
    action_type: "telegram_send",
    inputs: ["main"],
    outputs: ["main"],
    defaultConfig: {
        credential_id: "",
        chat_id: "{{ telegram_trigger.json.chat_id }}",
        message_text: "{{ ai_agent.json.output }}",
        parse_mode: "Markdown",
        disable_web_preview: true
    },
    fields: [
        { key: "credential_id", type: "credential", label: "Telegram Bot", credentialType: "telegram_bot" },
        { key: "chat_id", type: "text", label: "Chat ID" },
        { key: "message_text", type: "textarea", label: "Message Text" },
        { key: "parse_mode", type: "select", options: ["Markdown", "HTML", "None"], label: "Parse Mode" },
        { key: "disable_web_preview", type: "boolean", label: "Disable Web Preview" }
    ]
};
window.NodeConfigs.telegram_send = window.NODE_REGISTRY["telegram_send"];

// ✅ WhatsApp Trigger Node (Minimal Registration)
window.NODE_REGISTRY["whatsapp_trigger"] = {
    label: "WhatsApp Trigger",
    category: "Triggers",
    icon: "fab fa-whatsapp",
    color: "#25D366",
    type: "whatsapp_trigger",
    action_type: "whatsapp_trigger",
    inputs: [],
    outputs: ["main"],
    defaultConfig: {
        credential_id: ""
    },
    fields: [
        { key: "credential_id", type: "credential", label: "WhatsApp Account", credentialType: "meta_whatsapp" }
    ]
};
window.NodeConfigs["whatsapp_trigger"] = window.NODE_REGISTRY["whatsapp_trigger"];

// Global Node Manager
class NodeManager {
    static getIcon(type) {
        const icons = {
            'webhook': 'fas fa-bolt',
            'http-request': 'fas fa-globe',
            'email-trigger': 'fas fa-envelope',
            'email-send': 'fas fa-paper-plane',
            'schedule': 'fas fa-clock',
            'condition': 'fas fa-code-branch',
            'loop': 'fas fa-sync',
            'merge': 'fas fa-compress-arrows-alt',
            'function': 'fas fa-code',
            'ai_agent': 'fas fa-robot',
            'manual_trigger': 'fas fa-hand-pointer'
        };
        return icons[type] || 'fas fa-cube';
    }

    static getLabel(type) {
        if (window.NODE_REGISTRY[type]) return window.NODE_REGISTRY[type].label;
        if (window.NodeConfigs[type]) return window.NodeConfigs[type].label;
        return type.replace(/[-_]/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }

    static getConfig(type) {
        if (window.NODE_REGISTRY[type]) return window.NODE_REGISTRY[type].defaultConfig;
        const config = window.NodeConfigs[type] || {};
        return config.defaultConfig || config.defaults || {};
    }
}

// WhatsApp Trigger Node
window.NODE_REGISTRY["whatsapp_trigger"] = {
    label: "WhatsApp Trigger",
    category: "Triggers",
    icon: "fab fa-whatsapp",
    color: "#25D366",
    type: "whatsapp_trigger",
    action_type: "whatsapp_trigger",
    inputs: [],
    outputs: ["main"],
    defaultConfig: {
        credential_id: ""
    },
    fields: [
        { key: "credential_id", type: "credential", label: "WhatsApp Account", credentialType: "meta_whatsapp" }
    ]
};
window.NodeConfigs["whatsapp_trigger"] = window.NODE_REGISTRY["whatsapp_trigger"];

window.NodeManager = NodeManager;
console.log("Nodes.js loaded. AI Agent registered (n8n-style).");