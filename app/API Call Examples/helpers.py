"""
Shared helpers for API call examples.

Provides the base URL and a pre-configured requests session.
No authentication headers needed — all endpoints are open.
"""

import sys
import json
import requests

# ── Configuration ──────────────────────────────────────────────────────────
BASE_URL = "http://localhost/aisec-digital-risk"  # Change to your server IP in prod


def get_session() -> requests.Session:
    """Return a plain requests session (no auth required)."""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


def print_response(resp: requests.Response, label: str = "") -> None:
    """Pretty-print an HTTP response."""
    prefix = f"[{label}] " if label else ""
    print(f"\n{prefix}HTTP {resp.status_code}")
    try:
        print(json.dumps(resp.json(), indent=2, default=str))
    except Exception:
        print(resp.text)


def handle_error(resp: requests.Response, context: str = "") -> None:
    """Print error details and exit if the response is not successful."""
    if not resp.ok:
        print(f"\n❌ Error{f' in {context}' if context else ''}: HTTP {resp.status_code}")
        try:
            print(json.dumps(resp.json(), indent=2))
        except Exception:
            print(resp.text)
        sys.exit(1)
