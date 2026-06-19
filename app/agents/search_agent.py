"""
Search Agent — discovers articles and social media posts about a target.

Uses SearXNG (self-hosted meta-search engine) for search.
Runs multiple search passes (news, social, security) based on scan depth,
deduplicates results, and filters by date and relevance.
"""

import asyncio
import re
import logging
import time
import requests
from urllib.parse import quote
from typing import Optional

from app.core.config import get_settings
from app.agents.utils import (
    get_date_filter_str, parse_timeframe_to_cutoff,
    is_within_timeframe, filter_and_classify,
)
from app.agents.constants import (
    NEWS_SEARCH_QUERIES, SOCIAL_SEARCH_QUERIES, SECURITY_SEARCH_QUERIES,
)

logger = logging.getLogger("media_intel.agents.search")


class SearchAgent:
    """
    Discovers articles about a target through multiple SearXNG search passes.

    Runs news, social media, and security-focused searches at varying
    depth levels, then deduplicates and filters by date and relevance.
    """

    def __init__(self, max_concurrency: int = 3):
        self.settings = get_settings()
        self.max_concurrency = max_concurrency
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # ─────────────────────────────────────────────────
    # SearXNG search
    # ─────────────────────────────────────────────────

    def _search_searxng_all(self, query: str) -> list[dict]:
        """
        Retrieve all pages of SearXNG results up to SEARXNG_MAX_PAGES.
        Stops early if SearXNG returns empty lists or errors out.
        """
        all_results = []
        max_pages = self.settings.SEARXNG_MAX_PAGES

        for page in range(1, max_pages + 1):
            page_results = self._search_searxng_page(query, page)

            if not page_results:
                logger.debug(
                    f"No more results after page {page - 1} for: {query[:50]}"
                )
                break

            all_results.extend(page_results)
            logger.debug(
                f"SearXNG page {page}: {len(page_results)} results "
                f"for query: {query[:50]}"
            )

            if page < max_pages:
                # Polite backoff delay between sequential page crawls
                time.sleep(1.0)

        return all_results

    def _search_searxng_page(self, query: str, page: int) -> list[dict]:
        """
        Fetch a single page of results from SearXNG using JSON formatting.
        Returns empty list if blocked, forbidden, or on error.
        """
        url = (
            f"{self.settings.SEARXNG_URL}/search"
            f"?q={quote(query)}"
            f"&format=json"
            f"&pageno={page}"
        )
        try:
            resp = requests.get(url, headers=self.headers, timeout=30)

            if resp.status_code == 403:
                logger.error(
                    f"SearXNG returned 403 Forbidden on page {page}. "
                    f"Ensure JSON format is explicitly enabled in your searxng/settings.yml"
                )
                return []

            if resp.status_code != 200:
                logger.debug(
                    f"SearXNG page {page} returned status {resp.status_code} "
                    f"for query: {query[:50]}"
                )
                return []

            data = resp.json()
            return data.get("results", [])

        except requests.exceptions.Timeout:
            logger.warning(f"SearXNG timeout on page {page} for: {query[:50]}")
            return []
        except Exception as e:
            logger.warning(
                f"SearXNG error on page {page} for '{query[:50]}': {e}"
            )
            return []

    def _parse_searxng_result(self, item: dict) -> Optional[dict]:
        """
        Parse a single SearXNG result item into a normalized dict.
        Provides dual-key compatibility ('snippet' and 'content') to satisfy
        internal filtering modules.
        """
        if not isinstance(item, dict):
            return None

        url = item.get("url") or item.get("href") or item.get("link") or ""
        title = item.get("title") or "Untitled"

        # Safe evaluation extraction across common search response variants
        snippet = (
            item.get("content")
            or item.get("snippet")
            or item.get("description", "")[:500]
            or ""
        )

        if not url or not url.startswith("http"):
            return None

        return {
            "title": title,
            "url": url,
            "snippet": snippet,
            "content": snippet,  # 👈 FIX: Added to support legacy Whoogle code inside filter_and_classify
        }

    def _search_query(self, query: str) -> list[dict]:
        """
        Execute a full multi-page SearXNG search for one query.
        """
        raw_items = self._search_searxng_all(query)

        results = []
        for item in raw_items:
            try:
                parsed = self._parse_searxng_result(item)
                if parsed and parsed.get("url"):
                    results.append(parsed)
            except Exception as e:
                logger.debug(f"Failed to parse SearXNG result: {e}")
                continue

        if results:
            logger.debug(
                f"Query returned {len(results)} results: {query[:60]}"
            )
        return results

    async def _search_async(
        self, query: str, semaphore: asyncio.Semaphore
    ) -> list[dict]:
        """Run a single search query asynchronously with a polite delay."""
        async with semaphore:
            try:
                # Prevent slamming SearXNG's upstream search providers concurrently
                await asyncio.sleep(self.settings.SEARXNG_QUERY_DELAY)

                loop = asyncio.get_event_loop()
                results = await loop.run_in_executor(
                    None, self._search_query, query
                )
                return [r for r in results if r.get("url")]
            except Exception as e:
                logger.warning(f"Search failed for query '{query[:50]}': {e}")
                return []

    # ─────────────────────────────────────────────────
    # Discovery pipeline
    # ─────────────────────────────────────────────────

    async def discover(
        self,
        target: str,
        timeframe: str,
        depth: str = "standard",
    ) -> tuple[list, list]:
        """
        Run multi-pass discovery for a target using SearXNG.
        """
        date_filter = get_date_filter_str(timeframe)
        cutoff_date = parse_timeframe_to_cutoff(timeframe)

        # Build queries for all categories at the requested depth
        news_q = NEWS_SEARCH_QUERIES.get(depth, NEWS_SEARCH_QUERIES["standard"])
        social_q = SOCIAL_SEARCH_QUERIES.get(depth, SOCIAL_SEARCH_QUERIES["standard"])
        security_q = SECURITY_SEARCH_QUERIES.get(depth, SECURITY_SEARCH_QUERIES["standard"])

        all_templates = news_q + social_q + security_q
        all_queries = [
            q.format(target=target, timeframe=timeframe, date_filter=date_filter)
            for q in all_templates
        ]

        logger.info(
            f"Discovery starting: {len(all_queries)} queries, "
            f"depth={depth}, target='{target}'",
            extra={"action": "discovery_start", "target": target},
        )

        # Execute all queries concurrently (bounded by semaphore)
        semaphore = asyncio.Semaphore(self.max_concurrency)
        tasks = [self._search_async(q, semaphore) for q in all_queries]
        all_results = await asyncio.gather(*tasks)

        # Flatten and deduplicate by URL
        seen_urls: set[str] = set()
        unique_items: list[dict] = []
        for result_list in all_results:
            for item in result_list:
                url = item.get("url", "").rstrip("/").lower()
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique_items.append(item)

        total_raw = sum(len(r) for r in all_results)
        logger.info(
            f"Discovery raw: {total_raw} total, "
            f"{len(unique_items)} after dedup"
        )

        # Date filtering — optimized pass-through for un-dated metadata profiles
        date_filtered = []
        for item in unique_items:
            combined = f"{item.get('title', '')} {item.get('snippet', '')}".lower()

            # 1. Evaluate explicit ISO-stamps (YYYY-MM-DD)
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", combined)
            if date_match:
                if not is_within_timeframe(date_match.group(1), cutoff_date):
                    continue
                else:
                    date_filtered.append(item)
                    continue

            # 2. Heuristic check: Filter out explicitly old matches (years or past months)
            old_match = re.search(r"(\d+)\s+(year|month)s?\s+ago", combined)
            if old_match:
                num = int(old_match.group(1))
                unit = old_match.group(2)
                if unit == "year" and num >= 1:
                    continue
                tf_lower = timeframe.lower()
                if (
                    unit == "month"
                    and ("hour" in tf_lower or "day" in tf_lower or "week" in tf_lower)
                    and num >= 2
                ):
                    continue

            # 3. If no historical patterns trip the exclusion filters, retain the entry
            date_filtered.append(item)

        logger.info(f"Discovery after date filter: {len(date_filtered)}")

        # Classify and filter by relevance using safe key structures
        scrapable, snippet_based = filter_and_classify(
            date_filtered, target_name=target
        )

        logger.info(
            f"Discovery complete: {len(scrapable)} scrapable, "
            f"{len(snippet_based)} snippet-based",
            extra={"action": "discovery_complete"},
        )
        return scrapable, snippet_based
