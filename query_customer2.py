"""
Get parent customer by name
"""

import json
import yaml

from qbo_integration import QBOIntegration


def main():
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    qbo = QBOIntegration(
        client_id=config['quickbooks']['client_id'],
        client_secret=config['quickbooks']['client_secret'],
        redirect_uri=config['quickbooks']['redirect_uri'],
        environment=config['quickbooks']['environment']
    )
    
    print("=" * 60)
    print("SEARCH FOR GARY NOLAN CUSTOMER")
    print("=" * 60)
    
    # Search by name
    customer = qbo.find_customer_by_name("Gary Nolan")
    if customer:
        print(json.dumps(customer, indent=2, default=str))
    else:
        print("Not found by name, trying email...")
        customer = qbo.find_customer_by_email("gnolan@rvdslaw.ca")
        if customer:
            print(json.dumps(customer, indent=2, default=str))


if __name__ == "__main__":
    main()
