"""
Scrape Agent — fetches full article content from URLs.

Uses Crawl4AI for scraping with a plain-requests fallback.
Handles content truncation for LLM context limits.
"""

import asyncio
import logging
import requests
from typing import Optional

from app.core.config import get_settings
from app.agents.utils import smart_truncate

logger = logging.getLogger("media_intel.agents.scrape")


class ScrapeAgent:
    """
    Fetches full article content from URLs using Crawl4AI.

    Fallback chain:
      1. Prefetched content (from search results).
      2. Crawl4AI async scrape.
      3. Plain requests + BeautifulSoup fallback.
      4. Snippet fallback (title + snippet text).
    """

    def __init__(self):
        self.settings = get_settings()
        self._browser_config = None
        self._run_config = None

    def _get_crawler_configs(self):
        """
        Lazily initialize Crawl4AI config objects.

        Returns:
            Tuple of (BrowserConfig, CrawlerRunConfig).
        """
        if self._browser_config is None:
            try:
                from crawl4ai import BrowserConfig, CrawlerRunConfig, CacheMode
                self._browser_config = BrowserConfig(
                    headless=True,
                    verbose=False,
                    extra_args=[
                        "--disable-gpu",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-extensions",
                        "--disable-images",
                    ],
                )
                self._run_config = CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    word_count_threshold=20,
                    only_text=False,
                    remove_overlay_elements=True,
                    magic=True,
                )
            except ImportError:
                logger.warning("crawl4ai not installed — will use requests fallback only")
                return None, None
        return self._browser_config, self._run_config

    async def _scrape_crawl4ai(self, url: str) -> Optional[str]:
        """
        Scrape a URL using Crawl4AI async crawler.

        Args:
            url: URL to scrape.

        Returns:
            Markdown content string, or None on failure.
        """
        try:
            from crawl4ai import AsyncWebCrawler

            browser_config, run_config = self._get_crawler_configs()
            if browser_config is None:
                return None

            async with AsyncWebCrawler(config=browser_config) as crawler:
                result = await crawler.arun(url=url, config=run_config)

            if not result.success:
                logger.debug(
                    f"Crawl4AI failed for {url[:60]}: {result.error_message}"
                )
                return None

            # Prefer fit_markdown (main content extracted), fall back to full markdown
            content = (
                result.markdown.fit_markdown
                if result.markdown and result.markdown.fit_markdown
                else result.markdown_v2.raw_markdown
                if hasattr(result, "markdown_v2") and result.markdown_v2
                else result.markdown
                if isinstance(result.markdown, str)
                else None
            )

            if content and len(content.strip()) > 50:
                logger.debug(
                    f"Crawl4AI scraped {url[:60]} ({len(content)} chars)"
                )
                return content

            return None

        except Exception as e:
            logger.debug(f"Crawl4AI error for {url[:60]}: {e}")
            return None

    def _scrape_requests_fallback(self, url: str) -> Optional[str]:
        """
        Plain-requests + BeautifulSoup fallback scraper.

        Used when Crawl4AI is unavailable or fails.

        Args:
            url: URL to fetch.

        Returns:
            Cleaned text content, or None on failure.
        """
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }
            resp = requests.get(url, headers=headers, timeout=20, allow_redirects=True)

            if resp.status_code != 200:
                return None

            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return None

            try:
                from bs4 import BeautifulSoup
            except ImportError:
                # No BeautifulSoup — return raw text capped
                return resp.text[:5000] if resp.text else None

            soup = BeautifulSoup(resp.text, "html.parser")

            # Remove noise elements
            for tag in soup(["script", "style", "nav", "footer", "header",
                              "aside", "iframe", "noscript", "form"]):
                tag.decompose()

            # Try to find main content block
            main = (
                soup.find("article")
                or soup.find("main")
                or soup.find(id=lambda x: x and any(
                    kw in x.lower() for kw in ("content", "article", "main", "body")
                ))
                or soup.find(class_=lambda x: x and any(
                    kw in str(x).lower() for kw in ("article", "content", "post-body", "entry")
                ))
                or soup.find("body")
            )

            if main:
                text = main.get_text(separator="\n", strip=True)
            else:
                text = soup.get_text(separator="\n", strip=True)

            # Clean up excessive whitespace
            import re
            text = re.sub(r"\n{3,}", "\n\n", text)
            text = re.sub(r" {2,}", " ", text)
            text = text.strip()

            if len(text) > 100:
                logger.debug(
                    f"Requests fallback scraped {url[:60]} ({len(text)} chars)"
                )
                return text

            return None

        except requests.exceptions.Timeout:
            logger.debug(f"Requests fallback timeout for {url[:60]}")
            return None
        except Exception as e:
            logger.debug(f"Requests fallback error for {url[:60]}: {e}")
            return None

    async def scrape(
        self,
        url: str,
        title: str = "",
        snippet: str = "",
        prefetched_content: str = "",
    ) -> Optional[str]:
        """
        Fetch full content for a URL with multi-level fallback.

        Fallback chain:
        1. Prefetched content (already obtained during search).
        2. Crawl4AI async scraper (handles JS-heavy pages).
        3. Plain requests + BeautifulSoup (lightweight fallback).
        4. Snippet fallback (title + snippet text).

        Args:
            url: The URL to scrape.
            title: Article title (used for snippet fallback).
            snippet: Search snippet (used for snippet fallback).
            prefetched_content: Content already fetched during search.

        Returns:
            Truncated content string, or None if all methods fail.
        """
        raw_content: Optional[str] = None

        # ── Step 1: Prefetched content ──
        if prefetched_content and len(prefetched_content.strip()) > 100:
            raw_content = prefetched_content
            logger.debug(
                f"Using prefetched content for {url[:60]} "
                f"({len(raw_content)} chars)"
            )

        # ── Step 2: Crawl4AI ──
        if not raw_content:
            raw_content = await self._scrape_crawl4ai(url)

        # ── Step 3: Requests fallback ──
        if not raw_content or len(raw_content.strip()) < 50:
            loop = asyncio.get_event_loop()
            raw_content = await loop.run_in_executor(
                None, self._scrape_requests_fallback, url
            )
            if raw_content and len(raw_content.strip()) > 50:
                logger.debug(
                    f"Requests fallback succeeded for {url[:60]} "
                    f"({len(raw_content)} chars)"
                )

        # ── Step 4: Snippet fallback ──
        if not raw_content or len(raw_content.strip()) < 50:
            if snippet and len(snippet) >= 30:
                raw_content = f"TITLE: {title}\n\nSNIPPET CONTENT:\n{snippet}"
                logger.debug(f"Using snippet fallback for {url[:60]}")
            else:
                logger.debug(f"No content available for {url[:60]}")
                return None

        return smart_truncate(raw_content, self.settings.MAX_CONTENT_CHARS)
