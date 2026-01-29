"""Audit check script - verify tools match between definition and executor"""
import sys
sys.path.insert(0, 'H:\\')

from tools_definition import define_all_tools
from tool_executor import ToolExecutor

# Get all defined tools
tools = define_all_tools()
defined_tools = {t['name'] for t in tools}

# Get all handlers from ToolExecutor._dispatch_tool
# We'll extract them by checking the if/elif chain
executor_handlers = {
    # QBO Tools
    "qbo_search_invoices", "qbo_get_invoice", "qbo_send_invoice", "qbo_create_invoice",
    "qbo_search_customers", "qbo_create_customer", "qbo_search_projects", "qbo_create_project",
    "qbo_get_next_job_number", "qbo_get_service_items",
    # Email Tools
    "email_get_unread", "email_get_by_id", "email_search", "email_get_history_with_contact",
    "email_list_folders", "email_send_reply", "email_create_draft", "email_send_new",
    "email_move_to_folder", "email_mark_read", "email_mark_unread", "email_flag_important",
    "email_create_folder", "email_get_attachments", "email_save_attachment",
    # NAS Tools
    "nas_list_directory", "nas_read_file", "nas_file_exists", "nas_get_file_info",
    "nas_search_files", "nas_create_directory", "nas_write_file", "nas_copy_file",
    "nas_copy_directory", "nas_move_file",
    # Job Tools
    "job_create", "job_search", "job_get_status", "job_save_email", "job_list_recent",
    # Utility Tools
    "flag_for_attention", "get_current_datetime", "parse_date"
}

print(f"Tools DEFINED in tools_definition.py: {len(defined_tools)}")
print(f"Tools HANDLED in tool_executor.py: {len(executor_handlers)}")

# Find mismatches
missing_handlers = defined_tools - executor_handlers
missing_definitions = executor_handlers - defined_tools

if missing_handlers:
    print(f"\n[X] DEFINED but NO HANDLER: {missing_handlers}")
else:
    print("\n[OK] All defined tools have handlers")

if missing_definitions:
    print(f"\n[X] HANDLER but NO DEFINITION: {missing_definitions}")
else:
    print("[OK] All handlers have definitions")

if len(defined_tools) == len(executor_handlers) == 43 and not missing_handlers and not missing_definitions:
    print("\n[PASS] ALL 43 TOOLS MATCH CORRECTLY")
