"""
Claude Agent Tools - Comprehensive
==================================
All tools Claude needs to manage emails, QBO, and NAS file system.
NO DELETE operations - only read, create, copy, move.
"""

import os
import json
import shutil
import logging
from datetime import datetime
from typing import Optional, Dict, List


def define_all_tools() -> list:
    """Define ALL tools Claude can use."""
    
    tools = []
    
    # =========================================================================
    # QBO - INVOICES
    # =========================================================================
    
    tools.append({
        "name": "qbo_search_invoices",
        "description": """Search QuickBooks invoices. Multiple search methods available.
        
Returns invoice details: id, number, amount, balance, due_date, customer, line descriptions (contain property addresses).

Examples:
- By number: {"invoice_number": "26-003"}
- By address: {"address": "49 Magee"} (partial match works)
- By customer email: {"customer_email": "lawyer@firm.ca"}
- By company domain: {"company_domain": "rvdslaw.ca"} (finds all invoices for anyone @rvdslaw.ca)
- Recent: {"recent_count": 20}""",
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string", "description": "Exact invoice number like '26-003'"},
                "address": {"type": "string", "description": "Property address (partial match OK)"},
                "customer_email": {"type": "string", "description": "Customer's email address"},
                "company_domain": {"type": "string", "description": "Email domain like 'rvdslaw.ca'"},
                "recent_count": {"type": "integer", "description": "Get N most recent invoices (max 50)"}
            }
        }
    })
    
    tools.append({
        "name": "qbo_get_invoice",
        "description": "Get full details of a specific invoice by its QBO ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "string", "description": "QBO invoice ID"}
            },
            "required": ["invoice_id"]
        }
    })
    
    tools.append({
        "name": "qbo_send_invoice",
        "description": "Send an invoice to a recipient via QuickBooks email. Use after confirming you have the right invoice.",
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_id": {"type": "string", "description": "QBO invoice ID"},
                "recipient_email": {"type": "string", "description": "Email address to send to"}
            },
            "required": ["invoice_id", "recipient_email"]
        }
    })
    
    tools.append({
        "name": "qbo_create_invoice",
        "description": """Create a new invoice in QuickBooks.

Standard items available:
- "Boundary Survey & Real Property Report" ($1,147.83) - for survey_and_rpr jobs
- "Real Property Report - Basic" ($695.65) - for rpr_only jobs

The invoice number (DocNumber) should match the job number (e.g., "26-005").""",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "QBO customer ID"},
                "invoice_number": {"type": "string", "description": "Invoice/job number like '26-005'"},
                "item_name": {"type": "string", "description": "Service item name"},
                "amount": {"type": "number", "description": "Amount (uses item default if not specified)"},
                "due_date": {"type": "string", "description": "Due date YYYY-MM-DD"},
                "description": {"type": "string", "description": "Line item description (usually property address)"},
                "project_id": {"type": "string", "description": "QBO project ID to link to"}
            },
            "required": ["customer_id", "invoice_number", "item_name"]
        }
    })
    
    # =========================================================================
    # QBO - ESTIMATES/QUOTES
    # =========================================================================

    tools.append({
        "name": "qbo_create_estimate",
        "description": """Create an estimate/quote in QuickBooks.

CRITICAL WORKFLOW - Must be used in proposal workflow:
1. First, ensure proposal exists and pricing_verified_by is set (Nicholas confirmed)
2. Create estimate with this tool
3. Send estimate with qbo_send_estimate
4. Update proposal: status=estimate_sent, estimate_id=[ID from this tool]
5. Wait for client acceptance before creating job

Use this for non-metro or complex jobs that need custom pricing from Nicholas.
The estimate number format is "E26-005 - Community" (abbreviated if needed).

After creating, use qbo_send_estimate to email it to the client.
Then update the proposal with the estimate_id.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "QBO customer ID"},
                "amount": {"type": "number", "description": "Quote amount (must be verified by Nicholas first!)"},
                "description": {"type": "string", "description": "Service description (usually property address)"},
                "property_address": {"type": "string", "description": "Property address for description formatting"},
                "community": {"type": "string", "description": "Community name for estimate number suffix"},
                "expiration_days": {"type": "integer", "description": "Days until quote expires (default 30)"},
                "customer_memo": {"type": "string", "description": "Note visible to customer on the quote"}
            },
            "required": ["customer_id", "amount"]
        }
    })

    tools.append({
        "name": "qbo_send_estimate",
        "description": "Send an estimate/quote to a customer via QuickBooks email.",
        "input_schema": {
            "type": "object",
            "properties": {
                "estimate_id": {"type": "string", "description": "QBO estimate ID"},
                "recipient_email": {"type": "string", "description": "Override recipient (uses customer email if not provided)"}
            },
            "required": ["estimate_id"]
        }
    })

    tools.append({
        "name": "qbo_get_estimate",
        "description": "Get full details of an estimate by ID, including status (Pending, Accepted, Closed, Rejected).",
        "input_schema": {
            "type": "object",
            "properties": {
                "estimate_id": {"type": "string", "description": "QBO estimate ID"}
            },
            "required": ["estimate_id"]
        }
    })

    tools.append({
        "name": "qbo_search_estimates",
        "description": """Search for estimates/quotes in QuickBooks.

Status values: Pending, Accepted, Closed, Rejected""",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Filter by customer"},
                "doc_number": {"type": "string", "description": "Filter by estimate number (partial match)"},
                "status": {"type": "string", "description": "Filter by status: Pending, Accepted, Closed, Rejected"},
                "recent_count": {"type": "integer", "description": "How many to return (default 20)"}
            }
        }
    })

    tools.append({
        "name": "qbo_convert_estimate_to_invoice",
        "description": """Convert an accepted estimate to an invoice.

Use this when a client accepts a quote - it creates an invoice linked to the original estimate.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "estimate_id": {"type": "string", "description": "QBO estimate ID to convert"}
            },
            "required": ["estimate_id"]
        }
    })

    # =========================================================================
    # QBO - CUSTOMERS
    # =========================================================================

    tools.append({
        "name": "qbo_search_customers",
        "description": "Search for customers in QuickBooks by name or email.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Customer/company name (partial match)"},
                "email": {"type": "string", "description": "Email address"}
            }
        }
    })
    
    tools.append({
        "name": "qbo_create_customer",
        "description": "Create a new customer in QuickBooks. Returns existing customer if email already exists.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Customer/company name"},
                "email": {"type": "string", "description": "Email address"},
                "phone": {"type": "string", "description": "Phone number"}
            },
            "required": ["name", "email"]
        }
    })
    
    # =========================================================================
    # QBO - PROJECTS
    # =========================================================================
    
    tools.append({
        "name": "qbo_search_projects",
        "description": "Search for projects in QuickBooks. Projects are used for job tracking.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Project name (usually job number like '26-003')"},
                "customer_id": {"type": "string", "description": "Get projects for a specific customer"}
            }
        }
    })
    
    tools.append({
        "name": "qbo_create_project",
        "description": """Create a new project in QuickBooks. Projects track jobs.
        
Project name should be the job number (e.g., "26-005").
Description should include property address and due date.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "QBO customer ID"},
                "name": {"type": "string", "description": "Project name (job number)"},
                "description": {"type": "string", "description": "Project description"}
            },
            "required": ["customer_id", "name"]
        }
    })
    
    tools.append({
        "name": "qbo_get_next_job_number",
        "description": "Get the next available job number by checking existing QBO projects. Returns something like '26-005'.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    })
    
    # =========================================================================
    # QBO - GENERAL
    # =========================================================================
    
    tools.append({
        "name": "qbo_get_service_items",
        "description": "List all service items/products available for invoicing. Shows names and prices.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    })
    
    tools.append({
        "name": "qbo_record_payment",
        "description": """Record payment for invoices. Use when processing deposit emails.
        
        Example email from Nick:
        Subject: Deposit
        Body:
        25-180
        25-175
        25-242
        
        Claude extracts the invoice numbers and calls this tool to mark them as paid.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "invoice_numbers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of invoice/job numbers to mark as paid (e.g., ['25-180', '25-175'])"
                },
                "payment_date": {
                    "type": "string",
                    "description": "Payment date YYYY-MM-DD (defaults to today)"
                }
            },
            "required": ["invoice_numbers"]
        }
    })

    tools.append({
        "name": "qbo_create_time_entry",
        "description": """Create time entry in QuickBooks for field work or travel.

        Use this to log time against a job. Time entries track:
        - Who did the work (employee name)
        - How long they worked (hours)
        - Which job it's for (job number)
        - What type of work (field time, travel, etc.)

        The sync process automatically creates time entries from Data Sync uploads,
        but use this tool for manual time logging or corrections.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "employee_name": {
                    "type": "string",
                    "description": "Employee name (e.g., 'Allan', 'Nicholas', 'Dylan')"
                },
                "hours": {
                    "type": "number",
                    "description": "Hours worked (decimal, e.g., 2.5 for 2h 30m)"
                },
                "job_number": {
                    "type": "string",
                    "description": "Job number to link time to (e.g., '26-001')"
                },
                "entry_type": {
                    "type": "string",
                    "enum": ["field", "travel", "drafting", "research", "other"],
                    "description": "Type of work (default: field)"
                },
                "date": {
                    "type": "string",
                    "description": "Date of work YYYY-MM-DD (defaults to today)"
                },
                "description": {
                    "type": "string",
                    "description": "Description of work done"
                },
                "billable": {
                    "type": "boolean",
                    "description": "Whether time is billable (default: true for field, false for travel)"
                }
            },
            "required": ["employee_name", "hours", "job_number"]
        }
    })

    tools.append({
        "name": "qbo_get_time_entries",
        "description": "Get time entries for a job. Shows who worked on it and for how long.",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_number": {
                    "type": "string",
                    "description": "Job number (e.g., '26-001')"
                }
            },
            "required": ["job_number"]
        }
    })

    # =========================================================================
    # QBO - EXPENSES
    # =========================================================================

    tools.append({
        "name": "qbo_record_expense",
        "description": """Record an expense/receipt in QuickBooks.

Use this when processing receipt emails. Creates a purchase/expense entry in QBO.

Common expense categories:
- "Office Supplies" - Paper, pens, general supplies
- "Equipment" - Tools, instruments, hardware
- "Vehicle Expense" - Fuel, maintenance, repairs
- "Software/Subscriptions" - Adobe, Microsoft, subscriptions
- "Professional Development" - Training, memberships, certifications
- "Insurance" - Business insurance payments
- "Utilities" - Phone, internet
- "Other" - Anything that doesn't fit above (add note)

Example: Receipt from Staples for $45.67 on printer paper
→ vendor: "Staples", amount: 45.67, category: "Office Supplies", description: "Printer paper"
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "vendor": {
                    "type": "string",
                    "description": "Vendor/supplier name (e.g., 'Staples', 'Amazon', 'Shell')"
                },
                "amount": {
                    "type": "number",
                    "description": "Total amount including tax"
                },
                "category": {
                    "type": "string",
                    "enum": ["Office Supplies", "Equipment", "Vehicle Expense", "Software/Subscriptions",
                             "Professional Development", "Insurance", "Utilities", "Other"],
                    "description": "Expense category"
                },
                "description": {
                    "type": "string",
                    "description": "What was purchased"
                },
                "date": {
                    "type": "string",
                    "description": "Purchase date YYYY-MM-DD (defaults to today)"
                },
                "payment_method": {
                    "type": "string",
                    "enum": ["Credit Card", "Debit", "Cash", "EFT", "Other"],
                    "description": "How it was paid (default: Credit Card)"
                },
                "receipt_email_id": {
                    "type": "string",
                    "description": "Email message ID for reference (links expense to source)"
                }
            },
            "required": ["vendor", "amount", "category", "description"]
        }
    })

    tools.append({
        "name": "qbo_refresh_time",
        "description": """Refresh ALL QBO time entries for a job and update the spine.

Pulls all time entries from QBO, categorizes them (auto-posted field/travel,
manual field, drafting, research, etc.), calculates totals, and stores in
the job index.

Use this to:
- Update time totals for a job after manual QBO entries
- Verify all time is captured correctly
- Get a breakdown of time by category (field, travel, drafting, research)

Returns:
- time_totals: Breakdown by category (field_auto, travel_auto, drafting, research, other)
- entry_count: Number of time entries
- all_entries: List of all entries with their categorization
""",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_number": {
                    "type": "string",
                    "description": "Job number (e.g., '26-008')"
                }
            },
            "required": ["job_number"]
        }
    })

    tools.append({
        "name": "qbo_find_item_by_name",
        "description": """Find a specific QBO service item by name and get its current price.

Use this to look up standard pricing before quoting clients.

Common items:
- "Real Property Report - Basic" - RPR only (client has recent <10yr survey)
- "Boundary Survey & Real Property Report" - Full survey + RPR (no recent survey)
- "Residential Construction - Single Dwelling" - House build survey bundle (sub-items included)

IMPORTANT: This gives you the standard rate for informational/rough estimate purposes.
Before sending a FORMAL QBO estimate, Nicholas must confirm the actual price.
I can tell clients "roughly $X" but QBO estimates require Nicholas's approval.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Service item name to find (e.g., 'Boundary Survey & Real Property Report')"
                }
            },
            "required": ["item_name"]
        }
    })

    # =========================================================================
    # EMAIL - READING
    # =========================================================================

    tools.append({
        "name": "email_get_unread",
        "description": "Get unread emails from inbox. Returns list with sender, subject, preview, date, message_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "description": "Max emails to return (default 20)"},
                "folder": {"type": "string", "description": "Folder name (default 'Inbox')"}
            }
        }
    })
    
    tools.append({
        "name": "email_get_by_id",
        "description": "Get email content by message ID. Returns body (truncated to ~20K chars by default to save tokens), attachments list, headers. If body is truncated, response includes body_truncated=true and note about how to get full content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "Email message ID"},
                "include_full_body": {"type": "boolean", "description": "Set to true to get up to 100K chars instead of 20K. Only use when you actually need the full content (e.g., long legal documents, detailed specs). Default: false"}
            },
            "required": ["message_id"]
        }
    })
    
    tools.append({
        "name": "email_search",
        "description": """Search emails with Microsoft Graph query syntax.

IMPORTANT: Keep queries SIMPLE. Complex queries often fail.

Good examples (simple, reliable):
- "from:@rvdslaw.ca Rankin" (domain + keyword)
- "from:gnolan@rvdslaw.ca" (just sender)
- "subject:25-180" (just subject keyword)
- "Rankin Street" (just keywords)

Avoid (often fails):
- Complex AND/OR: "from:x AND (subject:y OR body:z)"
- Quoted phrases in combinations: "from:x AND \"exact phrase\""
- Date ranges with other filters: "from:x AND received>=2025-01-01"

Strategy: Start broad, then narrow down. If first search fails, try simpler query.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query - keep it simple!"},
                "max_results": {"type": "integer", "description": "Max results (default 20)"},
                "folder": {"type": "string", "description": "Folder to search (default all)"}
            },
            "required": ["query"]
        }
    })
    
    tools.append({
        "name": "email_get_history_with_contact",
        "description": "Get recent email history (sent and received) with a specific contact.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email_address": {"type": "string", "description": "Contact's email address"},
                "max_results": {"type": "integer", "description": "Max emails (default 10)"}
            },
            "required": ["email_address"]
        }
    })
    
    tools.append({
        "name": "email_list_folders",
        "description": "List all email folders/labels available.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    })
    
    # =========================================================================
    # EMAIL - SENDING/REPLYING
    # =========================================================================
    
    tools.append({
        "name": "email_send_reply",
        "description": """Send a reply to an email. The reply is sent immediately and preserves the email thread.

Use for: confirmations, status updates, simple responses, sending files to Nicholas.
Automatically uses Claude's signature (with "HUMAN" safe word notice).
Override with signature="nick" if needed.

Can include a file attachment - use this instead of email_send_with_attachment when replying
to keep the conversation in the same thread.

The reply is automatically linked to the job index if the conversation thread
is already associated with a job. Provide job_number explicitly if known.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "ID of email to reply to"},
                "body": {"type": "string", "description": "Reply body text (signature appended automatically)"},
                "attachment_path": {
                    "type": "string",
                    "description": "Optional: Full path to file to attach to the reply (e.g., PDF from job folder)"
                },
                "signature": {
                    "type": "string",
                    "description": "Override signature: 'claude' (default) or 'nick'",
                    "enum": ["claude", "nick"]
                },
                "job_number": {
                    "type": "string",
                    "description": "Job number to link this reply to (auto-detected from conversation if not provided)"
                }
            },
            "required": ["body"]
        }
    })
    
    tools.append({
        "name": "email_create_draft",
        "description": """Create an email draft for human review before sending.

Use when:
- Not confident about the response
- Bad news or delays to communicate  
- Pricing/money discussions
- Complex situations needing judgment

Automatically uses Nick's signature (human will review and send).
Override with signature="claude" if needed.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "ID of email to reply to (for threading)"},
                "body": {"type": "string", "description": "Draft body text (signature appended automatically)"},
                "reason": {"type": "string", "description": "Why this needs human review"},
                "signature": {
                    "type": "string",
                    "description": "Override signature: 'nick' (default) or 'claude'",
                    "enum": ["claude", "nick"]
                }
            },
            "required": ["message_id", "body", "reason"]
        }
    })
    
    tools.append({
        "name": "email_send_new",
        "description": """Send a new email (not a reply).

Set importance="high" for urgent communications that need immediate attention.
This shows as high priority in the recipient's inbox with a red exclamation mark.

SIGNATURES:
- signature="claude" for automated responses (includes "HUMAN" safe word notice)
- signature="nick" for drafts or emails that need Nick's signature
- Omit signature parameter for plain emails without signature""",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string", "description": "Email subject"},
                "body": {"type": "string", "description": "Email body (signature appended automatically if specified)"},
                "cc": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of CC email addresses"
                },
                "importance": {
                    "type": "string",
                    "description": "Email priority: 'high', 'normal', or 'low'. Use 'high' for questions to Nicholas.",
                    "enum": ["high", "normal", "low"]
                },
                "signature": {
                    "type": "string",
                    "description": "Which signature to append: 'claude' for automated responses, 'nick' for drafts/human review",
                    "enum": ["claude", "nick"]
                },
                "in_reply_to": {
                    "type": "string",
                    "description": "Message ID to reply to (keeps email in same thread). Use this for [Hive Mind] follow-ups to maintain conversation history."
                }
            },
            "required": ["to", "subject", "body"]
        }
    })

    tools.append({
        "name": "email_send_with_attachment",
        "description": """Send a NEW email with a file attachment from the NAS.

WARNING: This creates a NEW email thread! If you're replying to an existing email thread,
use email_send_reply with attachment_path instead to keep the conversation together.

ONLY use this tool when starting a brand new email conversation with an attachment.

SECURITY RESTRICTION: Can ONLY send attachments to internal Pardy Surveys addresses:
- @pardysurveys.com
- pardysurveys@outlook.com

Use this when Nicholas or Joe asks for a file from the server AND you need to start
a new conversation. For external clients, use QBO to send invoices/estimates, or
create a draft for Nicholas to review.

Max file size: 150MB (uses upload session for files over 3MB)""",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email (MUST be internal @pardysurveys address)"},
                "subject": {"type": "string", "description": "Email subject"},
                "body": {"type": "string", "description": "Email body"},
                "attachment_path": {"type": "string", "description": "Full path to file on NAS"},
                "signature": {
                    "type": "string",
                    "description": "Which signature to append",
                    "enum": ["claude", "nick"]
                }
            },
            "required": ["to", "subject", "body", "attachment_path"]
        }
    })

    tools.append({
        "name": "email_sync_sent_to_jobs",
        "description": """Scan recent sent mail and link to relevant jobs in the index.

USE THIS AT THE START OF EACH SESSION to capture Nick's manual email replies
that bypass the automation. This ensures the job index has complete email history
even for messages Nick sends directly through Outlook.

The tool looks for:
1. Job numbers in subject lines (e.g., "RE: 26-009 Survey")
2. Known job addresses mentioned in the email

Skips emails already sent by Claude (marked with [Hive Mind]).""",
        "input_schema": {
            "type": "object",
            "properties": {
                "hours": {
                    "type": "integer",
                    "description": "How many hours back to scan (default 24)",
                    "default": 24
                }
            },
            "required": []
        }
    })

    # =========================================================================
    # EMAIL - ORGANIZATION
    # =========================================================================

    tools.append({
        "name": "email_move_to_folder",
        "description": "Move an email to a specific folder.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "Email message ID"},
                "folder_name": {"type": "string", "description": "Destination folder name"}
            },
            "required": ["message_id", "folder_name"]
        }
    })
    
    tools.append({
        "name": "email_mark_read",
        "description": "Mark an email as read.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "Email message ID"}
            },
            "required": ["message_id"]
        }
    })
    
    tools.append({
        "name": "email_mark_unread",
        "description": "Mark an email as unread (to come back to it later).",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "Email message ID"}
            },
            "required": ["message_id"]
        }
    })
    
    tools.append({
        "name": "email_flag_important",
        "description": "Flag an email as important/starred.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "Email message ID"}
            },
            "required": ["message_id"]
        }
    })
    
    tools.append({
        "name": "email_create_folder",
        "description": "Create a new email folder.",
        "input_schema": {
            "type": "object",
            "properties": {
                "folder_name": {"type": "string", "description": "Name for new folder"}
            },
            "required": ["folder_name"]
        }
    })
    
    # =========================================================================
    # EMAIL - ATTACHMENTS
    # =========================================================================
    
    tools.append({
        "name": "email_get_attachments",
        "description": "Get list of attachments for an email with their IDs and names.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "Email message ID"}
            },
            "required": ["message_id"]
        }
    })
    
    tools.append({
        "name": "email_save_attachment",
        "description": """Save an email attachment to the NAS.

TWO MODES - use the appropriate one:

1. JOB ATTACHMENTS (preferred): Provide job_number
   - Tool looks up the correct folder from job spine
   - Saves to {job_folder}/Reference & Research/Emails/{filename}
   - Prevents errors from misremembered paths
   - Example: job_number="26-010" → saves to correct 26-010 folder

2. NON-JOB ATTACHMENTS: Provide save_path
   - For receipts, general documents, etc.
   - You specify the exact path
   - Example: save_path="/volume1/Pardy Surveys/Receipts/invoice.pdf"

WORKFLOW FOR JOB ATTACHMENTS:
1. First identify which job the email relates to (search by address, client, conversation)
2. Link the email to that job using job_link_email
3. Save attachment using job_number parameter (NOT save_path)

This ensures attachments always go to the correct folder from the job spine.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "Email message ID"},
                "attachment_id": {"type": "string", "description": "Attachment ID"},
                "job_number": {"type": "string", "description": "Job number (e.g. '26-010'). If provided, saves to job's Reference & Research/Emails folder. PREFERRED for job attachments."},
                "save_path": {"type": "string", "description": "Full path where to save. Only use for NON-JOB attachments (receipts, etc). For job attachments, use job_number instead."},
                "subfolder": {"type": "string", "description": "Subfolder within job folder. Default: 'Reference & Research/Emails'. Only used with job_number."}
            },
            "required": ["message_id", "attachment_id"]
        }
    })
    
    # =========================================================================
    # NAS FILE SYSTEM - READING
    # =========================================================================
    
    tools.append({
        "name": "nas_list_directory",
        "description": """List contents of a directory on the NAS.

Important paths (from config):
- Jobs folder: /Jobs/YYYY/ - Job folders organized by year
- Template: /Jobs/YYYY/YY-000 - Template/ - Template folder structure
- Data Sync: /Data Sync/office-jobs/ - Field data sync from Trimble
- Flagged: Flagged items for attention (path from config)

Use recursive=true to see all nested contents.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path to list"},
                "recursive": {"type": "boolean", "description": "If true, list all nested contents recursively (default: false)"}
            },
            "required": ["path"]
        }
    })
    
    tools.append({
        "name": "nas_read_file",
        "description": """Read file contents. Supports:
        - Text files (.txt, .json, .csv, .xml, .md)
        - Word documents (.docx) - extracts text
        - Excel spreadsheets (.xlsx) - returns rows
        - PDFs (.pdf) - extracts text (max 10 pages)
        
        Binary files (.dwg, .dxf, .jpg, .zip, etc.) are rejected - use nas_get_file_info for metadata only.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Full file path"},
                "max_lines": {"type": "integer", "description": "Max lines/rows to read (default 100)"}
            },
            "required": ["path"]
        }
    })
    
    tools.append({
        "name": "nas_file_exists",
        "description": "Check if a file or directory exists.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to check"}
            },
            "required": ["path"]
        }
    })
    
    tools.append({
        "name": "nas_get_file_info",
        "description": "Get file information: size, modified date, type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"}
            },
            "required": ["path"]
        }
    })
    
    tools.append({
        "name": "nas_search_files",
        "description": "Search for files by name pattern in a directory (recursive).",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Directory to search in"},
                "pattern": {"type": "string", "description": "Filename pattern (e.g., '*.pdf', '*invoice*')"},
                "max_results": {"type": "integer", "description": "Max results (default 50)"}
            },
            "required": ["directory", "pattern"]
        }
    })
    
    # =========================================================================
    # NAS FILE SYSTEM - WRITING (NO DELETE)
    # =========================================================================
    
    tools.append({
        "name": "nas_create_directory",
        "description": "Create a new directory (and parent directories if needed).",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path to create"}
            },
            "required": ["path"]
        }
    })
    
    tools.append({
        "name": "nas_write_file",
        "description": "Write content to a text file. Creates file if doesn't exist, overwrites if it does.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to write"},
                "content": {"type": "string", "description": "Content to write"}
            },
            "required": ["path", "content"]
        }
    })
    
    tools.append({
        "name": "nas_copy_file",
        "description": "Copy a file to a new location.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Source file path"},
                "destination": {"type": "string", "description": "Destination file path"}
            },
            "required": ["source", "destination"]
        }
    })
    
    tools.append({
        "name": "nas_copy_directory",
        "description": "Copy an entire directory tree to a new location. Useful for copying template folders.",
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Source directory path"},
                "destination": {"type": "string", "description": "Destination directory path"}
            },
            "required": ["source", "destination"]
        }
    })
    
    tools.append({
        "name": "nas_move_file",
        "description": "Move a file to a new location (for organizing, NOT deleting).",
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Source file path"},
                "destination": {"type": "string", "description": "Destination file path"}
            },
            "required": ["source", "destination"]
        }
    })
    
    # =========================================================================
    # JOB MANAGEMENT
    # =========================================================================
    
    tools.append({
        "name": "job_create",
        "description": """Create a complete new job: QBO customer, project, invoice, AND NAS folder structure.

This is the main tool for creating jobs from incoming requests. It:
1. Gets next job number from QBO
2. Creates/finds customer in QBO
3. Creates project in QBO
4. Creates invoice in QBO (with due_date)
5. Copies template folder to /Jobs/YYYY/
6. Adds to job index

DUE DATE HANDLING:
- If due_date is NOT provided, the system defaults to NEXT BUSINESS DAY
- The result will include "due_date_defaulted": true
- When you see this flag, you MUST ask the client to confirm the closing/due date in your reply

PURCHASER NAME:
- For law firm emails: if purchaser_name not in email, ask "Who should this be certified to?" in your reply

Metro areas (standard pricing from QBO): St. John's, Mount Pearl, Paradise, CBS, Portugal Cove-St. Philip's, Logy Bay-Middle Cove-Outer Cove, Holyrood, Petty Harbour-Maddox Cove
Non-metro: Requires quote - job still created but flagged.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_name": {"type": "string", "description": "Contact name (e.g., 'Gary Nolan')"},
                "client_email": {"type": "string", "description": "Contact email"},
                "client_business": {"type": "string", "description": "Business/firm name (e.g., 'Van Driel Law')"},
                "property_address": {"type": "string", "description": "Street address (e.g., '15 Forest Road')"},
                "community": {"type": "string", "description": "Town/city (e.g., 'St. John\\'s', 'Paradise')"},
                "due_date": {"type": "string", "description": "Closing/due date YYYY-MM-DD. If omitted, defaults to next business day and client should be asked to confirm."},
                "job_type": {
                    "type": "string",
                    "enum": ["survey_and_rpr", "rpr_only", "survey_only"],
                    "description": "Type of work"
                },
                "purchaser_name": {"type": "string", "description": "Purchaser name (who certificate is made to). Required for law firm requests - ask if not provided."},
                "conversation_id": {"type": "string", "description": "Email thread ID for tracking"},
                "message_id": {"type": "string", "description": "Original email message ID"}
            },
            "required": ["client_name", "client_email", "property_address", "community"]
        }
    })
    
    tools.append({
        "name": "job_search",
        "description": """Search for existing jobs. Returns ALL matches for disambiguation.

IMPORTANT: This returns multiple matches if query is ambiguous!
- Search "Green Acre" might return 3 different jobs on Green Acre streets
- Results are sorted: active/recent jobs first, then completed, then paid/closed
- Use match_count to see how many results
- If match_count > 1 and query was vague, ASK user which one they meant

Returns: {found, match_count, matches[], job (first/best match)}""",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_number": {"type": "string", "description": "Job number like '26-003' (exact match)"},
                "address": {"type": "string", "description": "Property address (partial match - may return multiple!)"},
                "client_email": {"type": "string", "description": "Client email address"},
                "conversation_id": {"type": "string", "description": "Email thread ID"}
            }
        }
    })

    tools.append({
        "name": "job_cancel",
        "description": """Cancel a job. This preserves history while marking the job as cancelled.

Actions taken:
1. Marks job as 'cancelled' in the spine (history preserved)
2. Renames QBO project to "[CANCELLED] XX-XXX"
3. Voids the invoice in QBO (unless void_invoice=false)
4. Job number is preserved but skipped for future jobs

Use when: A job needs to be cancelled (client backed out, duplicate entry, etc.)
The job number will be skipped - next job will get the next sequential number.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_number": {
                    "type": "string",
                    "description": "Job number to cancel (e.g., '26-011')"
                },
                "reason": {
                    "type": "string",
                    "description": "Reason for cancellation"
                },
                "void_invoice": {
                    "type": "boolean",
                    "description": "Whether to void the QBO invoice (default: true)"
                }
            },
            "required": ["job_number", "reason"]
        }
    })

    tools.append({
        "name": "job_get_status",
        "description": """Comprehensive job status from all sources - use for field work, documents, job status questions.

Reads LIVE from Data Sync folders - the SOURCE OF TRUTH for field work.

=== FIELD TIME DATA (from Data Sync) ===

Reads field_status.json which contains:
- time_spent: {field_hours: 6, travel_hours_oneway: 1}
- operator: "Allan", "Joe", etc.
- field_work_done: true/false
- notes: "BATTERY CHARGING ISSUES"

Note: QBO time entries may lag - Data Sync is always current for field work.

Every call ENRICHES the job_index with discovered data.

=== RETURNS ===

data_sync: Controller/field work tracking (LIVE from disk)
├── data_sync[]: Each layout sent to Trimble
│   ├── job_info.address, description, field_data_complete
│   └── field_uploads[]: Field data with time_spent, operator, notes
└── all_complete: true if every layout has field data

nas_folder: NAS job folder contents
├── layout_files[], field_data_files[]: Data folder
├── drawing_files[], report_files[]: Work products
├── reference_files{}: Research by category (CADO, Plans, Crown Lands)
└── saved_emails[]: Correspondence

document_control: Stamped/sent deliverables (PARSED FROM NAMING)
├── documents[]: Each document set
│   ├── doc_number: 1, 2, 3...
│   ├── description: "25-180-1.pdf" (stamped)
│   ├── drawing: "25-180--1.pdf" (double hyphen = drawing)
│   ├── sent_file: "9 Rankin Street (25-180-1).pdf" (parentheses = sent)
│   └── latest_revision: null or R1, R2...
├── total_documents, total_sent
└── all_sent: true if everything delivered

=== HIVE BEHAVIOR ===

Data SAVED to job_index after each call:
- Next query is instant (cached)
- Emails can find job history
- Claude knows what's been sent without searching

=== INTERPRETING DOCUMENT STATUS ===

total_documents=3, total_sent=2 → 1 document not yet delivered
latest_revision=2 → Document on revision R2
all_sent=true → Job fully delivered""",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_number": {"type": "string", "description": "Job number like '25-180'"}
            },
            "required": ["job_number"]
        }
    })
    
    tools.append({
        "name": "job_save_email",
        "description": "Save an email to a job's Reference & Research\\Emails folder. Also links to hive index.",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_number": {"type": "string", "description": "Job number"},
                "message_id": {"type": "string", "description": "Email message ID to save"}
            },
            "required": ["job_number", "message_id"]
        }
    })
    
    tools.append({
        "name": "job_link_email",
        "description": """Link current email to a job in the hive index (WITHOUT saving file to disk).

IMPORTANT: ALWAYS provide a summary! This is critical for token efficiency.

When follow-up emails arrive in the same thread, we use your stored summaries
instead of re-reading the full quoted chain. No summary = wasted tokens later.

WHAT GETS STORED:
- Email metadata (subject, from, date, message_id, conversation_id)
- Your summary (1-2 sentences describing content/purpose) - ALWAYS PROVIDE THIS
- key_info (structured data like closing dates, purchaser names, amounts)
- Full body (truncated to 10K chars for later deep dives if needed)

THREAD FOLLOWING: Set link_conversation=true to auto-link ALL emails in the same
conversation thread. This ensures follow-up emails are automatically associated.

When to use:
- After identifying the related job number
- For status inquiries, invoice requests, follow-ups
- When email doesn't need to be saved but should be tracked
- Use link_conversation=true for initial job requests to capture the whole thread

Example summary: "Lawyer requesting RPR for title insurance claim, closing Jan 30th"
Example key_info: {"closing_date": "2026-01-30", "document_requested": "RPR"}""",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_number": {"type": "string", "description": "Job number to link to"},
                "summary": {"type": "string", "description": "REQUIRED: 1-2 sentence summary of email content/purpose. Critical for token efficiency on follow-ups."},
                "key_info": {
                    "type": "object",
                    "description": "Structured extracted info: closing_date, purchaser_name, document_requested, deadline, quote_amount, etc."
                },
                "message_id": {"type": "string", "description": "Email message ID (uses current email if not provided)"},
                "link_conversation": {
                    "type": "boolean",
                    "description": "If true, also links all other emails in the same thread (default false)"
                }
            },
            "required": ["job_number"]
        }
    })
    
    tools.append({
        "name": "job_list_recent",
        "description": "List recent jobs from the job index.",
        "input_schema": {
            "type": "object",
            "properties": {
                "count": {"type": "integer", "description": "Number of recent jobs (default 10)"}
            }
        }
    })

    # =========================================================================
    # THREAD EMAIL TOOLS - For efficient access to stored email content
    # =========================================================================
    # These tools let Claude access emails stored in the job index without
    # hitting the Graph API. Summaries first, then expand to full body if needed.

    tools.append({
        "name": "job_get_thread_emails",
        "description": """Get all emails linked to a job, showing summaries for quick context.

Returns a list of emails with:
- Index number (use with job_get_email_body to get full content)
- Date, direction (inbound/outbound), sender
- Summary (your previously stored summary)
- Key info (extracted data like dates, names)

Use this to understand a thread's history without loading full content.
Then use job_get_email_body with the index number to expand specific emails.

Example flow:
1. job_get_thread_emails("26-004") -> see 5 emails with summaries
2. job_get_email_body("26-004", 3) -> get full body of email #3 for exact wording""",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_number": {"type": "string", "description": "Job number to get emails for"},
                "conversation_id": {"type": "string", "description": "Optional: filter to specific thread only"}
            },
            "required": ["job_number"]
        }
    })

    tools.append({
        "name": "job_get_email_body",
        "description": """Get the full stored body of a specific email from the job index.

Use after job_get_thread_emails to expand a specific email when you need:
- Exact wording for drafting a reply
- Specific details not captured in summary
- Full context of a particular message

This retrieves from the job index (instant) - no Graph API call needed.
The email_index is the number shown in job_get_thread_emails output.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_number": {"type": "string", "description": "Job number"},
                "email_index": {"type": "integer", "description": "Email index from job_get_thread_emails (1-based)"}
            },
            "required": ["job_number", "email_index"]
        }
    })
    
    tools.append({
        "name": "job_set_pending",
        "description": """Mark a job as awaiting human input.

Use AFTER you've emailed Nicholas with a question about this job.
This tracks that the job is waiting for an answer so future sessions 
can check for replies and continue the work.

Required: job_number, question (what you asked), email_id (message_id of your question email)
Optional: question_type, context (original request details for continuity)""",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_number": {"type": "string", "description": "Job number this question relates to"},
                "question": {"type": "string", "description": "Clear description of what you're asking"},
                "question_type": {
                    "type": "string",
                    "description": "Category: community_classification, pricing, clarification, access, other"
                },
                "email_id": {"type": "string", "description": "Message ID of the question email you sent"},
                "context": {
                    "type": "object",
                    "description": "Original request details for continuity (from, subject, key_info, etc.)"
                }
            },
            "required": ["job_number", "question", "email_id"]
        }
    })
    
    tools.append({
        "name": "job_clear_pending",
        "description": """Clear pending status after receiving and processing Nicholas's answer.

Call this AFTER you've continued work on a job that was awaiting input.
This removes the awaiting_input status so the job is no longer flagged as pending.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_number": {"type": "string", "description": "Job number to clear pending status for"},
                "resolution": {"type": "string", "description": "Brief note on how the question was resolved"}
            },
            "required": ["job_number"]
        }
    })
    
    tools.append({
        "name": "job_get_pending",
        "description": """Get all jobs currently awaiting input.

Use this at the START of email processing to check if any of your previous 
questions have been answered. Returns list of pending jobs with their 
question details and email IDs so you can search for replies.""",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    })
    
    tools.append({
        "name": "job_update",
        "description": """Update job fields and sync to QBO if applicable.

Use this when job information comes in later, like:
- due_date/closing_date from a follow-up email
- purchaser_name when discovered
- Notes about the job

This updates BOTH the spine AND syncs to QBO where applicable.
For example, updating due_date will also update the invoice DueDate in QBO.

TODO (FUTURE): When planner is implemented, updating due_date should trigger
rescheduling to ensure the job can be completed on time.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_number": {"type": "string", "description": "Job number to update (required)"},
                "due_date": {"type": "string", "description": "New closing/due date YYYY-MM-DD - syncs to QBO"},
                "purchaser_name": {"type": "string", "description": "Purchaser name"},
                "client_name": {"type": "string", "description": "Updated client name"},
                "notes": {"type": "string", "description": "Notes to append to job"}
            },
            "required": ["job_number"]
        }
    })

    # =========================================================================
    # PROPOSAL TRACKING (Pre-Job Inquiries)
    # =========================================================================

    tools.append({
        "name": "proposal_create",
        "description": """Create a new proposal for a pre-job inquiry.

Use when:
- Inquiry received but not ready to become a job
- Need pricing from Nicholas (non-metro or complex)
- Missing key information
- Client is shopping around / might not proceed

IMPORTANT: PRIMARY storage is internal proposal_index.json (always works).
Filesystem write to Proposals folder is backup (may fail on NAS permissions).

Status flow: new → info_gathering → awaiting_pricing → estimate_sent → accepted → converted

CRITICAL WORKFLOW:
1. Create proposal (status: new)
2. Gather info from client (status: info_gathering)
3. Once all info gathered → status: awaiting_pricing
4. Email Nicholas to verify pricing
5. After Nicholas confirms → Create QBO Estimate and send
6. After estimate sent → status: estimate_sent
7. After client accepts → status: accepted
8. Use proposal_convert_to_job to create full job

⚠️ 10-YEAR RULE: If client CONFIRMS survey is > 10 years old or doesn't exist, they need full Boundary Survey + RPR. But don't assume - we can often find old surveys through title search or neighbors.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_name": {"type": "string", "description": "Client/company name"},
                "client_email": {"type": "string", "description": "Client email address"},
                "client_phone": {"type": "string", "description": "Client phone number if provided"},
                "property_address": {"type": "string", "description": "Property address if known"},
                "community": {"type": "string", "description": "Community/city name"},
                "service_requested": {"type": "string", "description": "What they're asking for (RPR, survey, etc.)"},
                "job_type": {
                    "type": "string",
                    "description": "Type of work. Only set boundary_and_rpr if client CONFIRMS no survey exists or it's >10 years old. Use 'unknown' if we need to search first.",
                    "enum": ["boundary_and_rpr", "rpr_only", "construction", "other", "unknown"]
                },
                "reference_survey_year": {
                    "type": "integer",
                    "description": "Year of existing survey IF CLIENT KNOWS. Leave blank if unknown - we may find one through title search."
                },
                "closing_date": {"type": "string", "description": "Closing date if provided (YYYY-MM-DD)"},
                "purchaser_name": {"type": "string", "description": "Purchaser name if known"},
                "status": {
                    "type": "string",
                    "description": "Initial status (default: new)",
                    "enum": ["new", "info_gathering", "awaiting_pricing", "estimate_sent", "accepted"]
                },
                "missing_info": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of missing information needed (e.g., ['address', 'closing_date', 'previous_survey'])"
                },
                "notes": {"type": "string", "description": "Any additional notes or context"},
                "source_email_id": {"type": "string", "description": "Message ID of original inquiry email"},
                "conversation_id": {"type": "string", "description": "Email thread ID for tracking"}
            },
            "required": ["client_name", "client_email"]
        }
    })

    tools.append({
        "name": "proposal_update",
        "description": """Update an existing proposal with new information.

Use when:
- Client provides missing info
- Status changes (got pricing, sent quote, etc.)
- Need to add notes or communication records
- Nicholas verified pricing
- Estimate was sent or accepted

Can lookup proposal by proposal_id, conversation_id, or client_email.

STATUS TRANSITIONS:
- new → info_gathering: Started gathering details from client
- info_gathering → awaiting_pricing: All info gathered, need Nicholas to verify pricing
- awaiting_pricing → estimate_sent: After Nicholas verifies AND QBO estimate sent
- estimate_sent → accepted: Client accepts estimate
- accepted → converted: Use proposal_convert_to_job

NOTE: Don't assume no survey exists just because client doesn't have a copy. We can often find old surveys through title search or neighbors.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "proposal_id": {"type": "string", "description": "Proposal ID (or use conversation_id/client_email to find)"},
                "conversation_id": {"type": "string", "description": "Email thread ID (alternative lookup)"},
                "client_email": {"type": "string", "description": "Client email (alternative lookup)"},
                "status": {
                    "type": "string",
                    "enum": ["new", "info_gathering", "awaiting_pricing", "estimate_sent", "accepted", "declined", "expired"]
                },
                "property_address": {"type": "string"},
                "community": {"type": "string"},
                "closing_date": {"type": "string"},
                "purchaser_name": {"type": "string"},
                "job_type": {
                    "type": "string",
                    "description": "Type of work. Only set boundary_and_rpr if client CONFIRMS no survey or >10 years old.",
                    "enum": ["boundary_and_rpr", "rpr_only", "construction", "other", "unknown"]
                },
                "reference_survey_year": {
                    "type": "integer",
                    "description": "Year of existing survey IF CLIENT KNOWS. Leave blank if unknown."
                },
                "quoted_price": {"type": "number", "description": "Price quoted to client"},
                "quote_sent_date": {"type": "string", "description": "Date quote was sent (YYYY-MM-DD)"},
                "estimate_id": {"type": "string", "description": "QBO estimate ID if created"},
                "pricing_verified_by": {
                    "type": "string",
                    "description": "Who verified pricing (usually 'Nicholas'). REQUIRED before estimate can be sent!"
                },
                "missing_info": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "string", "description": "Additional notes to append"},
                "communication": {
                    "type": "object",
                    "description": "Communication to log (date, direction, summary)",
                    "properties": {
                        "direction": {"type": "string", "enum": ["inbound", "outbound"]},
                        "summary": {"type": "string"}
                    }
                }
            },
            "required": []
        }
    })

    tools.append({
        "name": "proposal_get",
        "description": """Get a specific proposal by ID, conversation_id, or client_email.

Returns full proposal details including next_steps guidance based on current status.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "proposal_id": {"type": "string", "description": "Proposal ID"},
                "conversation_id": {"type": "string", "description": "Email thread ID (alternative lookup)"},
                "client_email": {"type": "string", "description": "Client email (alternative lookup - returns active proposal)"}
            },
            "required": []
        }
    })

    tools.append({
        "name": "proposal_search",
        "description": """Search for proposals by various criteria.

Returns matching proposals sorted by date (most recent first).""",
        "input_schema": {
            "type": "object",
            "properties": {
                "client_email": {"type": "string", "description": "Search by client email"},
                "client_name": {"type": "string", "description": "Search by client name (partial match)"},
                "property_address": {"type": "string", "description": "Search by address (partial match)"},
                "status": {
                    "type": "string",
                    "description": "Filter by status",
                    "enum": ["new", "awaiting_info", "awaiting_pricing", "quoted", "accepted", "declined", "expired"]
                },
                "conversation_id": {"type": "string", "description": "Search by email thread ID"}
            }
        }
    })

    tools.append({
        "name": "proposal_list",
        "description": """List recent proposals, optionally filtered by status.

Use to see what inquiries are in progress.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Filter by status (optional)",
                    "enum": ["new", "awaiting_info", "awaiting_pricing", "quoted", "accepted", "declined", "expired"]
                },
                "count": {"type": "integer", "description": "Max number to return (default 20)"}
            }
        }
    })

    tools.append({
        "name": "proposal_convert_to_job",
        "description": """Convert an accepted proposal to a full job.

This is the culmination of the quote workflow:
1. Creates job using job_create (QBO customer, project, invoice, NAS folder)
2. Updates proposal status to 'accepted' with job_number
3. Archives proposal with job reference

Requires: proposal_id and all info needed for job_create (client_name, client_email,
property_address, community). If closing_date/purchaser not in proposal, provide them.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "proposal_id": {"type": "string", "description": "Proposal ID to convert"},
                "closing_date": {"type": "string", "description": "Closing date if not in proposal (YYYY-MM-DD)"},
                "purchaser_name": {"type": "string", "description": "Purchaser name if not in proposal"},
                "price": {"type": "number", "description": "Final price (uses quoted_price if not provided)"}
            },
            "required": ["proposal_id"]
        }
    })

    # =========================================================================
    # FLAGGING / ATTENTION
    # =========================================================================

    tools.append({
        "name": "flag_for_attention",
        "description": """Flag something for human (Nick's) attention.

This tool will:
1. Save details to flagged folder (backup/audit trail)
2. Move the email to "Needs Attention" folder in Outlook
3. Keep the email UNREAD so Nicholas sees it in his inbox

Use when:
- Can't determine what to do
- Something seems wrong or unusual
- Needs human judgment
- Outside your capabilities
- Error occurred

IMPORTANT: Do NOT call email_mark_read or email_move_to_folder separately - this tool handles both automatically.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Clear explanation of why this needs attention"},
                "email_info": {"type": "object", "description": "Email details if relevant (sender, subject, body)"},
                "context": {"type": "string", "description": "Additional context or what you tried"}
            },
            "required": ["reason"]
        }
    })
    
    # =========================================================================
    # UTILITIES
    # =========================================================================
    
    tools.append({
        "name": "log_system_error",
        "description": """Log a system/infrastructure error for tracking.

Use this when you encounter problems that suggest something is broken:
- Path not found / file not accessible when it should be
- API errors or unexpected responses
- Permission denied errors
- Tool failures that shouldn't happen
- Data inconsistencies

This logs to system_errors.jsonl for Nicholas to review.
Different from flag_for_attention - this is for SYSTEM issues, not email decisions.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "error_type": {
                    "type": "string",
                    "description": "Category: path_error, api_error, permission_error, data_error, tool_error"
                },
                "message": {"type": "string", "description": "Clear description of what went wrong"},
                "context": {"type": "object", "description": "Relevant details (paths, parameters, etc.)"}
            },
            "required": ["error_type", "message"]
        }
    })

    tools.append({
        "name": "get_current_datetime",
        "description": "Get current date and time in Newfoundland timezone.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    })
    
    tools.append({
        "name": "parse_date",
        "description": """Parse a natural language date into YYYY-MM-DD format.

Examples:
- "January 25" -> "2026-01-25"
- "closing next Friday" -> "2026-01-24"
- "Jan 25th" -> "2026-01-25" """,
        "input_schema": {
            "type": "object",
            "properties": {
                "date_text": {"type": "string", "description": "Date text to parse"}
            },
            "required": ["date_text"]
        }
    })
    
    return tools
