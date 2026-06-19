"""
Example 03 — Get a single target by ID.

Replace TARGET_ID with a real UUID from your database.
"""

from helpers import BASE_URL, get_session, print_response, handle_error

TARGET_ID = "YOUR-TARGET-UUID-HERE"

session = get_session()

print(f"Fetching target {TARGET_ID}...")
resp = session.get(f"{BASE_URL}/api/v1/targets/{TARGET_ID}")
print_response(resp, "Get Target")
handle_error(resp, "get_target")

data = resp.json()
print(f"\n✅ Target: {data['display_name']} ({data['target_type']})")
print(f"   Active : {data['is_active']}")
print(f"   Created: {data['created_at']}")
