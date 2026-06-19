"""
Example 09 — Poll a scan's status until it completes or fails.

Replace SCAN_ID with a real UUID from your database.
"""

import time
from helpers import BASE_URL, get_session, print_response, handle_error

SCAN_ID = "YOUR-SCAN-UUID-HERE"
POLL_INTERVAL_SEC = 10
MAX_ATTEMPTS = 60  # 10 minutes max

session = get_session()

print(f"Polling scan {SCAN_ID} ...")

for attempt in range(1, MAX_ATTEMPTS + 1):
    resp = session.get(f"{BASE_URL}/api/v1/scans/{SCAN_ID}")
    handle_error(resp, "get_scan")
    data = resp.json()
    status = data["status"]

    print(f"  [{attempt:02d}] status={status}")

    if status == "completed":
        print(f"\n✅ Scan completed!")
        print(f"   Total results   : {data['total_results']}")
        print(f"   New articles    : {data['new_articles_found']}")
        print(f"   Overall sentiment: {data['overall_sentiment']}")
        print(f"   Processing time : {data['processing_time_sec']}s")
        print(f"   Cost USD        : ${data['cost_usd']:.6f}")
        break
    elif status == "failed":
        print(f"\n❌ Scan failed: {data.get('error_message', 'Unknown error')}")
        break

    time.sleep(POLL_INTERVAL_SEC)
else:
    print(f"\n⏰ Timed out after {MAX_ATTEMPTS * POLL_INTERVAL_SEC}s")
