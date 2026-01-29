"""
Hive Mind Comprehensive Test Suite
==================================
Tests every component and the full agent loop to ensure everything works.
Run with: python test_hive_mind.py
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


class TestResults:
    """Collect and display test results."""
    def __init__(self):
        self.tests: List[Tuple[str, str, bool, str, float]] = []  # (category, name, passed, message, duration)
        self.start_time = time.time()

    def add(self, category: str, name: str, passed: bool, message: str = "", duration: float = 0):
        self.tests.append((category, name, passed, message, duration))
        symbol = "✓" if passed else "✗"
        status = "PASS" if passed else "FAIL"
        logger.info(f"  [{symbol}] {name}: {status}")
        if message:
            logger.info(f"      {message}")
        if duration > 0:
            logger.info(f"      Duration: {duration:.2f}s")

    def summary(self):
        total = len(self.tests)
        passed = sum(1 for t in self.tests if t[2])
        failed = total - passed

        logger.info("")
        logger.info("=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)

        # Group by category
        categories = {}
        for cat, name, p, msg, dur in self.tests:
            if cat not in categories:
                categories[cat] = {"passed": 0, "failed": 0, "tests": []}
            categories[cat]["tests"].append((name, p, msg, dur))
            if p:
                categories[cat]["passed"] += 1
            else:
                categories[cat]["failed"] += 1

        for cat, data in categories.items():
            cat_total = data["passed"] + data["failed"]
            logger.info(f"\n{cat}: {data['passed']}/{cat_total} passed")
            for name, p, msg, dur in data["tests"]:
                symbol = "✓" if p else "✗"
                logger.info(f"  [{symbol}] {name}")
                if not p and msg:
                    logger.info(f"      Error: {msg}")

        logger.info("")
        logger.info("-" * 60)
        total_time = time.time() - self.start_time
        logger.info(f"TOTAL: {passed}/{total} tests passed ({failed} failed)")
        logger.info(f"Total time: {total_time:.2f}s")
        logger.info("=" * 60)

        return failed == 0


def test_config_loader(results: TestResults):
    """Test configuration loading."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING: Config Loader")
    logger.info("=" * 60)

    try:
        from config_loader import get_config
        cfg = get_config()
        results.add("Config", "Import config_loader", True)

        # Test all path properties
        paths_to_test = [
            ("jobs_folder", cfg.jobs_folder),
            ("data_sync_folder", cfg.data_sync_folder),
            ("job_index_file", cfg.job_index_file),
            ("flagged_folder", cfg.flagged_folder),
            ("proposals_folder", cfg.proposals_folder),
            ("notification_queue", cfg.notification_queue),
            ("token_cache_graph", cfg.token_cache_graph),
            ("token_cache_qbo", cfg.token_cache_qbo),
        ]

        for name, path in paths_to_test:
            if path and len(path) > 0:
                results.add("Config", f"Path: {name}", True, path)
            else:
                results.add("Config", f"Path: {name}", False, "Empty or None")

        # Test credential properties (just check they exist, don't log values)
        creds = [
            ("email_client_id", cfg.email_client_id),
            ("anthropic_api_key", cfg.anthropic_api_key),
            ("qbo_client_id", cfg.qbo_client_id),
        ]
        for name, val in creds:
            if val and len(val) > 10:
                results.add("Config", f"Credential: {name}", True, f"Loaded ({len(val)} chars)")
            else:
                results.add("Config", f"Credential: {name}", False, "Missing or too short")

    except Exception as e:
        results.add("Config", "Config loading", False, str(e))


def test_file_paths(results: TestResults):
    """Test that critical paths exist."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING: File System Paths")
    logger.info("=" * 60)

    from config_loader import get_config
    cfg = get_config()

    paths_must_exist = [
        ("Jobs folder (current year)", os.path.join(cfg.jobs_folder, str(datetime.now().year))),
        ("Data Sync folder", cfg.data_sync_folder),
        ("Job index file", cfg.job_index_file),
        ("Graph token cache", cfg.token_cache_graph),
        ("QBO token cache", cfg.token_cache_qbo),
    ]

    for name, path in paths_must_exist:
        exists = os.path.exists(path)
        results.add("Paths", name, exists, path if exists else f"NOT FOUND: {path}")

    # Template folder
    year_short = str(datetime.now().year)[2:]
    template_path = os.path.join(cfg.jobs_folder, str(datetime.now().year), f"{year_short}-000 - Template")
    results.add("Paths", "Template folder", os.path.exists(template_path), template_path)


def test_job_index(results: TestResults):
    """Test job index loading and structure."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING: Job Index")
    logger.info("=" * 60)

    from config_loader import get_config
    cfg = get_config()

    try:
        with open(cfg.job_index_file, 'r') as f:
            job_index = json.load(f)

        results.add("Job Index", "Load job_index.json", True, f"{len(job_index)} jobs")

        # Check structure of a few jobs
        if job_index:
            sample_job_num = list(job_index.keys())[0]
            sample_job = job_index[sample_job_num]

            expected_fields = ["job_number", "created", "data_sync", "emails", "qbo"]
            for field in expected_fields:
                has_field = field in sample_job
                results.add("Job Index", f"Has field: {field}", has_field,
                           f"Sample job: {sample_job_num}")

        # Check for recent jobs
        recent_jobs = [j for j in job_index.values()
                      if j.get("created", "").startswith("202")]
        results.add("Job Index", "Has recent jobs", len(recent_jobs) > 0,
                   f"{len(recent_jobs)} jobs from 2020+")

    except Exception as e:
        results.add("Job Index", "Load job_index.json", False, str(e))


def test_email_service(results: TestResults):
    """Test email service authentication and basic operations."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING: Email Service (Microsoft Graph)")
    logger.info("=" * 60)

    from config_loader import get_config
    cfg = get_config()

    try:
        from email_service import EmailService
        results.add("Email", "Import EmailService", True)

        start = time.time()
        email_svc = EmailService(
            client_id=cfg.email_client_id,
            client_secret=cfg.email_client_secret,
            redirect_uri=cfg.email_redirect_uri,
            token_cache_file=cfg.token_cache_graph
        )
        results.add("Email", "Initialize EmailService", True, duration=time.time()-start)

        # Try silent auth (no browser popup)
        start = time.time()
        auth_success = email_svc.authenticate(allow_interactive=False)
        if auth_success:
            results.add("Email", "Silent authentication", True,
                       f"Token refreshed", duration=time.time()-start)

            # Try fetching recent emails
            start = time.time()
            since = datetime.now(timezone.utc) - timedelta(hours=24)
            emails = email_svc.get_emails_since(since)
            results.add("Email", "Fetch emails (24h)", True,
                       f"Found {len(emails)} emails", duration=time.time()-start)

            if emails:
                # Check email structure
                sample = emails[0]
                has_required = all(hasattr(sample, f) for f in
                                  ['message_id', 'subject', 'sender_email', 'body'])
                results.add("Email", "Email structure valid", has_required,
                           f"Sample: {sample.subject[:50]}..." if has_required else "Missing fields")
        else:
            results.add("Email", "Silent authentication", False,
                       "No cached token - need interactive auth first")

    except Exception as e:
        results.add("Email", "Email service test", False, str(e))


def test_qbo_integration(results: TestResults):
    """Test QuickBooks Online integration."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING: QuickBooks Online Integration")
    logger.info("=" * 60)

    from config_loader import get_config
    cfg = get_config()

    try:
        from qbo_integration import QBOIntegration
        results.add("QBO", "Import QBOIntegration", True)

        start = time.time()
        qbo = QBOIntegration(
            client_id=cfg.qbo_client_id,
            client_secret=cfg.qbo_client_secret,
            redirect_uri=cfg.qbo_redirect_uri,
            environment=cfg.qbo_environment,
            token_cache_file=cfg.token_cache_qbo
        )
        results.add("QBO", "Initialize QBOIntegration", True, duration=time.time()-start)

        # Check if tokens loaded
        if qbo.access_token:
            results.add("QBO", "Tokens loaded from cache", True)

            # Test API connection
            start = time.time()
            company = qbo.get_company_info()
            if company:
                results.add("QBO", "Get company info", True,
                           f"Connected to: {company.get('CompanyName')}",
                           duration=time.time()-start)

                # Test job number generation
                start = time.time()
                next_job = qbo.get_next_job_number()
                results.add("QBO", "Get next job number", True,
                           f"Next: {next_job}", duration=time.time()-start)

                # Test customer search
                start = time.time()
                customers = qbo._make_request('GET', '/query?query=SELECT * FROM Customer MAXRESULTS 5')
                if customers:
                    count = len(customers.get('QueryResponse', {}).get('Customer', []))
                    results.add("QBO", "Query customers", True,
                               f"Found {count} customers", duration=time.time()-start)

                # Test invoice search
                start = time.time()
                invoices = qbo.get_recent_invoices(limit=5)
                results.add("QBO", "Get recent invoices", True,
                           f"Found {len(invoices)} invoices", duration=time.time()-start)
            else:
                results.add("QBO", "Get company info", False, "API call returned None")
        else:
            results.add("QBO", "Tokens loaded from cache", False, "No access token")

    except Exception as e:
        results.add("QBO", "QBO test", False, str(e))


def test_tool_executor(results: TestResults):
    """Test tool executor initialization and basic tools."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING: Tool Executor")
    logger.info("=" * 60)

    from config_loader import get_config
    cfg = get_config()

    try:
        from tool_executor import ToolExecutor
        from qbo_integration import QBOIntegration
        from email_service import EmailService

        results.add("Tools", "Import ToolExecutor", True)

        # Initialize dependencies
        qbo = QBOIntegration(
            client_id=cfg.qbo_client_id,
            client_secret=cfg.qbo_client_secret,
            redirect_uri=cfg.qbo_redirect_uri,
            environment=cfg.qbo_environment,
            token_cache_file=cfg.token_cache_qbo
        )

        email_svc = EmailService(
            client_id=cfg.email_client_id,
            client_secret=cfg.email_client_secret,
            redirect_uri=cfg.email_redirect_uri,
            token_cache_file=cfg.token_cache_graph
        )

        start = time.time()
        executor = ToolExecutor(qbo, email_svc)
        results.add("Tools", "Initialize ToolExecutor", True,
                   duration=time.time()-start)

        # Check paths loaded from config
        paths_ok = (executor.JOBS_FOLDER == cfg.jobs_folder and
                   executor.DATA_SYNC_FOLDER == cfg.data_sync_folder)
        results.add("Tools", "Paths from config", paths_ok,
                   f"JOBS_FOLDER={executor.JOBS_FOLDER}")

        # Test job index loaded
        results.add("Tools", "Job index loaded", len(executor.job_index) > 0,
                   f"{len(executor.job_index)} jobs")

        # Test execute method exists (the actual method name)
        has_execute = hasattr(executor, 'execute') and callable(executor.execute)
        results.add("Tools", "Has execute method", has_execute)

        # Test a read-only tool (job_search)
        start = time.time()
        try:
            result = executor.execute("job_search", {"query": "26-001"})
            results.add("Tools", "Execute job_search", True,
                       f"Result: {type(result).__name__}", duration=time.time()-start)
        except Exception as e:
            results.add("Tools", "Execute job_search", False, str(e))

        # Test job_get_status
        start = time.time()
        try:
            result = executor.execute("job_get_status", {"job_number": "26-001"})
            # Result could be a dict or string depending on whether job exists
            if isinstance(result, dict):
                msg = f"Found: {result.get('found', False)}"
            else:
                msg = f"Result: {str(result)[:100]}"
            results.add("Tools", "Execute job_get_status", True, msg, duration=time.time()-start)
        except Exception as e:
            results.add("Tools", "Execute job_get_status", False, str(e))

    except Exception as e:
        results.add("Tools", "Tool executor test", False, str(e))


def test_claude_agent(results: TestResults):
    """Test Claude agent initialization and basic API call."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING: Claude Agent")
    logger.info("=" * 60)

    from config_loader import get_config
    cfg = get_config()

    try:
        from claude_agent import ClaudeAgent
        from tool_executor import ToolExecutor
        from qbo_integration import QBOIntegration
        from email_service import EmailService

        results.add("Agent", "Import ClaudeAgent", True)

        # Initialize dependencies
        qbo = QBOIntegration(
            client_id=cfg.qbo_client_id,
            client_secret=cfg.qbo_client_secret,
            redirect_uri=cfg.qbo_redirect_uri,
            environment=cfg.qbo_environment,
            token_cache_file=cfg.token_cache_qbo
        )

        email_svc = EmailService(
            client_id=cfg.email_client_id,
            client_secret=cfg.email_client_secret,
            redirect_uri=cfg.email_redirect_uri,
            token_cache_file=cfg.token_cache_graph
        )

        executor = ToolExecutor(qbo, email_svc)

        start = time.time()
        agent = ClaudeAgent(
            api_key=cfg.anthropic_api_key,
            tool_executor=executor,
            model=cfg.anthropic_model
        )
        results.add("Agent", "Initialize ClaudeAgent", True,
                   f"Model: {cfg.anthropic_model}", duration=time.time()-start)

        # Check required methods (actual method names from claude_agent.py)
        methods = ['process_email', 'chat']
        for method in methods:
            has_method = hasattr(agent, method) and callable(getattr(agent, method))
            results.add("Agent", f"Has {method} method", has_method)

        # Test a simple API call (just to verify credentials work)
        logger.info("  Testing Claude API call (this will use ~$0.01)...")
        start = time.time()
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
            response = client.messages.create(
                model=cfg.anthropic_model,
                max_tokens=50,
                messages=[{"role": "user", "content": "Reply with just 'OK' if you can read this."}]
            )
            reply = response.content[0].text
            results.add("Agent", "Claude API call", "OK" in reply.upper(),
                       f"Response: {reply[:50]}", duration=time.time()-start)
            results.add("Agent", "API tokens used", True,
                       f"Input: {response.usage.input_tokens}, Output: {response.usage.output_tokens}")
        except Exception as e:
            results.add("Agent", "Claude API call", False, str(e))

    except Exception as e:
        results.add("Agent", "Agent test", False, str(e))


def test_agent_with_mock_email(results: TestResults):
    """Test the full agent loop with a mock email (dry run)."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING: Full Agent Loop (Mock Email, Dry Run)")
    logger.info("=" * 60)

    from config_loader import get_config
    cfg = get_config()

    try:
        from claude_agent import ClaudeAgent
        from tool_executor import ToolExecutor
        from qbo_integration import QBOIntegration
        from email_service import EmailService, EmailMessage
        from datetime import datetime, timezone

        # Initialize
        qbo = QBOIntegration(
            client_id=cfg.qbo_client_id,
            client_secret=cfg.qbo_client_secret,
            redirect_uri=cfg.qbo_redirect_uri,
            environment=cfg.qbo_environment,
            token_cache_file=cfg.token_cache_qbo
        )

        email_svc = EmailService(
            client_id=cfg.email_client_id,
            client_secret=cfg.email_client_secret,
            redirect_uri=cfg.email_redirect_uri,
            token_cache_file=cfg.token_cache_graph
        )

        executor = ToolExecutor(qbo, email_svc)
        agent = ClaudeAgent(
            api_key=cfg.anthropic_api_key,
            tool_executor=executor,
            model=cfg.anthropic_model
        )

        # Create a mock email that looks like a survey request
        mock_email = EmailMessage(
            message_id="test-mock-001",
            subject="RE: Survey for 123 Test Street, St. John's",
            sender="Test Client",
            sender_email="test@example.com",
            body="""Hi,

I'd like to get a survey done for 123 Test Street in St. John's.
The closing date is February 15th, 2026.

Please let me know what you need from me.

Thanks,
Test Client""",
            html_body=None,
            attachments=[],
            received_date=datetime.now(timezone.utc),
            is_read=False,
            conversation_id="test-conv-001"
        )

        results.add("Full Loop", "Create mock email", True,
                   f"Subject: {mock_email.subject}")

        # Process with dry_run=True
        logger.info("\n  Processing mock email through Claude agent...")
        logger.info("  (This will make Claude API calls and show the agent's thinking)")
        logger.info("-" * 50)

        start = time.time()
        try:
            result = agent.process_email(mock_email, dry_run=True)
            duration = time.time() - start

            results.add("Full Loop", "Agent processed email", result.get('success', False),
                       f"Iterations: {result.get('iterations', 0)}", duration=duration)

            # Check what the agent decided to do
            if result.get('actions'):
                results.add("Full Loop", "Agent planned actions", True,
                           f"Actions: {len(result.get('actions', []))}")
                for i, action in enumerate(result.get('actions', [])[:5]):
                    logger.info(f"      Action {i+1}: {action}")

            if result.get('tool_calls'):
                results.add("Full Loop", "Agent made tool calls", True,
                           f"Tool calls: {len(result.get('tool_calls', []))}")
                for tc in result.get('tool_calls', [])[:5]:
                    logger.info(f"      Tool: {tc.get('name', 'unknown')}")

            if result.get('final_response'):
                resp = result['final_response'][:200]
                results.add("Full Loop", "Agent produced response", True,
                           f"Response preview: {resp}...")

        except Exception as e:
            results.add("Full Loop", "Agent processed email", False, str(e))
            import traceback
            traceback.print_exc()

    except Exception as e:
        results.add("Full Loop", "Full loop test", False, str(e))


def test_tools_definition(results: TestResults):
    """Test that all tools are properly defined."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING: Tools Definition")
    logger.info("=" * 60)

    try:
        from tools_definition import define_all_tools
        tools = define_all_tools()
        results.add("Tools Def", "Import define_all_tools", True, f"{len(tools)} tools defined")

        # Check each tool has required fields
        required_fields = ['name', 'description', 'input_schema']
        for tool in tools[:10]:  # Check first 10
            tool_name = tool.get('name', 'unnamed')
            has_all = all(f in tool for f in required_fields)
            if not has_all:
                results.add("Tools Def", f"Tool: {tool_name}", False, "Missing required fields")

        results.add("Tools Def", "Tool structure valid", True,
                   f"Checked {min(10, len(tools))} tools")

        # List all tool names
        tool_names = [t.get('name') for t in tools]
        logger.info(f"  Available tools: {', '.join(tool_names[:15])}...")

        # Check for critical tools (using actual names from tools_definition.py)
        critical_tools = ['job_search', 'job_get_status', 'job_create',
                         'email_send_new', 'email_send_reply', 'qbo_create_invoice']
        for tool_name in critical_tools:
            has_tool = tool_name in tool_names
            results.add("Tools Def", f"Has {tool_name}", has_tool)

    except Exception as e:
        results.add("Tools Def", "Tools definition test", False, str(e))


def test_hive_mind_prompt(results: TestResults):
    """Test the Hive Mind system prompt."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING: Hive Mind Prompt")
    logger.info("=" * 60)

    try:
        from hive_mind_prompt import build_system_prompt
        results.add("Prompt", "Import build_system_prompt", True)

        # build_system_prompt takes input_channel and include_business_context params
        prompt = build_system_prompt(input_channel="EMAIL", include_business_context=True)
        results.add("Prompt", "Generate system prompt", True,
                   f"{len(prompt)} characters")

        # Check for key sections (based on actual prompt structure in hive_mind_prompt.py)
        key_sections = [
            "IDENTITY",
            "THE SPINE",
            "MY TOOLS",  # Actual section name
            "STANCE",
            "OPERATIONAL KNOWLEDGE",
        ]
        for section in key_sections:
            has_section = section.upper() in prompt.upper()
            results.add("Prompt", f"Has section: {section}", has_section)

        # Check for business rules
        business_rules = ["575", "metro", "St. John's", "QBO", "RPR"]
        found_rules = sum(1 for r in business_rules if r.lower() in prompt.lower())
        results.add("Prompt", "Business rules present", found_rules >= 3,
                   f"Found {found_rules}/{len(business_rules)} key terms")

    except Exception as e:
        results.add("Prompt", "Prompt test", False, str(e))


def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("HIVE MIND COMPREHENSIVE TEST SUITE")
    logger.info("=" * 60)
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("")

    results = TestResults()

    # Run all test categories
    test_config_loader(results)
    test_file_paths(results)
    test_job_index(results)
    test_email_service(results)
    test_qbo_integration(results)
    test_tools_definition(results)
    test_hive_mind_prompt(results)
    test_tool_executor(results)
    test_claude_agent(results)
    test_agent_with_mock_email(results)

    # Print summary
    all_passed = results.summary()

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
