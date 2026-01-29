"""
Find original email from September 2025
"""

import json
import yaml
from datetime import datetime

from email_service import EmailService


def main():
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    email_service = EmailService(
        client_id=config['email']['client_id'],
        client_secret=config['email']['client_secret'],
        redirect_uri=config['email']['redirect_uri']
    )
    
    print("=" * 60)
    print("SEARCHING FOR ORIGINAL EMAIL - SEPTEMBER 2025")
    print("=" * 60)
    
    # Use Graph API filter for September 2025 emails
    # The project was created 2025-09-15, so look around that date
    
    # Build filter for emails from gnolan around mid-September
    filter_query = "(from/emailAddress/address eq 'gnolan@rvdslaw.ca') and receivedDateTime ge 2025-09-01 and receivedDateTime le 2025-09-20"
    
    endpoint = f"/me/messages?$filter={filter_query}&$top=20&$orderby=receivedDateTime desc&$select=subject,receivedDateTime,from,bodyPreview,id"
    
    result = email_service._make_graph_call(endpoint)
    
    if result and result.get('value'):
        print(f"Found {len(result['value'])} emails from September 2025\n")
        
        for msg in result['value']:
            date = msg.get('receivedDateTime', '')[:19]
            subject = msg.get('subject', '')
            preview = msg.get('bodyPreview', '')[:150]
            msg_id = msg.get('id', '')
            
            print(f"Date: {date}")
            print(f"Subject: {subject}")
            print(f"Preview: {preview}...")
            print(f"Message ID: {msg_id[:50]}...")
            
            # Check if mentions Rankin
            if 'rankin' in (subject + preview).lower():
                print("*** MENTIONS RANKIN - THIS IS LIKELY THE ORIGINAL ***")
            print("-" * 50)
    else:
        print("No results or API error")
        print(f"Result: {result}")


if __name__ == "__main__":
    main()
