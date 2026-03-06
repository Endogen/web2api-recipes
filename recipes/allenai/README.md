# Allen AI Playground

Chat with Allen AI's open-source language and vision models via the [Allen AI Playground](https://playground.allenai.org).

## Models

| Endpoint | Model | Description |
|---|---|---|
| `chat` | OLMo 3.1 32B Instruct | Default chat model |
| `olmo-32b` | OLMo 3.1 32B Instruct | Flagship instruction-tuned model |
| `olmo-32b-think` | OLMo 3.1 32B Think | Reasoning model with chain-of-thought |
| `olmo-7b` | OLMo 3 7B Instruct | Lightweight, fast inference |
| `tulu-8b` | Tülu 3 8B | Instruction-tuned Llama 3.1 |
| `tulu-70b` | Tülu 3 70B | Largest instruction-tuned model |
| `molmo2` | Molmo 2 8B | Vision model (images & video) |
| `molmo2-track` | Molmo 2 8B Tracking | Vision model with 8fps video tracking |
| `models` | — | List all available models |

## Usage

```
GET /allenai/chat?q=What is quantum computing?
GET /allenai/olmo-32b-think?q=Solve this step by step: 2^10
GET /allenai/models
```

### Vision (Molmo 2)

Send images or videos via POST with multipart form data:

```
POST /allenai/molmo2?q=Describe this image
Content-Type: multipart/form-data
files=@photo.jpg
```

### Tool Calling

Pass an MCP HTTP bridge URL to enable tool use:

```
GET /allenai/chat?q=Search for Bitcoin price&tools_url=http://localhost:8100
```

The model will discover tools from `{tools_url}/tools` and call them via `POST {tools_url}/tools/{name}`.

## Custom Scraper

This recipe uses a custom scraper (`scraper.py`) that communicates with Allen AI's streaming chat API directly, bypassing browser automation. It handles:

- NDJSON stream parsing
- Multi-turn tool calling loops
- File uploads for vision models
- Thinking/reasoning output extraction

## Requirements

- No API key needed — uses Allen AI's free public playground
- No environment variables required
