# FlowZen Pluggable AI Provider System

FlowZen features a pluggable AI provider architecture that supports **both local development (Ollama)** and **cloud production deployments (Google Gemini)** without requiring code modifications or workflow JSON changes.

---

## Environment Variable Configuration

The active AI provider is controlled entirely via environment variables.

| Environment Variable | Description | Default Value | Allowed Values |
| :--- | :--- | :--- | :--- |
| `AI_PROVIDER` | Active AI provider engine | `ollama` | `ollama`, `gemini`, `openai` |
| `GEMINI_API_KEY` | Google Gemini API Key | `""` | Any valid Gemini API key |
| `GEMINI_MODEL` | Google Gemini Model name | `gemini-2.5-flash` | `gemini-2.5-flash`, `gemini-1.5-flash`, `gemini-1.5-pro`, `gemini-2.0-flash` |
| `OLLAMA_HOST` | Ollama local endpoint URL | `http://localhost:11434` | Valid URL pointing to Ollama server |
| `OLLAMA_MODEL` | Default Ollama model name | `llama3:8b` | Any installed Ollama model |
| `OPENAI_API_KEY` | Optional OpenAI API Key for online routing | `""` | Any valid OpenAI key |

---

## Local Development Mode (Ollama)

To run FlowZen locally using offline/local LLMs via Ollama:

1. Ensure Ollama is installed and running on your local machine:
   ```bash
   ollama serve
   ollama pull llama3:8b
   ```

2. Set `AI_PROVIDER` in your `.env` file:
   ```env
   AI_PROVIDER=ollama
   OLLAMA_HOST=http://localhost:11434
   OLLAMA_MODEL=llama3:8b
   ```

3. Workflows and AI nodes will automatically connect to your local Ollama instance without making external internet API calls.

---

## Production Deployment Mode (Google Gemini)

To deploy FlowZen to cloud environments (Railway, Render, DigitalOcean, VPS) using Google Gemini:

1. Obtain a Google Gemini API Key from [Google AI Studio](https://aistudio.google.com/).

2. Configure environment variables in your deployment platform settings:
   ```env
   AI_PROVIDER=gemini
   GEMINI_API_KEY=your-actual-gemini-api-key
   GEMINI_MODEL=gemini-2.5-flash
   ```

3. Restart your FlowZen application container. All workflow AI nodes will execute seamlessly through Google Gemini 2.5 Flash without requiring local Ollama services.

---

## How Provider Switching Works

```
                     ┌──────────────────┐
                     │ Workflow AI Node │
                     └────────┬─────────┘
                              │
                      UniversalEngine
                              │
                    ┌─────────┴─────────┐
                    │ Router Inspection │
                    └─────────┬─────────┘
                              │
             ┌────────────────┴────────────────┐
   [AI_PROVIDER=ollama]               [AI_PROVIDER=gemini]
             │                                 │
   ┌─────────▼────────┐               ┌────────▼─────────┐
   │  OllamaProvider  │               │  GeminiProvider  │
   └─────────┬────────┘               └────────┬─────────┘
             │                                 │
   Local HTTP :11434                  Google Gemini API
```

1. When an AI node runs, `UniversalEngine` inspects the `AI_PROVIDER` environment variable.
2. If `AI_PROVIDER=gemini`, `UniversalEngine` dispatches the prompt, system instructions, and schema to `GeminiProvider`.
3. If `AI_PROVIDER=ollama`, `UniversalEngine` dispatches to `OllamaProvider`.
4. The output contract (`{"success": True, "output": {"text": "...", "json": {...}}}`) remains identical across providers so workflow nodes, agents, and frontend builder UIs operate without modifications.

---

## Error Handling & Fallbacks

- **Missing API Key**: If `AI_PROVIDER=gemini` and `GEMINI_API_KEY` is omitted, the provider returns a clean `{"success": False, "error": "Gemini API Key Missing"}` error payload instead of crashing the process.
- **SDK & REST Resilience**: `GeminiProvider` automatically attempts execution via the official `google-genai` SDK and seamlessly falls back to direct REST API calls if SDK imports or version mismatches occur.
- **JSON Parsing**: Structured JSON outputs automatically strip markdown code blocks (` ```json ... ``` `) and parse valid JSON dictionaries. If parsing fails, raw text is preserved under `raw_text` keys.
