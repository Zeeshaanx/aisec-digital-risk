"""
Database-level enumerations used across all models.
"""

import enum


class TargetType(str, enum.Enum):
    """Classification of monitoring targets."""
    person = "person"
    company = "company"
    team = "team"
    brand = "brand"
    organization = "organization"
    product = "product"
    other = "other"


class ScanType(str, enum.Enum):
    """Whether a scan runs once or on a recurring schedule."""
    one_time = "one_time"
    scheduled = "scheduled"


class ScanStatus(str, enum.Enum):
    """Lifecycle status of a scan execution."""
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ScanDepth(str, enum.Enum):
    """
    Controls the breadth of search queries.
    quick ≈ 6 queries, standard ≈ 15, thorough ≈ 30, exhaustive ≈ 51.
    """
    quick = "quick"
    standard = "standard"
    thorough = "thorough"
    exhaustive = "exhaustive"


class SentimentType(str, enum.Enum):
    """Sentiment classification from the target's perspective."""
    positive = "positive"
    negative = "negative"
    neutral = "neutral"


class SecuritySeverity(str, enum.Enum):
    """Severity level for security-related findings in articles."""
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    none = "none"
