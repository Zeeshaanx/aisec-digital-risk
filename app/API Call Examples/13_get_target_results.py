"""
Example 13 — Get all articles for a target across all scans.

Supports filtering by date range, sentiment, and platform.
Replace TARGET_ID with a real UUID from your database.
"""

from helpers import BASE_URL, get_session, print_response, handle_error

TARGET_ID = "YOUR-TARGET-UUID-HERE"

session = get_session()

params = {
    "limit": 50,
    "offset": 0,
    # Optional filters — uncomment to use:
    # "from_date": "2024-01-01T00:00:00",
    # "to_date":   "2024-12-31T23:59:59",
    # "sentiment": "negative",          # positive | negative | neutral
    # "platform":  "twitter",           # web | twitter | reddit | youtube
}

print(f"Fetching all results for target {TARGET_ID}...")
resp = session.get(f"{BASE_URL}/api/v1/results/target/{TARGET_ID}", params=params)
print_response(resp, "Target Results")
handle_error(resp, "get_target_results")

data = resp.json()

print(f"\n✅ Target results summary:")
print(f"   Total articles : {data['total_count']}")
print(f"   Returned       : {len(data['articles'])}")
print(f"   Has more       : {data['has_more']}")

sentiment = data.get("sentiment_summary", {})
print(f"\n   Sentiment breakdown:")
print(f"     Positive : {sentiment.get('positive', 0)} ({sentiment.get('positive_pct', 0)}%)")
print(f"     Negative : {sentiment.get('negative', 0)} ({sentiment.get('negative_pct', 0)}%)")
print(f"     Neutral  : {sentiment.get('neutral', 0)} ({sentiment.get('neutral_pct', 0)}%)")

platforms = data.get("platform_breakdown", {})
if platforms:
    print(f"\n   Platform breakdown:")
    for platform, count in sorted(platforms.items(), key=lambda x: x[1], reverse=True):
        print(f"     {platform:15}: {count}")

print(f"\n   Articles (first 5):")
for article in data["articles"][:5]:
    print(f"     - [{article['sentiment']:8}] {article['title'][:70]}")
    print(f"       Source  : {article.get('source_name', 'N/A')}")
    print(f"       Platform: {article.get('platform', 'web')}")
    print(f"       URL     : {article['url'][:80]}")
