"""Test nas_read_file through full tool executor - simulating API call."""
import yaml
import json

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

# Simulate exactly what Claude API would do
print('=== Simulating Claude API tool call ===')
print()

tool_name = 'nas_read_file'
tool_params = {
    'path': r"Z:\Jobs\2025\25-180 - Van Driel Law - 9 Rankin Street, St. John's\Description & Reports\25-180-1.docx",
    'max_lines': 20
}

print(f'Tool: {tool_name}')
print(f'Params: {tool_params}')
print()

result = te.execute(tool_name, tool_params)
parsed = json.loads(result)

print(f"Response type: {parsed.get('type', 'error')}")
print(f"Paragraphs: {parsed.get('paragraphs', 'N/A')}")
print()
print('Content returned to Claude:')
print('-' * 50)
content = parsed.get('content', parsed.get('error', 'No content'))
print(content[:800])
print('-' * 50)
print()
print(f'Approx tokens: ~{len(result.split())} words')
print('(vs 40K+ garbage tokens before fix)')
