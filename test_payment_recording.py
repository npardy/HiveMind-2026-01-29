"""
Test QBO Payment Recording - REAL TEST on 23-285
This will actually mark the invoice as paid in QBO!
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

# Initialize QBO
qbo = QBOIntegration(
    config['quickbooks']['client_id'],
    config['quickbooks']['client_secret'],
    config['quickbooks']['redirect_uri'],
    config['quickbooks']['environment']
)

if not qbo.access_token:
    print("ERROR: QBO not connected")
    exit(1)

print("QBO connected!")

te = ToolExecutor(qbo=qbo, email_service=None)

# Step 1: Check invoice status BEFORE
print("\n=== STEP 1: CHECK INVOICE 23-285 BEFORE ===")
search_result = te.execute('qbo_search_invoices', {'invoice_number': '23-285'})
print(f"Search result: {search_result}")

# Step 2: Check index BEFORE
print("\n=== STEP 2: INDEX STATE BEFORE ===")
idx = json.load(open('job_index.json'))
job_before = None
for k, v in idx.items():
    if v.get('job_number') == '23-285':
        job_before = v.get('qbo', {})
        break
print(f"QBO section: {json.dumps(job_before, indent=2)}")

# Step 3: Record payment
print("\n=== STEP 3: RECORDING PAYMENT FOR 23-285 ===")
payment_result = te.execute('qbo_record_payment', {
    'invoice_numbers': ['23-285'],
    'payment_date': '2026-01-20'
})
print(f"Payment result: {payment_result}")

# Step 4: Verify in QBO
print("\n=== STEP 4: VERIFY INVOICE STATUS IN QBO ===")
verify_result = te.execute('qbo_search_invoices', {'invoice_number': '23-285'})
print(f"After payment: {verify_result}")

# Step 5: Check index AFTER
print("\n=== STEP 5: INDEX STATE AFTER ===")
idx_after = json.load(open('job_index.json'))
job_after = None
for k, v in idx_after.items():
    if v.get('job_number') == '23-285':
        job_after = v.get('qbo', {})
        break
print(f"QBO section: {json.dumps(job_after, indent=2)}")

# Verify enrichment
print("\n=== VERIFICATION ===")
if job_after:
    if job_after.get('paid') == True:
        print("[OK] paid = True")
    else:
        print(f"[FAIL] paid = {job_after.get('paid')}")
    
    if job_after.get('paid_date'):
        print(f"[OK] paid_date = {job_after.get('paid_date')}")
    else:
        print("[FAIL] paid_date missing")
    
    if job_after.get('_updated'):
        print(f"[OK] _updated = {job_after.get('_updated')}")
    else:
        print("[FAIL] _updated missing")
    
    if job_after.get('status') == 'Paid':
        print("[OK] status = Paid")
    else:
        print(f"[FAIL] status = {job_after.get('status')}")
else:
    print("[FAIL] Job 23-285 not found in index")
