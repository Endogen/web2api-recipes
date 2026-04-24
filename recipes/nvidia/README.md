# NVIDIA NIM

Use NVIDIA-hosted models from [build.nvidia.com/models](https://build.nvidia.com/models) through the OpenAI-compatible `integrate.api.nvidia.com` API.

## Why this recipe exists

The build.nvidia.com site is mostly a front-end for NVIDIA's hosted inference API. For Web2API, the direct API is better than scraping with Playwright:

- simpler
- faster
- less brittle
- no browser auth dance

## Requirements

- `NVIDIA_API_KEY` environment variable
- a free NVIDIA API key/account from build.nvidia.com

## Endpoints

### `GET /nvidia/models`

List available model IDs.

Optional filters:

- `owner=meta`
- `prefix=google/gemma`

Examples:

```bash
curl -s 'http://localhost:8010/nvidia/models' | jq
curl -s 'http://localhost:8010/nvidia/models?owner=meta' | jq
```

### `GET /nvidia/chat?q=...`

Send a chat prompt to a model.

Optional params:

- `model` — defaults to `meta/llama-3.1-70b-instruct`
- `system`
- `temperature`
- `top_p`
- `max_tokens`

Examples:

```bash
curl -s 'http://localhost:8010/nvidia/chat?q=Explain+RAG&model=meta/llama-3.1-70b-instruct' | jq
curl -s 'http://localhost:8010/nvidia/chat?q=Write+a+haiku&model=google/gemma-3-27b-it&temperature=0.8' | jq
```

## Notes

- `/nvidia/models` is readable without auth upstream today, but `/nvidia/chat` requires `Authorization: Bearer $NVIDIA_API_KEY`.
- This recipe currently targets text chat models via `/v1/chat/completions`.
- If NVIDIA later exposes enough stable browser-only free flows that bypass API keys, then a Playwright fallback could make sense. Right now that would just be more fragile for no gain.
