export default {
    type: "ai_agent",
    label: "AI Agent",
    category: "AI",
    icon: "fas fa-robot",
    color: "#8b5cf6",

    inputs: ["input", "tools", "memory"],
    outputs: ["output", "decision", "tool_result"],

    defaultConfig: {
        credential_id: "",
        model: "gpt-4o",
        temperature: 0.7,
        max_steps: 5,
        response_mode: "text",
        memory_mode: "execution",
        max_tokens: 1024,
        tools_enabled: true,
        system_prompt: "You are an autonomous AI agent.",
        user_prompt: "{{ input.json }}"
    },

    uiSchema: {
        credential_id: {
            widget: "credential_select",
            credential_type: "ai_provider",
            label: "AI Provider"
        },
        model: {
            widget: "select",
            label: "Model",
            options: [
                { label: "GPT-4o", value: "gpt-4o" },
                { label: "GPT-4 Turbo", value: "gpt-4-turbo" },
                { label: "GPT-3.5 Turbo", value: "gpt-3.5-turbo" }
            ],
            description: "Select the AI model to use"
        },
        temperature: {
            widget: "slider",
            label: "Creativity (Temperature)",
            min: 0,
            max: 2,
            step: 0.1,
            description: "Higher values make output more random, lower values more deterministic"
        },
        max_steps: {
            widget: "number",
            label: "Max Reasoning Steps",
            min: 1,
            max: 10,
            description: "Maximum number of thought/action loops"
        },
        max_tokens: {
            widget: "number",
            label: "Max Tokens",
            min: 100,
            max: 32000,
            step: 100,
            default: 1024,
            description: "Maximum response length"
        },
        response_mode: {
            widget: "select",
            label: "Response Mode",
            options: [
                { label: "Text", value: "text" },
                { label: "JSON Object", value: "json" },
                { label: "Decision (Yes/No)", value: "decision" }
            ]
        },
        system_prompt: {
            widget: "textarea",
            label: "System Prompt",
            rows: 4,
            description: "Define the agent's persona and improved instructions"
        },
        user_prompt: {
            widget: "textarea",
            label: "User Prompt",
            rows: 4,
            description: "Input to the agent (supports {{ variables }})"
        },
        tools_enabled: {
            widget: "toggle",
            label: "Enable Tools",
            description: "Allow agent to use connected tools"
        },
        memory_mode: {
            widget: "select",
            label: "Memory Handling",
            options: [
                { label: "No Memory", value: "none" },
                { label: "Execution Memory", value: "execution" },
                { label: "Long-term (Vector DB)", value: "vector" }
            ]
        }
    }
};
