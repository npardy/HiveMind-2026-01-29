"""
Token Usage Comparison Test
===========================
Compare token usage between old approach (full email) vs new approach (smart context).
"""

import sys
import os
sys.path.insert(0, 'H:\\')

from email_service import EmailService, extract_new_content
from tool_executor import ToolExecutor
from config_loader import get_config

# Rough token estimate: ~4 chars per token for English text
def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return len(text) // 4

def main():
    print("=" * 70)
    print("TOKEN USAGE COMPARISON TEST")
    print("=" * 70)

    # Initialize services - load config directly from yaml
    import yaml
    config_path = r"H:\config.nas.yaml"
    print(f"Loading config from: {config_path}")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    print(f"Config loaded successfully")

    # Use local Windows paths for token cache
    email_svc = EmailService(
        client_id=config['email']['client_id'],
        client_secret=config['email']['client_secret'],
        redirect_uri=config['email'].get('redirect_uri', 'http://localhost:8000/callback'),
        token_cache_file=r"H:\graph_token_cache_v2.json"  # Local Windows path
    )

    # Need to also fix config loader for executor
    cfg = get_config()
    cfg._config = config  # Inject directly
    executor = ToolExecutor(None, email_svc)

    # Test 1: Check a real email with attachments
    print("\n[TEST 1] Email with attachments - checking what's returned")
    print("-" * 50)

    # Get a recent email
    recent = email_svc.get_unread_emails(max_results=5)
    if recent:
        test_email = recent[0]
        print(f"Email: {test_email.subject[:50]}...")
        print(f"From: {test_email.sender_email}")
        print(f"Body length: {len(test_email.body or '')} chars")
        print(f"Attachments: {len(test_email.attachments or [])}")

        if test_email.attachments:
            for att in test_email.attachments:
                print(f"  - {att.get('name', 'unnamed')}: {att.get('size', 0)} bytes")
                has_content = 'contentBytes' in att or 'data' in att
                print(f"    Has content data: {has_content}")

        # Simulate old approach - full email object
        old_tokens = estimate_tokens(str(test_email.body))
        if test_email.attachments:
            for att in test_email.attachments:
                if att.get('contentBytes'):
                    old_tokens += estimate_tokens(att['contentBytes'])
                elif att.get('data'):
                    old_tokens += estimate_tokens(att['data'])

        print(f"\nOLD APPROACH (if attachments included): ~{old_tokens:,} tokens")

        # New approach - what _email_get_by_id returns
        result = executor._email_get_by_id({"message_id": test_email.message_id})
        new_email_str = str(result)
        new_tokens = estimate_tokens(new_email_str)
        print(f"NEW APPROACH (attachment metadata only): ~{new_tokens:,} tokens")

        if old_tokens > 0:
            savings = ((old_tokens - new_tokens) / old_tokens) * 100
            print(f"SAVINGS: {savings:.1f}%")
    else:
        print("No unread emails to test with")

    # Test 2: Email chain extraction
    print("\n\n[TEST 2] Email chain quote stripping")
    print("-" * 50)

    sample_chain = """Hi Gary,

Yes, I can get that RPR done for you. Should have it by end of week.

Best,
Nick

On Wed, Jan 22, 2026 at 3:15 PM Gary Nolan <gnolan@rvdslaw.ca> wrote:

Hi Nick,

Following up on our conversation about 116A Northside Road. We need the RPR
for the title insurance claim regarding the overlap issue.

Please let me know if you can help.

Thanks,
Gary

________________________________
From: Nick Pardy <pardysurveys@outlook.com>
Sent: Tuesday, January 21, 2026 2:30 PM
To: Gary Nolan <gnolan@rvdslaw.ca>
Subject: RE: 116A Northside Road

Hey Gary,

I'll take a look at the file and get back to you.

All the best,
Nick Pardy, N.L.S., P.Surv.
Pardy Surveys Inc.
Phone: 709-330-1502
"""

    full_tokens = estimate_tokens(sample_chain)
    new_content, had_quotes = extract_new_content(sample_chain)
    stripped_tokens = estimate_tokens(new_content)

    print(f"Full chain: {len(sample_chain)} chars (~{full_tokens} tokens)")
    print(f"New content only: {len(new_content)} chars (~{stripped_tokens} tokens)")
    print(f"Had quotes: {had_quotes}")
    print(f"SAVINGS: {((full_tokens - stripped_tokens) / full_tokens) * 100:.1f}%")
    print(f"\nExtracted content:\n---\n{new_content}\n---")

    # Test 3: Job thread emails tool
    print("\n\n[TEST 3] Job thread emails - summary vs full body")
    print("-" * 50)

    # Find a job with emails
    job_with_emails = None
    for job_num, job_data in executor.job_index.items():
        emails = job_data.get('emails', {}).get('linked', [])
        if len(emails) >= 2:
            job_with_emails = job_num
            break

    if job_with_emails:
        print(f"Testing job: {job_with_emails}")

        # Get thread emails (summaries)
        thread_result = executor._job_get_thread_emails({"job_number": job_with_emails})
        thread_str = str(thread_result)
        thread_tokens = estimate_tokens(thread_str)

        # Compare to full bodies
        job_data = executor.job_index.get(job_with_emails, {})
        emails = job_data.get('emails', {}).get('linked', [])
        full_body_tokens = 0
        for email in emails:
            body = email.get('body_stored', '')
            full_body_tokens += estimate_tokens(body)

        print(f"Number of emails: {len(emails)}")
        print(f"Thread summaries: ~{thread_tokens} tokens")
        print(f"Full bodies (all): ~{full_body_tokens} tokens")
        if full_body_tokens > 0:
            print(f"SAVINGS when using summaries: {((full_body_tokens - thread_tokens) / full_body_tokens) * 100:.1f}%")

        # Show what summaries look like
        print(f"\nSample thread output:")
        for email in thread_result.get('emails', [])[:3]:
            print(f"  #{email.get('index')}: {email.get('date')[:10]} - {email.get('summary', '(no summary)')[:60]}...")
    else:
        print("No jobs with multiple emails found in index")

    # Test 4: Attachment data stripping verification
    print("\n\n[TEST 4] Attachment data stripping verification")
    print("-" * 50)

    # Search for an email with attachments
    search_result = email_svc.search_emails("has:attachment", max_results=3)
    if search_result:
        for email in search_result:
            if email.attachments:
                print(f"\nEmail: {email.subject[:40]}...")
                result = executor._email_get_by_id({"message_id": email.message_id})

                if result.get('attachments'):
                    for att in result['attachments']:
                        print(f"  Attachment: {att.get('name')}")
                        print(f"    Size: {att.get('size', 0):,} bytes")
                        print(f"    Has content data: {'data' in att or 'contentBytes' in att}")
                break
    else:
        print("No emails with attachments found in search")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()
