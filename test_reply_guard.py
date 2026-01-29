#!/usr/bin/env python3
"""
Test the reply guard mechanism.

Tests:
1. First reply succeeds
2. Second reply to same message_id is blocked
3. After reset_session_state(), can reply again
4. Different message_ids can both get replies
"""

import sys
import os
import json
sys.path.insert(0, os.path.dirname(__file__))

from unittest.mock import MagicMock, patch


def parse_result(result_str):
    """Parse JSON result string to dict."""
    return json.loads(result_str)


def test_reply_guard():
    """Test that duplicate replies are blocked."""
    print("=" * 60)
    print("TEST: Reply Guard Mechanism")
    print("=" * 60)

    # Mock the dependencies
    mock_qbo = MagicMock()
    mock_email = MagicMock()
    mock_email.reply_to_email = MagicMock(return_value=True)

    # Import after mocking
    from tool_executor import ToolExecutor

    # Create executor with mocks
    with patch('tool_executor.get_config') as mock_config:
        mock_cfg = MagicMock()
        mock_cfg.jobs_folder = "Z:\\Jobs"
        mock_cfg.data_sync_folder = "Z:\\Data Sync"
        mock_cfg.flagged_folder = "H:\\flagged"
        mock_cfg.job_index_file = "H:\\data\\job_index.json"
        mock_cfg.proposals_folder = "Z:\\Proposals"
        mock_config.return_value = mock_cfg

        executor = ToolExecutor(mock_qbo, mock_email)

    # Set up a fake current email
    mock_current_email = MagicMock()
    mock_current_email.message_id = "test-message-123"
    executor.set_current_email(mock_current_email)

    print("\n1. First reply should succeed...")
    result1 = parse_result(executor.execute("email_send_reply", {"body": "First reply"}))
    print(f"   Result: {result1}")
    assert result1.get("success") == True, f"First reply should succeed: {result1}"
    print("   [PASS]")

    print("\n2. Second reply to SAME message should be BLOCKED...")
    result2 = parse_result(executor.execute("email_send_reply", {"body": "Second reply"}))
    print(f"   Result: {result2}")
    assert result2.get("success") == False, f"Second reply should be blocked: {result2}"
    assert result2.get("skipped") == True or "Already replied" in str(result2.get("error", "")), f"Should indicate skipped: {result2}"
    print("   [PASS]")

    print("\n3. After reset_session_state(), should be able to reply again...")
    executor.reset_session_state()
    result3 = parse_result(executor.execute("email_send_reply", {"body": "Reply after reset"}))
    print(f"   Result: {result3}")
    assert result3.get("success") == True, f"Reply after reset should succeed: {result3}"
    print("   [PASS]")

    print("\n4. Different message_id should allow reply...")
    executor.reset_session_state()
    mock_current_email.message_id = "different-message-456"
    executor.set_current_email(mock_current_email)

    # Reply to first message
    result4a = parse_result(executor.execute("email_send_reply", {"body": "Reply to message A", "message_id": "msg-A"}))
    print(f"   Reply to msg-A: {result4a}")
    assert result4a.get("success") == True, f"Reply to msg-A should succeed: {result4a}"

    # Reply to different message
    result4b = parse_result(executor.execute("email_send_reply", {"body": "Reply to message B", "message_id": "msg-B"}))
    print(f"   Reply to msg-B: {result4b}")
    assert result4b.get("success") == True, f"Reply to msg-B should succeed: {result4b}"

    # Second reply to msg-A should fail
    result4c = parse_result(executor.execute("email_send_reply", {"body": "Second reply to message A", "message_id": "msg-A"}))
    print(f"   Second reply to msg-A: {result4c}")
    assert result4c.get("success") == False, f"Second reply to msg-A should be blocked: {result4c}"
    print("   [PASS]")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)
    return True


def test_inbox_only_fetch():
    """Test that get_emails_since uses inbox endpoint."""
    print("\n" + "=" * 60)
    print("TEST: Inbox-Only Email Fetching")
    print("=" * 60)

    # Read the email_service.py and verify the endpoint
    with open("H:\\email_service.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Find the get_emails_since method
    if "/me/mailFolders/inbox/messages" in content:
        print("   [PASS] get_emails_since uses /mailFolders/inbox/messages endpoint")
        return True
    else:
        print("   [FAIL] get_emails_since should use inbox endpoint")
        return False


def test_no_body_truncation():
    """Test that email body is not truncated."""
    print("\n" + "=" * 60)
    print("TEST: No Email Body Truncation")
    print("=" * 60)

    with open("H:\\claude_agent.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Check that we're NOT truncating
    if "email_msg.body[:12000]" in content or "email_msg.body[:6000]" in content:
        print("   [FAIL] Email body is still being truncated")
        return False

    if "{email_msg.body if email_msg.body else" in content:
        print("   [PASS] Email body is passed without truncation")
        return True
    else:
        print("   [?] Could not verify - check manually")
        return False


if __name__ == "__main__":
    all_passed = True

    try:
        all_passed &= test_reply_guard()
    except Exception as e:
        print(f"   [FAIL]: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False

    try:
        all_passed &= test_inbox_only_fetch()
    except Exception as e:
        print(f"   [FAIL]: {e}")
        all_passed = False

    try:
        all_passed &= test_no_body_truncation()
    except Exception as e:
        print(f"   [FAIL]: {e}")
        all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("ALL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED")
    print("=" * 60)

    sys.exit(0 if all_passed else 1)
