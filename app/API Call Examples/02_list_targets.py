"""
Example 02 — List all targets with pagination.
"""

from helpers import BASE_URL, get_session, print_response, handle_error

session = get_session()

params = {"limit": 20, "offset": 0}

print("Listing targets...")
resp = session.get(f"{BASE_URL}/api/v1/targets/", params=params)
print_response(resp, "List Targets")
handle_error(resp, "list_targets")

data = resp.json()
print(f"\n✅ Total targets: {data['total']}")
for t in data["targets"]:
    print(f"   - [{t['id']}] {t['display_name']} ({t['target_type']})")
