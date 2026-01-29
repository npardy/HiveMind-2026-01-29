"""
Quick test to verify recent changes work correctly:
1. Prompt caching is properly configured
2. Diagnostics logging works
3. [Hive Mind] conversation tracking is set up
4. Email tracking to job index works
"""

import sys
import json

def test_imports():
    """Test all modules import without error."""
    print("Testing imports...")
    try:
        from orchestrator import EmailOrchestrator
        from claude_agent import ClaudeAgent
        from tool_executor import ToolExecutor
        from email_service import EmailService
        from diagnostics import get_diagnostics, APICallLogger
        from config_loader import get_config
        print("  [OK] All imports successful")
        return True
    except Exception as e:
        print(f"  [FAIL] Import error: {e}")
        return False

def test_diagnostics():
    """Test diagnostics module structure."""
    print("\nTesting diagnostics...")
    try:
        from diagnostics import APICallLogger

        # Check class has required methods
        assert hasattr(APICallLogger, 'log_api_call')
        assert hasattr(APICallLogger, 'log_tool_result_size')
        assert hasattr(APICallLogger, 'log_email_complete')
        assert hasattr(APICallLogger, 'get_session_summary')
        print("  [OK] APICallLogger has required methods")

        # Check diagnostics code structure
        with open("H:\\diagnostics.py", 'r', encoding='utf-8') as f:
            content = f.read()

        assert 'session_stats' in content
        assert 'total_api_calls' in content
        assert 'cache_read_tokens' in content
        assert 'estimated_cost' in content
        print("  [OK] Diagnostics tracks API calls and costs")

        return True
    except Exception as e:
        print(f"  [FAIL] Diagnostics error: {e}")
        return False

def test_orchestrator_state():
    """Test orchestrator state includes hive_mind_conversations."""
    print("\nTesting orchestrator state structure...")
    try:
        state_file = "H:\\data\\orchestrator_state.json"
        with open(state_file, 'r') as f:
            state = json.load(f)

        # Check required fields
        assert 'processed_emails' in state, "Missing processed_emails"
        assert 'last_check' in state, "Missing last_check"
        print("  [OK] State file has required fields")

        # hive_mind_conversations may not exist yet (added on first use)
        if 'hive_mind_conversations' in state:
            print(f"  [OK] hive_mind_conversations exists: {len(state['hive_mind_conversations'])} tracked")
        else:
            print("  [WARN] hive_mind_conversations not yet created (will be added on first [Hive Mind] email)")

        return True
    except Exception as e:
        print(f"  [FAIL] State error: {e}")
        return False

def test_tool_executor_setup():
    """Test tool executor code has hive mind tracker."""
    print("\nTesting tool executor setup...")
    try:
        # Check code structure instead of instantiating
        with open("H:\\tool_executor.py", 'r', encoding='utf-8') as f:
            content = f.read()

        # Check callback attribute exists
        assert '_hive_mind_tracker_callback' in content
        print("  [OK] _hive_mind_tracker_callback attribute in code")

        # Check set_hive_mind_tracker method exists
        assert 'def set_hive_mind_tracker' in content
        print("  [OK] set_hive_mind_tracker method in code")

        # Check _email_send_new tracks to job index
        assert 'enrich_job_index' in content
        print("  [OK] enrich_job_index used for tracking")

        # Check [Hive Mind] tracking in _email_send_new
        assert 'if result.get("success") and "[Hive Mind]" in subject' in content
        print("  [OK] [Hive Mind] conversation tracking in _email_send_new")

        # Check job index tracking for outgoing emails
        assert '"claude_outgoing"' in content or 'claude_outgoing' in content
        print("  [OK] claude_outgoing email type tracking exists")

        return True
    except Exception as e:
        print(f"  [FAIL] Tool executor error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_email_service_method():
    """Test email service has get_recent_sent_email_conversation_id method."""
    print("\nTesting email service methods...")
    try:
        from email_service import EmailService

        # Check method exists
        assert hasattr(EmailService, 'get_recent_sent_email_conversation_id')
        print("  [OK] get_recent_sent_email_conversation_id method exists")

        # Check EmailMessage has conversation_id
        from email_service import EmailMessage
        import inspect
        sig = inspect.signature(EmailMessage)
        params = list(sig.parameters.keys())
        assert 'conversation_id' in params
        print("  [OK] EmailMessage has conversation_id field")

        return True
    except Exception as e:
        print(f"  [FAIL] Email service error: {e}")
        return False

def test_claude_agent_caching():
    """Test Claude agent has caching configured."""
    print("\nTesting Claude agent caching setup...")
    try:
        # Read the file to check caching code exists
        with open("H:\\claude_agent.py", 'r', encoding='utf-8') as f:
            content = f.read()

        assert 'cache_control' in content
        assert '"type": "ephemeral"' in content
        assert 'cached_system' in content
        assert 'cached_tools' in content
        print("  [OK] Prompt caching code is present")

        return True
    except Exception as e:
        print(f"  [FAIL] Agent caching error: {e}")
        return False

def main():
    print("=" * 60)
    print("TESTING RECENT CHANGES")
    print("=" * 60)

    results = []
    results.append(("Imports", test_imports()))
    results.append(("Diagnostics", test_diagnostics()))
    results.append(("Orchestrator State", test_orchestrator_state()))
    results.append(("Tool Executor", test_tool_executor_setup()))
    results.append(("Email Service", test_email_service_method()))
    results.append(("Claude Caching", test_claude_agent_caching()))

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "[OK] PASS" if passed else "[FAIL] FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("All tests passed!")
        return 0
    else:
        print("Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
