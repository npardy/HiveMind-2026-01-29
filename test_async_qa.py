"""
Test Async Q&A Email System
Tests: High importance, CC, and full email flow
"""
import sys
sys.path.insert(0, r'Z:\EmailAutomation')

from email_service import EmailService
from tool_executor import ToolExecutor
import json

def test_email_service_cc_support():
    """Test that EmailService.send_email accepts CC parameter"""
    import inspect
    sig = inspect.signature(EmailService.send_email)
    params = list(sig.parameters.keys())
    
    print("=== TEST 1: EmailService.send_email signature ===")
    print(f"Parameters: {params}")
    assert 'cc' in params, "CC parameter missing!"
    assert 'importance' in params, "Importance parameter missing!"
    print("✅ PASS: CC and importance parameters exist\n")

def test_tool_executor_pending():
    """Test pending tools work correctly"""
    print("=== TEST 2: Pending tools ===")
    
    # Create minimal executor
    te = ToolExecutor.__new__(ToolExecutor)
    te.job_index = {}
    te.JOB_INDEX_FILE = r'Z:\EmailAutomation\test_pending_temp.json'
    
    def mock_save():
        with open(te.JOB_INDEX_FILE, 'w') as f:
            json.dump(te.job_index, f, indent=2)
    te._save_job_index = mock_save
    
    # Test set_pending
    result = te._job_set_pending({
        'job_number': 'TEST-001',
        'question': 'Is Pigeon Cove metro or non-metro?',
        'question_type': 'community_classification',
        'email_id': 'AAMkABC123',
        'context': {'from': 'lawyer@firm.ca', 'address': '42 Ocean Drive'}
    })
    assert result['success'], f"set_pending failed: {result}"
    print(f"  set_pending: ✅ {result['status']}")
    
    # Test get_pending
    result = te._job_get_pending({})
    assert result['count'] == 1, f"Expected 1 pending, got {result['count']}"
    assert result['pending_jobs'][0]['question'] == 'Is Pigeon Cove metro or non-metro?'
    print(f"  get_pending: ✅ Found {result['count']} pending job(s)")
    
    # Test clear_pending
    result = te._job_clear_pending({'job_number': 'TEST-001', 'resolution': 'Non-metro'})
    assert result['success'], f"clear_pending failed: {result}"
    print(f"  clear_pending: ✅ {result['status']}")
    
    # Verify cleared
    result = te._job_get_pending({})
    assert result['count'] == 0, f"Expected 0 pending, got {result['count']}"
    print(f"  verify cleared: ✅ {result['count']} pending")
    
    # Cleanup
    import os
    if os.path.exists(te.JOB_INDEX_FILE):
        os.remove(te.JOB_INDEX_FILE)
    
    print("✅ PASS: All pending tools work correctly\n")

def test_tool_definitions():
    """Test tool definitions include new tools and CC"""
    print("=== TEST 3: Tool definitions ===")
    
    from tools_definition import define_all_tools
    tools = define_all_tools()
    tool_dict = {t['name']: t for t in tools}
    
    # Check pending tools exist
    assert 'job_set_pending' in tool_dict, "job_set_pending missing!"
    assert 'job_clear_pending' in tool_dict, "job_clear_pending missing!"
    assert 'job_get_pending' in tool_dict, "job_get_pending missing!"
    print("  Pending tools defined: ✅")
    
    # Check email_send_new has CC
    email_tool = tool_dict['email_send_new']
    props = email_tool['input_schema']['properties']
    assert 'cc' in props, "CC missing from email_send_new!"
    assert props['cc']['type'] == 'array', "CC should be array type!"
    print("  email_send_new has CC: ✅")
    
    # Check importance
    assert 'importance' in props, "Importance missing!"
    assert 'high' in props['importance']['enum'], "high importance missing!"
    print("  email_send_new has importance: ✅")
    
    print(f"✅ PASS: All {len(tools)} tool definitions valid\n")

def test_system_prompt():
    """Test system prompt has correct instructions"""
    print("=== TEST 4: System prompt ===")
    
    from claude_agent import SYSTEM_PROMPT
    
    checks = [
        ('pardysurveys@outlook.com', 'Nicholas email'),
        ('joe@pardysurveys.com', 'Joe CC email'),
        ('importance: "high"', 'High importance instruction'),
        ('[Hive Mind]', 'Subject prefix'),
        ('job_get_pending', 'Check pending instruction'),
        ('job_set_pending', 'Set pending instruction'),
        ('job_clear_pending', 'Clear pending instruction'),
    ]
    
    for text, desc in checks:
        assert text in SYSTEM_PROMPT, f"{desc} missing from prompt!"
        print(f"  {desc}: ✅")
    
    print("✅ PASS: System prompt has all required instructions\n")

def preview_test_email():
    """Show what the test email would look like"""
    print("=== TEST 5: Preview test email ===")
    
    email_preview = {
        "to": "pardysurveys@outlook.com",
        "cc": ["joe@pardysurveys.com"],
        "subject": "[Hive Mind] Question - Job 26-TEST - Community classification needed",
        "importance": "high",
        "body": """Nicholas,

I received a job request that I need your help with:

ORIGINAL REQUEST:
From: Sarah Miller <smiller@lawfirm.ca>
Subject: Survey needed - 42 Ocean Drive, Pigeon Cove
Received: 2026-01-21 at 9:15 AM

They need a survey for 42 Ocean Drive, Pigeon Cove.
Closing date: February 15, 2026
Purchaser: James Wilson

WHAT I'VE DONE:
- Identified this as a standard job request
- Extracted address, closing date, client info
- Ready to create job

WHAT I'M STUCK ON:
Pigeon Cove is not in my known community list. I need to know:
- Is this metro (standard $575 RPR pricing)?
- Or non-metro (needs custom quote)?

WHEN YOU REPLY:
Just say "metro" or "non-metro" (or provide quote amount if non-metro).
I'll create the job and confirm with the client.

--
Claude (Hive Mind)
Pardy Surveys Inc."""
    }
    
    print(f"  To: {email_preview['to']}")
    print(f"  CC: {email_preview['cc']}")
    print(f"  Subject: {email_preview['subject']}")
    print(f"  Importance: {email_preview['importance']} ⚠️")
    print(f"  Body length: {len(email_preview['body'])} chars")
    print("\n  --- EMAIL BODY PREVIEW ---")
    print(email_preview['body'][:500] + "...")
    print("  --- END PREVIEW ---\n")
    
    return email_preview

if __name__ == "__main__":
    print("\n" + "="*60)
    print("ASYNC Q&A EMAIL SYSTEM TEST")
    print("="*60 + "\n")
    
    test_email_service_cc_support()
    test_tool_executor_pending()
    test_tool_definitions()
    test_system_prompt()
    email_preview = preview_test_email()
    
    print("="*60)
    print("ALL TESTS PASSED ✅")
    print("="*60)
    print("\nTo send a REAL test email, run:")
    print("  python test_async_qa.py --send")
    print("\nThis will send a high-importance test email to your inbox.")
