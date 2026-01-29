"""Test multiple jobs building up the index"""
import os
import sys
import json
import yaml

from tool_executor import ToolExecutor
from qbo_integration import QBOIntegration
from email_service import EmailService

# Load config
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Initialize
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

# Test multiple jobs
test_jobs = ["25-180", "25-175", "25-170"]

print("=" * 80)
print("TESTING HIVE INTELLIGENCE - MULTIPLE JOBS")
print("=" * 80)

for job_num in test_jobs:
    print(f"\n>>> Querying {job_num}...")
    result = executor.execute("job_get_status", {"job_number": job_num})
    data = json.loads(result)
    
    if data.get("found"):
        print(f"    Found: {data.get('property_address', 'N/A')}")
        print(f"    Client: {data.get('client_business', 'N/A')}")
        print(f"    Controller jobs: {data.get('data_sync', {}).get('total_controller_jobs', 0)}")
        print(f"    Field data: {'YES' if data.get('has_field_data') else 'NO'}")
    else:
        print(f"    Not found")

print("\n" + "=" * 80)
print("INDEX CONTENTS AFTER QUERIES:")
print("=" * 80)

# Read the index directly
with open('job_index.json', 'r') as f:
    index = json.load(f)

print(f"\nTotal jobs in index: {len(index)}")
for job_num, job_data in index.items():
    print(f"\n  {job_num}:")
    print(f"    Address: {job_data.get('property_address', 'N/A')}")
    print(f"    Client: {job_data.get('client_business', 'N/A')}")
    print(f"    Controller jobs: {len(job_data.get('controller_jobs', []))}")
    print(f"    Emails linked: {len(job_data.get('emails', []))}")
    print(f"    Last updated: {job_data.get('last_updated', 'N/A')}")
