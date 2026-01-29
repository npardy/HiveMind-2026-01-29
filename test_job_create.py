"""Test job_create with new structure"""
import sys
import json
sys.path.insert(0, '.')

from tool_executor import ToolExecutor

# Create a mock QBO that returns a test job number
class MockQBO:
    access_token = None  # No token = skip QBO creation
    
    def get_next_job_number(self):
        return "26-TEST"

# Initialize with mock QBO
te = ToolExecutor(qbo=MockQBO(), email_service=None)

print("Creating test job...")
print()

# Call the internal method directly
result = te._job_create({
    "client_name": "Test Lawyer",
    "client_email": "test@test.com",
    "client_business": "Test Law Firm",
    "property_address": "999 Test Street",
    "community": "St. John's",
    "due_date": "2026-02-15",
    "job_type": "survey_and_rpr",
    "conversation_id": "test-conversation-123",
    "message_id": "test-message-456"
})

print("RESULT:")
print(json.dumps(result, indent=2))

# Now show the index entry
job_number = result.get('job_number')
if job_number and job_number in te.job_index:
    print()
    print("=" * 60)
    print(f"INDEX ENTRY FOR {job_number}:")
    print("=" * 60)
    print(json.dumps(te.job_index[job_number], indent=2))
else:
    print(f"Job {job_number} not found in index!")
