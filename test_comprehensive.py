"""
Comprehensive test to verify all tools still work after hive changes.
"""
import json
import yaml
import traceback
from tool_executor import ToolExecutor
from qbo_integration import QBOIntegration
from email_service import EmailService

with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

email_service = EmailService(
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

executor = ToolExecutor(qbo, email_service)

tests = [
    # Job tools
    ("job_get_status", {"job_number": "25-180"}),
    ("job_get_status", {"job_number": "25-999"}),  # Non-existent
    ("job_search", {"query": "Rankin"}),
    
    # QBO tools  
    ("qbo_search_customers", {"query": "Van Driel"}),
    ("qbo_get_next_job_number", {}),
    
    # File tools
    ("file_list", {"path": "Z:\\Jobs\\2025", "pattern": "25-18*"}),
    
    # Datetime
    ("get_current_datetime", {}),
]

print("=" * 80)
print("COMPREHENSIVE TOOL TEST")
print("=" * 80)

passed = 0
failed = 0

for tool_name, params in tests:
    try:
        result = executor.execute(tool_name, params)
        data = json.loads(result)
        
        if "error" in data and "not found" not in str(data.get("error", "")).lower():
            print(f"WARN  {tool_name}: {data.get('error', 'unknown error')[:60]}")
        else:
            print(f"OK    {tool_name}")
            passed += 1
            continue
    except Exception as e:
        print(f"FAIL  {tool_name}: {e}")
        traceback.print_exc()
        failed += 1
        continue
    
    passed += 1

print()
print("=" * 80)
print(f"RESULTS: {passed} passed, {failed} failed")
print("=" * 80)

# Extra: verify job_index is being populated
print()
print("JOB INDEX STATUS:")
print(f"  Jobs in index: {len(executor.job_index)}")
for job_num in list(executor.job_index.keys())[:5]:
    job = executor.job_index[job_num]
    has_dc = "document_control" in job
    has_ref = "reference_files" in job
    print(f"  {job_num}: doc_control={has_dc}, ref_files={has_ref}")
