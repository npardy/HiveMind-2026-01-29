"""
Test QBO Enrichment - verify that lookups populate the job index
"""
import json
import sys
import yaml
sys.path.insert(0, 'H:\\')

from qbo_integration import QBOIntegration
from tool_executor import ToolExecutor

# Load config
with open('config.yaml') as f:
    config = yaml.safe_load(f)

# Initialize QBO with credentials
qbo = QBOIntegration(
    config['quickbooks']['client_id'],
    config['quickbooks']['client_secret'],
    config['quickbooks']['redirect_uri'],
    config['quickbooks']['environment']
)

if not qbo.access_token:
    print("ERROR: QBO not connected. Token may have expired.")
    exit(1)

print("QBO connected!")

# Create executor with real QBO
te = ToolExecutor(qbo=qbo, email_service=None)

# Check index BEFORE
idx_before = json.load(open('job_index.json'))
job_before = None
for k, v in idx_before.items():
    if v.get('job_number') == '26-001':
        job_before = v
        break

print("\n=== QBO SECTION BEFORE ===")
print(json.dumps(job_before.get('qbo', {}) if job_before else "Not found", indent=2))

# Search for invoice - this should trigger enrichment
print("\n=== SEARCHING FOR INVOICE 26-001 ===")
result = te.execute('qbo_search_invoices', {'invoice_number': '26-001'})
print(result)

# Reload index and check AFTER
te.job_index = te._load_job_index()  # Reload
idx_after = json.load(open('job_index.json'))
job_after = None
for k, v in idx_after.items():
    if v.get('job_number') == '26-001':
        job_after = v
        break

print("\n=== QBO SECTION AFTER ===")
print(json.dumps(job_after.get('qbo', {}) if job_after else "Not found", indent=2))

# Check if _updated timestamp exists
if job_after and job_after.get('qbo', {}).get('_updated'):
    print("\n[OK] _updated timestamp present!")
else:
    print("\n[WARN] No _updated timestamp")
