"""
Get parent customer and check for area data
"""

import json
import yaml
import os

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
    print("GET PARENT CUSTOMER (ID 43)")
    print("=" * 60)
    
    # Query the customer directly
    customer = qbo.find_customer_by_id("43")
    if customer:
        print(json.dumps(customer, indent=2, default=str))
    else:
        # Try using the API directly
        print("Direct query failed, trying name search...")
        customer = qbo.find_customer_by_name("Gary Nolan")
        if customer:
            print(json.dumps(customer, indent=2, default=str))


if __name__ == "__main__":
    main()
