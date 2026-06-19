"""
Example 12 — Get all articles discovered by a specific scan.

Replace SCAN_ID with a completed scan UUID.
"""

from helpers import BASE_URL, get_session, print_response, handle_error

SCAN_ID = "YOUR-SCAN-UUID-HERE"

session = get_session()

params = {"limit": 50, "offset": 0}

print(f"Fetching results for scan {SCAN_ID}...")
resp = session.get(f"{BASE_URL}/api/v1/results/scan/{SCAN_ID}", params=params)
print_response(resp, "Scan Results")
handle_error(resp, "get_scan_results")

data = resp.json()

print(f"\n✅ Scan results summary:")
print(f"   Total articles  : {data['total_count']}")
print(f"   New articles    : {data.get('new_articles_found', 0)}")
print(f"   Has more        : {data['has_more']}")

sentiment = data.get("sentiment_summary", {})
print(f"\n   Sentiment breakdown:")
print(f"     Positive : {sentiment.get('positive', 0)} ({sentiment.get('positive_pct', 0)}%)")
print(f"     Negative : {sentiment.get('negative', 0)} ({sentiment.get('negative_pct', 0)}%)")
print(f"     Neutral  : {sentiment.get('neutral', 0)} ({sentiment.get('neutral_pct', 0)}%)")

alerts = data.get("security_alerts") or []
if alerts:
    print(f"\n   ⚠️  Security alerts: {len(alerts)}")
    for a in alerts[:3]:
        print(f"     [{a['severity'].upper()}] {a['title'][:80]}")

print(f"\n   Articles (first 5):")
for article in data["articles"][:5]:
    print(f"     - [{article['sentiment']:8}] {article['title'][:70]}")
    print(f"       {article['url'][:80]}")
