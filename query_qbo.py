"""
Search by domain and get more QBO details
"""

import json
import yaml

from email_service import EmailService
from qbo_integration import QBOIntegration


def main():
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
    
    print("=" * 60)
    print("DETAILED SEARCH FOR JOB 25-180")
    print("=" * 60)
    
    # 1. Get full project details from QBO
    print("\n--- QBO Project Details ---")
    project = qbo.find_project_by_name("25-180")
    if project:
        print(f"Project ID: {project.get('Id')}")
        print(f"Display Name: {project.get('DisplayName')}")
        print(f"Description: {project.get('Description')}")
        print(f"Customer Ref: {project.get('CustomerRef')}")
        # Print all fields
        print(f"\nFull project data:")
        print(json.dumps(project, indent=2, default=str))
    
    # 2. Get the customer referenced by customer ID 2317
    print("\n--- QBO Customer Details (Parent Customer) ---")
    # The invoice shows customer_id 2317 - let's get more info
    customers = qbo.get_customers()
    for c in customers:
        if c.get('Id') == '2317':
            print(json.dumps(c, indent=2, default=str))
            break
    
    # 3. Check if there's a parent customer
    print("\n--- Looking for Parent Customer relationship ---")
    for c in customers[:50]:  # Check first 50
        if '25-180' in c.get('DisplayName', ''):
            print(f"Found: {c.get('DisplayName')} - ID: {c.get('Id')}")
            if c.get('ParentRef'):
                parent_id = c.get('ParentRef', {}).get('value')
                print(f"  Parent ID: {parent_id}")
                # Find parent
                for p in customers:
                    if p.get('Id') == parent_id:
                        print(f"  Parent Name: {p.get('DisplayName')}")
                        print(f"  Parent Email: {p.get('PrimaryEmailAddr', {}).get('Address')}")


if __name__ == "__main__":
    main()
