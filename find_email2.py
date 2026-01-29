"""
Find original email - pagination approach
"""

import json
import yaml

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
    print("SEARCHING FOR ORIGINAL EMAIL - RANKIN STREET")
    print("=" * 60)
    
    # Use filter with proper date format (ISO 8601)
    filter_query = "from/emailAddress/address eq 'gnolan@rvdslaw.ca' and receivedDateTime ge 2025-09-01T00:00:00Z and receivedDateTime le 2025-09-20T23:59:59Z"
    
    endpoint = f"/me/messages?$filter={filter_query}&$top=50&$orderby=receivedDateTime desc&$select=subject,receivedDateTime,from,bodyPreview,id"
    
    print(f"\nQuerying Graph API...")
    result = email_service._make_graph_call(endpoint)
    
    if result and result.get('value'):
        print(f"Found {len(result['value'])} emails\n")
        
        for msg in result['value']:
            date = msg.get('receivedDateTime', '')[:19]
            subject = msg.get('subject', '')
            preview = (msg.get('bodyPreview', '') or '')[:150]
            msg_id = msg.get('id', '')
            
            print(f"Date: {date}")
            print(f"Subject: {subject}")
            print(f"Preview: {preview}...")
            
            if 'rankin' in (subject + preview).lower():
                print("\n*** MENTIONS RANKIN - THIS IS LIKELY THE ORIGINAL ***")
                print(f"Full Message ID: {msg_id}")
            print("-" * 50)
    elif result:
        print(f"Result returned but no 'value': {json.dumps(result, indent=2)}")
    else:
        print("API returned None - checking error...")
        
        # Try simpler query
        print("\nTrying simpler query...")
        simple_filter = "from/emailAddress/address eq 'gnolan@rvdslaw.ca'"
        endpoint2 = f"/me/messages?$filter={simple_filter}&$top=100&$orderby=receivedDateTime asc&$select=subject,receivedDateTime,bodyPreview"
        
        result2 = email_service._make_graph_call(endpoint2)
        if result2 and result2.get('value'):
            print(f"Found {len(result2['value'])} total emails from gnolan, sorted oldest first\n")
            
            for msg in result2['value']:
                date = msg.get('receivedDateTime', '')[:10]
                subject = msg.get('subject', '')
                preview = (msg.get('bodyPreview', '') or '')[:80]
                
                # Only show September 2025 ones
                if '2025-09' in date:
                    print(f"{date}: {subject}")
                    if 'rankin' in (subject + preview).lower():
                        print("  ^^^ MENTIONS RANKIN")


if __name__ == "__main__":
    main()
