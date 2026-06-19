"""
Scan management service.

Handles scan creation (one-time and scheduled), status tracking,
result retrieval from the database, and schedule cancellation.
No user association — scans are global resources.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    NotFoundException, ValidationException,
)
from app.core.normalization import normalize_url
from app.models.scan import Scan, ScanArticle
from app.models.article import Article
from app.models.target import Target
from app.models.enums import (
    ScanType, ScanStatus, ScanDepth,
    SentimentType, SecuritySeverity,
)

logger = logging.getLogger("media_intel.scan_service")


def _parse_interval_to_timedelta(interval: str) -> timedelta:
    """
    Convert a human-readable interval string to timedelta.

    Supports: hours, days, weeks, months (approximated as 30 days).

    Args:
        interval: String like '6 hours', '1 day', '2 weeks', '1 month'.

    Returns:
        timedelta object.

    Raises:
        ValidationException: If the interval format is unrecognized.
    """
    import re
    interval = interval.lower().strip()
    match = re.match(r"(\d+)\s*(hour|hours|day|days|week|weeks|month|months)", interval)
    if not match:
        raise ValidationException(f"Invalid interval format: '{interval}'")

    num = int(match.group(1))
    unit = match.group(2).rstrip("s")

    mapping = {
        "hour": timedelta(hours=num),
        "day": timedelta(days=num),
        "week": timedelta(weeks=num),
        "month": timedelta(days=num * 30),
    }
    return mapping.get(unit, timedelta(hours=24))


class ScanService:
    """
    Scan lifecycle management.

    Handles:
    - Creating one-time and scheduled scans.
    - Listing scans with filtering and pagination.
    - Recording scan results and article associations.
    - Retrieving results from the database (single source of truth).
    - Cancelling scheduled scans.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ═══════════════════════════════════════════════════════
    # SMART SCAN CACHING
    # ═══════════════════════════════════════════════════════

    async def get_cached_articles_by_urls(
        self,
        target_id: UUID,
        urls: list[str],
    ) -> dict[str, "Article"]:
        """
        Get existing articles for a target by their URLs.

        Used by the orchestrator to skip re-scraping and re-analyzing
        URLs that already have analysis results in the database.

        Args:
            target_id: The target UUID.
            urls: List of discovered URLs to check.

        Returns:
            Dict mapping normalized_url → Article for already-analyzed URLs.
        """
        if not urls:
            return {}

        norm_urls = list(set(normalize_url(u) for u in urls if u))
        if not norm_urls:
            return {}

        batch_size = 500
        cached = {}

        for i in range(0, len(norm_urls), batch_size):
            batch = norm_urls[i:i + batch_size]
            result = await self.db.execute(
                select(Article).where(
                    Article.target_id == target_id,
                    Article.normalized_url.in_(batch),
                )
            )
            for article in result.scalars().all():
                cached[article.normalized_url] = article

        return cached

    async def get_cached_articles_in_timeframe(
        self,
        target_id: UUID,
        timeframe: str,
    ) -> list["Article"]:
        """
        Get all existing articles for a target within a timeframe.

        Args:
            target_id: The target UUID.
            timeframe: How far back to look (e.g., '1 week').

        Returns:
            List of Article objects within the timeframe.
        """
        from app.agents.utils import parse_timeframe_to_cutoff

        cutoff = parse_timeframe_to_cutoff(timeframe)

        result = await self.db.execute(
            select(Article).where(
                Article.target_id == target_id,
                or_(
                    Article.published_date >= cutoff.date(),
                    Article.scraped_at >= cutoff.replace(tzinfo=timezone.utc),
                ),
            ).order_by(Article.scraped_at.desc())
        )
        return list(result.scalars().all())

    async def link_cached_articles_to_scan(
        self,
        scan_id: UUID,
        articles: list["Article"],
    ) -> int:
        """
        Link existing (cached) articles to a scan via ScanArticle.

        These articles already existed in the DB and are marked is_new=False.

        Args:
            scan_id: The scan UUID.
            articles: List of existing Article objects to link.

        Returns:
            Number of articles linked.
        """
        linked = 0

        for article in articles:
            existing_link = await self.db.execute(
                select(ScanArticle).where(
                    ScanArticle.scan_id == scan_id,
                    ScanArticle.article_id == article.id,
                )
            )
            if existing_link.scalar_one_or_none():
                continue

            scan_article = ScanArticle(
                scan_id=scan_id,
                article_id=article.id,
                is_new=False,
            )
            self.db.add(scan_article)
            linked += 1

        if linked > 0:
            await self.db.commit()

        return linked

    @staticmethod
    def article_to_result_dict(article: "Article") -> dict:
        """
        Convert an Article DB model to a result dict for aggregation.

        Args:
            article: An Article database model instance.

        Returns:
            Dict matching the format produced by AnalysisAgent.
        """
        return {
            "title": article.title,
            "url": article.original_url,
            "source_name": article.source_name,
            "source_type": article.source_type,
            "platform": article.platform or "web",
            "published_date": (
                article.published_date.isoformat()
                if article.published_date else None
            ),
            "author": article.author,
            "summary": article.summary,
            "what_others_say": article.what_others_say,
            "target_perspective": article.target_perspective,
            "key_quotes": article.key_quotes or [],
            "snippet_content": article.snippet_content,
            "sentiment": (
                article.sentiment.value
                if hasattr(article.sentiment, "value")
                else str(article.sentiment)
            ),
            "sentiment_reasoning": article.sentiment_reasoning,
            "headline_vs_body": article.headline_vs_body,
            "risk_flags": article.risk_flags or ["none"],
            "risk_details": article.risk_details,
            "security_severity": (
                article.security_severity.value
                if hasattr(article.security_severity, "value")
                else str(article.security_severity)
            ),
            "security_details": article.security_details,
            "security_keywords": article.security_keywords or [],
            "content_completeness": article.content_completeness,
        }

    # ═══════════════════════════════════════════════════════
    # SCAN CRUD
    # ═══════════════════════════════════════════════════════

    async def create_scan(
        self,
        target_id: UUID,
        scan_type: ScanType,
        scan_depth: ScanDepth = ScanDepth.standard,
        timeframe: str = "24 hours",
        schedule_interval: Optional[str] = None,
    ) -> Scan:
        """
        Create a new scan record.

        For one-time scans: status is set to 'pending', execution starts immediately.
        For scheduled scans: the schedule definition is stored, first execution is queued.

        Args:
            target_id: UUID of the target to scan.
            scan_type: 'one_time' or 'scheduled'.
            scan_depth: Search breadth.
            timeframe: How far back to search.
            schedule_interval: Recurrence interval (required for scheduled).

        Returns:
            The created Scan object.

        Raises:
            NotFoundException: If the target doesn't exist.
            ValidationException: If scheduled scan is missing interval.
        """
        target_result = await self.db.execute(
            select(Target).where(Target.id == target_id, Target.is_active == True)
        )
        target = target_result.scalar_one_or_none()
        if not target:
            raise NotFoundException("Target", str(target_id))

        is_schedule_active = scan_type == ScanType.scheduled
        next_run_at = None

        if scan_type == ScanType.scheduled:
            if not schedule_interval:
                raise ValidationException(
                    "schedule_interval is required for scheduled scans"
                )
            delta = _parse_interval_to_timedelta(schedule_interval)
            next_run_at = datetime.now(timezone.utc) + delta

        scan = Scan(
            target_id=target_id,
            scan_type=scan_type,
            scan_depth=scan_depth,
            timeframe=timeframe,
            schedule_interval=schedule_interval,
            is_schedule_active=is_schedule_active,
            next_run_at=next_run_at,
            status=ScanStatus.pending,
        )
        self.db.add(scan)
        await self.db.commit()
        await self.db.refresh(scan)

        logger.info(
            f"Scan created: {scan.id} type={scan_type.value} target={target.display_name}",
            extra={
                "action": "scan_create",
                "scan_id": str(scan.id),
                "target_id": str(target_id),
            },
        )
        return scan

    async def get_scan_by_id(self, scan_id: UUID) -> Scan:
        """
        Get a scan by UUID.

        Args:
            scan_id: The scan's UUID.

        Returns:
            The Scan object.

        Raises:
            NotFoundException: If not found.
        """
        result = await self.db.execute(
            select(Scan).where(Scan.id == scan_id)
        )
        scan = result.scalar_one_or_none()
        if not scan:
            raise NotFoundException("Scan", str(scan_id))
        return scan

    async def list_scans(
        self,
        status_filter: Optional[ScanStatus] = None,
        scan_type_filter: Optional[ScanType] = None,
        target_id_filter: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Scan], int]:
        """
        List all scans with optional filtering and pagination.

        Args:
            status_filter: Optional status filter.
            scan_type_filter: Optional type filter.
            target_id_filter: Optional target UUID filter.
            limit: Pagination limit.
            offset: Pagination offset.

        Returns:
            Tuple of (list of Scan objects, total count).
        """
        conditions = []

        if status_filter:
            conditions.append(Scan.status == status_filter)
        if scan_type_filter:
            conditions.append(Scan.scan_type == scan_type_filter)
        if target_id_filter:
            conditions.append(Scan.target_id == target_id_filter)

        query = select(Scan)
        count_query = select(func.count(Scan.id))

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        query = query.order_by(Scan.created_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(query)
        scans = list(result.scalars().all())

        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        return scans, total

    async def list_scheduled_scans(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Scan], int]:
        """
        List all active scheduled scans.

        Args:
            limit: Pagination limit.
            offset: Pagination offset.

        Returns:
            Tuple of (list of scheduled Scan objects, total count).
        """
        conditions = [
            Scan.scan_type == ScanType.scheduled,
            Scan.is_schedule_active == True,
        ]

        query = (
            select(Scan)
            .where(and_(*conditions))
            .order_by(Scan.next_run_at.asc())
            .limit(limit).offset(offset)
        )
        count_query = select(func.count(Scan.id)).where(and_(*conditions))

        result = await self.db.execute(query)
        scans = list(result.scalars().all())

        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        return scans, total

    async def cancel_scheduled_scan(self, scan_id: UUID) -> Scan:
        """
        Cancel a scheduled scan.

        Stops future executions but retains historical results.

        Args:
            scan_id: The scan UUID.

        Returns:
            The updated Scan object.

        Raises:
            NotFoundException: If scan not found.
            ValidationException: If the scan isn't a scheduled scan.
        """
        scan = await self.get_scan_by_id(scan_id)

        if scan.scan_type != ScanType.scheduled:
            raise ValidationException("Only scheduled scans can be cancelled")

        scan.is_schedule_active = False
        scan.next_run_at = None
        await self.db.commit()
        await self.db.refresh(scan)

        logger.info(
            f"Scheduled scan cancelled: {scan_id}",
            extra={"action": "scan_cancel", "scan_id": str(scan_id)},
        )
        return scan

    # ═══════════════════════════════════════════════════════
    # SCAN EXECUTION SUPPORT — called by agent orchestrator
    # ═══════════════════════════════════════════════════════

    async def mark_scan_running(self, scan_id: UUID) -> Scan:
        """Mark a scan as running (called when execution begins)."""
        scan = await self.get_scan_by_id(scan_id)
        scan.status = ScanStatus.running
        scan.started_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(scan)
        return scan

    async def save_articles(
        self,
        target_id: UUID,
        scan_id: UUID,
        articles_data: list[dict],
    ) -> tuple[int, int]:
        """
        Save scraped articles to the database with deduplication.

        For each article:
        1. Normalize the URL.
        2. Check if (target_id, normalized_url) already exists.
        3. If new → insert. If duplicate → skip.
        4. Create ScanArticle link (is_new flag).

        Args:
            target_id: The target UUID.
            scan_id: The scan UUID.
            articles_data: List of article dicts from the agent.

        Returns:
            Tuple of (new_articles_count, total_linked_count).
        """
        new_count = 0
        total_linked = 0

        for data in articles_data:
            if not data:
                continue

            original_url = data.get("url", "")
            if not original_url:
                continue

            norm_url = normalize_url(original_url)

            existing_result = await self.db.execute(
                select(Article).where(
                    Article.target_id == target_id,
                    Article.normalized_url == norm_url,
                )
            )
            existing = existing_result.scalar_one_or_none()

            is_new = False
            if existing:
                article = existing
            else:
                pub_date = None
                pd_str = data.get("published_date")
                if pd_str:
                    try:
                        pub_date = datetime.strptime(str(pd_str)[:10], "%Y-%m-%d").date()
                    except (ValueError, TypeError):
                        pass

                sentiment_str = (data.get("sentiment") or "neutral").lower()
                if "positive" in sentiment_str:
                    sentiment = SentimentType.positive
                elif "negative" in sentiment_str:
                    sentiment = SentimentType.negative
                else:
                    sentiment = SentimentType.neutral

                sec_str = (data.get("security_severity") or "none").lower()
                try:
                    security_sev = SecuritySeverity(sec_str)
                except ValueError:
                    security_sev = SecuritySeverity.none

                article = Article(
                    target_id=target_id,
                    original_url=original_url,
                    normalized_url=norm_url,
                    title=data.get("title"),
                    source_name=data.get("source_name"),
                    source_type=data.get("source_type"),
                    platform=data.get("platform", "web"),
                    author=data.get("author"),
                    published_date=pub_date,
                    summary=data.get("summary"),
                    what_others_say=data.get("what_others_say"),
                    target_perspective=data.get("target_perspective"),
                    key_quotes=data.get("key_quotes", []),
                    snippet_content=data.get("snippet_content"),
                    sentiment=sentiment,
                    sentiment_reasoning=data.get("sentiment_reasoning"),
                    headline_vs_body=data.get("headline_vs_body"),
                    risk_flags=data.get("risk_flags", ["none"]),
                    risk_details=data.get("risk_details"),
                    security_severity=security_sev,
                    security_details=data.get("security_details"),
                    security_keywords=data.get("security_keywords", []),
                    content_completeness=data.get("content_completeness"),
                )
                self.db.add(article)
                await self.db.flush()
                is_new = True
                new_count += 1

            scan_article = ScanArticle(
                scan_id=scan_id,
                article_id=article.id,
                is_new=is_new,
            )
            self.db.add(scan_article)
            total_linked += 1

        await self.db.commit()

        logger.info(
            f"Articles saved: {new_count} new, {total_linked} total linked for scan {scan_id}",
            extra={
                "action": "articles_saved",
                "scan_id": str(scan_id),
                "new_count": new_count,
                "total_linked": total_linked,
            },
        )
        return new_count, total_linked

    async def complete_scan(
        self,
        scan_id: UUID,
        report: dict,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        new_articles: int = 0,
    ) -> Scan:
        """
        Mark a scan as completed and store the summary report.

        Args:
            scan_id: The scan UUID.
            report: Aggregated report dict from the agent.
            input_tokens: LLM input tokens used.
            output_tokens: LLM output tokens used.
            cost_usd: Estimated USD cost.
            new_articles: Number of newly discovered articles.

        Returns:
            The updated Scan object.
        """
        scan = await self.get_scan_by_id(scan_id)

        sentiment = report.get("sentiment_summary", {})
        scan.status = ScanStatus.completed
        scan.completed_at = datetime.now(timezone.utc)
        scan.processing_time_sec = report.get("query", {}).get("processing_time_seconds", 0)
        scan.total_results = report.get("total_results", 0)
        scan.new_articles_found = new_articles
        scan.positive_count = sentiment.get("positive", 0)
        scan.negative_count = sentiment.get("negative", 0)
        scan.neutral_count = sentiment.get("neutral", 0)
        scan.positive_pct = sentiment.get("positive_pct", 0.0)
        scan.negative_pct = sentiment.get("negative_pct", 0.0)
        scan.neutral_pct = sentiment.get("neutral_pct", 0.0)
        scan.overall_sentiment = report.get("overall_sentiment")
        scan.risk_summary = report.get("risk_summary", [])
        scan.security_alerts = report.get("security_alerts", [])
        scan.platform_breakdown = report.get("source_breakdown", {}).get("by_platform", {})
        scan.input_tokens = input_tokens
        scan.output_tokens = output_tokens
        scan.cost_usd = cost_usd

        if scan.scan_type == ScanType.scheduled and scan.is_schedule_active:
            if scan.schedule_interval:
                delta = _parse_interval_to_timedelta(scan.schedule_interval)
                scan.next_run_at = datetime.now(timezone.utc) + delta

        await self.db.commit()
        await self.db.refresh(scan)

        logger.info(
            f"Scan completed: {scan_id} — {scan.total_results} results",
            extra={
                "action": "scan_complete",
                "scan_id": str(scan_id),
                "duration": scan.processing_time_sec,
            },
        )
        return scan

    async def fail_scan(self, scan_id: UUID, error_message: str) -> Scan:
        """
        Mark a scan as failed with an error message.

        Args:
            scan_id: The scan UUID.
            error_message: Description of the failure.

        Returns:
            The updated Scan object.
        """
        scan = await self.get_scan_by_id(scan_id)
        scan.status = ScanStatus.failed
        scan.completed_at = datetime.now(timezone.utc)
        scan.error_message = error_message[:2000]
        scan.retry_count += 1

        if scan.scan_type == ScanType.scheduled and scan.is_schedule_active:
            if scan.schedule_interval:
                delta = _parse_interval_to_timedelta(scan.schedule_interval)
                scan.next_run_at = datetime.now(timezone.utc) + delta

        await self.db.commit()
        await self.db.refresh(scan)

        logger.error(
            f"Scan failed: {scan_id} — {error_message[:200]}",
            extra={"action": "scan_fail", "scan_id": str(scan_id)},
        )
        return scan

    async def get_articles_for_target(
        self,
        target_id: UUID,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        sentiment: Optional[str] = None,
        platform: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Article], int]:
        """
        Get all articles for a target from the database.

        Args:
            target_id: The target UUID.
            from_date: Optional start date filter.
            to_date: Optional end date filter.
            sentiment: Optional sentiment filter.
            platform: Optional platform filter.
            limit: Pagination limit.
            offset: Pagination offset.

        Returns:
            Tuple of (list of Article objects, total count).
        """
        conditions = [Article.target_id == target_id]

        if from_date:
            conditions.append(
                or_(
                    Article.published_date >= from_date.date(),
                    Article.scraped_at >= from_date,
                )
            )
        if to_date:
            conditions.append(
                or_(
                    Article.published_date <= to_date.date(),
                    Article.scraped_at <= to_date,
                )
            )
        if sentiment:
            try:
                sent_enum = SentimentType(sentiment.lower())
                conditions.append(Article.sentiment == sent_enum)
            except ValueError:
                pass
        if platform:
            conditions.append(Article.platform == platform.lower())

        query = (
            select(Article)
            .where(and_(*conditions))
            .order_by(Article.scraped_at.desc())
            .limit(limit).offset(offset)
        )
        count_query = select(func.count(Article.id)).where(and_(*conditions))

        result = await self.db.execute(query)
        articles = list(result.scalars().all())

        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        return articles, total

    async def get_articles_for_scan(
        self,
        scan_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Article], int, int]:
        """
        Get all articles linked to a specific scan.

        Args:
            scan_id: The scan UUID.
            limit: Pagination limit.
            offset: Pagination offset.

        Returns:
            Tuple of (list of Article objects, total count, new articles count).
        """
        query = (
            select(Article)
            .join(ScanArticle, ScanArticle.article_id == Article.id)
            .where(ScanArticle.scan_id == scan_id)
            .order_by(Article.scraped_at.desc())
            .limit(limit).offset(offset)
        )
        count_query = (
            select(func.count(Article.id))
            .join(ScanArticle, ScanArticle.article_id == Article.id)
            .where(ScanArticle.scan_id == scan_id)
        )
        new_count_query = (
            select(func.count(ScanArticle.id))
            .where(ScanArticle.scan_id == scan_id, ScanArticle.is_new == True)
        )

        result = await self.db.execute(query)
        articles = list(result.scalars().all())

        count_result = await self.db.execute(count_query)
        total = count_result.scalar() or 0

        new_result = await self.db.execute(new_count_query)
        new_count = new_result.scalar() or 0

        return articles, total, new_count

    async def get_due_scheduled_scans(self) -> list[Scan]:
        """Get all scheduled scans that are due for execution."""
        result = await self.db.execute(
            select(Scan)
            .options(selectinload(Scan.target))
            .where(
                Scan.scan_type == ScanType.scheduled,
                Scan.is_schedule_active == True,
                Scan.next_run_at <= datetime.now(timezone.utc),
            )
            .order_by(Scan.next_run_at.asc())
        )
        return list(result.scalars().all())

    async def get_all_active_schedules(self) -> list[Scan]:
        """Get all active scheduled scans (for scheduler reload on startup)."""
        result = await self.db.execute(
            select(Scan)
            .options(selectinload(Scan.target))
            .where(
                Scan.scan_type == ScanType.scheduled,
                Scan.is_schedule_active == True,
            )
        )
        return list(result.scalars().all())
