"""
Example 04 — Update a target's details.

Replace TARGET_ID with a real UUID from your database.
"""

from helpers import BASE_URL, get_session, print_response, handle_error

TARGET_ID = "YOUR-TARGET-UUID-HERE"

session = get_session()

payload = {
    "description": "Updated description — CEO of Tesla, SpaceX, and xAI",
    "is_active": True,
}

print(f"Updating target {TARGET_ID}...")
resp = session.put(f"{BASE_URL}/api/v1/targets/{TARGET_ID}", json=payload)
print_response(resp, "Update Target")
handle_error(resp, "update_target")

data = resp.json()
print(f"\n✅ Updated: {data['display_name']}")
print(f"   Description: {data['description']}")
