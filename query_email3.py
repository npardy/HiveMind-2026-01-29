"""
Final query - find original email mentioning Rankin - fixed
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
    print("SEARCHING FOR ORIGINAL EMAIL FOR JOB 25-180")
    print("=" * 60)
    
    # Get email history with contact - get more emails to look further back
    print("\n--- Email history with gnolan@rvdslaw.ca (50 emails) ---")
    history = email_service.get_email_history_with_contact("gnolan@rvdslaw.ca", max_results=50)
    
    print(f"Retrieved {len(history)} emails total")
    
    found_matches = []
    
    for email in history:
        subject = email.get('subject', '') or ''
        snippet = email.get('snippet', '') or ''
        date = email.get('date', '') or ''
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
        print("\nNo direct mentions of 'Rankin' found in snippets.")
        print("\nShowing received emails around September 2025 (job created before Sep 19):")
        
        sept_emails = [e for e in history if '2025-09' in (e.get('date', '') or '')]
        if sept_emails:
            for email in sept_emails:
                direction = email.get('direction', '')
                if direction == 'received':
                    print(f"\n  Date: {email.get('date')}")
                    print(f"  Subject: {email.get('subject')}")
                    preview = email.get('snippet') or ''
                    print(f"  Preview: {preview[:100]}...")
        
        print("\n\nALL received emails from gnolan:")
        for email in history:
            if email.get('direction') == 'received':
                print(f"\n  {email.get('date')}: {email.get('subject')}")


if __name__ == "__main__":
    main()
