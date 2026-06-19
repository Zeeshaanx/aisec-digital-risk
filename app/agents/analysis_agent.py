"""
Analysis Agent — LLM-powered content analysis.

Performs sentiment analysis, security threat detection, and risk assessment
from the target's perspective. Uses GPT-4o-mini for cost efficiency.
"""

import logging
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import get_settings
from app.agents.utils import (
    extract_json, clean_analysis_result, detect_security_severity,
    detect_platform_from_url, check_content_relevance,
    is_within_timeframe, get_timeframe_description,
)
from app.agents.constants import (
    SCRAPE_ANALYSIS_SYSTEM, SCRAPE_ANALYSIS_USER,
    SNIPPET_ANALYSIS_SYSTEM, SNIPPET_ANALYSIS_USER,
)

logger = logging.getLogger("media_intel.agents.analysis")


class AnalysisAgent:
    """
    LLM-powered content analysis from the target's perspective.

    Performs:
    - Sentiment analysis (positive/negative/neutral for the target).
    - Security threat detection (severity + keywords).
    - Risk flag assignment.
    - Content relevance verification.

    Tracks token usage and cost per analysis call.
    """

    def __init__(self):
        self.settings = get_settings()
        self.model = ChatOpenAI(
            model=self.settings.LLM_MODEL,
            temperature=0,
            openai_api_key=self.settings.OPENAI_API_KEY,
        )
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0

    def _track_cost(self, response) -> None:
        """Track token usage and cost from an LLM response."""
        if hasattr(response, "response_metadata"):
            usage = response.response_metadata.get("token_usage", {})
            i = usage.get("prompt_tokens", 0)
            o = usage.get("completion_tokens", 0)
            cost = (
                (i / 1000) * self.settings.INPUT_COST_PER_1K
                + (o / 1000) * self.settings.OUTPUT_COST_PER_1K
            )
            self.total_input_tokens += i
            self.total_output_tokens += o
            self.total_cost += cost

    async def _invoke_with_retry(self, messages: list, max_retries: int = 2) -> Optional[dict]:
        """Invoke LLM with JSON extraction and retry logic."""
        for attempt in range(max_retries):
            try:
                response = await self.model.ainvoke(messages)
                self._track_cost(response)
                text = response.content if hasattr(response, "content") else ""
                result = extract_json(text)
                if result is not None:
                    return result
                if attempt < max_retries - 1:
                    messages = [
                        SystemMessage(content="Return ONLY raw valid JSON. No markdown."),
                        HumanMessage(content="Fix:\n" + text[:3000]),
                    ]
            except Exception as e:
                logger.warning(f"LLM invoke error (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    return None
        return None

    async def analyze_article(
        self,
        target: str,
        url: str,
        title: str,
        content: str,
        timeframe: str,
        cutoff_date=None,
    ) -> Optional[dict]:
        """
        Analyze a fully scraped article.

        Args:
            target: Target name.
            url: Article URL.
            title: Article title.
            content: Full article content (already truncated).
            timeframe: Scan timeframe string.
            cutoff_date: Datetime cutoff for date validation.

        Returns:
            Cleaned analysis dict, or None if skipped/failed.
        """
        timeframe_desc = get_timeframe_description(timeframe)

        # Pre-scan for security issues
        security_sev, security_kws = detect_security_severity(content)
        if security_sev and security_sev in ("critical", "high"):
            logger.info(f"Security [{security_sev.upper()}] detected in {url[:60]}: {security_kws[:3]}")

        messages = [
            SystemMessage(content=SCRAPE_ANALYSIS_SYSTEM),
            HumanMessage(content=SCRAPE_ANALYSIS_USER.format(
                target=target, title=title, url=url,
                timeframe_desc=timeframe_desc, content=content,
            )),
        ]
        result = await self._invoke_with_retry(messages)

        if isinstance(result, dict):
            if result.get("skipped"):
                return None

            # Date check
            pub_date = result.get("published_date")
            if pub_date and cutoff_date and not is_within_timeframe(pub_date, cutoff_date):
                return None

            cleaned = clean_analysis_result(result)
            if cleaned:
                if not cleaned.get("url"):
                    cleaned["url"] = url
                if not cleaned.get("title"):
                    cleaned["title"] = title

                # Merge keyword-based security detection
                if security_sev:
                    existing = cleaned.get("security_severity", "none")
                    if existing == "none":
                        cleaned["security_severity"] = security_sev
                    cleaned["security_keywords"] = security_kws

                return cleaned
        return None

    async def analyze_snippet(
        self,
        target: str,
        url: str,
        title: str,
        snippet: str,
        timeframe: str,
        cutoff_date=None,
    ) -> Optional[dict]:
        """
        Analyze a social media snippet (non-scrapable content).

        Args:
            target: Target name.
            url: Post URL.
            title: Post title.
            snippet: Search snippet text.
            timeframe: Scan timeframe string.
            cutoff_date: Datetime cutoff for date validation.

        Returns:
            Cleaned analysis dict, or None if skipped/failed.
        """
        platform = detect_platform_from_url(url)
        timeframe_desc = get_timeframe_description(timeframe)

        if not snippet or len(snippet.strip()) < 15:
            if title and len(title) >= 20:
                snippet = title
            else:
                return None

        # Relevance check
        relevance = check_content_relevance(
            target=target, title=title, snippet=snippet,
        )
        if not relevance["relevant"] and relevance["confidence"] in ("high", "medium"):
            return None

        # Pre-scan for security
        security_sev, security_kws = detect_security_severity(f"{title} {snippet}")

        messages = [
            SystemMessage(content=SNIPPET_ANALYSIS_SYSTEM),
            HumanMessage(content=SNIPPET_ANALYSIS_USER.format(
                target=target, platform=platform, title=title,
                url=url, snippet=snippet, timeframe_desc=timeframe_desc,
            )),
        ]
        result = await self._invoke_with_retry(messages)

        if isinstance(result, dict):
            if result.get("skipped"):
                return None

            cleaned = clean_analysis_result(result)
            if cleaned:
                if not cleaned.get("url"):
                    cleaned["url"] = url
                if not cleaned.get("title"):
                    cleaned["title"] = title
                if not cleaned.get("platform"):
                    cleaned["platform"] = platform
                if not cleaned.get("snippet_content"):
                    cleaned["snippet_content"] = snippet

                # Date check
                pub_date = cleaned.get("published_date")
                if pub_date and cutoff_date and not is_within_timeframe(pub_date, cutoff_date):
                    return None

                # Merge security detection
                if security_sev:
                    existing = cleaned.get("security_severity", "none")
                    if existing == "none":
                        cleaned["security_severity"] = security_sev
                    cleaned["security_keywords"] = security_kws

                return cleaned
        return None

    def get_usage(self) -> dict:
        """Return token usage and cost summary."""
        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "cost_usd": self.total_cost,
        }

    def reset_usage(self) -> None:
        """Reset token/cost counters."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
