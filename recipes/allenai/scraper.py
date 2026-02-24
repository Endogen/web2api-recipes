"""Allen AI Playground scraper — chat with OLMo, Tülu, and Molmo models."""

from __future__ import annotations

import logging
from typing import Any

from playwright.async_api import Page

from web2api.scraper import BaseScraper, ScrapeResult

logger = logging.getLogger(__name__)

API_BASE = "https://olmo-api.allen.ai"
PLAYGROUND_URL = "https://playground.allenai.org"

# Endpoint name → model ID mapping
_MODEL_MAP: dict[str, str] = {
    "chat": "Olmo-3.1-32B-Instruct",
    "olmo-32b": "Olmo-3.1-32B-Instruct",
    "olmo-32b-think": "Olmo-3.1-32B-Think",
    "olmo-7b": "Olmo-3-7B-Instruct",
    "tulu-8b": "cs-Llama-3.1-Tulu-3.1-8B",
    "tulu-70b": "cs-Llama-3.1-Tulu-3-70B",
    "models": None,
}

_SUPPORTED = set(_MODEL_MAP.keys())

# JavaScript that runs in the browser context to call the Allen AI API.
# We navigate to the playground first so fetch() has the right origin.
_CHAT_JS = """
async ([apiBase, modelId, prompt]) => {
    const anonId = crypto.randomUUID();
    const boundary = '----FormBoundary' + Math.random().toString(36).slice(2);
    const parts = [
        `--${boundary}\\r\\nContent-Disposition: form-data; name="content"\\r\\n\\r\\n${prompt}\\r\\n`,
        `--${boundary}\\r\\nContent-Disposition: form-data; name="model"\\r\\n\\r\\n${modelId}\\r\\n`,
        `--${boundary}\\r\\nContent-Disposition: form-data; name="host"\\r\\n\\r\\nai2_model_hub\\r\\n`,
        `--${boundary}--\\r\\n`
    ].join('');

    const resp = await fetch(apiBase + '/v4/threads/', {
        method: 'POST',
        headers: {
            'X-Anonymous-User-ID': anonId,
            'Content-Type': 'multipart/form-data; boundary=' + boundary,
        },
        body: parts,
    });

    if (!resp.ok) {
        const text = await resp.text();
        return { error: `HTTP ${resp.status}: ${text.slice(0, 500)}` };
    }

    const text = await resp.text();
    const lines = text.trim().split('\\n').filter(l => l.trim());
    let content = '';
    let thinking = null;
    let threadId = null;
    let messageId = null;
    let finishReason = null;
    let modelUsed = modelId;

    for (const line of lines) {
        try {
            const evt = JSON.parse(line);
            if (evt.type === 'start') {
                threadId = evt.message;
            }
            if (evt.type === 'modelResponse' && evt.content !== undefined) {
                content += evt.content;
            }
            if (evt.type === 'thinkingResponse' && evt.content !== undefined) {
                thinking = (thinking || '') + evt.content;
            }
            if (evt.messages) {
                const assistant = evt.messages.find(m => m.role === 'assistant');
                if (assistant && assistant.final) {
                    content = assistant.content || content;
                    thinking = assistant.thinking || thinking;
                    finishReason = assistant.finishReason;
                    messageId = assistant.id;
                    if (assistant.modelId) modelUsed = assistant.modelId;
                }
            }
        } catch {}
    }

    return { content, thinking, threadId, messageId, finishReason, model: modelUsed };
}
"""

_MODELS_JS = """
async (apiBase) => {
    const resp = await fetch(apiBase + '/v4/models/');
    if (!resp.ok) return { error: `HTTP ${resp.status}` };
    return await resp.json();
}
"""


class Scraper(BaseScraper):
    """Query Allen AI models via their public API."""

    def supports(self, endpoint: str) -> bool:
        return endpoint in _SUPPORTED

    async def scrape(
        self, endpoint: str, page: Page, params: dict[str, Any]
    ) -> ScrapeResult:
        # Navigate to the playground so fetch() has the correct origin
        await page.goto(PLAYGROUND_URL, wait_until="domcontentloaded")

        if endpoint == "models":
            return await self._list_models(page)

        model_id = _MODEL_MAP[endpoint]
        query = (params.get("query") or "").strip()
        if not query:
            return ScrapeResult(
                items=[{"prompt": "", "response": "", "model": model_id}]
            )

        return await self._chat(page, model_id, query)

    async def _chat(
        self, page: Page, model_id: str, prompt: str
    ) -> ScrapeResult:
        """Send a prompt and collect the streamed response."""
        result = await page.evaluate(_CHAT_JS, [API_BASE, model_id, prompt])

        if isinstance(result, dict) and "error" in result:
            raise RuntimeError(result["error"])

        item: dict[str, Any] = {
            "prompt": prompt,
            "response": result.get("content", ""),
            "model": result.get("model", model_id),
        }

        thinking = result.get("thinking")
        if thinking:
            item["thinking"] = thinking

        thread_id = result.get("threadId")
        if thread_id:
            item["thread_id"] = thread_id

        message_id = result.get("messageId")
        if message_id:
            item["message_id"] = message_id

        finish_reason = result.get("finishReason")
        if finish_reason:
            item["finish_reason"] = finish_reason

        return ScrapeResult(items=[item])

    async def _list_models(self, page: Page) -> ScrapeResult:
        """Fetch available models from the API."""
        result = await page.evaluate(_MODELS_JS, API_BASE)

        if isinstance(result, dict) and "error" in result:
            raise RuntimeError(result["error"])

        items = []
        for model in result:
            if not model.get("is_visible") or model.get("is_deprecated"):
                continue
            items.append({
                "title": model.get("name", ""),
                "id": model.get("id", ""),
                "family": model.get("family_id", ""),
                "type": model.get("model_type", ""),
                "description": model.get("description", ""),
                "can_think": model.get("can_think", False),
                "can_call_tools": model.get("can_call_tools", False),
                "accepts_files": model.get("accepts_files", False),
            })

        return ScrapeResult(items=items)
