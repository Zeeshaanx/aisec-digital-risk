"""
Example 08 — List all scans with optional filters.
"""

from helpers import BASE_URL, get_session, print_response, handle_error

session = get_session()

# Optional query params — set to None to omit
params = {
    "limit": 20,
    "offset": 0,
    # "status": "completed",       # pending | running | completed | failed
    # "scan_type": "one_time",     # one_time | scheduled
    # "target_id": "UUID-HERE",    # filter by specific target
}

# Remove None values
params = {k: v for k, v in params.items() if v is not None}

print("Listing scans...")
resp = session.get(f"{BASE_URL}/api/v1/scans/", params=params)
print_response(resp, "List Scans")
handle_error(resp, "list_scans")

data = resp.json()
print(f"\n✅ Total scans: {data['total']}")
for s in data["scans"]:
    print(
        f"   - [{s['id']}] {s['scan_type']:10} "
        f"status={s['status']:10} "
        f"target={s['target_id']}"
    )
