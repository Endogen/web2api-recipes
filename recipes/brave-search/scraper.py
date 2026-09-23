"""Brave Search scraper — DOM-based extraction with anti-detection."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from web2api.scraper import BaseScraper, InvalidParamsError, ScrapeResult, coerce_int

logger = logging.getLogger(__name__)


class Scraper(BaseScraper):
    """Extract Brave Search results via rendered DOM."""

    def supports(self, endpoint: str) -> bool:
        return endpoint == "search"

    async def scrape(self, endpoint: str, page: Page, params: dict[str, Any]) -> ScrapeResult:
        query = (params.get("query") or "").strip()
        if not query:
            raise InvalidParamsError("missing search query — pass q=<query>")

        count = coerce_int(params.get("count", 20), name="count", default=20)
        if not 1 <= count <= 50:
            raise InvalidParamsError("count must be between 1 and 50")
        page_num = coerce_int(params.get("page", 1), name="page", default=1)
        if page_num < 1:
            raise InvalidParamsError("page must be at least 1")
        offset = (page_num - 1) * 20

        url = f"https://search.brave.com/search?q={quote(query, safe='')}&offset={offset}"

        # Anti-detection: remove webdriver flag before navigation
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)

        # Check for CAPTCHA
        title = await page.title()
        if "captcha" in title.lower():
            raise RuntimeError("Brave Search returned a CAPTCHA — headless browser was detected")

        # Wait for result snippets
        try:
            await page.wait_for_selector('#results .snippet[data-type="web"]', timeout=12000)
        except PlaywrightTimeoutError:
            title = await page.title()
            if "captcha" in title.lower():
                raise RuntimeError(
                    "Brave Search returned a CAPTCHA — headless browser was detected"
                ) from None
            return ScrapeResult(items=[], current_page=page_num, has_next=False)

        # Extract web results (skip AI answers, ads, etc.)
        snippets = await page.query_selector_all('#results .snippet[data-type="web"]')

        items: list[dict[str, Any]] = []
        for snippet in snippets[:count]:
            item = await self._parse_snippet(snippet)
            if item:
                items.append(item)

        next_link = await page.query_selector(
            "a[rel='next'], a[aria-label='Next'], .pagination a.next"
        )

        return ScrapeResult(
            items=items,
            current_page=page_num,
            has_next=next_link is not None,
        )

    @staticmethod
    async def _parse_snippet(snippet: Any) -> dict[str, Any] | None:
        """Parse a single web result snippet."""
        try:
            # Title — look for the title element inside the link
            title = ""
            for sel in [
                "[class*='title']",
                "a h2",
                "a h3",
            ]:
                el = await snippet.query_selector(sel)
                if el:
                    title = (await el.text_content() or "").strip()
                    if title:
                        break
            if not title:
                return None

            # URL — first external link
            href = ""
            links = await snippet.query_selector_all("a[href^='http']")
            for link in links:
                h = await link.get_attribute("href") or ""
                if "brave.com" not in h:
                    href = h
                    break
            if not href:
                return None

            # Description — the .content element
            desc = ""
            for sel in [".content", "[class*='snippet-description']", "p"]:
                el = await snippet.query_selector(sel)
                if el:
                    desc = (await el.text_content() or "").strip()
                    if desc:
                        break

            # Site name
            site = ""
            site_el = await snippet.query_selector("[class*='site-name']")
            if site_el:
                # Get just the first text node (site name, not the breadcrumb)
                site = (await site_el.text_content() or "").strip()
                # Clean up breadcrumb (e.g. "Wikipedia de.wikipedia.org › wiki")
                parts = site.split("\n")
                site = parts[0].strip() if parts else site

            result: dict[str, Any] = {
                "title": title,
                "url": href,
                "snippet": desc,
            }
            if site:
                result["site"] = site

            return result

        except PlaywrightError as exc:
            logger.debug("Skipping malformed Brave result: %s", exc)
            return None
