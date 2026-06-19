"""
Example 05 — Soft-delete (deactivate) a target.

Replace TARGET_ID with a real UUID from your database.
"""

from helpers import BASE_URL, get_session, print_response, handle_error

TARGET_ID = "YOUR-TARGET-UUID-HERE"

session = get_session()

print(f"Deleting target {TARGET_ID}...")
resp = session.delete(f"{BASE_URL}/api/v1/targets/{TARGET_ID}")
print_response(resp, "Delete Target")
handle_error(resp, "delete_target")

print(f"\n✅ {resp.json()['message']}")
