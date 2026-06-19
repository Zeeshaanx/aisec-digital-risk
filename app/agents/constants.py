"""
Agent constants — search queries, keyword lists, URL patterns, and prompts.

Centralized here to keep agent modules focused on logic.
"""

# ═══════════════════════════════════════════════════════
# SECURITY KEYWORDS — severity-classified
# ═══════════════════════════════════════════════════════

SECURITY_KEYWORDS = {
    "critical": [
        "data breach confirmed", "zero-day", "0-day", "0day",
        "ransomware attack", "remote code execution", "rce exploit",
        "critical vulnerability exploited", "actively exploited",
        "emergency patch", "credentials leaked", "database exposed",
        "customer data leaked", "supply chain attack", "backdoor discovered",
        "authentication bypass", "mass data exposure", "ssn leaked",
        "credit card data", "payment data breach", "full database dump",
    ],
    "high": [
        "data breach", "hacked", "cyberattack", "cyber attack",
        "malware detected", "exploit discovered", "unauthorized access",
        "security incident", "data leak", "data exposure",
        "privilege escalation", "sql injection", "xss vulnerability",
        "api key leaked", "source code leaked", "sensitive data exposed",
        "security breach", "system compromised", "phishing campaign",
        "credential stuffing", "brute force attack", "account takeover",
        "personally identifiable", "pii exposed", "hipaa violation",
    ],
    "medium": [
        "vulnerability disclosed", "security flaw", "bug bounty",
        "security patch", "security update", "security advisory",
        "cve-", "phishing attempt", "ddos", "denial of service",
        "security vulnerability", "cross-site scripting",
        "insecure configuration", "exposed endpoint", "open port",
        "information disclosure", "misconfiguration", "unpatched",
        "security warning", "suspicious activity",
    ],
    "low": [
        "security research", "responsible disclosure", "penetration test",
        "security audit", "compliance issue", "security review",
        "security assessment", "code review finding", "best practice",
        "security recommendation",
    ],
}

# ═══════════════════════════════════════════════════════
# PLATFORM DETECTION
# ═══════════════════════════════════════════════════════

PLATFORM_DOMAIN_MAP = {
    "twitter.com": "twitter", "x.com": "twitter",
    "reddit.com": "reddit", "instagram.com": "instagram",
    "tiktok.com": "tiktok", "facebook.com": "facebook",
    "fb.com": "facebook", "youtube.com": "youtube",
    "youtu.be": "youtube", "linkedin.com": "linkedin",
    "threads.net": "threads", "medium.com": "medium",
    "quora.com": "quora", "tumblr.com": "tumblr",
    "substack.com": "substack", "pinterest.com": "pinterest",
    "snapchat.com": "snapchat", "bsky.app": "bluesky",
    "mastodon.social": "mastodon",
}

SCRAPABLE_SOCIAL_DOMAINS = [
    "reddit.com", "youtube.com", "medium.com",
    "quora.com", "tumblr.com", "substack.com",
]

NON_SCRAPABLE_SOCIAL_DOMAINS = [
    "twitter.com", "x.com", "instagram.com", "tiktok.com",
    "facebook.com", "linkedin.com", "threads.net",
    "snapchat.com", "pinterest.com",
]

PROFILE_URL_PATTERNS = [
    r"espn\.com/.*/player/", r"foxsports\.com/.+\-player",
    r"transfermarkt\..*/spieler/", r"fbref\.com/.*players/",
    r"soccerway\.com/players/", r"whoscored\.com/Players/",
    r"newsnow\.com/", r"google\.com/search", r"news\.google\.com",
    r"/player-profile/", r"/players?/[^/]+/?$", r"/profile/[^/]+/?$",
    r"/bio/", r"/about/", r"wikipedia\.org/wiki/",
    r"/category/[^/]+/?$", r"/tag/[^/]+/?$", r"/topic/[^/]+/?$",
    r"twitter\.com/[^/]+/?$", r"x\.com/[^/]+/?$",
    r"instagram\.com/[^/]+/?$", r"facebook\.com/[^/]+/?$",
    r"tiktok\.com/@[^/]+/?$", r"linkedin\.com/in/[^/]+/?$",
    r"linkedin\.com/company/[^/]+/?$",
    r"youtube\.com/channel/", r"youtube\.com/@",
    r"youtube\.com/c/", r"youtube\.com/user/",
    r"reddit\.com/r/[^/]+/?$", r"reddit\.com/user/[^/]+/?$",
]

SOCIAL_POST_PATTERNS = [
    r"twitter\.com/.+/status/\d+", r"x\.com/.+/status/\d+",
    r"instagram\.com/p/", r"instagram\.com/reel/",
    r"tiktok\.com/.*/video/\d+",
    r"facebook\.com/.*/posts/", r"facebook\.com/.*permalink",
    r"linkedin\.com/.*/posts/",
    r"reddit\.com/r/.*/comments/",
    r"youtube\.com/watch\?v=",
    r"threads\.net/.*/post/",
]

FAN_PAGE_PATTERNS = [
    r"fans?\s*[-–—]\s*", r"fan\s*page", r"fan\s*club",
    r"fan\s*group", r"supporters?\s*club", r"supporters?\s*group",
    r"▻\s*\w+",
    r"shared\s+(a\s+)?(post|link|photo|video)\s+(in|to|from)",
    r"shared\s+to\s+", r"posted\s+in\s+", r"wrote\s+in\s+.*group",
]

RESHARE_SOURCE_PATTERNS = [
    r"\(shared\s+(in|by|from|to)\s+", r"▻",
    r"via\s+.+fans", r"repost(ed)?\s+(from|by)",
]

# ═══════════════════════════════════════════════════════
# SEARCH QUERY TEMPLATES
# ═══════════════════════════════════════════════════════

NEWS_SEARCH_QUERIES = {
    "quick": [
        '"{target}" news {timeframe} {date_filter}',
        '"{target}" latest report {date_filter}',
    ],
    "standard": [
        '"{target}" news {timeframe} {date_filter}',
        '"{target}" latest report article {date_filter}',
        '"{target}" opinion analysis editorial {date_filter}',
        '"{target}" interview statement {date_filter}',
        '"{target}" controversy criticism {date_filter}',
        '"{target}" announcement update {date_filter}',
    ],
    "thorough": [
        '"{target}" news {timeframe} {date_filter}',
        '"{target}" latest report article {date_filter}',
        '"{target}" opinion analysis editorial {date_filter}',
        '"{target}" interview statement reaction {date_filter}',
        '"{target}" controversy criticism backlash {date_filter}',
        '"{target}" announcement update breaking {date_filter}',
        '"{target}" praised celebrated achievement {date_filter}',
        '"{target}" investigation lawsuit legal {date_filter}',
        '"{target}" financial earnings revenue {date_filter}',
        '"{target}" review evaluation assessment {date_filter}',
        '"{target}" rumor speculation {date_filter}',
        '"{target}" partnership collaboration deal {date_filter}',
    ],
    "exhaustive": [
        '"{target}" news {timeframe} {date_filter}',
        '"{target}" latest report article {date_filter}',
        '"{target}" opinion analysis editorial {date_filter}',
        '"{target}" interview statement reaction {date_filter}',
        '"{target}" controversy criticism backlash {date_filter}',
        '"{target}" announcement update breaking {date_filter}',
        '"{target}" praised celebrated achievement success {date_filter}',
        '"{target}" investigation lawsuit legal court {date_filter}',
        '"{target}" financial earnings revenue profit loss {date_filter}',
        '"{target}" review evaluation assessment {date_filter}',
        '"{target}" rumor speculation transfer {date_filter}',
        '"{target}" partnership collaboration deal agreement {date_filter}',
        '"{target}" scandal leaked exposed {date_filter}',
        '"{target}" fans supporters reaction {date_filter}',
        '"{target}" press conference comments {date_filter}',
        '"{target}" future plans strategy {date_filter}',
        '"{target}" compared vs versus rivalry {date_filter}',
        '"{target}" award honor recognition {date_filter}',
    ],
}

SOCIAL_SEARCH_QUERIES = {
    "quick": [
        '"{target}" site:reddit.com {date_filter}',
        '"{target}" site:twitter.com OR site:x.com {date_filter}',
    ],
    "standard": [
        '"{target}" site:reddit.com {date_filter}',
        '"{target}" site:twitter.com OR site:x.com {date_filter}',
        '"{target}" site:youtube.com {date_filter}',
        '"{target}" site:instagram.com {date_filter}',
        '"{target}" site:tiktok.com {date_filter}',
    ],
    "thorough": [
        '"{target}" site:reddit.com discussion {date_filter}',
        '"{target}" site:reddit.com opinion {date_filter}',
        '"{target}" site:twitter.com OR site:x.com {date_filter}',
        '"{target}" site:twitter.com reaction {date_filter}',
        '"{target}" site:youtube.com {date_filter}',
        '"{target}" site:instagram.com {date_filter}',
        '"{target}" site:tiktok.com {date_filter}',
        '"{target}" site:facebook.com {date_filter}',
        '"{target}" site:linkedin.com {date_filter}',
        '"{target}" fans react discuss forum {date_filter}',
    ],
    "exhaustive": [
        '"{target}" site:reddit.com discussion {date_filter}',
        '"{target}" site:reddit.com opinion {date_filter}',
        '"{target}" site:reddit.com news {date_filter}',
        '"{target}" site:twitter.com OR site:x.com {date_filter}',
        '"{target}" site:twitter.com reaction opinion {date_filter}',
        '"{target}" site:twitter.com controversy {date_filter}',
        '"{target}" site:youtube.com review {date_filter}',
        '"{target}" site:youtube.com analysis {date_filter}',
        '"{target}" site:youtube.com reaction {date_filter}',
        '"{target}" site:instagram.com {date_filter}',
        '"{target}" site:tiktok.com {date_filter}',
        '"{target}" site:tiktok.com viral {date_filter}',
        '"{target}" site:facebook.com {date_filter}',
        '"{target}" site:facebook.com group {date_filter}',
        '"{target}" site:linkedin.com {date_filter}',
        '"{target}" fans react discuss {date_filter}',
        '"{target}" forum discussion thread {date_filter}',
        '"{target}" site:medium.com {date_filter}',
        '"{target}" site:quora.com {date_filter}',
    ],
}

SECURITY_SEARCH_QUERIES = {
    "quick": [
        '"{target}" data breach {date_filter}',
        '"{target}" hack OR vulnerability {date_filter}',
    ],
    "standard": [
        '"{target}" data breach {date_filter}',
        '"{target}" hack OR hacked OR cyberattack {date_filter}',
        '"{target}" vulnerability OR CVE {date_filter}',
        '"{target}" security incident {date_filter}',
    ],
    "thorough": [
        '"{target}" data breach {date_filter}',
        '"{target}" hack OR hacked OR cyberattack {date_filter}',
        '"{target}" vulnerability OR CVE {date_filter}',
        '"{target}" security incident {date_filter}',
        '"{target}" data leak OR data exposure {date_filter}',
        '"{target}" ransomware OR malware {date_filter}',
        '"{target}" bug bounty OR responsible disclosure {date_filter}',
        '"{target}" phishing OR credential {date_filter}',
    ],
    "exhaustive": [
        '"{target}" data breach {date_filter}',
        '"{target}" hack OR hacked OR cyberattack {date_filter}',
        '"{target}" vulnerability OR CVE {date_filter}',
        '"{target}" security incident {date_filter}',
        '"{target}" data leak OR data exposure {date_filter}',
        '"{target}" ransomware OR malware {date_filter}',
        '"{target}" bug bounty OR responsible disclosure {date_filter}',
        '"{target}" phishing OR credential {date_filter}',
        '"{target}" zero-day OR 0day {date_filter}',
        '"{target}" exploit OR backdoor {date_filter}',
        '"{target}" source code leaked {date_filter}',
        '"{target}" unauthorized access {date_filter}',
        '"{target}" supply chain attack {date_filter}',
        '"{target}" privacy violation OR GDPR {date_filter}',
    ],
}


# ═══════════════════════════════════════════════════════
# LLM PROMPTS
# ═══════════════════════════════════════════════════════

SCRAPE_ANALYSIS_SYSTEM = """
You are a media intelligence and security analyst. You receive article CONTENT (already scraped)
and a TARGET name. Analyze FROM THE TARGET'S PERSPECTIVE.

!!!! IMPORTANT: The content has already been provided to you. Do NOT use any tools. !!!!
!!!! Do NOT call firecrawl_scrape or any other tool. Analyze the text below directly. !!!!

━━━ STEP 1: VERIFY CONTENT ━━━
Check the provided content:
- Single article/post? → Continue
- Profile/stats page? → Return {{"skipped": true, "reason": "profile_page"}}
- Feed/listing page? → Return {{"skipped": true, "reason": "aggregator_page"}}
- Empty or irrelevant? → Return {{"skipped": true, "reason": "irrelevant_content"}}

━━━ STEP 2: CONTENT RELEVANCE CHECK ━━━
!!!! CRITICAL: The content must DIRECTLY discuss the target !!!!

REJECT (return skipped) if:
- The content is FROM a fan page / fan group but does NOT contain original news or info
- The target is only mentioned in the page name but NOT in the article/post body
- The content is a reshare / repost with no substantive information

ACCEPT only if:
- The article/post body contains direct discussion of the target
- There are facts, quotes, opinions, or news specifically about the target

If not relevant → Return {{"skipped": true, "reason": "not_about_target"}}

━━━ STEP 3: DATE CHECK ━━━
If the article date is clearly OUTSIDE the specified time period:
→ Return {{"skipped": true, "reason": "outside_timeframe", "published_date": "YYYY-MM-DD"}}

━━━ STEP 4: TARGET-PERSPECTIVE SENTIMENT ━━━
Ask: "Is this content GOOD or BAD for the TARGET specifically?"
- Read ENTIRE provided content — not just headlines
- Most impact on target favorable → "positive"
- Most impact on target unfavorable → "negative"
- Mixed or purely factual → "neutral"

━━━ STEP 5: SECURITY & THREAT ANALYSIS ━━━
Check for: DATA BREACH, VULNERABILITY, CYBERATTACK, DATA LEAK,
UNAUTHORIZED ACCESS, PRIVACY VIOLATION, SUPPLY CHAIN issues.
Security severity: "critical" | "high" | "medium" | "low" | "none"

━━━ STEP 6: RISK FLAGS ━━━
"data_breach" | "security_risk" | "reputation_risk" | "legal_risk" |
"financial_risk" | "misinformation" | "privacy_risk" | "physical_threat" |
"competitive_risk" | "vulnerability_disclosed" | "cyberattack" |
"supply_chain_risk" | "compliance_risk" | "none"

━━━ OUTPUT — raw JSON only. NO tools. NO markdown. ━━━
{{
  "title": "", "url": "", "source_name": "", "source_type": "",
  "platform": "web", "published_date": "YYYY-MM-DD or null",
  "author": "or null",
  "summary": "3-5 sentences from the content",
  "key_quotes": ["quote1", "quote2"],
  "what_others_say": "What is said about the target",
  "target_perspective": "Impact on target specifically",
  "sentiment": "positive | negative | neutral",
  "sentiment_reasoning": "Why — from target's perspective",
  "headline_vs_body": "match | mismatch",
  "risk_flags": [],
  "risk_details": "",
  "security_severity": "critical | high | medium | low | none",
  "security_details": "Description of security issue if any"
}}
"""

SCRAPE_ANALYSIS_USER = """
TARGET: "{target}"
ARTICLE: "{title}"
URL: {url}
TIMEFRAME: Content must be from {timeframe_desc}

!!!! DO NOT use any tools. The article content is provided below. Analyze it directly. !!!!

━━━ ARTICLE CONTENT START ━━━
{content}
━━━ ARTICLE CONTENT END ━━━

1. Check if content body actually discusses "{target}"
2. Verify this is a real article (skip if profile/feed/outside timeframe)
3. Read ALL provided content
4. Sentiment FROM "{target}"'s PERSPECTIVE
5. Check for ANY security threats TO "{target}"
6. Risks TO "{target}"
7. Return ONLY raw JSON — NO tools, NO markdown
"""

SNIPPET_ANALYSIS_SYSTEM = """
You are a social media and security analyst. You receive a post that CANNOT be scraped.
You have the SEARCH SNIPPET with the post content.
Analyze FROM THE TARGET'S PERSPECTIVE.

!!!! CRITICAL: CONTENT RELEVANCE CHECK !!!!
Before analyzing, verify the snippet ACTUALLY discusses the target.
If the target only appears in a fan page name but not in the post → skip.

DO NOT use any tools. Analyze the snippet only.

RISK FLAGS: "data_breach" | "security_risk" | "reputation_risk" | "legal_risk" |
"financial_risk" | "misinformation" | "privacy_risk" | "physical_threat" |
"competitive_risk" | "vulnerability_disclosed" | "cyberattack" |
"supply_chain_risk" | "compliance_risk" | "none"

OUTPUT — raw JSON only:
{{
  "title": "", "url": "", "source_name": "",
  "source_type": "social_media_post",
  "platform": "twitter|reddit|instagram|tiktok|facebook|youtube|linkedin|web",
  "published_date": "or null", "author": "or null",
  "summary": "Summary of post",
  "snippet_content": "Original snippet",
  "what_others_say": "What's said about the target",
  "target_perspective": "Impact on the target",
  "sentiment": "positive | negative | neutral",
  "sentiment_reasoning": "Why from target's perspective",
  "risk_flags": [], "risk_details": "",
  "security_severity": "critical | high | medium | low | none",
  "security_details": "Description of security issue if any",
  "content_completeness": "full | partial | minimal"
}}
"""

SNIPPET_ANALYSIS_USER = """
TARGET: "{target}"
PLATFORM: {platform}
POST: "{title}"
URL: {url}
TIMEFRAME: Content should be from {timeframe_desc}
SNIPPET: \"\"\"{snippet}\"\"\"

DO NOT use tools. Analyze snippet FROM "{target}"'s PERSPECTIVE.
Is this GOOD or BAD for "{target}"? Any security threats or risks?
Return ONLY raw JSON.
"""
