"""
Example 11 — Cancel a scheduled scan.

Stops future executions. Historical results are preserved.
Replace SCAN_ID with a real UUID from your database.
"""

from helpers import BASE_URL, get_session, print_response, handle_error

SCAN_ID = "YOUR-SCHEDULED-SCAN-UUID-HERE"

session = get_session()

print(f"Cancelling scheduled scan {SCAN_ID}...")
resp = session.delete(f"{BASE_URL}/api/v1/scans/{SCAN_ID}/schedule")
print_response(resp, "Cancel Scheduled Scan")
handle_error(resp, "cancel_scheduled_scan")

print(f"\n✅ {resp.json()['message']}")
