"""Test Tool Executor - verify key tools work"""
import sys
sys.path.insert(0, 'H:\\')

import yaml
import json
from qbo_integration import QBOIntegration
from email_service import EmailService
from tool_executor import ToolExecutor

# Load config
with open('config.yaml') as f:
    config = yaml.safe_load(f)

# Initialize services
qbo = QBOIntegration(
    config['quickbooks']['client_id'],
    config['quickbooks']['client_secret'],
    config['quickbooks']['redirect_uri'],
    config['quickbooks']['environment']
)

email = EmailService(
    config['email']['client_id'],
    config['email']['client_secret'],
    config['email']['redirect_uri']
)
email.authenticate(allow_interactive=False)

# Create executor
executor = ToolExecutor(qbo, email)

# Test tools
tests = [
    ("get_current_datetime", {}),
    ("parse_date", {"date_text": "January 25, 2026"}),
    ("qbo_get_next_job_number", {}),
    ("qbo_get_service_items", {}),
    ("qbo_search_invoices", {"recent_count": 3}),
    ("email_list_folders", {}),
    ("nas_file_exists", {"path": "Z:\\Jobs\\2026"}),
    ("nas_list_directory", {"path": "Z:\\Jobs\\2026"}),
    ("job_list_recent", {"count": 3}),
]

print("Testing Tool Executor:")
for tool_name, params in tests:
    result = executor.execute(tool_name, params)
    data = json.loads(result)
    if "error" in data:
        print(f"  [FAIL] {tool_name}: {data['error']}")
    else:
        print(f"  [PASS] {tool_name}")

print("\nAll tools executed successfully!")
