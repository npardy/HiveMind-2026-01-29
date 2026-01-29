"""
Deep query for Job 25-180 - Get customer details and find original email
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
    
    print("=" * 60)
    print("DEEP QUERY FOR JOB 25-180")
    print("=" * 60)
    
    # 1. Get full invoice details
    print("\n--- Get Full Invoice Details (ID: 11183) ---")
    result = executor.execute("qbo_get_invoice", {"invoice_id": "11183"})
    inv_detail = json.loads(result)
    print(json.dumps(inv_detail, indent=2))
    
    # 2. Search customers for Van Driel
    print("\n--- Search Customers: Van Driel ---")
    result = executor.execute("qbo_search_customers", {"name": "Van Driel"})
    cust_result = json.loads(result)
    print(json.dumps(cust_result, indent=2))
    
    # 3. Try simpler email searches
    print("\n--- Search Emails: 'Rankin' only ---")
    result = executor.execute("email_search", {"query": "Rankin"})
    email1 = json.loads(result)
    print(f"Found: {email1.get('count', 0)} emails")
    if email1.get('emails'):
        for e in email1['emails'][:5]:
            print(f"  - {e.get('received')}: {e.get('subject')} (from {e.get('sender_email')})")
    
    # 4. Search for Van Driel emails
    print("\n--- Search Emails: 'from:vandriel' ---")
    result = executor.execute("email_search", {"query": "from:vandriel"})
    email2 = json.loads(result)
    print(f"Found: {email2.get('count', 0)} emails")
    if email2.get('emails'):
        for e in email2['emails'][:5]:
            print(f"  - {e.get('received')}: {e.get('subject')} (from {e.get('sender_email')})")
    
    # 5. Check the job folder for emails
    print("\n--- Check Job Folder for saved emails ---")
    emails_path = "Z:\\Jobs\\2025\\25-180 - Van Driel Law - 9 Rankin Street, St. John's\\Reference & Research\\Emails"
    result = executor.execute("nas_list_directory", {"path": emails_path})
    folder_emails = json.loads(result)
    print(json.dumps(folder_emails, indent=2))
    
    # 6. Check Correspondence folder  
    print("\n--- Check Correspondence folder ---")
    corr_path = "Z:\\Jobs\\2025\\25-180 - Van Driel Law - 9 Rankin Street, St. John's\\Correspondance"
    result = executor.execute("nas_list_directory", {"path": corr_path})
    corr_result = json.loads(result)
    print(json.dumps(corr_result, indent=2))


if __name__ == "__main__":
    main()
