"""
Query Job 25-180 - Safe read-only script
"""

import json
import yaml
from datetime import datetime

from email_service import EmailService
from qbo_integration import QBOIntegration
from tool_executor import ToolExecutor


def main():
    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    # Initialize services
    print("=" * 60)
    print("Initializing services...")
    print("=" * 60)
    
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
    
    print("\n" + "=" * 60)
    print("SEARCHING FOR JOB 25-180")
    print("=" * 60)
    
    # 1. Search job index / folders
    print("\n--- Step 1: Search Job Index/Folders ---")
    result = executor.execute("job_search", {"job_number": "25-180"})
    job_result = json.loads(result)
    print(json.dumps(job_result, indent=2))
    
    # 2. Search QBO invoices by invoice number
    print("\n--- Step 2: Search QBO Invoices by Number ---")
    result = executor.execute("qbo_search_invoices", {"invoice_number": "25-180"})
    invoice_result = json.loads(result)
    print(json.dumps(invoice_result, indent=2))
    
    # 3. Search QBO invoices by address
    print("\n--- Step 3: Search QBO Invoices by Address (Rankin) ---")
    result = executor.execute("qbo_search_invoices", {"address": "Rankin"})
    addr_result = json.loads(result)
    print(json.dumps(addr_result, indent=2))
    
    # 4. Search QBO projects for 25-180
    print("\n--- Step 4: Search QBO Projects for 25-180 ---")
    result = executor.execute("qbo_search_projects", {"name": "25-180"})
    project_result = json.loads(result)
    print(json.dumps(project_result, indent=2))
    
    # 5. Get job status
    print("\n--- Step 5: Get Job Status ---")
    result = executor.execute("job_get_status", {"job_number": "25-180"})
    status_result = json.loads(result)
    print(json.dumps(status_result, indent=2))
    
    # 6. Search emails for the address
    print("\n--- Step 6: Search Emails for 'Rankin Street' ---")
    result = executor.execute("email_search", {"query": "subject:Rankin OR body:Rankin Street"})
    email_result = json.loads(result)
    print(json.dumps(email_result, indent=2))
    
    # 7. Search emails for job number
    print("\n--- Step 7: Search Emails for '25-180' ---")
    result = executor.execute("email_search", {"query": "25-180"})
    email_result2 = json.loads(result)
    print(json.dumps(email_result2, indent=2))
    
    print("\n" + "=" * 60)
    print("QUERY COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
