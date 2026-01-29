"""
Email Automation Orchestrator v2 - Agent-based
==============================================
Uses Claude with tools to process emails intelligently.
Claude reasons, searches, and takes actions - not just classifies.
"""

import os
import json
import time
import logging
import argparse
from datetime import datetime, timezone, timedelta

import yaml

from config_loader import get_config
from email_service import EmailService
from qbo_integration import QBOIntegration
from job_manager import JobManager
from tool_executor import ToolExecutor
from claude_agent import ClaudeAgent
from notification_watcher import NotificationWatcher


class EmailOrchestrator:
    """
    Main orchestrator - fetches emails and lets Claude agent process them.
    """

    def __init__(self, config_path: str, dry_run: bool = False):
        # Load config via centralized loader
        self.cfg = get_config()
        self.cfg.load(config_path)
        self.config = self.cfg.config  # Raw dict for backwards compatibility

        # State file path from config base
        self.STATE_FILE = os.path.join(os.path.dirname(self.cfg.job_index_file), "orchestrator_state.json")

        self._setup_logging()

        self.dry_run = dry_run
        self.state = self._load_state()

        self.logger = logging.getLogger(__name__)

        if dry_run:
            self.logger.info("=" * 50)
            self.logger.info("DRY RUN MODE - No actions will be taken")
            self.logger.info("=" * 50)

        # Initialize services with paths from config
        self.email_service = EmailService(
            client_id=self.cfg.email_client_id,
            client_secret=self.cfg.email_client_secret,
            redirect_uri=self.cfg.email_redirect_uri,
            token_cache_file=self.cfg.token_cache_graph
        )

        self.qbo = QBOIntegration(
            client_id=self.cfg.qbo_client_id,
            client_secret=self.cfg.qbo_client_secret,
            redirect_uri=self.cfg.qbo_redirect_uri,
            environment=self.cfg.qbo_environment,
            token_cache_file=self.cfg.token_cache_qbo
        )

        self.job_manager = JobManager(self.qbo)

        self.tool_executor = ToolExecutor(self.qbo, self.email_service)

        # Set up [Hive Mind] conversation tracking callback
        self.tool_executor.set_hive_mind_tracker(self.track_hive_mind_conversation)

        self.agent = ClaudeAgent(
            api_key=self.cfg.anthropic_api_key,
            tool_executor=self.tool_executor,
            model=self.cfg.anthropic_model
        )

        # Notification watcher for Data Sync integration
        self.notification_watcher = NotificationWatcher(
            notification_file=self.cfg.notification_queue,
            tool_executor=self.tool_executor,
            agent=self.agent
        )

        self.headless = self.cfg.email_headless
    
    def _load_config(self, config_path: str) -> dict:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _setup_logging(self):
        # Get log file path from config, extract folder from it
        log_file_path = self.cfg.log_file
        log_folder = os.path.dirname(log_file_path)
        os.makedirs(log_folder, exist_ok=True)

        # Create dated log file
        log_file = os.path.join(log_folder, f"email_automation_{datetime.now().strftime('%Y-%m-%d')}.log")

        logging.basicConfig(
            level=getattr(logging, self.cfg.log_level, logging.INFO),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
    
    def _load_state(self) -> dict:
        default_state = {
            'last_check': datetime.now(timezone.utc).isoformat(),
            'api_calls_today': 0,
            'api_call_date': datetime.now().strftime('%Y-%m-%d'),
            'processed_emails': [],  # Track message IDs we've already processed
            'hive_mind_conversations': []  # Track conversation_ids of outgoing [Hive Mind] emails
        }

        if os.path.exists(self.STATE_FILE):
            try:
                with open(self.STATE_FILE, 'r') as f:
                    state = json.load(f)
                    # Reset daily counter if new day
                    if state.get('api_call_date') != datetime.now().strftime('%Y-%m-%d'):
                        state['api_calls_today'] = 0
                        state['api_call_date'] = datetime.now().strftime('%Y-%m-%d')
                    # Ensure processed_emails exists
                    if 'processed_emails' not in state:
                        state['processed_emails'] = []
                    # Ensure hive_mind_conversations exists
                    if 'hive_mind_conversations' not in state:
                        state['hive_mind_conversations'] = []
                    return state
            except:
                pass
        return default_state

    def _mark_email_processed(self, message_id: str):
        """Mark an email as processed so we don't process it again."""
        if message_id not in self.state['processed_emails']:
            self.state['processed_emails'].append(message_id)

    def _is_email_processed(self, message_id: str) -> bool:
        """Check if we've already processed this email."""
        return message_id in self.state.get('processed_emails', [])

    def track_hive_mind_conversation(self, conversation_id: str):
        """Track a [Hive Mind] conversation_id for detecting Nicholas's replies."""
        if conversation_id and conversation_id not in self.state.get('hive_mind_conversations', []):
            self.state['hive_mind_conversations'].append(conversation_id)
            self._save_state()
            self.logger.info(f"  -> Tracking [Hive Mind] conversation: {conversation_id[:30]}...")

    def is_hive_mind_reply(self, conversation_id: str) -> bool:
        """Check if this email is part of a tracked [Hive Mind] conversation (Nicholas's reply)."""
        return conversation_id in self.state.get('hive_mind_conversations', [])

    def _save_state(self):
        with open(self.STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2, default=str)
    
    def self_test(self) -> bool:
        """Run comprehensive self-test."""
        self.logger.info("")
        self.logger.info("=" * 50)
        self.logger.info("SELF-TEST: Validating system components")
        self.logger.info("=" * 50)

        all_passed = True
        tests = []

        # Test 1: Jobs folder (from config)
        jobs_folder = self.cfg.jobs_folder
        year_folder = os.path.join(jobs_folder, str(datetime.now().year))
        if os.path.exists(year_folder):
            tests.append(("Jobs folder", True, f"Found {year_folder}"))
        else:
            tests.append(("Jobs folder", False, f"Not found: {year_folder}"))
            all_passed = False

        # Test 2: Template
        year_short = str(datetime.now().year)[2:]
        template_path = os.path.join(year_folder, f"{year_short}-000 - Template")
        if os.path.exists(template_path):
            tests.append(("Template folder", True, f"Found"))
        else:
            tests.append(("Template folder", False, f"Not found: {template_path}"))
            all_passed = False

        # Test 3: Field data sync (from config)
        data_sync_folder = self.cfg.data_sync_folder
        if os.path.exists(data_sync_folder):
            tests.append(("Field data sync", True, f"Found {data_sync_folder}"))
        else:
            tests.append(("Field data sync", False, f"Not found: {data_sync_folder}"))
            all_passed = False

        # Test 4: QBO
        if self.qbo.access_token:
            company = self.qbo.get_company_info()
            if company:
                tests.append(("QBO connection", True, f"Connected to: {company.get('CompanyName')}"))
                next_job = self.qbo.get_next_job_number()
                tests.append(("QBO job numbering", True, f"Next job: {next_job}"))
            else:
                tests.append(("QBO connection", False, "Token exists but API failed"))
                all_passed = False
        else:
            tests.append(("QBO connection", False, "Not authenticated"))
            all_passed = False

        # Test 5: Email token (from config)
        token_cache = self.cfg.token_cache_graph
        if os.path.exists(token_cache):
            tests.append(("Email token cache", True, f"Exists at {token_cache}"))
        else:
            tests.append(("Email token cache", False, f"Not found: {token_cache}"))

        # Test 6: Job index (from config)
        job_index_file = self.cfg.job_index_file
        if os.path.exists(job_index_file):
            job_count = len(self.job_manager.job_index)
            tests.append(("Job index", True, f"{job_count} jobs indexed at {job_index_file}"))
        else:
            tests.append(("Job index", False, f"Not found: {job_index_file}"))

        # Test 7: Notification queue folder (Data Sync integration)
        notification_path = self.cfg.notification_queue
        notification_dir = os.path.dirname(notification_path)
        if os.path.exists(notification_dir):
            tests.append(("Notification queue", True, f"Folder ready: {notification_dir}"))
        else:
            tests.append(("Notification queue", True, f"Will be created on first event: {notification_dir}"))
            # Not a failure - folder gets created when first event is written

        # Print results
        self.logger.info("")
        for test_name, passed, message in tests:
            symbol = "+" if passed else "X"
            self.logger.info(f"  [{symbol}] {test_name}: {'PASS' if passed else 'FAIL'}")
            self.logger.info(f"      {message}")

        self.logger.info("")
        self.logger.info("All tests PASSED" if all_passed else "Some tests FAILED")
        self.logger.info("=" * 50)

        return all_passed
    
    def start(self):
        """Start the email automation service."""
        self.logger.info("=" * 60)
        self.logger.info("Starting Email Automation System (Agent Mode)")
        self.logger.info(f"Dry run: {self.dry_run}")
        self.logger.info(f"API calls today: {self.state['api_calls_today']}")
        self.logger.info("=" * 60)
        
        if not self.self_test():
            self.logger.error("Self-test failed. Fix issues before starting.")
            return
        
        if not self.email_service.authenticate(allow_interactive=not self.headless):
            self.logger.error("Failed to authenticate with email.")
            return
        
        self.logger.info("Email automation running. Press Ctrl+C to stop.")
        self.logger.info(f"Notification queue: {self.cfg.notification_queue}")

        check_interval = self.cfg.email_check_interval

        try:
            while True:
                # Process new emails (by timestamp, filtered by processed IDs)
                self._process_new_emails()

                # Process Data Sync notifications (field uploads, layout jobs)
                notification_count = self.notification_watcher.check_and_process()
                if notification_count > 0:
                    self.logger.info(f"Processed {notification_count} Data Sync notification(s)")

                time.sleep(check_interval)
        except KeyboardInterrupt:
            self.logger.info("Shutting down...")
        finally:
            self._save_state()
            # Print session diagnostics summary
            try:
                from diagnostics import get_diagnostics
                get_diagnostics().print_session_summary()
            except Exception as e:
                self.logger.error(f"Failed to print diagnostics summary: {e}")
    
    def _maybe_sync_manual_replies(self):
        """
        Sync Nick's manual email replies to the job index.
        Only runs every 30 minutes to avoid wasting API calls.

        Uses timestamp-based fetching to only check emails sent since last sync.
        """
        # Only sync every 30 minutes, not every check cycle
        last_sent_sync = self.state.get('last_sent_sync')
        if last_sent_sync:
            last_sync_dt = datetime.fromisoformat(last_sent_sync.replace('Z', '+00:00'))
            minutes_since_sync = (datetime.now(timezone.utc) - last_sync_dt).total_seconds() / 60
            if minutes_since_sync < 30:
                return  # Too soon, skip this cycle

        try:
            if last_sent_sync:
                hours_back = (datetime.now(timezone.utc) - last_sync_dt).total_seconds() / 3600
                # Cap at 24 hours to avoid huge fetches after long downtime
                hours_back = min(hours_back + 0.1, 24)  # +0.1 for overlap buffer
            else:
                hours_back = 2  # First run: check last 2 hours

            result = self.tool_executor.execute("email_sync_sent_to_jobs", {"hours": hours_back})
            import json
            parsed = json.loads(result)

            if parsed.get("linked", 0) > 0:
                self.logger.info(f"Synced {parsed['linked']} manual reply(s) to job index")

            # Update last sync time
            self.state['last_sent_sync'] = datetime.now(timezone.utc).isoformat()

        except Exception as e:
            self.logger.warning(f"Failed to sync manual replies: {e}")

    def _process_new_emails(self):
        """Fetch and process new emails that need attention."""
        # Periodically sync Nick's manual replies (runs every 5 min, not every cycle)
        self._maybe_sync_manual_replies()

        # Step 1: Get just the message IDs currently in Inbox (lightweight API call)
        # This doesn't care about order - just what's IN the inbox right now
        inbox_ids = self.email_service.get_inbox_message_ids(max_results=50)

        if not inbox_ids:
            self.logger.info("Inbox empty")
            self.state['last_check'] = datetime.now(timezone.utc).isoformat()
            self._save_state()
            return

        # Step 2: Find IDs we haven't processed yet (simple set comparison, no Claude involved)
        unprocessed_ids = [
            msg_id for msg_id in inbox_ids
            if not self._is_email_processed(msg_id)
        ]

        if not unprocessed_ids:
            self.logger.info(f"Checked {len(inbox_ids)} inbox emails, all already processed")
            self.state['last_check'] = datetime.now(timezone.utc).isoformat()
            self._save_state()
            return

        # Step 3: Only NOW fetch full content for emails that need processing
        self.logger.info(f"Found {len(unprocessed_ids)} unprocessed email(s), fetching content...")
        unprocessed_emails = self.email_service.get_emails_by_ids(unprocessed_ids)

        for email_msg in unprocessed_emails:
            self.logger.info("")
            self.logger.info(f"Processing: {email_msg.subject}")
            self.logger.info(f"  From: {email_msg.sender} <{email_msg.sender_email}>")

            # Self-Sent Email Handling:
            # Claude sends from pardysurveys@outlook.com. Nicholas also sends from same address.
            # We track message IDs AND conversation IDs to distinguish Claude's emails.
            subject = email_msg.subject or ""
            sender_is_pardy = (email_msg.sender_email or "").lower() == "pardysurveys@outlook.com"
            is_tracked_hive_mind_reply = self.is_hive_mind_reply(email_msg.conversation_id)

            # Check if this specific message was sent by Claude
            # Uses internet_message_id which is consistent across folders (unlike Graph API message_id)
            check_id = getattr(email_msg, 'internet_message_id', None) or email_msg.message_id
            is_claude_sent = self.tool_executor.is_claude_sent_message(check_id)

            # Debug logging to help diagnose self-reply issues
            if sender_is_pardy:
                self.logger.debug(f"  [DEBUG] internet_message_id: {getattr(email_msg, 'internet_message_id', 'NOT SET')[:60] if getattr(email_msg, 'internet_message_id', None) else 'NOT SET'}...")
                self.logger.debug(f"  [DEBUG] Checking ID for Claude-sent: {check_id[:60]}...")

            if is_claude_sent and not is_tracked_hive_mind_reply:
                # This specific message was sent by Claude - skip to prevent feedback loop
                self.logger.info(f"  -> Skipping Claude's automated email (message ID tracked as Claude-sent)")
                self._mark_email_processed(email_msg.message_id)
                continue
            elif sender_is_pardy and not is_claude_sent:
                # Sender is pardysurveys but this specific message wasn't sent by Claude = Nicholas
                self.logger.info(f"  -> Processing Nicholas's email from pardysurveys (message not Claude-sent)")
            elif is_tracked_hive_mind_reply:
                # This email is part of a tracked [Hive Mind] conversation - it's Nicholas's reply!
                self.logger.info(f"  -> Processing Nicholas's reply to [Hive Mind] email (conversation tracked)")

            try:
                # Reset session state before each email (prevents duplicate replies)
                self.tool_executor.reset_session_state()

                # Let Claude agent handle it
                result = self.agent.process_email(email_msg, dry_run=self.dry_run)

                self.state['api_calls_today'] += result.get('iterations', 1)

                # Mark as processed regardless of outcome (to avoid retry loops)
                self._mark_email_processed(email_msg.message_id)

                if result.get('success'):
                    self.logger.info(f"  -> Handled in {result.get('iterations')} iteration(s)")
                else:
                    self.logger.warning(f"  -> Failed: {result.get('error')}")

            except Exception as e:
                self.logger.error(f"  -> Error processing email: {e}")
                # Still mark as processed to avoid infinite retry
                self._mark_email_processed(email_msg.message_id)
                # Flag for attention
                self.job_manager.flag_for_attention(
                    {
                        'sender': email_msg.sender,
                        'sender_email': email_msg.sender_email,
                        'subject': email_msg.subject,
                        'received_date': str(email_msg.received_date),
                        'body': email_msg.body[:2000]
                    },
                    f"Processing error: {e}"
                )

        self.state['last_check'] = datetime.now(timezone.utc).isoformat()
        self._save_state()

    def process_single_email(self, message_id: str):
        """Process a specific email by ID (for testing)."""
        if not self.email_service.authenticate(allow_interactive=True):
            self.logger.error("Failed to authenticate")
            return
        
        email_msg = self.email_service.get_email_by_id(message_id)
        if not email_msg:
            self.logger.error(f"Email not found: {message_id}")
            return
        
        self.logger.info(f"Processing: {email_msg.subject}")
        result = self.agent.process_email(email_msg, dry_run=self.dry_run)
        
        print("\n" + "=" * 50)
        print("RESULT:")
        print(json.dumps(result, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description='Email Automation (Agent Mode)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would happen without taking actions')
    parser.add_argument('--test', action='store_true', help='Run self-test and exit')
    parser.add_argument('--process', type=str, metavar='MESSAGE_ID', help='Process a specific email by ID')
    
    args = parser.parse_args()
    
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    orchestrator = EmailOrchestrator(config_path, dry_run=args.dry_run)
    
    if args.test:
        orchestrator.self_test()
    elif args.process:
        orchestrator.process_single_email(args.process)
    else:
        orchestrator.start()


if __name__ == '__main__':
    main()
