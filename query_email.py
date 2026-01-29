"""
Final query - find original email and check for area data
"""

import json
import yaml
from datetime import datetime

from email_service import EmailService
from qbo_integration import QBOIntegration


def main():
    # Load config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    email_service = EmailService(
        client_id=config['email']['client_id'],
        client_secret=config['email']['client_secret'],
        redirect_uri=config['email']['redirect_uri']
    )
    
    print("=" * 60)
    print("SEARCHING FOR ORIGINAL EMAIL")
    print("=" * 60)
    
    # Try get email history with the contact
    print("\n--- Email history with gnolan@rvdslaw.ca ---")
    try:
        history = email_service.get_email_history_with_contact("gnolan@rvdslaw.ca", max_results=20)
        print(f"Found {len(history)} emails")
        
        # Look for emails mentioning Rankin or 9 Rankin
        for email in history:
            subject = email.get('subject', '') if isinstance(email, dict) else str(email)
            body_preview = email.get('body', '')[:300] if isinstance(email, dict) else ''
            received = email.get('received', '') if isinstance(email, dict) else ''
            
            if 'rankin' in (subject + body_preview).lower() or '25-180' in (subject + body_preview):
                print("\n*** POTENTIAL MATCH ***")
                print(f"Date: {received}")
                print(f"Subject: {subject}")
                print(f"Preview: {body_preview[:200]}...")
                print("-" * 40)
                
    except Exception as e:
        print(f"Error getting email history: {e}")
    
    # Try searching with different patterns
    print("\n--- Try basic folder searches ---")
    
    # Check for any received emails
    print("\nListing Inbox...")
    try:
        from email_service import EmailMessage
        msgs = email_service.get_unread_emails(folder='Inbox', max_results=5)
        print(f"Got {len(msgs)} unread emails (confirms connection works)")
    except Exception as e:
        print(f"Inbox access error: {e}")


if __name__ == "__main__":
    main()
