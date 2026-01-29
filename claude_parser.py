"""
Claude Integration - Email parsing and classification using Claude AI
"""

import anthropic
import logging
import json
from typing import Dict, Optional
from email_service import EmailMessage

class ClaudeParser:
    """Uses Claude to parse and classify emails"""
    
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.logger = logging.getLogger(__name__)
    
    def classify_and_extract(self, email_msg: EmailMessage,
                            known_lawyer_domains: list = None) -> Dict:
        """
        Classify email and extract relevant information
        
        Returns dict with:
        - category: job_request, invoice_request, quote_request, question, 
                   correspondence, spam, etc.
        - confidence: float 0-1
        - extracted_data: dict with relevant fields
        - suggested_action: what to do with this email
        - response_text: optional auto-response text
        """
        
        # Build context for Claude
        lawyer_context = ""
        if known_lawyer_domains and any(domain in email_msg.sender_email 
                                       for domain in known_lawyer_domains):
            lawyer_context = "This email is from a known law firm client."
        
        prompt = f"""Analyze this email and classify it, then extract relevant information.

Email Details:
From: {email_msg.sender} <{email_msg.sender_email}>
Subject: {email_msg.subject}
Date: {email_msg.received_date}
{lawyer_context}

Body:
{email_msg.body}

Attachments: {', '.join([a['filename'] for a in email_msg.attachments]) if email_msg.attachments else 'None'}

Context: This is Pardy Surveys Inc., a land surveying company in Newfoundland and Labrador/Nova Scotia.
Most requests come from law firms for real estate closings.

IMPORTANT PATTERNS:
- Email chains contain quoted replies below separator lines (______ or "From:")
- Look at ENTIRE body including quoted portions for closing dates, addresses, job numbers
- Closing dates are often in SUBJECT LINES deep in the chain (e.g., "closing November 4")
- Job numbers follow pattern YY-NNN (e.g., 26-004, 25-123)
- Address format: "## Street Name, Community" (e.g., "15 Forest Road, St. John's")

JOB TYPES (critical for pricing):
- "survey_and_rpr" or "Survey & RPR" - most common, full survey with Real Property Report
- "rpr_only" - just updating an existing RPR, no new survey work
- "survey_only" - boundary survey without RPR (less common, needs quote)

METRO AREA communities (standard pricing): St. John's, Mount Pearl, Paradise, CBS, Conception Bay South, Portugal Cove-St. Philip's, PC-SP, PCSP, Logy Bay-Middle Cove-Outer Cove, LG-MC-OC, Holyrood, Petty Harbour-Maddox Cove, Petty Harbour, Maddox Cove

Classify this email into ONE category:

CATEGORIES:
1. job_request - NEW survey request ("please do a survey", "survey & RPR", etc.)
2. quote_request - Asking for price estimate BEFORE committing
3. invoice_request - Asking for invoice to be sent ("can we get the invoice")
4. status_inquiry - Asking about survey status or completion date  
5. general_question - Question about completed work (e.g., "what is the plastic stand")
6. correspondence - Follow-up about existing job (thank you, additional info, etc.)
7. vendor_invoice - Invoice FROM a vendor/supplier TO us
8. spam - Marketing, newsletters, automated messages
9. personal - Personal non-business email
10. urgent - Urgent matter requiring immediate attention

RESPOND IN VALID JSON FORMAT ONLY:
{{
  "category": "one of the categories above",
  "confidence": 0.95,
  "extracted_data": {{
    "job_number": "YY-NNN if found anywhere in email/thread, otherwise null",
    "client_name": "person who SENT the email (e.g., 'Debbie Aylward', 'Gary Nolan')",
    "client_email": "sender's email address",
    "client_business": "law firm or business name if applicable (e.g., 'William O\\'Keefe Law', 'Van Driel Law', 'Hyde Park Homes'), null if individual",
    "purchaser_name": "person BUYING the property (e.g., 'Yvonne Smith'), null if not mentioned",
    "property_address": "street address ONLY without community (e.g., '15 Forest Road')",
    "community": "town/city ONLY (e.g., 'St. John\\'s', 'Tors Cove', 'CBS') - CRITICAL",
    "job_type": "survey_and_rpr / rpr_only / survey_only / other",
    "is_metro_area": true/false based on community,
    "due_date": "YYYY-MM-DD format, or null if not found",
    "due_date_raw": "exact text (e.g., 'closing November 4')",
    "pid_number": "PID if mentioned",
    "file_number": "lawyer's file/matter number if mentioned",
    "urgency_level": "normal/high/urgent",
    "key_points": ["main point 1", "main point 2"],
    "community_unknown": true if community cannot be determined (PDF check needed)
  }},
  "suggested_action": "auto_create_job/flag_for_quote/flag_for_attention/archive",
  "reasoning": "brief explanation"
}}

CRITICAL RULES:
1. DUE DATE: Search subject lines AND body for "closing [date]". Convert to YYYY-MM-DD. This is CRITICAL.
2. COMMUNITY: Extract from address after comma. If "15 Forest Road, St. John's" -> community is "St. John's". If unknown, set community_unknown: true.
3. JOB TYPE: "Survey & RPR" or "new survey & RPR" = survey_and_rpr. "Updated RPR" alone = rpr_only. "boundary survey" = survey_only.
4. CLIENT: The sender is the client (law firm paralegal, lawyer, or individual). Extract their name and business."""
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            # Extract JSON from response
            response_text = response.content[0].text
            
            # Try to parse JSON (handle cases where Claude adds markdown)
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].strip()
            else:
                json_str = response_text.strip()
            
            result = json.loads(json_str)
            
            self.logger.info(f"Email classified as: {result.get('category')} "
                           f"(confidence: {result.get('confidence')})")
            
            return result
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse Claude response as JSON: {e}")
            self.logger.error(f"Response was: {response_text}")
            return {
                "category": "needs_manual_review",
                "confidence": 0.0,
                "extracted_data": {},
                "suggested_action": "flag_for_attention",
                "response_needed": False,
                "reasoning": "Failed to parse AI response"
            }
        except Exception as e:
            self.logger.error(f"Error calling Claude API: {e}")
            return {
                "category": "error",
                "confidence": 0.0,
                "extracted_data": {},
                "suggested_action": "flag_for_attention",
                "response_needed": False,
                "reasoning": f"API error: {str(e)}"
            }
    
    def generate_response(self, email_msg, category: str, job_context: dict = None, 
                          email_history: list = None) -> dict:
        """
        Generate an email response based on category and context.
        
        Returns: {
            "response_text": "...",
            "can_auto_send": True/False,
            "needs_info": True/False,
            "reason": "..."
        }
        """
        context_str = ""
        if job_context:
            # Field work status
            field_status = "Not started"
            if job_context.get('field_work_done'):
                field_dates = job_context.get('field_dates', [])
                if field_dates:
                    field_status = f"Complete (collected: {', '.join(field_dates[:3])})"
                else:
                    field_status = "Complete"
            elif job_context.get('layout_exists'):
                field_status = "Layout created, awaiting field collection"
            
            # Plan status
            plan_status = "Not started"
            if job_context.get('plan_drafted'):
                plan_status = "Drafted"
            elif job_context.get('field_work_done'):
                plan_status = "In progress (field work complete)"
            
            context_str = f"""
Job Context:
- Job Number: {job_context.get('job_number', 'Not assigned')}
- Property: {job_context.get('property_address', 'Unknown')}, {job_context.get('community', '')}, NL
- Client: {job_context.get('client_business') or job_context.get('client_name', 'Unknown')}
- Due Date: {job_context.get('due_date', 'Not set')}
- Job Type: {job_context.get('job_type', 'Unknown')}
- Field Work: {field_status}
- Plan/Drawing: {plan_status}
- Report: {'Done' if job_context.get('report_done') else 'Not done'}
"""
        
        history_str = ""
        if email_history:
            history_str = "\n\nRecent email history with this contact:\n"
            for h in email_history[:5]:  # Last 5 emails
                history_str += f"- {h.get('date', '')}: {h.get('subject', '')[:50]}\n"
        
        prompt = f"""You are responding on behalf of Pardy Surveys Inc., a land surveying company in Newfoundland.
Write a professional, friendly, and concise email response.

Original Email:
From: {email_msg.sender} <{email_msg.sender_email}>
Subject: {email_msg.subject}
Body: {email_msg.body[:1500]}

Category: {category}
{context_str}{history_str}

RESPONSE GUIDELINES:
- Be professional but warm - you're Nick, the owner
- Keep it brief (2-4 sentences usually)
- Sign off as just "Nick"
- For status inquiries: Give honest, specific update based on job context
  - "Field work is done, plan is being drafted" 
  - "Should have it to you by [due date]"
  - "Running a bit behind, will have it to you by [realistic date]"
- Never make promises you can't keep based on the context
- If field work not done and due date is soon, acknowledge delay

AUTO-SEND RULES (can_auto_send = true ONLY if ALL apply):
1. Response is a simple factual status update based on job context
2. No bad news or delays to communicate
3. No pricing, quotes, or money discussed
4. No commitments beyond what's already in the job
5. Standard response that doesn't need your judgment

Set can_auto_send = false if:
- Communicating delays or problems
- Anything about pricing or payment
- Client seems frustrated or urgent
- Response requires judgment or negotiation
- You're not 100% confident in the response

Respond with JSON:
{{
  "response_text": "The email body (no greeting like 'Hi X' - just start with content, end with Nick)",
  "can_auto_send": true/false,
  "needs_info": true/false (true if context is missing to give good response),
  "reason": "Brief explanation"
}}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text
            
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_str = response_text.split("```")[1].strip()
            else:
                json_str = response_text.strip()
            
            return json.loads(json_str)
            
        except Exception as e:
            self.logger.error(f"Error generating response: {e}")
            return {
                "response_text": None,
                "can_auto_send": False,
                "needs_info": True,
                "reason": f"Error: {str(e)}"
            }
