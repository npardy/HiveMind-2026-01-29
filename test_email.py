"""Test Email Service"""
import sys
sys.path.insert(0, 'H:\\')

import yaml
from email_service import EmailService

# Load config
with open('config.yaml') as f:
    config = yaml.safe_load(f)

# Initialize
email = EmailService(
    config['email']['client_id'],
    config['email']['client_secret'],
    config['email']['redirect_uri']
)

# Test authentication (silent - won't open browser)
if email.authenticate(allow_interactive=False):
    print("[PASS] Email authenticated (cached token)")
    
    # Test list folders
    folders = email.list_folders()
    print(f"[PASS] Found {len(folders)} email folders")
    
    # Test get unread
    unread = email.get_unread_emails(max_results=5)
    print(f"[PASS] Unread emails: {len(unread)} found")
else:
    print("[WARN] Could not authenticate silently - may need interactive auth")
