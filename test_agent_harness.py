"""
Test Agent Harness - Full Visibility into Agent Processing
==========================================================
Tests the EXACT same system prompt and tools as production,
with comprehensive logging of every tool call, response, and token usage.

Usage: python test_agent_harness.py
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

import yaml
from anthropic import Anthropic

# Import system components (same as production)
from email_service import EmailService
from qbo_integration import QBOIntegration
from tool_executor import ToolExecutor
from tools_definition import define_all_tools

# ===========================================================================
# EXACT SYSTEM PROMPT FROM claude_agent.py (DO NOT MODIFY)
# ===========================================================================

SYSTEM_PROMPT = """You are Nick's email assistant for Pardy Surveys Inc., a land surveying company in Newfoundland and Nova Scotia, Canada.

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
Newfoundland: St. John's, Mount Pearl, Paradise, Conception Bay South, Torbay, Portugal Cove-St. Philip's, Logy Bay-Middle Cove-Outer Cove
Nova Scotia: Areas within 50km of Annapolis Valley office

Non-metro = Needs quote = Flag for Nick

## KEY GUIDELINES

1. **TAKE ACTION** - Don't just observe. Every email should result in something happening.
2. **Send invoices confidently** - If you find a matching invoice, send it.
3. **Create jobs** - If it's a clear job request with address + closing date + metro area, create it.
4. **Draft when uncertain** - If something needs judgment, create a draft for Nick.
5. **Flag important stuff** - Government notices, payments, anything Nick needs to see.
6. **File everything else** - Marketing goes to Marketing, newsletters to Newsletters.
7. **Sign as Nick** - All replies signed "Nick"

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


# ===========================================================================
# FAKE EMAIL MESSAGE CLASS
# ===========================================================================

@dataclass
class FakeEmailMessage:
    """Mimics the real EmailMessage structure."""
    message_id: str
    conversation_id: str
    sender: str
    sender_email: str
    subject: str
    body: str
    received_date: datetime
    attachments: List[Dict] = None
    
    def __post_init__(self):
        if self.attachments is None:
            self.attachments = []


# ===========================================================================
# INSTRUMENTED TOOL EXECUTOR - LOGS EVERYTHING
# ===========================================================================

class InstrumentedToolExecutor:
    """
    Wraps the real ToolExecutor to log all tool calls with timing.
    """
    
    def __init__(self, real_executor: ToolExecutor):
        self.real_executor = real_executor
        self.tool_logs = []
        
    def set_current_email(self, email_msg):
        self.real_executor.set_current_email(email_msg)
    
    def execute(self, tool_name: str, params: dict) -> str:
        """Execute tool and log everything."""
        start_time = time.time()
        
        result = self.real_executor.execute(tool_name, params)
        
        elapsed = time.time() - start_time
        
        # Log the call
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "tool_name": tool_name,
            "input": params,
            "output": json.loads(result) if result else None,
            "duration_ms": round(elapsed * 1000, 2)
        }
        self.tool_logs.append(log_entry)
        
        return result


# ===========================================================================
# TEST HARNESS - MAIN CLASS
# ===========================================================================

class AgentTestHarness:
    """
    Runs the agent loop with full instrumentation and logging.
    """
    
    def __init__(self, config_path: str, dry_run: bool = True):
        self.config = self._load_config(config_path)
        self.dry_run = dry_run
        
        # Initialize services (same as orchestrator.py)
        self.email_service = EmailService(
            client_id=self.config['email']['client_id'],
            client_secret=self.config['email']['client_secret'],
            redirect_uri=self.config['email']['redirect_uri']
        )
        
        self.qbo = QBOIntegration(
            client_id=self.config['quickbooks']['client_id'],
            client_secret=self.config['quickbooks']['client_secret'],
            redirect_uri=self.config['quickbooks']['redirect_uri'],
            environment=self.config['quickbooks']['environment']
        )
        
        # Create instrumented executor
        real_executor = ToolExecutor(self.qbo, self.email_service)
        self.tool_executor = InstrumentedToolExecutor(real_executor)
        
        # Claude client
        self.client = Anthropic(api_key=self.config['anthropic']['api_key'])
        self.model = self.config['anthropic'].get('model', 'claude-sonnet-4-20250514')
        self.tools = define_all_tools()
        
        # Tracking
        self.iteration_logs = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        
    def _load_config(self, config_path: str) -> dict:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def run_test(self, fake_email: FakeEmailMessage, max_iterations: int = 15) -> dict:
        """
        Run the agent loop with full logging.
        Returns comprehensive results.
        """
        print("\n" + "=" * 80)
        print("AGENT TEST HARNESS - FULL VISIBILITY MODE")
        print("=" * 80)
        print(f"Dry Run: {self.dry_run}")
        print(f"Model: {self.model}")
        print(f"Max Iterations: {max_iterations}")
        print("=" * 80)
        
        # Set context
        self.tool_executor.set_current_email(fake_email)
        
        # Build user message (same as claude_agent.py)
        user_message = f"""Process this email and TAKE ACTION on it:

From: {fake_email.sender} <{fake_email.sender_email}>
Subject: {fake_email.subject}
Date: {fake_email.received_date}
Conversation ID: {fake_email.conversation_id}
Message ID: {fake_email.message_id}

Body:
{fake_email.body[:6000] if fake_email.body else '(empty)'}"""

        if fake_email.attachments:
            user_message += f"\n\nAttachments: {', '.join(a.get('name', 'unnamed') for a in fake_email.attachments)}"
        
        user_message += "\n\nRemember: TAKE ACTION. Don't just read it - handle it. Search, verify, send, create, flag, file."
        
        # System prompt with dry run note
        system = SYSTEM_PROMPT
        if self.dry_run:
            system += "\n\n## DRY RUN MODE ACTIVE\nShow your full reasoning and what tools you WOULD call. Use search tools to demonstrate your logic, but don't execute action tools (send_reply, send_invoice, job_create, etc.)."
        
        messages = [{"role": "user", "content": user_message}]
        
        print("\n" + "-" * 80)
        print("INPUT EMAIL")
        print("-" * 80)
        print(f"From: {fake_email.sender} <{fake_email.sender_email}>")
        print(f"Subject: {fake_email.subject}")
        print(f"Body: {fake_email.body}")
        print("-" * 80)
        
        # Agent loop
        iteration = 0
        actions_taken = []
        final_text = ""
        
        while iteration < max_iterations:
            iteration += 1
            iter_start = time.time()
            
            print(f"\n{'=' * 80}")
            print(f"ITERATION {iteration}")
            print("=" * 80)
            
            # Clear tool logs for this iteration
            iter_tool_logs_start = len(self.tool_executor.tool_logs)
            
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=system,
                    tools=self.tools,
                    messages=messages
                )
            except Exception as e:
                print(f"ERROR: Claude API error: {e}")
                return {"success": False, "error": str(e), "iterations": iteration}
            
            # Track tokens
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            
            print(f"\n--- CLAUDE RESPONSE ---")
            print(f"Stop Reason: {response.stop_reason}")
            print(f"Input Tokens: {input_tokens:,}")
            print(f"Output Tokens: {output_tokens:,}")
            
            # Process content blocks
            print(f"\n--- CONTENT BLOCKS ({len(response.content)}) ---")
            
            for i, block in enumerate(response.content):
                print(f"\n[Block {i+1}] Type: {block.type}")
                
                if hasattr(block, 'text') and block.text:
                    print(f"Text: {block.text[:500]}{'...' if len(block.text) > 500 else ''}")
                
                if block.type == "tool_use":
                    print(f"Tool: {block.name}")
                    print(f"Input: {json.dumps(block.input, indent=2)}")
            
            if response.stop_reason == "tool_use":
                tool_results = []
                
                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        
                        # Action tools that modify state
                        action_tools = [
                            "email_send_reply", "email_send_new", "email_create_draft",
                            "qbo_send_invoice", "qbo_create_invoice", "qbo_create_customer", "qbo_create_project",
                            "job_create",
                            "email_move_to_folder", "email_create_folder",
                            "nas_write_file", "nas_copy_file", "nas_copy_directory", "nas_create_directory"
                        ]
                        
                        print(f"\n--- EXECUTING TOOL: {tool_name} ---")
                        
                        if self.dry_run and tool_name in action_tools:
                            result = json.dumps({
                                "dry_run": True,
                                "would_execute": tool_name,
                                "with_params": tool_input,
                                "message": f"DRY RUN: Would call {tool_name}"
                            })
                            print(f"[DRY RUN] Would call: {tool_name}")
                            print(f"[DRY RUN] With params: {json.dumps(tool_input, indent=2)}")
                            actions_taken.append(f"[DRY RUN] {tool_name}")
                        else:
                            result = self.tool_executor.execute(tool_name, tool_input)
                            actions_taken.append(tool_name)
                            print(f"Result: {result[:1000]}{'...' if len(result) > 1000 else ''}")
                        
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result
                        })
                
                # Continue conversation
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
                
                # Log this iteration
                iter_tool_logs = self.tool_executor.tool_logs[iter_tool_logs_start:]
                iter_elapsed = time.time() - iter_start
                
                self.iteration_logs.append({
                    "iteration": iteration,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "stop_reason": response.stop_reason,
                    "tools_called": [t["tool_name"] for t in iter_tool_logs],
                    "duration_ms": round(iter_elapsed * 1000, 2)
                })
                
            else:
                # Claude is done
                for block in response.content:
                    if hasattr(block, 'text'):
                        final_text += block.text
                
                iter_elapsed = time.time() - iter_start
                self.iteration_logs.append({
                    "iteration": iteration,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "stop_reason": response.stop_reason,
                    "tools_called": [],
                    "duration_ms": round(iter_elapsed * 1000, 2)
                })
                
                print(f"\n{'=' * 80}")
                print("AGENT COMPLETE")
                print("=" * 80)
                break
        
        # Build result
        result = {
            "success": True,
            "iterations": iteration,
            "actions": actions_taken,
            "final_response": final_text,
            "tool_logs": self.tool_executor.tool_logs,
            "iteration_logs": self.iteration_logs,
            "token_usage": {
                "total_input": self.total_input_tokens,
                "total_output": self.total_output_tokens,
                "total": self.total_input_tokens + self.total_output_tokens
            }
        }
        
        return result
    
    def print_analysis(self, result: dict):
        """Print detailed analysis of the test run."""
        print("\n" + "=" * 80)
        print("ANALYSIS SUMMARY")
        print("=" * 80)
        
        print(f"\n### Iterations: {result['iterations']}")
        print(f"### Success: {result['success']}")
        
        print(f"\n### Token Usage")
        print(f"  Input Tokens:  {result['token_usage']['total_input']:,}")
        print(f"  Output Tokens: {result['token_usage']['total_output']:,}")
        print(f"  Total Tokens:  {result['token_usage']['total']:,}")
        
        # Estimate cost (Claude Sonnet pricing: $3/M input, $15/M output)
        input_cost = (result['token_usage']['total_input'] / 1_000_000) * 3
        output_cost = (result['token_usage']['total_output'] / 1_000_000) * 15
        total_cost = input_cost + output_cost
        print(f"  Estimated Cost: ${total_cost:.4f}")
        
        print(f"\n### Actions Taken ({len(result['actions'])})")
        for action in result['actions']:
            print(f"  - {action}")
        
        print(f"\n### Tool Call Details ({len(result['tool_logs'])})")
        for i, log in enumerate(result['tool_logs'], 1):
            print(f"\n  [{i}] {log['tool_name']} ({log['duration_ms']}ms)")
            print(f"      Input:  {json.dumps(log['input'], indent=None)[:100]}")
            output_str = json.dumps(log['output'], indent=None)
            print(f"      Output: {output_str[:100]}{'...' if len(output_str) > 100 else ''}")
        
        print(f"\n### Iteration Breakdown")
        for log in result['iteration_logs']:
            tools = ', '.join(log['tools_called']) if log['tools_called'] else '(none)'
            print(f"  Iter {log['iteration']}: {log['input_tokens']:,}in/{log['output_tokens']:,}out, "
                  f"{log['duration_ms']}ms, stop={log['stop_reason']}, tools=[{tools}]")
        
        print(f"\n### Final Response")
        print("-" * 40)
        print(result['final_response'])
        print("-" * 40)


# ===========================================================================
# MAIN - RUN THE TEST
# ===========================================================================

def main():
    # Create fake email
    fake_email = FakeEmailMessage(
        message_id="FAKE-MSG-001-TEST",
        conversation_id="FAKE-CONV-001-TEST",
        sender="Nicholas Pardy",
        sender_email="nick@pardysurveys.com",
        subject="Info request - Job 25-180",
        body="""Can you tell me everything about job 25-180? I need the address, client info, property area from the files, and a copy of the original email when we received the request.""",
        received_date=datetime.now(timezone.utc),
        attachments=[]
    )
    
    # Initialize harness
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    harness = AgentTestHarness(config_path, dry_run=True)  # DRY RUN = True for safety
    
    print("\n" + "#" * 80)
    print("# STARTING EMAIL AUTOMATION AGENT TEST")
    print("# Using EXACT system prompt and tools from production")
    print("# DRY RUN MODE - No actual emails will be sent")
    print("#" * 80)
    
    # Run the test
    result = harness.run_test(fake_email)
    
    # Print analysis
    harness.print_analysis(result)
    
    # Save full log to file
    log_file = os.path.join(os.path.dirname(__file__), 'test_output_detailed.json')
    with open(log_file, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n[Full logs saved to: {log_file}]")
    
    return result


if __name__ == '__main__':
    main()
