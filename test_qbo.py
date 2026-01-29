"""Test QBO integration"""
import sys
sys.path.insert(0, 'H:\\')

import yaml
from qbo_integration import QBOIntegration

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

# Test connection
info = qbo.get_company_info()
if info:
    print(f"[PASS] QBO connected: {info.get('CompanyName')}")
    
    # Test job number
    job_num = qbo.get_next_job_number()
    print(f"[PASS] Next job number: {job_num}")
    
    # Test search invoices
    invoices = qbo.get_recent_invoices(5)
    print(f"[PASS] Recent invoices: {len(invoices)} found")
    
    # Test service items
    items = qbo.get_items()
    print(f"[PASS] Service items: {len(items)} found")
else:
    print("[FAIL] Could not connect to QBO")
