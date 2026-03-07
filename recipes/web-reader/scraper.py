"""Web Reader scraper — extract readable text from any URL."""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse

from playwright.async_api import Page

from web2api.scraper import BaseScraper, ScrapeResult

# Max characters to return (prevents huge pages from overwhelming the model)
MAX_TEXT_LENGTH = 8000

# Elements to remove before extracting text
NOISE_SELECTORS = [
    "script", "style", "noscript", "iframe",
    "nav", "footer", "header",
    "[role='navigation']", "[role='banner']", "[role='contentinfo']",
    ".cookie-banner", ".cookie-consent", "#cookie-notice",
    ".ad", ".ads", ".advertisement", "[class*='sidebar']",
    "[class*='popup']", "[class*='modal']", "[class*='overlay']",
    "[class*='newsletter']", "[class*='subscribe']",
]


class Scraper(BaseScraper):
    """Fetch a URL and extract its readable text content."""

    def supports(self, endpoint: str) -> bool:
        return endpoint == "read"

    async def scrape(
        self, endpoint: str, page: Page, params: dict[str, Any]
    ) -> ScrapeResult:
        url = (params.get("query") or "").strip()
        if not url:
            raise RuntimeError("Missing URL — pass q=<url>")

        # Ensure it's a valid URL
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        parsed = urlparse(url)
        if not parsed.hostname:
            raise RuntimeError(f"Invalid URL: {url}")

        # Navigate with anti-detection
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            raise RuntimeError(f"Failed to load {url}: {e}")

        # Wait for content to render
        await asyncio.sleep(2)

        # Get the page title
        title = (await page.title() or "").strip()

        # Remove noise elements
        for selector in NOISE_SELECTORS:
            try:
                await page.evaluate(
                    f'document.querySelectorAll("{selector}").forEach(e => e.remove())'
                )
            except Exception:
                pass

        # Try to find the main content area
        text = ""
        for container in ["article", "main", "[role='main']", ".content", "#content"]:
            try:
                el = await page.query_selector(container)
                if el:
                    text = (await el.text_content() or "").strip()
                    if len(text) > 200:
                        break
            except Exception:
                pass

        # Fall back to body if no good container found
        if len(text) < 200:
            try:
                body = await page.query_selector("body")
                if body:
                    text = (await body.text_content() or "").strip()
            except Exception:
                pass

        if not text:
            raise RuntimeError(f"Could not extract text from {url}")

        # Clean up whitespace: collapse multiple newlines and spaces
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        text = text.strip()

        # Truncate if too long
        truncated = False
        if len(text) > MAX_TEXT_LENGTH:
            text = text[:MAX_TEXT_LENGTH]
            # Cut at last complete sentence or paragraph
            last_break = max(
                text.rfind(". "),
                text.rfind(".\n"),
                text.rfind("\n\n"),
            )
            if last_break > MAX_TEXT_LENGTH // 2:
                text = text[: last_break + 1]
            truncated = True

        # Get the final URL (after redirects)
        final_url = page.url

        item: dict[str, Any] = {
            "title": title or final_url,
            "url": final_url,
            "text": text,
        }
        if truncated:
            item["truncated"] = "true"

        return ScrapeResult(
            items=[item],
            current_page=1,
            has_next=False,
        )
