"""
Example 10 — List all active scheduled scans.
"""

from helpers import BASE_URL, get_session, print_response, handle_error

session = get_session()

params = {"limit": 20, "offset": 0}

print("Listing scheduled scans...")
resp = session.get(f"{BASE_URL}/api/v1/scans/scheduled", params=params)
print_response(resp, "List Scheduled Scans")
handle_error(resp, "list_scheduled_scans")

data = resp.json()
print(f"\n✅ Active scheduled scans: {data['total']}")
for s in data["scans"]:
    print(
        f"   - [{s['id']}] interval={s['schedule_interval']:12} "
        f"next_run={s.get('next_run_at', 'N/A')} "
        f"target={s['target_id']}"
    )
