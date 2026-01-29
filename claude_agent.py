"""
Claude Agent - Hive Mind with Full Tool Access
==============================================
Hive Mind processes inputs from multiple channels using tools to search, reason, and act.
This is the operational intelligence for Pardy Surveys - handling everything from
email processing to job management to QBO integration.
"""

import json
import logging
from anthropic import Anthropic
from typing import Optional
from datetime import datetime

from tools_definition import define_all_tools
from hive_mind_prompt import build_system_prompt
from email_service import extract_new_content, deduplicate_thread_content
from diagnostics import get_diagnostics


# Legacy prompt - kept for reference but no longer used
LEGACY_SYSTEM_PROMPT = """You are Nick's email assistant for Pardy Surveys Inc., a land surveying company in Newfoundland and Nova Scotia, Canada.

Your job is to FULLY HANDLE every email that comes in. Not just read them - DEAL with them. Every email should result in one of:
- A reply sent
- A draft created for Nick to review
- Email moved to appropriate folder
- Email flagged for Nick's attention
- Some combination of the above

You have FULL access to QuickBooks Online, Email, and the NAS file system.

## YOUR MINDSET
Think like Nick's executive assistant who has been working with him for years. You know the business, you know the clients, you know what's important. Handle everything you can. Only bother Nick with things that truly need his judgment.

## EMAIL CATEGORIES AND HOW TO HANDLE THEM

### BUSINESS - JOB REQUESTS (HIGH PRIORITY)
These come from lawyers, real estate agents, title companies requesting surveys.
Look for: property addresses, closing dates, "survey", "RPR", "real property report"

**Action:**
1. Extract: property address, community, closing date, purchaser name, client info
2. Check if metro area (standard pricing) or non-metro (needs quote)
3. If metro area with closing date: CREATE THE JOB using job_create (this creates QBO customer, project, invoice, and folder)
4. Send confirmation reply with job number
5. Save email to job folder
6. Mark as read

If non-metro or missing key info: Create a draft asking for clarification, flag for attention.

### BUSINESS - INVOICE REQUESTS (HIGH PRIORITY)
"Can I get the invoice for X?" or "Invoice for job 26-003 please"

**Action:**
1. Search for invoice using qbo_search_invoices (try address, job number, customer email)
2. VERIFY it's the right invoice (check address matches request)
3. SEND the invoice using qbo_send_invoice
4. Send reply confirming you sent it
5. Mark as read

If can't find invoice or uncertain: Draft a response asking for clarification.

### BUSINESS - STATUS INQUIRIES (HIGH PRIORITY)
"Any update on my survey?" or "When will 123 Main Street be done?"

**Action:**
1. Find the job using job_search
2. Check status using job_get_status (field work done? drawings done? report done?)
3. Send honest, helpful reply about current status
4. If job not found, draft response asking for more details
5. Mark as read

### BUSINESS - EXISTING JOB CORRESPONDENCE
Follow-up emails in existing threads about jobs in progress.

**Action:**
1. Find the job (check conversation_id first, then search by address/client)
2. Save email to job folder using job_save_email
3. Reply if needed, or just acknowledge
4. Mark as read

### IMPORTANT NOTICES - FLAG FOR ATTENTION
These need Nick to see them but don't need immediate action:
- Property Online (Nova Scotia land registry) - system notices, outages
- Government notices
- Professional association emails
- Banking/payment confirmations (Interac transfers, etc.)
- Bills and invoices TO the company
- Subscription renewals

**Action:**
1. Flag for attention using flag_for_attention
2. Move to appropriate folder if one exists
3. Mark as read

### NEWSLETTERS & SUBSCRIPTIONS - FILE AWAY
- GEODNET, surveying industry news
- Tech newsletters (Replit, etc.)
- Professional development

**Action:**
1. Move to "Newsletters" folder (create if doesn't exist)
2. Mark as read
(Don't flag these - Nick can read them when he has time)

### MARKETING & PROMOTIONS - IGNORE
- Walmart, Temu, Amazon promotions
- Sales emails from vendors
- "Deal of the day" type emails

**Action:**
1. Move to "Marketing" folder or just mark as read
2. Do NOT flag these - they're noise

### SPAM & SUSPICIOUS - IGNORE
- Obvious spam
- Phishing attempts
- Unknown senders with suspicious content

**Action:**
1. Mark as read (or move to Junk if clearly spam)
2. Do NOT engage

### PERSONAL - FLAG FOR ATTENTION
- School messages (kids)
- Family stuff
- Personal appointments

**Action:**
1. Flag for attention with note "Personal - [brief description]"
2. Mark as read

## METRO AREAS (Standard Pricing - can create job immediately)
St. John's, Mount Pearl, Paradise, Conception Bay South, Portugal Cove-St. Philip's, Logy Bay-Middle Cove-Outer Cove, Holyrood, Petty Harbour-Maddox Cove

Non-metro = Needs quote = Flag for Nick

## KEY GUIDELINES

1. **TAKE ACTION** - Don't just observe. Every email should result in something happening.
2. **Send invoices confidently** - If you find a matching invoice, send it.
3. **Create jobs** - If it's a clear job request with address + closing date + metro area, create it.
4. **Draft when uncertain** - If something needs judgment, create a draft for Nick.
5. **Flag important stuff** - Government notices, payments, anything Nick needs to see.
6. **File everything else** - Marketing goes to Marketing, newsletters to Newsletters.
7. **Sign as Nick** - All replies signed "Nick"
8. **LINK EMAILS TO JOBS** - When you identify which job an email relates to, use job_link_email to record the connection. This builds the hive intelligence - future emails about this job will have context.

## HIVE INTELLIGENCE
The system builds accumulated knowledge about each job. When you identify a job:
- Use job_link_email to link this email to the job (records summary + key info)
- Use job_get_status to see full context (field data, documents sent, previous emails)
- The index remembers everything, so future emails about this job will have full context

## ASYNC Q&A - WHEN YOU NEED HELP
Sometimes you'll encounter situations where you can't proceed without Nicholas's input. Rather than silently failing or making wrong assumptions, you can ASK him and continue later.

**NICHOLAS'S EMAIL:** pardysurveys@outlook.com
**ALWAYS CC:** joe@pardysurveys.com

**AT THE START OF EVERY PROCESSING SESSION:**
1. Call job_get_pending to check if any jobs are awaiting your attention
2. If there are pending jobs, search for replies to your question emails FIRST
3. If Nicholas has replied, process his answer and continue the work
4. Call job_clear_pending when you've resolved the question

**WHEN YOU GET STUCK:**
1. Send an email using email_send_new with:
   - to: "pardysurveys@outlook.com"
   - cc: ["joe@pardysurveys.com"]
   - subject: "[Hive Mind] Question - Job XX-XXX - Brief description"
   - importance: "high" ← CRITICAL: This MUST be set to "high" - these questions need to be at the TOP of Nicholas's inbox
   - Body: Include FULL context:
     * Original request (from, subject, key details)
     * What you've done so far
     * What you're stuck on (specific question)
     * What you'll do with his answer
2. Call job_set_pending to record:
   - job_number (create a partial job entry if needed)
   - question (clear description)
   - question_type (community_classification, pricing, clarification, access, other)
   - email_id (the message_id of your question email)
   - context (original request details for continuity)
3. Move on to other emails - don't wait

**QUESTION TYPES:**
- community_classification: "Is Pigeon Cove metro or non-metro?"
- pricing: "What should I quote for a survey in Trepassey?"
- clarification: "Client didn't provide closing date - should I ask or create without?"
- access: "QBO is returning errors - can you check credentials?"
- other: Anything that doesn't fit above

**WHEN NICHOLAS REPLIES:**
His reply will come in as a regular email threaded with your question. You'll see it in the inbox.
1. job_get_pending shows you which jobs are waiting
2. The email_id in pending lets you search for the thread
3. Read the full thread for context
4. Process his answer (create job, send quote, whatever was pending)
5. Call job_clear_pending with a brief resolution note

This async loop is how you stay autonomous while still getting help when needed. Don't be afraid to ask - it's better than making wrong assumptions.

## EMAIL STYLE
Professional but warm. Newfoundland-friendly. Keep it brief.

Job confirmation example:
"Hi Gary,

Thanks for this - I've set it up as job 26-005 for 15 Forest Road, Paradise.

Closing is January 25th, I'll have everything ready well before then. Invoice sent through QuickBooks.

Nick"

Invoice sent example:
"Hi Gary,

Just sent the invoice for 49 Magee Drive through QuickBooks.

Nick"

Status update example:
"Hi Gary,

Quick update on 26-003 (15 Forest Road) - field work was completed yesterday. Working on the drawings now, should have everything to you by end of week.

Nick"

## IMPORTANT SENDERS TO RECOGNIZE
- @rvdslaw.ca, @bfrlaw.ca, @coxandpalmer.com - Law firms (job requests, invoice requests)
- @propertyonline.ca, @novascotia.ca - Government (flag for attention)
- @notification.intuit.com - QuickBooks notifications
- @interac.ca - Payment notifications (flag)

## DRY RUN MODE
If in dry run mode, describe exactly what you WOULD do in detail, including the specific tool calls you would make. Don't actually execute action tools (send_reply, send_invoice, job_create, etc.) but DO use search tools to show your reasoning.
"""


# Domains to skip entirely (don't waste API calls)
SKIP_DOMAINS = [
    'walmart.ca', 'e.walmart.ca',
    'temu.com', 'temuemail.com',
    'amazon.ca', 'amazon.com',
    'newegg.ca', 'newegg.com',
    'adorama.com',
    'eufylife.com',
    'marketing.', 'promo.', 'newsletter@',
    'noreply@bidsandtenders',  # Bid notifications not relevant
]

def should_skip_email(sender_email: str) -> bool:
    """Check if email should be skipped entirely (obvious spam/marketing)."""
    sender = sender_email.lower()
    for domain in SKIP_DOMAINS:
        if domain in sender:
            return True
    return False


class ClaudeAgent:
    """
    Claude with full tool access for email processing.
    """

    def __init__(self, api_key: str, tool_executor, model: str = "claude-sonnet-4-20250514"):
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.executor = tool_executor
        self.logger = logging.getLogger(__name__)
        self.tools = define_all_tools()

    def _get_thread_context(self, conversation_id: str) -> str:
        """
        Look up existing thread context from the job index.

        =====================================================================
        EMAIL CONTEXT RETRIEVAL STRATEGY
        =====================================================================

        WHAT THIS DOES:
        When a new email arrives that's part of an existing thread (same
        conversation_id), we check if we already have context stored in the
        job index from when we processed earlier emails in this thread.

        WHAT WE RETURN:
        - Job number and basic info (property address, client)
        - Summaries of previous emails in the thread (last 5 max)
        - Key info extracted from those emails (dates, names, amounts)

        WHY THIS MATTERS FOR TOKEN EFFICIENCY:
        Email chains can have 10+ messages with full quoted content = 50K+ chars.
        By returning stored summaries instead of making Claude re-read all that
        quoted text, we can save significant tokens.

        WHEN THESE SUMMARIES ARE ACTUALLY USED (see process_email below):
        The summaries returned here are only used to REPLACE quoted content when:
        1. We have GOOD context (actual "Summary:" entries exist, not just metadata)
        2. The new message content is meaningful (not just "Thanks" or "Ok")
        3. The email actually had quoted content detected

        If ANY of those conditions fail, we send the FULL email body anyway.
        This is the CONSERVATIVE approach - better to send too much than lose context.

        HOW SUMMARIES GET STORED:
        When Claude calls job_link_email with a summary parameter, it gets stored
        in the job index. See _job_link_email() in tool_executor.py.

        IF CLAUDE NEEDS THE FULL EMAIL BODY (drilling down):
        Two options depending on whether email is stored in job index:

        OPTION 1 - From job index (instant, no API call):
        - job_get_thread_emails(job_number) -> list all emails with summaries
        - job_get_email_body(job_number, index) -> full body of specific email
        - Full body stored when job_link_email was called (no truncation)

        OPTION 2 - From Graph API (network call, always works):
        - email_get_by_id(message_id) -> fetch email from Microsoft
        - Supports include_full_body=true for very long emails

        RELATED CODE:
        - process_email() below: Decides whether to use summaries or full body
        - _job_link_email() in tool_executor.py: Stores summaries and full body
        - _job_get_thread_emails() in tool_executor.py: Lists emails with summaries
        - _job_get_email_body() in tool_executor.py: Gets full stored body
        - extract_new_content() in email_service.py: Strips quoted reply chains
        - email_get_by_id tool: Fetches email from Graph API if needed
        =====================================================================
        """
        if not conversation_id or not hasattr(self.executor, 'job_index'):
            return ""

        # Search for jobs with this conversation linked
        for job_num, job_data in self.executor.job_index.items():
            if not isinstance(job_data, dict) or not job_num.startswith('2'):
                continue

            linked_emails = job_data.get('emails', {}).get('linked', [])
            matching_emails = [
                e for e in linked_emails
                if isinstance(e, dict) and e.get('conversation_id') == conversation_id
            ]

            if matching_emails:
                # Build context from stored summaries
                context_parts = [f"Job: {job_num}"]

                if job_data.get('property_address'):
                    context_parts.append(f"Property: {job_data['property_address']}")
                if job_data.get('client_business'):
                    context_parts.append(f"Client: {job_data['client_business']}")

                context_parts.append(f"\nPrevious emails in this thread ({len(matching_emails)}):")

                for email in matching_emails[-5:]:  # Last 5 emails max to keep context reasonable
                    direction = email.get('direction', '?')
                    date = email.get('date', '?')[:10] if email.get('date') else '?'
                    summary = email.get('summary', '(no summary stored)')
                    sender = email.get('from', '?')

                    context_parts.append(f"  - [{direction}] {date} from {sender}")
                    if summary and summary != '(no summary stored)':
                        context_parts.append(f"    Summary: {summary}")

                    # Include key_info if present (structured data like dates, names)
                    key_info = email.get('key_info', {})
                    if key_info:
                        info_str = ", ".join(f"{k}: {v}" for k, v in key_info.items() if v)
                        if info_str:
                            context_parts.append(f"    Key info: {info_str}")

                return "\n".join(context_parts)

        return ""

    def process_email(self, email_msg, dry_run: bool = False) -> dict:
        """
        Process an email using Claude with tools.
        Returns result with success status and what was done.

        =====================================================================
        EMAIL CONTENT STRATEGY - TOKEN EFFICIENCY VS CONTEXT PRESERVATION
        =====================================================================

        THE PROBLEM:
        Email chains accumulate quoted replies. A 10-message thread might have
        50K+ chars of repeated content. Sending all that to Claude wastes tokens
        and money ($10/day was observed before these optimizations).

        THE SOLUTION:
        1. When Claude processes an email, it stores a SUMMARY in the job index
           (via job_link_email tool with summary parameter)
        2. When follow-up emails arrive in the same thread, we can show Claude
           the stored summaries instead of the full quoted chain
        3. Full body is also stored (truncated to 10K) for when Claude needs
           exact wording

        THE CONSERVATIVE APPROACH:
        We ONLY strip quoted content when ALL THREE conditions are met:
        1. Email actually has quoted content detected (had_quotes)
        2. We have GOOD stored context with actual summaries (has_good_context)
        3. The new message is meaningful, not just "Thanks" (new_content_meaningful)

        If ANY condition fails, we send the FULL body. This ensures:
        - First email in thread: Gets full body (no quotes anyway)
        - Reply to unknown thread: Gets full body (no stored context)
        - "Thanks!" reply: Gets full body (need context of what they're thanking)
        - Forwarded email: Gets full body (critical info might be in forward)

        WHEN CLAUDE NEEDS MORE:
        - Claude can call email_get_by_id to fetch full email from Graph API
        - email_get_by_id supports include_full_body=true for very long emails
        - Full body is also stored in job index as body_stored (10K truncated)

        TO MODIFY THIS LOGIC:
        - Adjust the conditions in the if/else block below
        - Change new_content_meaningful threshold (currently 100 chars)
        - Modify has_good_context check (currently requires "Summary:" in context)
        - Update extract_new_content() in email_service.py for quote detection

        RELATED CODE:
        - _get_thread_context() above: Retrieves stored summaries
        - extract_new_content() in email_service.py: Strips quoted chains
        - _job_link_email() in tool_executor.py: Stores summaries and body
        - orchestrator.py: Skips self-sent [Hive Mind] emails
        =====================================================================
        """
        # Check if we should skip this email entirely (marketing/spam)
        if should_skip_email(email_msg.sender_email):
            self.logger.info(f"    Skipping marketing email from {email_msg.sender_email}")
            # Just mark as read without using Claude
            try:
                self.executor.execute("email_mark_read", {"message_id": email_msg.message_id})
            except:
                pass
            return {
                "success": True,
                "skipped": True,
                "reason": "Marketing/spam domain",
                "iterations": 0,
                "actions": ["auto_mark_read"]
            }

        # Set context so tools know which email we're processing
        self.executor.set_current_email(email_msg)

        # =================================================================
        # STEP 1: Extract new content and detect if email has quoted chain
        # =================================================================
        body = email_msg.body if email_msg.body else ""

        # Deduplicate repeated [Hive Mind] emails in the thread chain
        # This prevents sending Claude the same [Hive Mind] email multiple times
        body = deduplicate_thread_content(body)

        new_content, had_quotes = extract_new_content(body)
        # had_quotes = True if we found "On X wrote:", "From:", etc.

        # =================================================================
        # STEP 2: Check if we have good stored context for this thread
        # =================================================================
        thread_context = ""
        has_good_context = False
        if email_msg.conversation_id:
            thread_context = self._get_thread_context(email_msg.conversation_id)
            # Only trust context if it has actual summaries, not just job metadata
            # This prevents stripping quotes when we only know the job number
            has_good_context = thread_context and "Summary:" in thread_context

        # =================================================================
        # STEP 3: Check if new content alone is meaningful
        # =================================================================
        # Short replies like "Thanks" need the quoted context to make sense
        new_content_meaningful = len(new_content) > 100 or (
            new_content and new_content.lower().strip().rstrip('.!') not in [
                'thanks', 'thank you', 'ok', 'okay', 'sounds good', 'perfect',
                'great', 'got it', 'will do', 'noted', 'confirmed', 'yes', 'no'
            ]
        )

        # =================================================================
        # STEP 4: Build user message based on what context we have
        # =================================================================
        # ONLY strip quotes if ALL THREE conditions are true
        if had_quotes and has_good_context and new_content_meaningful:
            # Safe to use stored summaries - we have reliable context
            user_message = f"""Process this email and TAKE ACTION on it:

From: {email_msg.sender} <{email_msg.sender_email}>
Subject: {email_msg.subject}
Date: {email_msg.received_date}
Conversation ID: {email_msg.conversation_id}
Message ID: {email_msg.message_id}

NEW MESSAGE CONTENT:
{new_content}

THREAD CONTEXT (from previous processing - summaries stored in job index):
{thread_context}

Note: Quoted chain was stripped since you've already processed this thread. If you need the full original email, use email_get_by_id."""
        else:
            # Default: send full body - don't risk losing context
            # Covers: no quotes, no stored context, short replies, unknown threads
            user_message = f"""Process this email and TAKE ACTION on it:

From: {email_msg.sender} <{email_msg.sender_email}>
Subject: {email_msg.subject}
Date: {email_msg.received_date}
Conversation ID: {email_msg.conversation_id}
Message ID: {email_msg.message_id}

Body:
{body}"""

            # Add thread context as BONUS info if available (but keep full body too)
            if thread_context:
                user_message += f"""

ADDITIONAL CONTEXT (this thread is linked to a job):
{thread_context}"""

        if email_msg.attachments:
            user_message += f"\n\nAttachments: {', '.join(a.get('name', 'unnamed') for a in email_msg.attachments)}"

        user_message += "\n\nRemember: TAKE ACTION. Don't just read it - handle it. Search, verify, send, create, flag, file."

        # Build system prompt for EMAIL channel
        system = build_system_prompt(input_channel="EMAIL", include_business_context=True)
        if dry_run:
            system += "\n\n## DRY RUN MODE ACTIVE\nShow your full reasoning and what tools you WOULD call. Use search tools to demonstrate your logic, but don't execute action tools (send_reply, send_invoice, job_create, etc.)."
        
        messages = [{"role": "user", "content": user_message}]
        
        # Agent loop
        max_iterations = 15
        iteration = 0
        actions_taken = []
        
        self.logger.info(f"  Starting agent for: {email_msg.subject[:50]}")
        
        while iteration < max_iterations:
            iteration += 1
            self.logger.info(f"  Iteration {iteration}")
            
            try:
                # Enable prompt caching - system prompt and tools are cached
                # after first call, reducing token costs by 90% for those components
                cached_system = [
                    {
                        "type": "text",
                        "text": system,
                        "cache_control": {"type": "ephemeral"}
                    }
                ]

                # Add cache control to tools (on the last tool to cache all of them)
                cached_tools = list(self.tools)  # Make a copy
                if cached_tools:
                    cached_tools[-1] = {
                        **cached_tools[-1],
                        "cache_control": {"type": "ephemeral"}
                    }

                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=cached_system,
                    tools=cached_tools,
                    messages=messages
                )
            except Exception as e:
                self.logger.error(f"  Claude API error: {e}")
                return {"success": False, "error": str(e), "iterations": iteration}

            # Track tool calls for this iteration
            tool_calls_this_iter = []
            tool_results_chars = 0

            # Process response
            if response.stop_reason == "tool_use":
                tool_results = []

                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        tool_calls_this_iter.append(tool_name)

                        # Action tools that modify state
                        action_tools = [
                            "email_send_reply", "email_send_new", "email_create_draft",
                            "qbo_send_invoice", "qbo_create_invoice", "qbo_create_customer", "qbo_create_project",
                            "job_create",
                            "email_move_to_folder", "email_create_folder",
                            "nas_write_file", "nas_copy_file", "nas_copy_directory", "nas_create_directory"
                        ]

                        if dry_run and tool_name in action_tools:
                            result = json.dumps({
                                "dry_run": True,
                                "would_execute": tool_name,
                                "with_params": tool_input,
                                "message": f"DRY RUN: Would call {tool_name}"
                            })
                            self.logger.info(f"    DRY RUN would call: {tool_name}")
                            actions_taken.append(f"[DRY RUN] {tool_name}")
                        else:
                            result = self.executor.execute(tool_name, tool_input)
                            actions_taken.append(tool_name)
                            self.logger.info(f"    Executed: {tool_name}")

                        # Log tool result size for diagnostics
                        result_chars = get_diagnostics().log_tool_result_size(tool_name, result)
                        tool_results_chars += result_chars

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result
                        })
                
                # Log API call with diagnostics
                get_diagnostics().log_api_call(
                    email_subject=email_msg.subject,
                    email_sender=email_msg.sender,
                    iteration=iteration,
                    response=response,
                    system_prompt_chars=len(system),
                    tools_chars=len(json.dumps(self.tools)),
                    messages_chars=len(json.dumps(messages, default=str)),
                    tool_calls_this_iteration=tool_calls_this_iter,
                    tool_results_chars=tool_results_chars
                )

                # Continue conversation
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

            else:
                # Log final API call
                get_diagnostics().log_api_call(
                    email_subject=email_msg.subject,
                    email_sender=email_msg.sender,
                    iteration=iteration,
                    response=response,
                    system_prompt_chars=len(system),
                    tools_chars=len(json.dumps(self.tools)),
                    messages_chars=len(json.dumps(messages, default=str)),
                    tool_calls_this_iteration=[],
                    tool_results_chars=0
                )

                # Claude is done
                final_text = ""
                for block in response.content:
                    if hasattr(block, 'text'):
                        final_text += block.text

                self.logger.info(f"  Complete after {iteration} iterations")
                self.logger.info(f"  Actions: {', '.join(actions_taken)}")

                # Log email completion
                get_diagnostics().log_email_complete(email_msg.subject, iteration, actions_taken)

                return {
                    "success": True,
                    "iterations": iteration,
                    "actions": actions_taken,
                    "final_response": final_text
                }
        
        # Max iterations
        self.logger.warning("  Hit max iterations")
        return {
            "success": False,
            "error": "Max iterations reached",
            "iterations": iteration,
            "actions": actions_taken
        }
    
    def chat(self, message: str, dry_run: bool = False, channel: str = "CHAT") -> str:
        """
        Interactive chat mode - for testing or manual queries.
        Example: "Find the invoice for 49 Magee Drive and send it to lawyer@firm.ca"

        Args:
            message: The user's message
            dry_run: If True, don't execute action tools
            channel: Input channel (CHAT for interactive, EMAIL for email-style, etc.)
        """
        system = build_system_prompt(input_channel=channel, include_business_context=True)
        if dry_run:
            system += "\n\nDRY RUN: Show what you would do but don't execute action tools."
        
        messages = [{"role": "user", "content": message}]
        
        max_iterations = 10
        for iteration in range(max_iterations):
            # Enable prompt caching for chat mode too
            cached_system = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"}
                }
            ]
            cached_tools = list(self.tools)
            if cached_tools:
                cached_tools[-1] = {
                    **cached_tools[-1],
                    "cache_control": {"type": "ephemeral"}
                }

            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=cached_system,
                tools=cached_tools,
                messages=messages
            )
            
            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = self.executor.execute(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result
                        })
                
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
            else:
                # Done
                for block in response.content:
                    if hasattr(block, 'text'):
                        return block.text
                return ""
        
        return "Max iterations reached"
