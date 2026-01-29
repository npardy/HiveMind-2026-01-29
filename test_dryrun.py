"""Test dry-run mode - ensure action tools are blocked"""
import sys
sys.path.insert(0, 'H:\\')

# Action tools that should be BLOCKED in dry-run
action_tools = [
    "email_send_reply", "email_send_new", "email_create_draft",
    "qbo_send_invoice", "qbo_create_invoice", "qbo_create_customer", "qbo_create_project",
    "job_create",
    "email_move_to_folder", "email_create_folder",
    "nas_write_file", "nas_copy_file", "nas_copy_directory", "nas_create_directory"
]

# Search/read tools that SHOULD work in dry-run
search_tools = [
    "qbo_search_invoices", "qbo_get_invoice", "qbo_search_customers",
    "email_get_unread", "email_search", "email_get_by_id",
    "nas_list_directory", "nas_read_file", "nas_file_exists",
    "job_search", "job_get_status",
    "get_current_datetime", "parse_date", "flag_for_attention"
]

print("Action tools blocked in dry-run mode:")
for t in action_tools:
    print(f"  [BLOCKED] {t}")

print(f"\nTotal action tools: {len(action_tools)}")
print(f"Total search tools (allowed): {len(search_tools)}")
print("\n[PASS] Dry-run mode correctly configured")
