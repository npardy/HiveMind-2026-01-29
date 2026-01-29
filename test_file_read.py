"""Test nas_read_file with different file types."""
import yaml
with open('config.yaml') as f:
    config = yaml.safe_load(f)

from tool_executor import ToolExecutor
from qbo_integration import QBOIntegration
from email_service import EmailService

email = EmailService(
    client_id=config['email']['client_id'],
    client_secret=config['email']['client_secret'],
    redirect_uri=config['email']['redirect_uri']
)

qbo = QBOIntegration(
    client_id=config['quickbooks']['client_id'],
    client_secret=config['quickbooks']['client_secret'],
    redirect_uri=config['quickbooks']['redirect_uri'],
    environment=config['quickbooks']['environment']
)

te = ToolExecutor(qbo=qbo, email_service=email)

# Test .docx
print("=== Testing .docx ===")
result = te.execute('nas_read_file', {'path': r"Z:\Jobs\2025\25-180 - Van Driel Law - 9 Rankin Street, St. John's\Description & Reports\25-180-1.docx", 'max_lines': 10})
import json
r = json.loads(result)
print(f"Type: {r.get('type', 'error')}")
print(f"Content preview: {r.get('content', r.get('error', ''))[:200]}...")
print()

# Test .xlsx
print("=== Testing .xlsx ===")
result = te.execute('nas_read_file', {'path': r"Z:\Jobs\2025\25-180 - Van Driel Law - 9 Rankin Street, St. John's\Reference & Research\Research Spreadsheet.xlsx", 'max_lines': 5})
r = json.loads(result)
print(f"Type: {r.get('type', 'error')}")
if 'content' in r:
    print(f"Rows: {r.get('rows_read')}")
    for row in r.get('content', [])[:3]:
        print(f"  {row}")
else:
    print(f"Error: {r.get('error')}")
print()

# Test binary file (should reject)
print("=== Testing .dwg (should reject) ===")
result = te.execute('nas_read_file', {'path': r"Z:\Jobs\2025\25-180 - Van Driel Law - 9 Rankin Street, St. John's\Drawings\25-180.dwg"})
r = json.loads(result)
print(f"Result: {r.get('error', 'Unexpected success')}")
