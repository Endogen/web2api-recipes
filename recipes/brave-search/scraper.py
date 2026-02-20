"""Brave Search scraper — DOM-based extraction with anti-detection."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any
from urllib.parse import quote

from playwright.async_api import Page

from web2api.scraper import BaseScraper, ScrapeResult


class Scraper(BaseScraper):
    """Extract Brave Search results via rendered DOM."""

    def supports(self, endpoint: str) -> bool:
        return endpoint == "search"

    async def scrape(self, endpoint: str, page: Page, params: dict[str, Any]) -> ScrapeResult:
        query = (params.get("query") or "").strip()
        if not query:
            raise RuntimeError("Missing search query — pass q=<query>")

        count = min(int(params.get("count", "20")), 50)
        page_num = max(int(params.get("page", "1")), 1)
        offset = (page_num - 1) * 20

        url = f"https://search.brave.com/search?q={quote(query)}&offset={offset}"

        # Anti-detection: remove webdriver flag before navigation
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)

        # Let JS render results
        await asyncio.sleep(3)

        # Check for CAPTCHA
        title = await page.title()
        if "captcha" in title.lower():
            raise RuntimeError(
                "Brave Search returned a CAPTCHA — headless browser was detected"
            )

        # Wait for result snippets
        try:
            await page.wait_for_selector(
                '#results .snippet[data-type="web"]', timeout=8000
            )
        except Exception:
            return ScrapeResult(items=[], current_page=page_num, has_next=False)

        # Extract web results (skip AI answers, ads, etc.)
        snippets = await page.query_selector_all('#results .snippet[data-type="web"]')

        items: list[dict[str, Any]] = []
        for snippet in snippets[:count]:
            item = await self._parse_snippet(snippet)
            if item:
                items.append(item)

        # Check for next page
        has_next = len(snippets) >= 10

        return ScrapeResult(
            items=items,
            current_page=page_num,
            has_next=has_next,
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

        except Exception:
            return None
