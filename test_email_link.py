"""Test email linking"""
import json
import yaml
from tool_executor import ToolExecutor
from qbo_integration import QBOIntegration
from email_service import EmailService

with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

email_service = EmailService(
    client_id=config['email']['client_id'],
    client_secret=config['email']['client_secret'],
    redirect_uri=config['email']['redirect_uri']
)

qbo = QBOIntegration(
    client_id=config['quickbooks']['client_id'],
    client_secret=config['quickbooks']['client_secret'],
    redirect_uri=config['quickbooks']['redirect_uri'],
    environment=config['quickbooks']['environment']
)

executor = ToolExecutor(qbo, email_service)

# Test: manually call link_email_to_job
executor._link_email_to_job(
    job_number='25-180',
    email_info={
        'message_id': 'TEST123',
        'subject': 'RE: Survey for 9 Rankin Street',
        'from': 'gnolan@rvdslaw.ca',
        'date': '2026-01-19T10:00:00Z',
        'direction': 'inbound'
    },
    summary='Client confirming closing date moved to Feb 1',
    key_info={'closing_date': '2026-02-01', 'urgency': 'normal'}
)

# Verify
with open('job_index.json', 'r') as f:
    idx = json.load(f)

emails = idx.get('25-180', {}).get('emails', [])
print(f'Emails linked to 25-180: {len(emails)}')
for e in emails:
    subj = e.get('subject', '?')
    print(f'  - {subj}')
    if e.get('summary'):
        print(f'    Summary: {e.get("summary")}')
    if e.get('key_info'):
        print(f'    Key info: {e.get("key_info")}')
