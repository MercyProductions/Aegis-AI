# Aegis Model Provider Setup

This project is configured for local-first routing with optional cloud escalation. The backend discovers installed Ollama models at runtime and marks cloud providers usable only when the matching API key is present in `.env`.

## Local Ollama Pack

Run the model pull script from PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\pull-local-model-pack.ps1
```

The pack includes fast chat, reasoning, code, and embedding lanes:

- Chat: `llama3.2:1b`, `llama3.2:3b`, `llama3.1:8b`, `gemma3:1b`, `gemma3:4b`, `gemma3:12b`, `mistral:7b`, `qwen2.5:7b`, `qwen2.5:14b`
- Reasoning: `phi4-mini`, `phi4`, `gpt-oss:20b`, `qwen3:4b`, `qwen3:8b`, `qwen3:14b`, `deepseek-r1:1.5b`, `deepseek-r1:7b`, `deepseek-r1:8b`, `deepseek-r1:14b`
- Coding: `qwen2.5-coder:1.5b`, `qwen2.5-coder:3b`, `qwen2.5-coder:7b`, `qwen2.5-coder:14b`, `qwen2.5-coder:32b`, `codellama:7b`, `deepseek-coder-v2:16b`, `devstral:24b`, `starcoder2:3b`, `starcoder2:7b`, `granite-code:3b`, `granite-code:8b`, `codegemma:2b`
- Embeddings: `nomic-embed-text`, `mxbai-embed-large`, `all-minilm`

Pull logs are written to `logs/model-pulls`, with a rolling `summary.json`.

## Mega Local Queue

After the base pack, run the guarded mega queue:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\pull-mega-model-pack.ps1 -MinimumFreeGb 24
```

This queue adds larger models when disk space allows and skips anything that would take the drive below the configured free-space floor:

- Larger coding: `qwen3-coder:30b`
- Larger general/reasoning: `gemma3:27b`, `qwen3:30b`, `qwq:32b`, `qwen2.5:32b`, `mistral-small:24b`, `magistral:24b`
- Large RAG/chat/MoE: `command-r:35b`, `mixtral:8x7b`, `yi:34b`
- 70B/72B frontier local queue: `llama3.3:70b`, `llama3.1:70b`, `qwen2.5:72b`
- Vision: `llama3.2-vision:11b`, `llama3.2-vision:90b`, `llava:13b`, `llava:34b`
- Extra embeddings: `bge-m3`, `snowflake-arctic-embed2`

Mega pull logs are written to `logs/model-pulls-mega`.

## Cloud Provider Keys

Add only the providers you want Aegis to use:

```env
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
OPENROUTER_API_KEY=
PERPLEXITY_API_KEY=
XAI_API_KEY=
GROQ_API_KEY=
MISTRAL_API_KEY=
DEEPSEEK_API_KEY=
TOGETHER_API_KEY=
CEREBRAS_API_KEY=
FIREWORKS_API_KEY=
COHERE_API_KEY=
GEMINI_API_KEY=
HUGGINGFACE_API_KEY=
NVIDIA_API_KEY=
SAMBANOVA_API_KEY=
```

When a key is blank, that provider remains visible in the registry but is skipped during execution. When a key is set, the router can use that provider for matching roles.

## Routing Behavior

- Normal questions route to a fast chat model.
- Code creation, debugging, review, and refactors route to code models.
- Architecture and planning route to reasoning models.
- Fresh research prefers Perplexity or OpenRouter when configured, then falls back to local reasoning.
- Image, realtime voice, and audio lanes are registered for future UI/API integration.
- Embedding models are kept out of chat completions and reserved for future RAG/indexing.
