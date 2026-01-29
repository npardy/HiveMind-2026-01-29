"""
Final query - find original email mentioning Rankin
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
    
    print("=" * 60)
    print("SEARCHING FOR ORIGINAL EMAIL FOR JOB 25-180")
    print("=" * 60)
    
    # Get email history with contact
    print("\n--- Email history with gnolan@rvdslaw.ca ---")
    history = email_service.get_email_history_with_contact("gnolan@rvdslaw.ca", max_results=50)
    
    found_matches = []
    
    for email in history:
        subject = email.get('subject', '')
        snippet = email.get('snippet', '')
        date = email.get('date', '')
        direction = email.get('direction', '')
        
        # Check if mentions Rankin
        if 'rankin' in (subject + snippet).lower():
            found_matches.append(email)
            print(f"\n*** MATCH FOUND ***")
            print(f"Date: {date}")
            print(f"Direction: {direction}")
            print(f"Subject: {subject}")
            print(f"Preview: {snippet}")
    
    if not found_matches:
        print("\nNo direct mentions of 'Rankin' found.")
        print("\nShowing all emails with this contact:")
        for email in history[:10]:
            print(f"\n  Date: {email.get('date')}")
            print(f"  Direction: {email.get('direction')}")
            print(f"  Subject: {email.get('subject')}")
            print(f"  Preview: {email.get('snippet')[:80]}...")


if __name__ == "__main__":
    main()
