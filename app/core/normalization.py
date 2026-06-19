"""
Normalization utilities for target names and URLs.

Ensures consistent deduplication by converting variant forms to canonical keys:
- Target names: lowercased, accent-stripped, punctuation-normalized.
- URLs: tracking params removed, trailing slashes stripped, lowercased.
"""

import re
import unicodedata
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode


def normalize_target_name(name: str) -> str:
    """
    Normalize a target name to a canonical deduplication key.

    Pipeline:
    1. Strip leading/trailing whitespace.
    2. Collapse multiple internal spaces to one.
    3. Convert to lowercase.
    4. Strip accents/diacritics (NFD decomposition → remove combining chars).
    5. Remove non-alphanumeric characters (except spaces).
    6. Final collapse of whitespace.

    Args:
        name: Raw target name (e.g., "José García-López").

    Returns:
        Normalized key (e.g., "jose garcialopez").

    Examples:
        >>> normalize_target_name("  John   Doe  ")
        'john doe'
        >>> normalize_target_name("José García")
        'jose garcia'
        >>> normalize_target_name("O'Brien-Smith")
        'obriensmith'
        >>> normalize_target_name("ACME Corp.")
        'acme corp'
    """
    if not name:
        return ""

    # Step 1-2: Trim and collapse spaces
    text = " ".join(name.split())

    # Step 3: Lowercase
    text = text.lower()

    # Step 4: Strip accents (NFD decomposition, remove combining characters)
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")

    # Step 5: Remove non-alphanumeric (keep spaces)
    text = re.sub(r"[^a-z0-9\s]", "", text)

    # Step 6: Final space collapse
    text = " ".join(text.split())

    return text


def normalize_url(url: str) -> str:
    """
    Normalize a URL for deduplication.

    Pipeline:
    1. Lowercase the scheme and domain.
    2. Strip trailing slashes from the path.
    3. Remove tracking parameters (utm_*, fbclid, gclid, etc.).
    4. Remove fragment (#...).
    5. Reconstruct clean URL.

    Args:
        url: Raw URL string.

    Returns:
        Normalized URL string.

    Examples:
        >>> normalize_url("https://Example.com/Article/?utm_source=twitter&id=5")
        'https://example.com/article?id=5'
        >>> normalize_url("https://news.com/story/#comments")
        'https://news.com/story'
    """
    if not url:
        return ""

    try:
        parsed = urlparse(url.strip())

        # Lowercase scheme and host
        scheme = (parsed.scheme or "https").lower()
        host = (parsed.hostname or "").lower()
        port = f":{parsed.port}" if parsed.port and parsed.port not in (80, 443) else ""
        netloc = f"{host}{port}"

        # Strip trailing slashes from path
        path = parsed.path.rstrip("/").lower()

        # Remove tracking params
        tracking_prefixes = ("utm_", "fbclid", "gclid", "mc_", "ref", "source", "pk_")
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=False)
            clean_params = {
                k: v for k, v in params.items()
                if not any(k.lower().startswith(p) for p in tracking_prefixes)
            }
            query = urlencode(clean_params, doseq=True) if clean_params else ""
        else:
            query = ""

        # Reconstruct without fragment
        normalized = urlunparse((scheme, netloc, path, "", query, ""))
        return normalized

    except Exception:
        # Fallback: lowercase and strip slashes
        return url.strip().rstrip("/").lower()


def display_name_from_input(name: str) -> str:
    """
    Clean user input for display while preserving original casing.

    Just trims whitespace and collapses multiple spaces.

    Args:
        name: Raw user input.

    Returns:
        Cleaned display-friendly name.
    """
    if not name:
        return ""
    return " ".join(name.split())
