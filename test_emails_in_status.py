"""Test that job_get_status returns emails from hive."""
import yaml
with open('config.yaml') as f:
    config = yaml.safe_load(f)

from tool_executor import ToolExecutor
from qbo_integration import QBOIntegration
from email_service import EmailService

email = EmailService(
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

te = ToolExecutor(qbo=qbo, email_service=email)
result_str = te.execute('job_get_status', {'job_number': '25-180'})

import json
result = json.loads(result_str)

print('=== job_get_status now returns emails and qbo from hive ===')
print()
emails = result.get('emails', [])
print(f'emails count: {len(emails)}')
for e in emails:
    print(f'  - {e.get("subject")}: {e.get("summary", "no summary")}')
print()
print(f'qbo: {result.get("qbo", {})}')
