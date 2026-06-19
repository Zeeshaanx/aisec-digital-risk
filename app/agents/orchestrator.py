"""
Scan Orchestrator — coordinates the full scan pipeline.

Pipeline:
1. SearchAgent discovers articles.
2. **Cache check**: skip URLs already analyzed for this target.
3. ScrapeAgent fetches full content for NEW scrapable URLs only.
4. AnalysisAgent performs LLM-based analysis on NEW content only.
5. Results are deduplicated and saved to the database.
6. Cached + new results are combined for the full report.
"""

import asyncio
import time
import logging
from datetime import datetime
from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.core.normalization import normalize_url
from app.agents.search_agent import SearchAgent
from app.agents.scrape_agent import ScrapeAgent
from app.agents.analysis_agent import AnalysisAgent
from app.agents.utils import (
    parse_timeframe_to_cutoff, get_timeframe_description,
    check_content_relevance, classify_url,
)
from app.services.scan_service import ScanService
from app.models.target import Target

logger = logging.getLogger("media_intel.agents.orchestrator")


class ScanOrchestrator:
    """
    Coordinates the full scan execution pipeline.

    Features:
    - Smart caching: skips scraping/analysis for URLs already in the DB.
    - Fresh agent instances per scan to avoid state leakage.
    - Concurrent processing with configurable limits.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.search_agent = SearchAgent(max_concurrency=self.settings.MAX_CONCURRENCY)
        self.scrape_agent = ScrapeAgent()
        self.analysis_agent = AnalysisAgent()
        self.scan_service = ScanService(db)

    async def execute_scan(
        self,
        scan_id: UUID,
        target_id: UUID,
    ) -> dict:
        """
        Execute a complete scan pipeline with smart caching.

        Steps:
        1. Mark scan as running, load target.
        2. Run SearchAgent discovery (Firecrawl).
        3. Check DB for already-analyzed URLs (cache).
        4. Scrape + analyze only NEW URLs.
        5. Analyze only NEW snippets.
        6. Save new articles to DB.
        7. Link cached articles to this scan.
        8. Aggregate ALL results (cached + new).
        9. Complete scan with summary.

        Args:
            scan_id: The scan UUID.
            target_id: The target UUID.

        Returns:
            Aggregated report dict.
        """
        start_time = time.time()

        # Step 1: Mark running and load target
        scan = await self.scan_service.mark_scan_running(scan_id)

        target_result = await self.db.execute(
            select(Target).where(Target.id == target_id)
        )
        target_obj = target_result.scalar_one_or_none()
        target_name = target_obj.display_name if target_obj else "Unknown"

        logger.info(
            f"Scan execution started: {scan_id} — target='{target_name}'",
            extra={
                "action": "scan_execute_start",
                "scan_id": str(scan_id),
                "target_id": str(target_id),
            },
        )

        try:
            timeframe = scan.timeframe
            depth = (
                scan.scan_depth.value
                if hasattr(scan.scan_depth, "value")
                else str(scan.scan_depth)
            )
            cutoff_date = parse_timeframe_to_cutoff(timeframe)

            # Step 2: Discovery
            self.analysis_agent.reset_usage()
            scrapable, snippet_based = await self.search_agent.discover(
                target=target_name,
                timeframe=timeframe,
                depth=depth,
            )

            logger.info(
                f"Discovery complete: {len(scrapable)} scrapable, "
                f"{len(snippet_based)} snippet-based",
            )

            # Step 3: Smart cache check
            new_scrapable = scrapable
            new_snippet_based = snippet_based
            cached_articles = []
            cached_result_dicts = []

            if self.settings.ENABLE_SCAN_CACHING:
                (
                    new_scrapable,
                    new_snippet_based,
                    cached_articles,
                    cached_result_dicts,
                ) = await self._apply_cache(
                    target_id=target_id,
                    scrapable=scrapable,
                    snippet_based=snippet_based,
                )

            # Step 4: Scrape + Analyze NEW scrapable articles
            new_results = []

            if new_scrapable:
                semaphore = asyncio.Semaphore(self.settings.MAX_CONCURRENCY)
                tasks = [
                    self._process_scrapable_article(
                        target_name, article, semaphore, timeframe, cutoff_date,
                    )
                    for article in new_scrapable
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in results:
                    if isinstance(r, Exception):
                        logger.warning(f"Article processing error: {r}")
                    elif r is not None:
                        new_results.append(r)

            # Step 5: Analyze NEW snippets
            if new_snippet_based:
                semaphore = asyncio.Semaphore(self.settings.MAX_CONCURRENCY)
                tasks = [
                    self._process_snippet(
                        target_name, post, semaphore, timeframe, cutoff_date,
                    )
                    for post in new_snippet_based
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in results:
                    if isinstance(r, Exception):
                        logger.warning(f"Snippet processing error: {r}")
                    elif r is not None:
                        new_results.append(r)

            # Step 6: Save NEW articles to DB
            new_count, new_linked = await self.scan_service.save_articles(
                target_id=target_id,
                scan_id=scan_id,
                articles_data=new_results,
            )

            logger.info(
                f"Articles saved: {new_count} new, {new_linked} total for scan {scan_id}",
            )

            # Step 7: Link cached articles to this scan
            cached_linked = 0
            if cached_articles:
                cached_linked = await self.scan_service.link_cached_articles_to_scan(
                    scan_id=scan_id,
                    articles=cached_articles,
                )
                logger.info(
                    f"Cached articles linked: {cached_linked} for scan {scan_id}",
                )

            # Step 8: Aggregate ALL results (cached + new)
            all_results = cached_result_dicts + new_results
            duration = time.time() - start_time
            report = self._aggregate(
                target_name, timeframe, depth, all_results, duration,
            )

            # Step 9: Complete scan
            usage = self.analysis_agent.get_usage()
            total_linked = new_linked + cached_linked

            await self.scan_service.complete_scan(
                scan_id=scan_id,
                report=report,
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                cost_usd=usage["cost_usd"],
                new_articles=new_count,
            )

            report["new_articles_found"] = new_count
            report["cached_articles_reused"] = len(cached_articles)
            report["total_articles_linked"] = total_linked
            report["cost"] = usage

            logger.info(
                f"Scan completed: {scan_id} — {report['total_results']} results "
                f"({new_count} new, {len(cached_articles)} cached), "
                f"${usage['cost_usd']:.6f}",
                extra={
                    "action": "scan_execute_complete",
                    "scan_id": str(scan_id),
                    "duration": round(duration, 2),
                },
            )

            return report

        except Exception as e:
            duration = time.time() - start_time
            logger.exception(
                f"Scan execution failed: {scan_id} — {e}",
                extra={"action": "scan_execute_fail", "scan_id": str(scan_id)},
            )
            await self.scan_service.fail_scan(scan_id, str(e)[:2000])
            raise

    async def _apply_cache(
        self,
        target_id: UUID,
        scrapable: list[dict],
        snippet_based: list[dict],
    ) -> tuple[list[dict], list[dict], list, list[dict]]:
        """
        Check discovered URLs against the database cache.

        Separates articles into:
        - new_scrapable: URLs NOT in DB → need scraping + analysis
        - new_snippet_based: URLs NOT in DB → need snippet analysis
        - cached_articles: Article DB objects already analyzed
        - cached_result_dicts: Cached articles as result dicts for aggregation

        Args:
            target_id: The target UUID.
            scrapable: Discovered scrapable articles from SearchAgent.
            snippet_based: Discovered snippet-based articles from SearchAgent.

        Returns:
            Tuple of (new_scrapable, new_snippet_based, cached_articles, cached_result_dicts).
        """
        all_urls = []
        for article in scrapable:
            url = article.get("url", "")
            if url:
                all_urls.append(url)
        for post in snippet_based:
            url = post.get("url", "")
            if url:
                all_urls.append(url)

        if not all_urls:
            return scrapable, snippet_based, [], []

        cached_map = await self.scan_service.get_cached_articles_by_urls(
            target_id=target_id,
            urls=all_urls,
        )

        if not cached_map:
            logger.info(
                f"Cache check: 0 cached out of {len(all_urls)} discovered URLs"
            )
            return scrapable, snippet_based, [], []

        new_scrapable = []
        new_snippet_based = []
        cached_articles = []
        cached_result_dicts = []
        seen_cached_ids = set()

        for article in scrapable:
            url = article.get("url", "")
            norm = normalize_url(url) if url else ""
            if norm in cached_map:
                cached_art = cached_map[norm]
                if cached_art.id not in seen_cached_ids:
                    seen_cached_ids.add(cached_art.id)
                    cached_articles.append(cached_art)
                    cached_result_dicts.append(
                        ScanService.article_to_result_dict(cached_art)
                    )
            else:
                new_scrapable.append(article)

        for post in snippet_based:
            url = post.get("url", "")
            norm = normalize_url(url) if url else ""
            if norm in cached_map:
                cached_art = cached_map[norm]
                if cached_art.id not in seen_cached_ids:
                    seen_cached_ids.add(cached_art.id)
                    cached_articles.append(cached_art)
                    cached_result_dicts.append(
                        ScanService.article_to_result_dict(cached_art)
                    )
            else:
                new_snippet_based.append(post)

        logger.info(
            f"Cache check: {len(cached_articles)} cached, "
            f"{len(new_scrapable)} new scrapable, "
            f"{len(new_snippet_based)} new snippets "
            f"(out of {len(all_urls)} discovered URLs)",
            extra={"action": "cache_check"},
        )

        return new_scrapable, new_snippet_based, cached_articles, cached_result_dicts

    async def _process_scrapable_article(
        self,
        target: str,
        article: dict,
        semaphore: asyncio.Semaphore,
        timeframe: str,
        cutoff_date: datetime,
    ) -> Optional[dict]:
        """
        Process a single scrapable article: scrape → verify → analyze.

        Args:
            target: Target name.
            article: Article dict from search results.
            semaphore: Concurrency limiter.
            timeframe: Scan timeframe.
            cutoff_date: Datetime cutoff for date validation.

        Returns:
            Analysis result dict, or None if skipped.
        """
        async with semaphore:
            url = article.get("url", "")
            title = article.get("title", "") or "Untitled"
            snippet = article.get("snippet", "") or ""
            prefetched = article.get("prefetched_content", "")

            cls, _ = classify_url(url)
            if cls in ("skip", "profile"):
                return None

            try:
                content = await self.scrape_agent.scrape(
                    url=url,
                    title=title,
                    snippet=snippet,
                    prefetched_content=prefetched,
                )

                if not content:
                    return None

                relevance = check_content_relevance(
                    target=target,
                    title=title,
                    snippet=snippet,
                    source_name=article.get("source_name", ""),
                    author=article.get("author", ""),
                    full_content=content,
                )
                if not relevance["relevant"]:
                    logger.debug(f"Not relevant: {url[:60]} — {relevance['reason']}")
                    return None

                result = await self.analysis_agent.analyze_article(
                    target=target,
                    url=url,
                    title=title,
                    content=content,
                    timeframe=timeframe,
                    cutoff_date=cutoff_date,
                )
                return result

            except Exception as e:
                logger.warning(f"Error processing {url[:60]}: {e}")
                return None

    async def _process_snippet(
        self,
        target: str,
        post: dict,
        semaphore: asyncio.Semaphore,
        timeframe: str,
        cutoff_date: datetime,
    ) -> Optional[dict]:
        """
        Process a single snippet-based social media post.

        Args:
            target: Target name.
            post: Post dict from search results.
            semaphore: Concurrency limiter.
            timeframe: Scan timeframe.
            cutoff_date: Datetime cutoff for date validation.

        Returns:
            Analysis result dict, or None if skipped.
        """
        async with semaphore:
            url = post.get("url", "")
            title = post.get("title", "") or "Untitled"
            snippet = post.get("snippet", "") or ""

            try:
                result = await self.analysis_agent.analyze_snippet(
                    target=target,
                    url=url,
                    title=title,
                    snippet=snippet,
                    timeframe=timeframe,
                    cutoff_date=cutoff_date,
                )
                return result

            except Exception as e:
                logger.warning(f"Error processing snippet {url[:60]}: {e}")
                return None

    def _aggregate(
        self,
        target: str,
        timeframe: str,
        depth: str,
        results: list,
        duration: float,
    ) -> dict:
        """
        Aggregate analysis results into a summary report.

        Combines both cached (reused) and freshly analyzed results
        into a unified report with sentiment, risk, and security summaries.

        Args:
            target: Target name.
            timeframe: Scan timeframe.
            depth: Scan depth.
            results: List of analysis result dicts (cached + new).
            duration: Processing time in seconds.

        Returns:
            Aggregated report dict.
        """
        valid = [r for r in results if r is not None]

        sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
        risks = set()
        platforms = {}
        sources = {}
        security_alerts = []

        for r in valid:
            sent = r.get("sentiment", "neutral")
            if sent in sentiment_counts:
                sentiment_counts[sent] += 1

            for flag in r.get("risk_flags", []):
                flag_str = str(flag) if not isinstance(flag, str) else flag
                if flag_str and flag_str != "none":
                    risks.add(flag_str)

            plat = r.get("platform", "web") or "web"
            platforms[plat] = platforms.get(plat, 0) + 1

            src = r.get("source_name", "unknown") or "unknown"
            sources[src] = sources.get(src, 0) + 1

            sec_sev = r.get("security_severity", "none")
            if sec_sev and sec_sev != "none":
                security_alerts.append({
                    "severity": sec_sev,
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "summary": r.get("summary", ""),
                    "security_details": r.get("security_details", ""),
                    "security_keywords": r.get("security_keywords", []),
                    "risk_flags": r.get("risk_flags", []),
                })

        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        security_alerts.sort(
            key=lambda x: severity_order.get(x.get("severity", "low"), 4)
        )

        total_valid = len(valid)
        pos_pct = (
            round(sentiment_counts["positive"] / total_valid * 100, 1)
            if total_valid else 0
        )
        neg_pct = (
            round(sentiment_counts["negative"] / total_valid * 100, 1)
            if total_valid else 0
        )
        neu_pct = (
            round(sentiment_counts["neutral"] / total_valid * 100, 1)
            if total_valid else 0
        )

        return {
            "query": {
                "target": target,
                "timeframe": timeframe,
                "depth": depth,
                "date_range": get_timeframe_description(timeframe),
                "generated_at": datetime.now().isoformat(),
                "processing_time_seconds": round(duration, 2),
            },
            "total_results": total_valid,
            "source_breakdown": {
                "by_platform": platforms,
                "by_source": sources,
            },
            "sentiment_summary": {
                **sentiment_counts,
                "positive_pct": pos_pct,
                "negative_pct": neg_pct,
                "neutral_pct": neu_pct,
            },
            "overall_sentiment": (
                max(sentiment_counts, key=sentiment_counts.get) if valid else "none"
            ),
            "risk_summary": sorted(list(risks)) if risks else ["none"],
            "security_alerts": security_alerts,
            "security_alert_count": len(security_alerts),
            "results": valid,
        }
