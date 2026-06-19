"""
Example 06 — Create a one-time scan for a target.

The scan executes immediately in the background.
Poll 07_get_scan_status.py to check when it completes.

Replace TARGET_ID with a real UUID from your database.
"""

from helpers import BASE_URL, get_session, print_response, handle_error

TARGET_ID = "YOUR-TARGET-UUID-HERE"

session = get_session()

payload = {
    "target_id": TARGET_ID,
    "scan_type": "one_time",
    "scan_depth": "standard",   # quick | standard | thorough | exhaustive
    "timeframe": "24 hours",    # how far back to search
}

print("Creating one-time scan...")
resp = session.post(f"{BASE_URL}/api/v1/scans/", json=payload)
print_response(resp, "Create One-Time Scan")
handle_error(resp, "create_scan")

data = resp.json()
print(f"\n✅ Scan ID  : {data['id']}")
print(f"   Status   : {data['status']}")
print(f"   Type     : {data['scan_type']}")
print(f"   Target ID: {data['target_id']}")
print(f"\n👉 Use scan ID to poll status: 07_get_scan_status.py")
