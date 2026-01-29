"""Send a test email to trigger the Hive Mind system."""
import sys
import yaml
from email_service import EmailService

with open('H:\\config.yaml') as f:
    config = yaml.safe_load(f)

email = EmailService(
    config['email']['client_id'],
    config['email']['client_secret'],
    config['email']['redirect_uri']
)
email.authenticate(allow_interactive=False)

# Send test email
result = email.send_email(
    to_email='pardysurveys@outlook.com',
    subject='[TEST] Token logging test - please ignore',
    body='This is a test email to trigger the Hive Mind system and verify token logging is working.\n\nPlease ignore this message.'
)
print('Email sent!' if result else 'Failed to send')
