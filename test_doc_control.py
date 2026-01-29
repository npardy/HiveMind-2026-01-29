"""Test job_get_status for 25-170 (multiple documents)"""
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

print("=" * 80)
print("DOCUMENT CONTROL FOR 25-170")
print("=" * 80)

result = executor.execute("job_get_status", {"job_number": "25-170"})
data = json.loads(result)

print(json.dumps(data.get("document_control"), indent=2))
