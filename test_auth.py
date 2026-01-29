"""Test Microsoft Graph authentication."""
import yaml
import os

# Delete old token cache to force re-auth
cache_file = "graph_token_cache.json"
try:
    if os.path.exists(cache_file):
        os.remove(cache_file)
        print(f"Deleted {cache_file}")
except Exception as e:
    print(f"Could not delete cache: {e}")

# Load config
with open('config.yaml') as f:
    config = yaml.safe_load(f)

from email_service import EmailService

email = EmailService(
    client_id=config['email']['client_id'],
    client_secret=config['email']['client_secret']
)

if email.authenticate():
    print("Authentication successful!")
    # Quick test - get inbox count
    inbox = email.get_unread_emails(max_results=5)
    print(f"Found {len(inbox)} unread emails")
else:
    print("Authentication FAILED")
