
"""
Example 01 — Create a target.

Creates a new monitoring target (or returns an existing matched one).
"""

from helpers import BASE_URL, get_session, print_response, handle_error

session = get_session()

payload = {
    "name": "Elon Musk",
    "target_type": "person",
    "description": "CEO of Tesla and SpaceX, owner of X (Twitter)",
}

print("Creating target...")
resp = session.post(f"{BASE_URL}/api/v1/targets/", json=payload)
print_response(resp, "Create Target")
handle_error(resp, "create_target")

data = resp.json()
target_id = data["target"]["id"]
is_new = data["is_new"]
matched_by = data.get("matched_by")

print(f"\n✅ Target ID   : {target_id}")
print(f"   Is new      : {is_new}")
print(f"   Matched by  : {matched_by or 'N/A (new)'}")
print(f"   Display name: {data['target']['display_name']}")
