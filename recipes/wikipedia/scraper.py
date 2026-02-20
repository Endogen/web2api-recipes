"""Wikipedia scraper — search articles and extract structured content."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote

from playwright.async_api import Page

from web2api.scraper import BaseScraper, ScrapeResult


class Scraper(BaseScraper):
    """Scrape Wikipedia search results and article content."""

    def supports(self, endpoint: str) -> bool:
        return endpoint in ("search", "article")

    async def scrape(self, endpoint: str, page: Page, params: dict[str, Any]) -> ScrapeResult:
        if endpoint == "search":
            return await self._search(page, params)
        return await self._article(page, params)

    async def _search(self, page: Page, params: dict[str, Any]) -> ScrapeResult:
        query = (params.get("query") or "").strip()
        if not query:
            raise RuntimeError("Missing search query — pass q=<query>")

        count = min(int(params.get("count", "20")), 50)
        page_num = max(int(params.get("page", "1")), 1)
        offset = (page_num - 1) * 20

        url = (
            f"https://en.wikipedia.org/w/index.php"
            f"?search={quote(query)}&title=Special:Search&ns0=1&offset={offset}"
        )

        await page.goto(url, wait_until="domcontentloaded")

        # Wikipedia may redirect directly to an article on exact match
        if "/wiki/" in page.url and "Special:Search" not in page.url:
            return await self._article_from_redirect(page, query)

        await page.wait_for_selector(".mw-search-results, .mw-search-nonefound", timeout=10000)

        # Check for no results
        none_found = await page.query_selector(".mw-search-nonefound")
        if none_found:
            return ScrapeResult(items=[], current_page=page_num, has_next=False)

        items = await self._extract_search_results(page, count)

        has_next = await page.query_selector(".mw-nextlink") is not None

        return ScrapeResult(
            items=items,
            current_page=page_num,
            has_next=has_next,
        )

    async def _article(self, page: Page, params: dict[str, Any]) -> ScrapeResult:
        query = (params.get("query") or "").strip()
        if not query:
            raise RuntimeError("Missing article title — pass q=<title>")

        # Support both plain titles and URL slugs
        slug = query.replace(" ", "_")
        url = f"https://en.wikipedia.org/wiki/{quote(slug, safe='/:')}"

        await page.goto(url, wait_until="domcontentloaded")

        # Check for missing article
        no_article = await page.query_selector(".noarticletext")
        if no_article:
            raise RuntimeError(f"Wikipedia article not found: {query}")

        return await self._extract_article(page)

    async def _article_from_redirect(self, page: Page, original_query: str) -> ScrapeResult:
        """Handle direct redirect to article (exact match search)."""
        result = await self._extract_article(page)
        if result.items:
            result.items[0]["redirected_from"] = original_query
        return result

    async def _extract_article(self, page: Page) -> ScrapeResult:
        """Extract structured content from an article page."""
        item: dict[str, Any] = {}

        # Title
        title_el = await page.query_selector("#firstHeading")
        if title_el:
            item["title"] = (await title_el.text_content() or "").strip()

        # Canonical URL
        item["url"] = page.url

        # Summary — first paragraph(s) before the TOC
        item["summary"] = await self._extract_summary(page)

        # Infobox key-value pairs
        infobox = await self._extract_infobox(page)
        if infobox:
            item["infobox"] = infobox

        # Table of contents
        toc = await self._extract_toc(page)
        if toc:
            item["table_of_contents"] = toc

        # Sections with content
        item["sections"] = await self._extract_sections(page)

        # Categories
        categories = await self._extract_categories(page)
        if categories:
            item["categories"] = categories

        # Languages available
        lang_count = len(await page.query_selector_all("#p-lang li, .interlanguage-link"))
        if lang_count:
            item["languages_available"] = lang_count

        # Serialize complex values to JSON strings (FieldValue only allows scalars)
        for key, val in item.items():
            if isinstance(val, (list, dict)):
                item[key] = json.dumps(val, ensure_ascii=False)

        return ScrapeResult(items=[item], current_page=1, has_next=False)

    @staticmethod
    async def _extract_search_results(page: Page, count: int) -> list[dict[str, Any]]:
        """Extract search result entries."""
        items: list[dict[str, Any]] = []

        results = await page.query_selector_all(".mw-search-result")

        for result in results[:count]:
            try:
                # Title + URL
                heading = await result.query_selector(".mw-search-result-heading a")
                if not heading:
                    continue
                title = (await heading.text_content() or "").strip()
                href = await heading.get_attribute("href") or ""
                url = f"https://en.wikipedia.org{href}" if href.startswith("/") else href

                # Snippet
                snippet_el = await result.query_selector(".searchresult")
                snippet = (await snippet_el.text_content() or "").strip() if snippet_el else ""

                # Word count / size hint
                size_el = await result.query_selector(".mw-search-result-data")
                size_info = (await size_el.text_content() or "").strip() if size_el else ""

                item: dict[str, Any] = {
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                }
                if size_info:
                    item["size_info"] = size_info

                items.append(item)
            except Exception:
                continue

        return items

    @staticmethod
    async def _extract_summary(page: Page) -> str:
        """Extract the lead section (paragraphs before the first heading or TOC)."""
        paragraphs: list[str] = []

        # Get all direct <p> children of the content div, before the TOC
        els = await page.query_selector_all(
            "#mw-content-text .mw-parser-output > p"
        )
        for el in els:
            text = (await el.text_content() or "").strip()
            # Skip empty paragraphs and the coordinates line
            if not text or len(text) < 10:
                continue
            paragraphs.append(text)
            # Usually 2-3 paragraphs is enough for a summary
            if len(paragraphs) >= 3:
                break

        return "\n\n".join(paragraphs)

    @staticmethod
    async def _extract_infobox(page: Page) -> dict[str, str]:
        """Extract key-value pairs from the infobox table."""
        infobox: dict[str, str] = {}

        table = await page.query_selector(".infobox, .infobox_v2")
        if not table:
            return infobox

        rows = await table.query_selector_all("tr")
        for row in rows:
            header = await row.query_selector("th")
            data = await row.query_selector("td")
            if header and data:
                key = (await header.text_content() or "").strip()
                val = (await data.text_content() or "").strip()
                if key and val:
                    # Clean up excessive whitespace
                    val = re.sub(r"\s+", " ", val)
                    infobox[key] = val

        return infobox

    @staticmethod
    async def _extract_toc(page: Page) -> list[str]:
        """Extract table of contents headings."""
        toc_items: list[str] = []

        entries = await page.query_selector_all(
            "#toc .toctext, .vector-toc-text, .mw-toc-text .toctext"
        )
        for entry in entries:
            text = (await entry.text_content() or "").strip()
            if text:
                toc_items.append(text)

        return toc_items

    @staticmethod
    async def _extract_sections(page: Page) -> list[dict[str, str]]:
        """Extract article sections with their heading and text content."""
        sections: list[dict[str, str]] = []

        # Get all h2/h3 headings and their following content
        headings = await page.query_selector_all(
            "#mw-content-text .mw-parser-output > h2, "
            "#mw-content-text .mw-parser-output > h3"
        )

        for heading in headings:
            headline = await heading.query_selector(".mw-headline, h2, h3")
            if not headline:
                headline = heading
            title = (await headline.text_content() or "").strip()

            # Skip edit links text and meta sections
            title = re.sub(r"\[edit\]$", "", title).strip()
            if not title or title.lower() in ("references", "external links", "notes", "further reading"):
                continue

            # Collect text from sibling elements until the next heading
            content_parts: list[str] = []
            sibling = await heading.evaluate_handle(
                "el => el.nextElementSibling"
            )

            for _ in range(50):  # safety cap
                if not sibling:
                    break
                tag = await sibling.evaluate("el => el.tagName")
                if tag in ("H2", "H3"):
                    break
                if tag == "P":
                    text = await sibling.evaluate("el => el.textContent")
                    text = (text or "").strip()
                    if text:
                        content_parts.append(text)
                sibling = await sibling.evaluate_handle(
                    "el => el.nextElementSibling"
                )

            level = "h2" if await heading.evaluate("el => el.tagName") == "H2" else "h3"

            sections.append({
                "heading": title,
                "level": level,
                "content": "\n\n".join(content_parts),
            })

        return sections

    @staticmethod
    async def _extract_categories(page: Page) -> list[str]:
        """Extract article categories."""
        categories: list[str] = []
        cat_links = await page.query_selector_all("#mw-normal-catlinks ul li a")
        for link in cat_links:
            text = (await link.text_content() or "").strip()
            if text:
                categories.append(text)
        return categories
