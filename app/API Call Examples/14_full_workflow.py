"""
Example 14 — Full end-to-end workflow.

Demonstrates the complete pipeline:
1. Create a target
2. Create a one-time scan
3. Poll until completed
4. Retrieve and display results
"""

import time
from helpers import BASE_URL, get_session, print_response, handle_error

session = get_session()

print("=" * 60)
print("  Media Intelligence API — Full Workflow Example")
print("=" * 60)

# ── Step 1: Create target ──────────────────────────────────
print("\n[1/4] Creating target...")

target_payload = {
    "name": "OpenAI",
    "target_type": "company",
    "description": "Artificial intelligence research company, maker of ChatGPT",
}

resp = session.post(f"{BASE_URL}/api/v1/targets/", json=target_payload)
handle_error(resp, "create_target")
target_data = resp.json()
target_id = target_data["target"]["id"]

print(f"  ✅ Target: {target_data['target']['display_name']}")
print(f"     ID     : {target_id}")
print(f"     Is new : {target_data['is_new']}")
if target_data.get("matched_by"):
    print(f"     Matched: {target_data['matched_by']} "
          f"(confidence={target_data.get('match_confidence', 0):.0%})")

# ── Step 2: Create one-time scan ───────────────────────────
print("\n[2/4] Creating one-time scan...")

scan_payload = {
    "target_id": target_id,
    "scan_type": "one_time",
    "scan_depth": "standard",
    "timeframe": "24 hours",
}

resp = session.post(f"{BASE_URL}/api/v1/scans/", json=scan_payload)
handle_error(resp, "create_scan")
scan_data = resp.json()
scan_id = scan_data["id"]

print(f"  ✅ Scan ID: {scan_id}")
print(f"     Status : {scan_data['status']}")

# ── Step 3: Poll for completion ────────────────────────────
print("\n[3/4] Polling scan status...")

POLL_INTERVAL = 10
MAX_WAIT = 600  # 10 minutes
elapsed = 0

while elapsed < MAX_WAIT:
    time.sleep(POLL_INTERVAL)
    elapsed += POLL_INTERVAL

    resp = session.get(f"{BASE_URL}/api/v1/scans/{scan_id}")
    handle_error(resp, "poll_scan")
    scan_status = resp.json()
    status = scan_status["status"]

    print(f"  [{elapsed:4}s] status={status}")

    if status == "completed":
        print(f"\n  ✅ Scan completed in {elapsed}s!")
        print(f"     Total results    : {scan_status['total_results']}")
        print(f"     New articles     : {scan_status['new_articles_found']}")
        print(f"     Overall sentiment: {scan_status['overall_sentiment']}")
        print(f"     Cost USD         : ${scan_status['cost_usd']:.6f}")
        break
    elif status == "failed":
        print(f"\n  ❌ Scan failed: {scan_status.get('error_message', 'Unknown')}")
        break
else:
    print(f"\n  ⏰ Timed out after {MAX_WAIT}s")

# ── Step 4: Retrieve results ───────────────────────────────
print("\n[4/4] Fetching scan results...")

resp = session.get(
    f"{BASE_URL}/api/v1/results/scan/{scan_id}",
    params={"limit": 10, "offset": 0},
)
handle_error(resp, "get_results")
results = resp.json()

print(f"\n  ✅ Results summary:")
print(f"     Total articles : {results['total_count']}")
print(f"     New articles   : {results.get('new_articles_found', 0)}")

sentiment = results.get("sentiment_summary", {})
print(f"     Positive       : {sentiment.get('positive', 0)} ({sentiment.get('positive_pct', 0)}%)")
print(f"     Negative       : {sentiment.get('negative', 0)} ({sentiment.get('negative_pct', 0)}%)")
print(f"     Neutral        : {sentiment.get('neutral', 0)} ({sentiment.get('neutral_pct', 0)}%)")

alerts = results.get("security_alerts") or []
if alerts:
    print(f"\n  ⚠️  Security alerts: {len(alerts)}")
    for a in alerts[:3]:
        print(f"     [{a['severity'].upper()}] {a['title'][:70]}")

print(f"\n  Top articles:")
for i, article in enumerate(results["articles"][:5], 1):
    print(f"  {i}. [{article['sentiment']:8}] {article['title'][:65]}")
    print(f"      {article['url'][:80]}")

print("\n" + "=" * 60)
print("  ✅ Full workflow complete!")
print(f"  Target ID : {target_id}")
print(f"  Scan ID   : {scan_id}")
print("=" * 60)
