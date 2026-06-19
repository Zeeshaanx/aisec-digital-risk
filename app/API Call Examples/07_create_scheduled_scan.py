"""
Example 07 — Create a scheduled (recurring) scan for a target.

The first execution starts immediately. Subsequent runs happen
at the specified interval.

Replace TARGET_ID with a real UUID from your database.
"""

from helpers import BASE_URL, get_session, print_response, handle_error

TARGET_ID = "YOUR-TARGET-UUID-HERE"

session = get_session()

payload = {
    "target_id": TARGET_ID,
    "scan_type": "scheduled",
    "scan_depth": "standard",
    "timeframe": "24 hours",
    "schedule_interval": "24 hours",   # 6 hours | 12 hours | 24 hours | 1 week
}

print("Creating scheduled scan...")
resp = session.post(f"{BASE_URL}/api/v1/scans/", json=payload)
print_response(resp, "Create Scheduled Scan")
handle_error(resp, "create_scheduled_scan")

data = resp.json()
print(f"\n✅ Scan ID        : {data['id']}")
print(f"   Status          : {data['status']}")
print(f"   Type            : {data['scan_type']}")
print(f"   Interval        : {data['schedule_interval']}")
print(f"   Next run at     : {data.get('next_run_at', 'N/A')}")
print(f"   Schedule active : {data['is_schedule_active']}")
