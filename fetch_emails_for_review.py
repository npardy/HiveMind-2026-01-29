"""
Fetch emails for review - Johnny Appleseed and internal [Hive Mind] emails
Run this on the NAS where the email tokens are cached.
"""
import sys
import json
from datetime import datetime, timedelta

# Add HiveMind to path
sys.path.insert(0, '/volume1/HiveMind')

from config_loader import ConfigLoader
from email_service import EmailService

def main():
    # Load config
    config = ConfigLoader()

    # Initialize email service
    email = EmailService(
        config.email_client_id,
        config.email_client_secret,
        config.email_redirect_uri
    )

    if not email.authenticate(allow_interactive=False):
        print("ERROR: Could not authenticate to email")
        return

    print("=" * 80)
    print("FETCHING EMAILS FOR REVIEW")
    print("=" * 80)

    # Cutoff: 8pm on Jan 26, 2026
    cutoff = datetime(2026, 1, 26, 20, 0, 0)

    # 1. Get email history with johnnyappleseednl@outlook.com
    print("\n\n" + "=" * 80)
    print("EMAILS WITH: johnnyappleseednl@outlook.com")
    print("=" * 80)

    johnny_emails = email.get_email_history_with_contact(
        "johnnyappleseednl@outlook.com",
        max_results=50
    )

    for e in johnny_emails:
        email_date = e.get('received_date') or e.get('sent_date', '')
        # Parse date and filter
        try:
            if isinstance(email_date, str):
                # Try parsing
                for fmt in ['%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S%z', '%Y-%m-%dT%H:%M:%S%z']:
                    try:
                        dt = datetime.strptime(email_date.replace('+00:00', 'Z').replace(' ', 'T'), fmt.replace('%z', 'Z'))
                        break
                    except:
                        continue
            else:
                dt = email_date
        except:
            dt = datetime.now()  # Include if can't parse

        print(f"\n{'='*60}")
        print(f"DATE: {email_date}")
        print(f"FROM: {e.get('from', 'Unknown')}")
        print(f"TO: {e.get('to', 'Unknown')}")
        print(f"SUBJECT: {e.get('subject', 'No subject')}")
        print(f"-" * 60)
        print(f"BODY:\n{e.get('body', 'No body')[:3000]}")
        print(f"{'='*60}")

    # 2. Get [Hive Mind] emails (internal communications)
    print("\n\n" + "=" * 80)
    print("INTERNAL [HIVE MIND] EMAILS (pardysurveys to pardysurveys)")
    print("=" * 80)

    # Search for [Hive Mind] emails
    try:
        hive_mind_emails = email.search_emails(
            query="[Hive Mind]",
            max_results=30
        )

        for e in hive_mind_emails:
            print(f"\n{'='*60}")
            print(f"DATE: {e.received_datetime if hasattr(e, 'received_datetime') else 'Unknown'}")
            print(f"FROM: {e.sender if hasattr(e, 'sender') else 'Unknown'}")
            print(f"SUBJECT: {e.subject if hasattr(e, 'subject') else 'No subject'}")
            print(f"-" * 60)
            body = e.body if hasattr(e, 'body') else str(e)
            print(f"BODY:\n{body[:3000]}")
            print(f"{'='*60}")
    except Exception as ex:
        print(f"Error searching [Hive Mind] emails: {ex}")

    print("\n\nDONE")

if __name__ == "__main__":
    main()
