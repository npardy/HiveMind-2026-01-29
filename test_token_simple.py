"""
Simple Token Savings Test - No API calls
=========================================
Test the email chain stripping and job index summary features
without requiring email authentication.
"""

import sys
import json
sys.path.insert(0, 'H:\\')

from email_service import extract_new_content

# Rough token estimate: ~4 chars per token for English text
def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return len(text) // 4

def test_quote_stripping():
    """Test email chain quote stripping savings."""
    print("\n" + "=" * 70)
    print("TEST 1: Email Chain Quote Stripping")
    print("=" * 70)

    # Real-world style email chain
    sample_chain = """Hi Gary,

Yes, I can get that RPR done for you. Should have it by end of week.

Best,
Nick

On Wed, Jan 22, 2026 at 3:15 PM Gary Nolan <gnolan@rvdslaw.ca> wrote:

Hi Nick,

Following up on our conversation about 116A Northside Road. We need the RPR
for the title insurance claim regarding the overlap issue. The client is
getting anxious as the closing date is approaching quickly.

Please let me know if you can help with this.

Thanks,
Gary

________________________________
From: Nick Pardy <pardysurveys@outlook.com>
Sent: Tuesday, January 21, 2026 2:30 PM
To: Gary Nolan <gnolan@rvdslaw.ca>
Subject: RE: 116A Northside Road

Hey Gary,

I'll take a look at the file and get back to you. I need to check our
records to see if we have the existing survey data and can proceed with
the RPR without additional field work.

All the best,

Nick Pardy, N.L.S., P.Surv.
Pardy Surveys Inc.

Phone: 709-330-1502
Website: pardysurveys.com
Email: pardysurveys@outlook.com

________________________________
From: Gary Nolan <gnolan@rvdslaw.ca>
Sent: Monday, January 20, 2026 10:15 AM
To: Nick Pardy <pardysurveys@outlook.com>
Subject: 116A Northside Road

Hi Nick,

We have a new matter involving 116A Northside Road. There appears to be
an overlap issue with the neighboring property that needs to be resolved
before closing.

Could you please review and provide a quote for an RPR?

Thanks,
Gary Nolan
Partner
RVDS Law
"""

    full_tokens = estimate_tokens(sample_chain)
    new_content, had_quotes = extract_new_content(sample_chain)
    stripped_tokens = estimate_tokens(new_content)

    print(f"\nFull email chain: {len(sample_chain)} chars (~{full_tokens} tokens)")
    print(f"New content only: {len(new_content)} chars (~{stripped_tokens} tokens)")
    print(f"Quote markers detected: {had_quotes}")

    savings = ((full_tokens - stripped_tokens) / full_tokens) * 100
    print(f"\n[OK] TOKEN SAVINGS: {savings:.1f}%")
    print(f"  Saved ~{full_tokens - stripped_tokens} tokens per email chain")

    print(f"\nExtracted new content:")
    print("-" * 40)
    print(new_content)
    print("-" * 40)

    return savings

def test_job_index_summary_vs_full():
    """Test summary vs full body savings from job index."""
    print("\n" + "=" * 70)
    print("TEST 2: Job Index Summary vs Full Body")
    print("=" * 70)

    # Load actual job index
    try:
        with open(r"H:\data\job_index.json", 'r', encoding='utf-8') as f:
            job_index = json.load(f)
    except Exception as e:
        print(f"Could not load job index: {e}")
        return 0

    # Find jobs with emails that have both summary and body_stored
    total_summary_tokens = 0
    total_body_tokens = 0
    jobs_with_emails = 0
    email_count = 0

    for job_num, job_data in job_index.items():
        if not isinstance(job_data, dict):
            continue
        emails = job_data.get('emails', {}).get('linked', [])
        if not emails:
            continue

        jobs_with_emails += 1
        for email in emails:
            email_count += 1
            summary = email.get('summary', '')
            body = email.get('body_stored', '')

            total_summary_tokens += estimate_tokens(summary)
            total_body_tokens += estimate_tokens(body)

    print(f"\nJobs with linked emails: {jobs_with_emails}")
    print(f"Total emails in index: {email_count}")
    print(f"\nSummaries total: ~{total_summary_tokens:,} tokens")
    print(f"Full bodies total: ~{total_body_tokens:,} tokens")

    if total_body_tokens > 0:
        savings = ((total_body_tokens - total_summary_tokens) / total_body_tokens) * 100
        print(f"\n[OK] TOKEN SAVINGS using summaries: {savings:.1f}%")
        print(f"  Claude gets summaries by default, can drill down when needed")
        return savings
    else:
        print("\nNo full bodies stored yet - this is expected for older emails")
        return 0

def test_attachment_stripping_impact():
    """Show the impact of attachment base64 stripping."""
    print("\n" + "=" * 70)
    print("TEST 3: Attachment Base64 Stripping Impact")
    print("=" * 70)

    # Typical attachment sizes
    attachments = [
        ("Small PDF (100KB)", 100 * 1024),
        ("Medium PDF (500KB)", 500 * 1024),
        ("Large PDF (2MB)", 2 * 1024 * 1024),
        ("Survey Image (5MB)", 5 * 1024 * 1024),
    ]

    print("\nOLD APPROACH: Attachment contentBytes included in response")
    print("NEW APPROACH: Only metadata (name, size, type) - no base64 data")
    print()

    for name, size_bytes in attachments:
        # Base64 is ~33% larger than binary
        base64_size = int(size_bytes * 1.33)
        tokens_old = base64_size // 4
        tokens_new = 50  # Just metadata

        print(f"{name}:")
        print(f"  OLD: ~{tokens_old:,} tokens")
        print(f"  NEW: ~{tokens_new:,} tokens")
        print(f"  SAVINGS: {((tokens_old - tokens_new) / tokens_old) * 100:.1f}%")
        print()

def test_real_email_example():
    """Use the flagged email as a real example."""
    print("\n" + "=" * 70)
    print("TEST 4: Real Flagged Email Example")
    print("=" * 70)

    try:
        with open(r"H:\flagged\2026-01-23_13-38-32_gnolan@rvdslaw.ca.txt", 'r', encoding='utf-8') as f:
            flagged_content = f.read()
    except Exception as e:
        print(f"Could not read flagged email: {e}")
        return

    # This email has a thread in it
    lines = flagged_content.split('\n')
    # Find the actual email body (after the metadata header)
    body_start = 0
    for i, line in enumerate(lines):
        if line.startswith("From: Gary Nolan"):
            body_start = i
            break

    email_body = '\n'.join(lines[body_start:])

    full_tokens = estimate_tokens(email_body)
    new_content, had_quotes = extract_new_content(email_body)
    stripped_tokens = estimate_tokens(new_content)

    print(f"\nReal email from Gary Nolan (116A Northside Road)")
    print(f"Full email: {len(email_body)} chars (~{full_tokens} tokens)")
    print(f"New content: {len(new_content)} chars (~{stripped_tokens} tokens)")

    if full_tokens > 0:
        savings = ((full_tokens - stripped_tokens) / full_tokens) * 100
        print(f"\n[OK] TOKEN SAVINGS: {savings:.1f}%")

def main():
    print("=" * 70)
    print("TOKEN EFFICIENCY TEST SUITE")
    print("=" * 70)
    print("\nTesting the email efficiency improvements without API calls")

    test_quote_stripping()
    test_job_index_summary_vs_full()
    test_attachment_stripping_impact()
    test_real_email_example()

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print("""
The new email efficiency system provides token savings through:

1. QUOTE STRIPPING (60-80% savings on reply chains)
   - Detects "On X wrote:", "From:", etc.
   - Only sends new content when we have good stored context
   - Conservative: falls back to full body if uncertain

2. SUMMARY-FIRST ACCESS (70-90% savings on job context)
   - job_get_thread_emails returns summaries by default
   - job_get_email_body for drilling down when needed
   - Full bodies stored, truncation only on presentation

3. ATTACHMENT STRIPPING (99%+ savings on emails with attachments)
   - No more base64 contentBytes in responses
   - Only metadata: name, size, contentType
   - Use email_save_attachment when actual file needed

Combined, these can reduce a 232K token email to under 5K tokens
while still giving Claude access to full content on demand.
""")

if __name__ == "__main__":
    main()
