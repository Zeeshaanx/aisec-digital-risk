"""
Agent utility functions.

Shared helpers for URL classification, content relevance checking,
security detection, date parsing, platform detection, and JSON extraction.
"""

import re
import json
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse
from typing import Optional

from app.agents.constants import (
    SECURITY_KEYWORDS, PLATFORM_DOMAIN_MAP,
    SCRAPABLE_SOCIAL_DOMAINS, NON_SCRAPABLE_SOCIAL_DOMAINS,
    PROFILE_URL_PATTERNS, SOCIAL_POST_PATTERNS,
    FAN_PAGE_PATTERNS, RESHARE_SOURCE_PATTERNS,
)

logger = logging.getLogger("media_intel.agents.utils")


# ═══════════════════════════════════════════════════════
# DATE / TIMEFRAME
# ═══════════════════════════════════════════════════════

def parse_timeframe_to_cutoff(timeframe: str) -> datetime:
    """Convert timeframe string like '24 hours', '1 week' to a cutoff datetime."""
    now = datetime.now()
    tf = timeframe.lower().strip()
    match = re.match(r"(\d+)\s*(hour|hours|day|days|week|weeks|month|months|year|years)", tf)
    if match:
        num = int(match.group(1))
        unit = match.group(2).rstrip("s")
        deltas = {
            "hour": timedelta(hours=num), "day": timedelta(days=num),
            "week": timedelta(weeks=num), "month": timedelta(days=num * 30),
            "year": timedelta(days=num * 365),
        }
        return now - deltas.get(unit, timedelta(hours=24))
    try:
        hours = int(re.search(r"\d+", tf).group())
        return now - timedelta(hours=hours)
    except Exception:
        return now - timedelta(hours=24)


def get_date_filter_str(timeframe: str) -> str:
    """Generate 'after:YYYY-MM-DD' for search queries."""
    cutoff = parse_timeframe_to_cutoff(timeframe)
    return f"after:{cutoff.strftime('%Y-%m-%d')}"


def get_timeframe_description(timeframe: str) -> str:
    """Human-readable date range for prompts."""
    cutoff = parse_timeframe_to_cutoff(timeframe)
    now = datetime.now()
    return f"from {cutoff.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}"


def is_within_timeframe(published_date_str, cutoff_date) -> bool:
    """Check if a published date falls within the allowed timeframe."""
    if not published_date_str:
        return True
    try:
        pd = datetime.strptime(str(published_date_str)[:10], "%Y-%m-%d")
        cutoff_day = cutoff_date.replace(hour=0, minute=0, second=0, microsecond=0)
        return pd >= cutoff_day
    except (ValueError, TypeError):
        return True


# ═══════════════════════════════════════════════════════
# URL CLASSIFICATION
# ═══════════════════════════════════════════════════════

def get_domain(url: str) -> str:
    """Extract and clean the domain from a URL."""
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def detect_platform_from_url(url: str) -> str:
    """Detect platform from URL. Never returns 'unknown', defaults to 'web'."""
    if not url:
        return "web"
    domain = get_domain(url)
    for pattern, platform in PLATFORM_DOMAIN_MAP.items():
        if pattern in domain:
            return platform
    return "web"


def is_non_scrapable_social(url: str) -> bool:
    """Check if URL is from a non-scrapable social platform."""
    domain = get_domain(url)
    return any(d in domain for d in NON_SCRAPABLE_SOCIAL_DOMAINS)


def is_social_post(url: str) -> bool:
    """Check if URL matches a social media post pattern."""
    return any(re.search(p, url, re.IGNORECASE) for p in SOCIAL_POST_PATTERNS)


def is_profile_or_aggregator(url: str) -> bool:
    """Check if URL matches a profile or aggregator page pattern."""
    return any(re.search(p, url, re.IGNORECASE) for p in PROFILE_URL_PATTERNS)


def classify_url(url: str) -> tuple[str, str]:
    """
    Classify a URL into categories for processing.

    Returns:
        Tuple of (classification, reason).
        Classification: 'scrape', 'snippet', 'profile', 'skip'.
    """
    if not url or not url.startswith("http"):
        return "skip", "Invalid URL"
    if is_social_post(url):
        if is_non_scrapable_social(url):
            return "snippet", "Social post (non-scrapable)"
        return "scrape", "Social post (scrapable)"
    if is_profile_or_aggregator(url):
        return "profile", "Profile or aggregator"
    if is_non_scrapable_social(url):
        return "snippet", "Non-scrapable social"
    return "scrape", "Scrapable URL"


# ═══════════════════════════════════════════════════════
# CONTENT RELEVANCE
# ═══════════════════════════════════════════════════════

def is_fan_page_content(title: str, snippet: str, source_name: str,
                        author: str, url: str) -> bool:
    """Detect if content is from a fan page / reshare."""
    combined_meta = f"{source_name or ''} {author or ''}".lower()
    for pat in FAN_PAGE_PATTERNS:
        if re.search(pat, combined_meta, re.IGNORECASE):
            return True
    for pat in RESHARE_SOURCE_PATTERNS:
        if re.search(pat, combined_meta, re.IGNORECASE):
            return True
    if "▻" in (source_name or "") or "▻" in (author or "") or "▻" in (snippet or ""):
        return True
    url_lower = (url or "").lower()
    for pat in [r"facebook\.com/groups/", r"facebook\.com/.*fans"]:
        if re.search(pat, url_lower):
            return True
    return False


def check_content_relevance(target: str, title: str, snippet: str,
                            source_name: str = "", author: str = "",
                            full_content: str = "") -> dict:
    """
    Verify content actually discusses the target directly.

    Returns:
        Dict with 'relevant' (bool), 'confidence', 'reason', 'is_fan_page'.
    """
    target_lower = target.lower().strip()
    target_parts = [p.strip() for p in target_lower.split() if len(p.strip()) > 2]

    fan_page = is_fan_page_content(title, snippet, source_name, author, "")

    title_lower = (title or "").lower()
    title_has_target = target_lower in title_lower
    if not title_has_target and len(target_parts) > 1:
        title_has_target = all(part in title_lower for part in target_parts)

    body_text = (snippet or "").lower()
    if full_content:
        body_text = full_content.lower()
    body_has_target = target_lower in body_text
    if not body_has_target and len(target_parts) > 1:
        body_has_target = all(part in body_text for part in target_parts)

    meta_text = f"{source_name or ''} {author or ''}".lower()
    meta_mentions = meta_text.count(target_lower)
    body_mentions = body_text.count(target_lower)

    if fan_page and not body_has_target:
        return {"relevant": False, "confidence": "high",
                "reason": "Fan page with no target mention in content", "is_fan_page": True}
    if fan_page and body_has_target and body_mentions <= meta_mentions:
        return {"relevant": False, "confidence": "medium",
                "reason": f"Fan page — target {body_mentions}x in body vs {meta_mentions}x in metadata",
                "is_fan_page": True}
    if not title_has_target and not body_has_target:
        return {"relevant": False, "confidence": "high",
                "reason": "Target not in title or body", "is_fan_page": fan_page}
    if title_has_target and not body_has_target and not full_content:
        return {"relevant": True, "confidence": "low",
                "reason": "Target in title only", "is_fan_page": fan_page}
    if body_has_target:
        conf = "high" if body_mentions >= 2 else "medium"
        return {"relevant": True, "confidence": conf,
                "reason": f"Target mentioned {body_mentions}x in body", "is_fan_page": fan_page}
    return {"relevant": True, "confidence": "low",
            "reason": "Could not verify", "is_fan_page": fan_page}


# ═══════════════════════════════════════════════════════
# SECURITY DETECTION
# ═══════════════════════════════════════════════════════

def detect_security_severity(text: str) -> tuple[Optional[str], list[str]]:
    """Scan text for security keywords with word boundary matching."""
    if not text:
        return None, []
    text_lower = text.lower()
    all_matches = {}

    for severity in ["critical", "high", "medium", "low"]:
        for kw in SECURITY_KEYWORDS[severity]:
            kw_lower = kw.lower()

            # Use word boundary matching to avoid false positives
            # e.g., "0-day" should not match "30-day" or "90-day"
            pattern = r'(?<!\w)' + re.escape(kw_lower) + r'(?!\w)'

            if re.search(pattern, text_lower):
                if severity not in all_matches:
                    all_matches[severity] = []
                all_matches[severity].append(kw)

    if not all_matches:
        return None, []

    for sev in ["critical", "high", "medium", "low"]:
        if sev in all_matches:
            all_kws = []
            for s in all_matches:
                all_kws.extend(all_matches[s])
            return sev, list(set(all_kws))

    return None, []

# ═══════════════════════════════════════════════════════
# CONTENT HELPERS
# ═══════════════════════════════════════════════════════

def smart_truncate(text: str, max_chars: int = 12000) -> str:
    """Truncate long content keeping beginning and end for context."""
    if not text or len(text) <= max_chars:
        return text
    start_chars = int(max_chars * 0.6)
    end_chars = max_chars - start_chars - 100
    return (
        text[:start_chars].rstrip()
        + "\n\n[... CONTENT TRUNCATED ...]\n\n"
        + text[-end_chars:].lstrip()
    )


def extract_json(text: str) -> Optional[dict | list]:
    """Extract JSON from LLM output, handling markdown code blocks."""
    if not text or not text.strip():
        return None
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", cleaned)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    m = re.search(r"$$[\s\S]*$$", cleaned)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None


def clean_analysis_result(result: dict) -> Optional[dict]:
    """Clean and normalize an LLM analysis result dict."""
    if not result or not isinstance(result, dict):
        return None
    if result.get("skipped"):
        return None
    cleaned = {}
    text_fields = [
        "title", "url", "source_name", "source_type", "platform",
        "published_date", "author", "summary", "what_others_say",
        "target_perspective", "sentiment", "sentiment_reasoning",
        "headline_vs_body", "risk_details", "content_completeness",
        "snippet_content", "security_severity", "security_details",
    ]
    for key in text_fields:
        val = result.get(key)
        if val is not None and not isinstance(val, str):
            cleaned[key] = str(val)
        else:
            cleaned[key] = val

    # Normalize sentiment
    sentiment = (cleaned.get("sentiment") or "neutral").lower().strip()
    if "positive" in sentiment:
        cleaned["sentiment"] = "positive"
    elif "negative" in sentiment:
        cleaned["sentiment"] = "negative"
    else:
        cleaned["sentiment"] = "neutral"

    # Normalize lists
    def safe_list(val):
        if not val:
            return []
        if isinstance(val, str):
            return [val]
        if isinstance(val, list):
            return [str(item) if not isinstance(item, str) else item for item in val]
        return [str(val)]

    cleaned["key_quotes"] = safe_list(result.get("key_quotes"))
    cleaned["risk_flags"] = safe_list(result.get("risk_flags")) or ["none"]
    cleaned["security_keywords"] = safe_list(result.get("security_keywords"))

    if not cleaned.get("platform"):
        cleaned["platform"] = "web"

    sec_sev = (cleaned.get("security_severity") or "none").lower().strip()
    if sec_sev not in ("critical", "high", "medium", "low", "none"):
        sec_sev = "none"
    cleaned["security_severity"] = sec_sev

    if not cleaned.get("title"):
        cleaned["title"] = (cleaned.get("url") or "Untitled")[:80]

    return cleaned


def filter_and_classify(articles: list, target_name: str = None) -> tuple[list, list]:
    """Filter and classify articles into scrapable and snippet-based."""
    scrapable = []
    snippet_based = []
    for article in articles:
        url = article.get("url", "")
        cls, reason = classify_url(url)
        if cls in ("skip", "profile"):
            continue
        if target_name:
            relevance = check_content_relevance(
                target=target_name,
                title=article.get("title", ""),
                snippet=article.get("snippet", ""),
                source_name=article.get("source_name", ""),
                author=article.get("author", ""),
            )
            if not relevance["relevant"] and relevance["confidence"] in ("high", "medium"):
                continue
        if cls == "scrape":
            scrapable.append(article)
        elif cls == "snippet":
            snippet_based.append(article)
    return scrapable, snippet_based
