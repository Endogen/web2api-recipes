"""Web Reader scraper — extract readable text from any URL."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import urlparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page
from web2api.network_security import (
    UnsafeOutboundURL,
    private_network_access_enabled,
    validate_public_http_url,
)
from web2api.scraper import BaseScraper, InvalidParamsError, ScrapeResult

logger = logging.getLogger(__name__)

# Max characters to return (prevents huge pages from overwhelming the model)
MAX_TEXT_LENGTH = 8000

# Elements to remove before extracting text
NOISE_SELECTORS = [
    "script",
    "style",
    "noscript",
    "iframe",
    "nav",
    "footer",
    "header",
    "[role='navigation']",
    "[role='banner']",
    "[role='contentinfo']",
    ".cookie-banner",
    ".cookie-consent",
    "#cookie-notice",
    ".ad",
    ".ads",
    ".advertisement",
    "[class*='sidebar']",
    "[class*='popup']",
    "[class*='modal']",
    "[class*='overlay']",
    "[class*='newsletter']",
    "[class*='subscribe']",
]

CONTENT_SELECTORS = ("article", "main", "[role='main']", ".content", "#content")


def _normalize_url(raw_url: str) -> str:
    url = raw_url.strip()
    if not url:
        raise InvalidParamsError("missing URL — pass q=<url>")
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    if not urlparse(url).hostname:
        raise InvalidParamsError(f"invalid URL: {url}")
    return url


def _clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _truncate_text(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_TEXT_LENGTH:
        return text, False
    shortened = text[:MAX_TEXT_LENGTH]
    last_break = max(
        shortened.rfind(". "),
        shortened.rfind(".\n"),
        shortened.rfind("\n\n"),
    )
    if last_break > MAX_TEXT_LENGTH // 2:
        shortened = shortened[: last_break + 1]
    return shortened, True


async def _remove_noise(page: Page) -> None:
    for selector in NOISE_SELECTORS:
        try:
            await page.eval_on_selector_all(
                selector,
                "elements => elements.forEach(el => el.remove())",
            )
        except PlaywrightError as exc:
            logger.debug("Could not remove selector %s: %s", selector, exc)


async def _extract_readable_text(page: Page) -> str:
    for selector in CONTENT_SELECTORS:
        try:
            element = await page.query_selector(selector)
            if element is None:
                continue
            text = (await element.text_content() or "").strip()
            if len(text) > 200:
                return text
        except PlaywrightError as exc:
            logger.debug("Could not read selector %s: %s", selector, exc)

    try:
        body = await page.query_selector("body")
        return (await body.text_content() or "").strip() if body is not None else ""
    except PlaywrightError as exc:
        logger.debug("Could not read page body: %s", exc)
        return ""


class Scraper(BaseScraper):
    """Fetch a URL and extract its readable text content."""

    def supports(self, endpoint: str) -> bool:
        return endpoint == "read"

    async def scrape(self, endpoint: str, page: Page, params: dict[str, Any]) -> ScrapeResult:
        url = _normalize_url(str(params.get("query") or ""))
        try:
            await asyncio.to_thread(
                validate_public_http_url,
                url,
                allow_private_network=private_network_access_enabled(),
            )
        except UnsafeOutboundURL as exc:
            raise InvalidParamsError(str(exc)) from exc

        # Navigate with anti-detection
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except PlaywrightError as exc:
            raise RuntimeError(f"Failed to load {url}: {exc}") from exc

        # Wait for content to render
        await page.wait_for_timeout(2000)

        # Get the page title
        title = (await page.title() or "").strip()

        # Remove noise elements
        await _remove_noise(page)
        text = await _extract_readable_text(page)

        if not text:
            raise RuntimeError(f"Could not extract text from {url}")

        text, truncated = _truncate_text(_clean_text(text))

        # Get the final URL (after redirects)
        final_url = page.url
        try:
            await asyncio.to_thread(
                validate_public_http_url,
                final_url,
                allow_private_network=private_network_access_enabled(),
            )
        except UnsafeOutboundURL as exc:
            raise RuntimeError(f"unsafe final URL: {exc}") from exc

        item: dict[str, Any] = {
            "title": title or final_url,
            "url": final_url,
            "text": text,
        }
        if truncated:
            item["truncated"] = True

        return ScrapeResult(
            items=[item],
            current_page=1,
            has_next=False,
        )
