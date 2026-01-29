"""
Email Service - Microsoft Graph API Implementation
Handles OAuth2 authentication and email operations via Microsoft Graph
"""

import msal
import requests
import json
import os
import re
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, quote
import threading

logger = logging.getLogger(__name__)


def extract_new_content(body: str) -> tuple[str, bool]:
    """
    Extract only the NEW content from an email, stripping quoted reply chains.

    Returns:
        (new_content, had_quoted_content) - The new part and whether quotes were stripped

    Common quote markers:
    - "On <date> <person> wrote:"
    - "From: <email>"
    - "-----Original Message-----"
    - "> " prefixed lines
    - "________________________________" (Outlook separator)
    """
    if not body:
        return "", False

    lines = body.split('\n')
    new_lines = []
    found_quote_start = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Check for common quote start markers
        if not found_quote_start:
            # "On Mon, Jan 23, 2026 at 10:30 AM John wrote:"
            if re.match(r'^On .+wrote:?\s*$', stripped, re.IGNORECASE):
                found_quote_start = True
                continue

            # "From: someone@email.com" at start of line (not inline)
            if re.match(r'^From:\s+\S+@\S+', stripped, re.IGNORECASE):
                found_quote_start = True
                continue

            # Outlook: "-----Original Message-----"
            if '-----Original Message-----' in stripped:
                found_quote_start = True
                continue

            # Outlook horizontal rule separator
            if stripped.startswith('_' * 20):
                found_quote_start = True
                continue

            # Gmail-style: "---------- Forwarded message ---------"
            if 'Forwarded message' in stripped and '---' in stripped:
                found_quote_start = True
                continue

            new_lines.append(line)
        # Once we find a quote marker, stop

    new_content = '\n'.join(new_lines).strip()

    # Also strip trailing signature if it's clearly after the main content
    # (signature usually starts with -- or has very short lines at end)

    return new_content, found_quote_start


def deduplicate_thread_content(body: str) -> str:
    """
    Remove duplicate [Hive Mind] emails from a quoted thread chain.

    Outlook includes the full thread in the body, and when Claude sends a [Hive Mind]
    email asking Nicholas for pricing, then Nicholas replies, the body contains:
    1. Nicholas's new reply
    2. The [Hive Mind] email (quoted)
    3. Previous emails which may ALSO include the same [Hive Mind] email

    This function removes duplicate [Hive Mind] blocks to reduce token waste.
    """
    if not body or '[Hive Mind]' not in body:
        return body

    # Split by common email separators
    separators = [
        '________________________________________',
        '-----Original Message-----',
        '________________________________',
    ]

    # Find sections that contain [Hive Mind]
    lines = body.split('\n')
    sections = []
    current_section = []

    for line in lines:
        # Check if this line starts a new quoted email section
        is_separator = any(sep in line for sep in separators)
        if is_separator and current_section:
            sections.append('\n'.join(current_section))
            current_section = [line]
        else:
            current_section.append(line)

    if current_section:
        sections.append('\n'.join(current_section))

    # Track seen [Hive Mind] content to detect duplicates
    seen_hive_mind_signatures = set()
    deduplicated_sections = []

    for section in sections:
        if '[Hive Mind]' in section:
            # Create a signature based on key content (client, property, conversation ID)
            # to detect duplicates even if formatting varies slightly
            signature_parts = []
            for line in section.split('\n'):
                line_lower = line.lower().strip()
                if any(key in line_lower for key in ['client:', 'property:', 'conversation id:', '**client:**', '**property:**']):
                    signature_parts.append(line.strip())

            signature = '|'.join(sorted(signature_parts))

            if signature and signature in seen_hive_mind_signatures:
                # Skip this duplicate [Hive Mind] section
                deduplicated_sections.append("\n[...duplicate Hive Mind email removed...]\n")
                continue
            elif signature:
                seen_hive_mind_signatures.add(signature)

        deduplicated_sections.append(section)

    return '\n'.join(deduplicated_sections)


def html_to_text(html: str) -> str:
    """
    Convert HTML email to plain text.
    Strips all HTML tags, CSS, scripts, and extracts readable content.
    """
    if not html:
        return ""
    
    # Remove script and style elements entirely
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<head[^>]*>.*?</head>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Replace common block elements with newlines
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</?p[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</?div[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</?tr[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</?li[^>]*>', '\n• ', text, flags=re.IGNORECASE)
    
    # Remove all remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Decode common HTML entities
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    text = text.replace('&rsquo;', "'")
    text = text.replace('&lsquo;', "'")
    text = text.replace('&rdquo;', '"')
    text = text.replace('&ldquo;', '"')
    text = text.replace('&mdash;', '—')
    text = text.replace('&ndash;', '–')
    
    # Clean up whitespace
    text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces/tabs to single space
    text = re.sub(r'\n\s*\n', '\n\n', text)  # Multiple newlines to double
    text = re.sub(r'\n{3,}', '\n\n', text)  # Max 2 newlines
    text = text.strip()
    
    return text


@dataclass
class EmailMessage:
    """Structured email message from Graph API"""
    message_id: str
    subject: str
    sender: str
    sender_email: str
    body: str
    html_body: Optional[str]
    attachments: List[Dict]
    received_date: datetime
    is_read: bool
    conversation_id: Optional[str] = None  # Thread ID - all emails in same chain share this
    internet_message_id: Optional[str] = None  # RFC822 Message-ID - consistent across folders
    
class OAuth2Handler(BaseHTTPRequestHandler):
    """Handles OAuth2 callback"""
    auth_code = None
    
    def do_GET(self):
        """Handle GET request with auth code"""
        query = urlparse(self.path).query
        params = parse_qs(query)
        
        if 'code' in params:
            OAuth2Handler.auth_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"""
                <html><body>
                <h1>Authorization Successful!</h1>
                <p>You can close this window and return to the application.</p>
                <script>window.close();</script>
                </body></html>
            """)
        else:
            self.send_response(400)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress logging"""
        pass

class EmailService:
    """Microsoft Graph API Email Service with OAuth2"""
    
    # Microsoft Graph API endpoints
    AUTHORITY = "https://login.microsoftonline.com/consumers"
    GRAPH_ENDPOINT = "https://graph.microsoft.com/v1.0"
    
    # Scopes needed for full email access
    SCOPES = [
        "https://graph.microsoft.com/Mail.ReadWrite",
        "https://graph.microsoft.com/Mail.Send",
        "https://graph.microsoft.com/User.Read"
    ]
    
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str = "http://localhost:8000/callback", token_cache_file: str = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        # Token cache path - use provided value, or try config_loader, or fallback
        if token_cache_file:
            self.token_cache_file = token_cache_file
        else:
            try:
                from config_loader import get_config
                self.token_cache_file = get_config().token_cache_graph
            except Exception:
                # Fallback for standalone use
                self.token_cache_file = os.path.join(os.path.dirname(__file__), "data", "graph_token_cache_v2.json")
        self.access_token = None
        self.logger = logging.getLogger(__name__)
        
        # Initialize MSAL app
        self.app = msal.ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=self.AUTHORITY,
            token_cache=self._load_token_cache()
        )
    
    def _load_token_cache(self):
        """Load token cache from file"""
        cache = msal.SerializableTokenCache()
        if os.path.exists(self.token_cache_file):
            with open(self.token_cache_file, 'r') as f:
                cache.deserialize(f.read())
        return cache
    
    def _save_token_cache(self):
        """Save token cache to file"""
        if self.app.token_cache.has_state_changed:
            with open(self.token_cache_file, 'w') as f:
                f.write(self.app.token_cache.serialize())
    
    def _get_auth_code_interactive(self) -> Optional[str]:
        """Get authorization code via browser"""
        auth_url = self.app.get_authorization_request_url(
            scopes=self.SCOPES,
            redirect_uri=self.redirect_uri
        )
        
        self.logger.info("Opening browser for authorization...")
        self.logger.info(f"If browser doesn't open, go to: {auth_url}")
        
        # Start local server to catch callback
        server = HTTPServer(('localhost', 8000), OAuth2Handler)
        OAuth2Handler.auth_code = None
        
        # Open browser
        webbrowser.open(auth_url)
        
        # Wait for callback (timeout after 5 minutes)
        server.timeout = 300
        server.handle_request()
        server.server_close()
        
        return OAuth2Handler.auth_code
    
    def authenticate(self, allow_interactive: bool = True) -> bool:
        """
        Authenticate with Microsoft Graph API.
        
        For NAS/headless deployment, set allow_interactive=False to prevent
        browser popup attempts. Will only use cached tokens.
        """
        # Try to get token from cache
        accounts = self.app.get_accounts()
        if accounts:
            self.logger.info("Found cached account, attempting silent authentication...")
            result = self.app.acquire_token_silent(self.SCOPES, account=accounts[0])
            if result and 'access_token' in result:
                self.access_token = result['access_token']
                self._save_token_cache()  # Save in case MSAL refreshed internally
                self.logger.info("Silent authentication successful")
                return True
            else:
                self.logger.warning("Silent authentication failed - tokens may be expired")
        
        # Need interactive authentication
        if not allow_interactive:
            self.logger.error("No valid cached tokens and interactive auth disabled (headless mode)")
            self.logger.error("Run with allow_interactive=True on a machine with a browser first")
            return False
        
        self.logger.info("No cached token, starting interactive authentication...")
        auth_code = self._get_auth_code_interactive()
        
        if not auth_code:
            self.logger.error("Failed to get authorization code")
            return False
        
        # Exchange code for token
        result = self.app.acquire_token_by_authorization_code(
            code=auth_code,
            scopes=self.SCOPES,
            redirect_uri=self.redirect_uri
        )
        
        if 'access_token' in result:
            self.access_token = result['access_token']
            self._save_token_cache()
            self.logger.info("Authentication successful!")
            return True
        else:
            self.logger.error(f"Authentication failed: {result.get('error_description', 'Unknown error')}")
            return False
    
    def _make_graph_call(self, endpoint: str, method: str = "GET", data: dict = None, prefer_text_body: bool = False) -> Optional[dict]:
        """Make authenticated call to Graph API"""
        if not self.access_token:
            if not self.authenticate():
                return None
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        # Request plain text body instead of HTML (preserves links, cleaner for AI processing)
        if prefer_text_body:
            headers['Prefer'] = 'outlook.body-content-type="text"'
        
        url = f"{self.GRAPH_ENDPOINT}{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data)
            elif method == "PATCH":
                response = requests.patch(url, headers=headers, json=data)
            
            if response.status_code == 401:
                # Token expired, re-authenticate
                self.logger.info("Token expired, re-authenticating...")
                if self.authenticate():
                    return self._make_graph_call(endpoint, method, data)
                return None
            
            response.raise_for_status()
            return response.json() if response.content else {}
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Graph API call failed: {e}")
            return None
    
    def get_new_emails(self, only_unread: bool = True) -> List[EmailMessage]:
        """Fetch new emails from inbox"""
        filter_query = "$filter=isRead eq false" if only_unread else ""
        endpoint = f"/me/messages?{filter_query}&$top=50&$orderby=receivedDateTime desc"
        
        result = self._make_graph_call(endpoint, prefer_text_body=True)
        if not result or 'value' not in result:
            return []
        
        emails = []
        for msg in result['value']:
            try:
                email = self._parse_email_message(msg)
                emails.append(email)
            except Exception as e:
                self.logger.error(f"Error parsing email: {e}")
                continue
        
        self.logger.info(f"Fetched {len(emails)} emails")
        return emails
    
    def get_emails_since(self, since_datetime: datetime) -> List[EmailMessage]:
        """Fetch only emails received after a specific time from INBOX only.

        IMPORTANT: Uses /mailFolders/inbox/messages instead of /messages to avoid
        picking up our own sent replies (which would cause duplicate processing).
        """
        # Format datetime for Graph API (ISO 8601)
        since_str = since_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Filter: received after timestamp (from INBOX only, not Sent Items)
        filter_query = f"$filter=receivedDateTime ge {since_str}"
        endpoint = f"/me/mailFolders/inbox/messages?{filter_query}&$top=50&$orderby=receivedDateTime asc"

        result = self._make_graph_call(endpoint, prefer_text_body=True)
        if not result or 'value' not in result:
            return []

        emails = []
        for msg in result['value']:
            try:
                email = self._parse_email_message(msg)
                emails.append(email)
            except Exception as e:
                self.logger.error(f"Error parsing email: {e}")
                continue

        self.logger.info(f"Fetched {len(emails)} emails since {since_str}")
        return emails

    def get_inbox_message_ids(self, max_results: int = 50) -> List[str]:
        """Fetch just the message IDs from Inbox (lightweight call).

        Used to compare against our processed IDs list to find emails
        that need processing - without fetching full email content.

        Args:
            max_results: Maximum number of IDs to return

        Returns:
            List of message ID strings currently in Inbox
        """
        # Only request id field - minimal data transfer
        endpoint = f"/me/mailFolders/inbox/messages?$top={max_results}&$select=id"

        result = self._make_graph_call(endpoint)
        if not result or 'value' not in result:
            return []

        return [msg['id'] for msg in result['value']]

    def get_emails_by_ids(self, message_ids: List[str]) -> List[EmailMessage]:
        """Fetch full email content for specific message IDs.

        Args:
            message_ids: List of message IDs to fetch

        Returns:
            List of EmailMessage objects
        """
        emails = []
        for msg_id in message_ids:
            try:
                # Explicitly request internetMessageId - needed for Claude-sent detection
                # The internetMessageId (RFC822 Message-ID) is consistent across folders,
                # unlike the Graph API 'id' which changes when the same email appears in different folders
                result = self._make_graph_call(
                    f"/me/messages/{msg_id}?$select=id,subject,from,body,receivedDateTime,isRead,conversationId,internetMessageId,hasAttachments",
                    prefer_text_body=True
                )
                if result:
                    email = self._parse_email_message(result)
                    emails.append(email)
            except Exception as e:
                self.logger.error(f"Error fetching email {msg_id[:20]}: {e}")
                continue

        return emails

    def get_inbox_needing_response(self, max_age_days: int = 7) -> List[EmailMessage]:
        """
        Get inbox emails that might need a response.

        Logic: Emails in Inbox that are:
        - Received within max_age_days
        - From external senders (not pardysurveys)
        - Where we haven't replied yet (no sent mail in same conversation)

        This catches emails you've read but haven't responded to.
        """
        # Calculate cutoff date
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Get recent inbox emails (read or unread)
        # Include internetMessageId for Claude-sent detection
        filter_query = f"$filter=receivedDateTime ge {cutoff_str}"
        endpoint = f"/me/mailFolders/inbox/messages?{filter_query}&$top=50&$orderby=receivedDateTime desc&$select=id,subject,from,body,receivedDateTime,isRead,conversationId,internetMessageId,hasAttachments"

        result = self._make_graph_call(endpoint, prefer_text_body=True)
        if not result or 'value' not in result:
            return []

        emails = []
        for msg in result['value']:
            try:
                # Skip emails from ourselves
                sender_email = msg.get('from', {}).get('emailAddress', {}).get('address', '').lower()
                if 'pardysurveys' in sender_email:
                    continue

                email = self._parse_email_message(msg)
                emails.append(email)
            except Exception as e:
                self.logger.error(f"Error parsing email: {e}")
                continue

        self.logger.info(f"Found {len(emails)} inbox emails that may need response")
        return emails
    
    def _parse_email_message(self, msg: dict) -> EmailMessage:
        """Parse Graph API email message"""
        sender_data = msg.get('from', {}).get('emailAddress', {})
        
        # Get body - convert HTML to plain text to save API costs
        body_data = msg.get('body', {})
        raw_body = body_data.get('content', '')
        content_type = body_data.get('contentType', '')
        
        # We request text format via Prefer header, so body should already be plain text
        # Microsoft preserves links in format: text<https://link.com>
        if content_type.lower() == 'html':
            # Fallback if HTML somehow returned - use our converter
            body = html_to_text(raw_body)
            html_body = raw_body
        else:
            # Text format - use directly (this is the normal case now)
            body = raw_body
            html_body = None
        
        # Get attachments info
        attachments = []
        if msg.get('hasAttachments', False):
            att_endpoint = f"/me/messages/{msg['id']}/attachments"
            att_result = self._make_graph_call(att_endpoint)
            if att_result and 'value' in att_result:
                for att in att_result['value']:
                    attachments.append({
                        'filename': att.get('name', 'unknown'),
                        'content_type': att.get('contentType', ''),
                        'size': att.get('size', 0),
                        'id': att.get('id'),
                        'data': att.get('contentBytes')  # Base64 encoded
                    })
        
        return EmailMessage(
            message_id=msg['id'],
            subject=msg.get('subject', '(No Subject)'),
            sender=sender_data.get('name', ''),
            sender_email=sender_data.get('address', ''),
            body=body,
            html_body=html_body,
            attachments=attachments,
            received_date=datetime.fromisoformat(msg['receivedDateTime'].replace('Z', '+00:00')),
            is_read=msg.get('isRead', False),
            conversation_id=msg.get('conversationId'),  # Thread ID for matching related emails
            internet_message_id=msg.get('internetMessageId')  # RFC822 ID - consistent across folders
        )
    
    def mark_as_read(self, message_id: str) -> bool:
        """Mark email as read"""
        endpoint = f"/me/messages/{message_id}"
        data = {"isRead": True}
        result = self._make_graph_call(endpoint, method="PATCH", data=data)
        return result is not None
    
    def move_to_folder(self, message_id: str, folder_name: str) -> bool:
        """Move email to folder. Supports nested paths like 'Email/Marketing'."""
        # Handle nested folder paths (e.g., "Email/Marketing")
        folder_parts = folder_name.split('/')

        # Start at root level
        current_parent_id = None
        current_folder_id = None

        for i, part in enumerate(folder_parts):
            # Get folders at current level
            if current_parent_id:
                endpoint = f"/me/mailFolders/{current_parent_id}/childFolders"
            else:
                endpoint = "/me/mailFolders"

            folders_result = self._make_graph_call(endpoint)
            if not folders_result:
                return False

            # Find matching folder at this level
            found_id = None
            for folder in folders_result.get('value', []):
                if folder.get('displayName') == part:
                    found_id = folder['id']
                    break

            if not found_id:
                # Create folder at this level
                if current_parent_id:
                    create_endpoint = f"/me/mailFolders/{current_parent_id}/childFolders"
                else:
                    create_endpoint = "/me/mailFolders"

                create_result = self._make_graph_call(
                    create_endpoint,
                    method="POST",
                    data={"displayName": part}
                )
                if create_result:
                    found_id = create_result['id']
                else:
                    # 409 Conflict means folder already exists - re-fetch to find it
                    folders_retry = self._make_graph_call(endpoint)
                    if folders_retry:
                        for folder in folders_retry.get('value', []):
                            if folder.get('displayName') == part:
                                found_id = folder['id']
                                break
                    if not found_id:
                        return False

            # Move to next level
            current_parent_id = found_id
            current_folder_id = found_id

        if not current_folder_id:
            return False

        # Move message to final folder
        endpoint = f"/me/messages/{message_id}/move"
        data = {"destinationId": current_folder_id}
        result = self._make_graph_call(endpoint, method="POST", data=data)
        return result is not None
    
    def send_email(self, to_email: str, subject: str, body: str, html: bool = False, importance: str = None, cc: list = None, signature: str = None, in_reply_to: str = None) -> dict:
        """Send an email

        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body
            html: If True, body is HTML content
            importance: Optional - "high", "normal", or "low"
            cc: Optional list of CC email addresses
            signature: Optional - "claude" or "nick" to append signature
            in_reply_to: Optional message ID to thread this email with (keeps conversation together)

        Returns:
            dict with success status and message_id if available
        """
        # Append signature if requested
        final_body = body
        if signature:
            try:
                from signatures import get_signature_html_body
                sig_html = get_signature_html_body(signature)
                if sig_html:
                    if html:
                        # Body is already HTML, append signature
                        final_body = body + "<br><br>" + sig_html
                    else:
                        # Convert plain text body to HTML and append signature
                        html_body = body.replace('\n', '<br>')
                        final_body = f"<div>{html_body}</div><br><br>{sig_html}"
                    html = True  # Force HTML since we're adding HTML signature
            except Exception as e:
                self.logger.warning(f"Failed to load signature '{signature}': {e}")
        
        message = {
            "message": {
                "subject": subject,
                "body": {
                    "contentType": "HTML" if html else "Text",
                    "content": final_body
                },
                "toRecipients": [
                    {
                        "emailAddress": {
                            "address": to_email
                        }
                    }
                ]
            }
        }
        
        # Add CC recipients if specified
        if cc:
            message["message"]["ccRecipients"] = [
                {"emailAddress": {"address": addr}} for addr in cc
            ]
        
        # Add importance if specified
        if importance and importance.lower() in ("high", "normal", "low"):
            message["message"]["importance"] = importance.lower()

        # Thread with existing conversation if in_reply_to is specified
        if in_reply_to:
            original = self._make_graph_call(f"/me/messages/{in_reply_to}")
            if original and original.get("conversationId"):
                message["message"]["conversationId"] = original["conversationId"]
                self.logger.info(f"Threading email with conversation {original['conversationId'][:30]}...")

        result = self._make_graph_call("/me/sendMail", method="POST", data=message)
        if result is None:
            return {"success": False}

        # Try to get the sent message ID from Sent Items
        sent_msg_id = self._get_recent_sent_message_id(subject, seconds_ago=30)
        return {"success": True, "message_id": sent_msg_id}

    def get_recent_sent_email_conversation_id(self, subject_contains: str, seconds_ago: int = 60) -> Optional[str]:
        """
        Get the conversation_id of a recently sent email by matching subject.

        Used to track [Hive Mind] emails after sending them, so we can detect
        Nicholas's replies in the same conversation thread.

        Args:
            subject_contains: Partial subject to match (e.g., "[Hive Mind]")
            seconds_ago: How far back to look (default 60 seconds)

        Returns:
            conversation_id if found, None otherwise
        """
        # Calculate cutoff time
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
        cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Query Sent Items for recent emails matching subject
        filter_query = f"$filter=sentDateTime ge {cutoff_str} and contains(subject, '{subject_contains}')"
        endpoint = f"/me/mailFolders/sentItems/messages?{filter_query}&$top=1&$orderby=sentDateTime desc"

        result = self._make_graph_call(endpoint)
        if result and result.get('value'):
            msg = result['value'][0]
            conversation_id = msg.get('conversationId')
            if conversation_id:
                self.logger.info(f"Found sent email conversation_id: {conversation_id[:30]}...")
                return conversation_id

        return None

    def _get_recent_sent_message_id(self, subject_contains: str = None, seconds_ago: int = 30) -> Optional[str]:
        """
        Get the internetMessageId of the most recently sent email.
        Used internally after sending to track which emails Claude sent.

        NOTE: We return internetMessageId (RFC822 Message-ID), NOT the Graph API 'id'.
        The Graph API 'id' is different for the same email in different folders (Sent Items vs Inbox).
        The internetMessageId is consistent across all folders, so we can detect Claude's sent
        emails even when they appear in Inbox (e.g., when emailing yourself for testing).

        Args:
            subject_contains: Optional partial subject to match (for verification)
            seconds_ago: How far back to look (default 30 seconds)

        Returns:
            internetMessageId if found, None otherwise
        """
        # Calculate cutoff time
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
        cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Query Sent Items for the most recent email - include internetMessageId
        filter_query = f"$filter=sentDateTime ge {cutoff_str}"
        endpoint = f"/me/mailFolders/sentItems/messages?{filter_query}&$top=1&$orderby=sentDateTime desc&$select=id,subject,internetMessageId"

        result = self._make_graph_call(endpoint)
        if result and result.get('value'):
            msg = result['value'][0]
            internet_msg_id = msg.get('internetMessageId')
            msg_subject = msg.get('subject', '')
            if internet_msg_id:
                self.logger.info(f"Found sent email internetMessageId: {internet_msg_id[:50]}... subject: {msg_subject[:50]}")
                return internet_msg_id

        self.logger.warning(f"Could not find recently sent email (looked back {seconds_ago}s)")
        return None

    def send_email_with_attachment(self, to_email: str, subject: str, body: str,
                                    attachment_path: str, html: bool = False,
                                    signature: str = None) -> dict:
        """
        Send an email with a file attachment.

        SECURITY: Only allows sending to @pardysurveys.com or @outlook.com (our accounts)

        Args:
            to_email: Recipient email (must be internal pardysurveys address)
            subject: Email subject
            body: Email body
            attachment_path: Full path to file on NAS
            html: If True, body is HTML content
            signature: Optional - "claude" or "nick" to append signature

        Returns:
            dict with success status and error message if failed
        """
        import base64
        import mimetypes

        # SECURITY CHECK: Only allow internal email addresses containing "pardysurveys"
        # This covers: pardysurveys@outlook.com, joe@pardysurveys.com, nick@pardysurveys.com, etc.
        email_lower = to_email.lower()
        if 'pardysurveys' not in email_lower:
            self.logger.warning(f"Blocked attachment send to external address: {to_email}")
            return {
                "success": False,
                "error": f"Security: Can only send file attachments to Pardy Surveys addresses (must contain 'pardysurveys'). '{to_email}' is not allowed."
            }

        # Check file exists
        if not os.path.exists(attachment_path):
            return {"success": False, "error": f"File not found: {attachment_path}"}

        # Check file size (Graph API max: 150MB via upload session)
        file_size = os.path.getsize(attachment_path)
        if file_size > 150 * 1024 * 1024:  # 150MB hard limit
            return {"success": False, "error": f"File too large ({file_size / 1024 / 1024:.1f}MB). Max 150MB for email attachments."}

        # Get filename and mime type
        filename = os.path.basename(attachment_path)
        mime_type, _ = mimetypes.guess_type(attachment_path)
        if not mime_type:
            mime_type = 'application/octet-stream'

        # Append signature if requested
        final_body = body
        if signature:
            try:
                from signatures import get_signature_html_body
                sig_html = get_signature_html_body(signature)
                if sig_html:
                    if html:
                        final_body = body + "<br><br>" + sig_html
                    else:
                        html_body = body.replace('\n', '<br>')
                        final_body = f"<div>{html_body}</div><br><br>{sig_html}"
                    html = True
            except Exception as e:
                self.logger.warning(f"Failed to load signature '{signature}': {e}")

        # Use draft + upload session approach for all attachments (supports up to 150MB)
        return self._send_attachment_via_draft(to_email, subject, final_body, attachment_path, filename, mime_type, file_size, html)

    def _send_attachment_via_draft(self, to_email: str, subject: str, body: str,
                                    attachment_path: str, filename: str, mime_type: str,
                                    file_size: int, html: bool = False) -> dict:
        """
        Send email with attachment using draft + upload session approach.
        Works for files up to 150MB.

        Process:
        1. Create a draft message
        2. Upload the attachment using upload session (for large files) or direct (for small)
        3. Send the draft
        """
        import base64

        # Step 1: Create draft message
        draft_data = {
            "subject": subject,
            "body": {
                "contentType": "HTML" if html else "Text",
                "content": body
            },
            "toRecipients": [
                {"emailAddress": {"address": to_email}}
            ]
        }

        draft = self._make_graph_call("/me/messages", method="POST", data=draft_data)
        if not draft or not draft.get('id'):
            return {"success": False, "error": "Failed to create draft message"}

        draft_id = draft['id']
        self.logger.info(f"Created draft for attachment: {draft_id[:30]}...")

        # Step 2: Upload attachment
        try:
            if file_size <= 3 * 1024 * 1024:
                # Small file - use direct attachment
                with open(attachment_path, 'rb') as f:
                    file_content = f.read()
                file_base64 = base64.b64encode(file_content).decode('utf-8')

                attach_data = {
                    "@odata.type": "#microsoft.graph.fileAttachment",
                    "name": filename,
                    "contentType": mime_type,
                    "contentBytes": file_base64
                }

                result = self._make_graph_call(f"/me/messages/{draft_id}/attachments", method="POST", data=attach_data)
                if not result:
                    # Clean up draft
                    self._make_graph_call(f"/me/messages/{draft_id}", method="DELETE")
                    return {"success": False, "error": "Failed to attach file to draft"}
            else:
                # Large file - use upload session
                upload_success = self._upload_large_attachment(draft_id, attachment_path, filename, mime_type, file_size)
                if not upload_success:
                    # Clean up draft
                    self._make_graph_call(f"/me/messages/{draft_id}", method="DELETE")
                    return {"success": False, "error": "Failed to upload large attachment"}

        except Exception as e:
            # Clean up draft on error
            self._make_graph_call(f"/me/messages/{draft_id}", method="DELETE")
            return {"success": False, "error": f"Failed to process attachment: {e}"}

        # Step 3: Send the draft
        result = self._make_graph_call(f"/me/messages/{draft_id}/send", method="POST")
        if result is not None:
            self.logger.info(f"Sent email with attachment '{filename}' ({file_size / 1024 / 1024:.1f}MB) to {to_email}")
            # Try to get the sent message ID from Sent Items
            sent_msg_id = self._get_recent_sent_message_id(subject, seconds_ago=60)
            return {"success": True, "filename": filename, "message_id": sent_msg_id}
        else:
            return {"success": False, "error": "Failed to send draft"}

    def _upload_large_attachment(self, message_id: str, file_path: str, filename: str,
                                  mime_type: str, file_size: int) -> bool:
        """
        Upload a large attachment (>3MB) using Graph API upload session.
        Supports files up to 150MB.
        """
        import requests

        # Create upload session
        session_data = {
            "AttachmentItem": {
                "@odata.type": "#microsoft.graph.attachmentItem",
                "attachmentType": "file",
                "name": filename,
                "size": file_size,
                "contentType": mime_type
            }
        }

        session_result = self._make_graph_call(
            f"/me/messages/{message_id}/attachments/createUploadSession",
            method="POST",
            data=session_data
        )

        if not session_result or not session_result.get('uploadUrl'):
            self.logger.error("Failed to create upload session")
            return False

        upload_url = session_result['uploadUrl']
        self.logger.info(f"Created upload session for {filename} ({file_size / 1024 / 1024:.1f}MB)")

        # Upload file in chunks (4MB chunks)
        chunk_size = 4 * 1024 * 1024  # 4MB
        try:
            with open(file_path, 'rb') as f:
                chunk_start = 0
                while chunk_start < file_size:
                    chunk_end = min(chunk_start + chunk_size, file_size) - 1
                    chunk_data = f.read(chunk_size)
                    actual_chunk_size = len(chunk_data)

                    headers = {
                        'Content-Type': 'application/octet-stream',
                        'Content-Length': str(actual_chunk_size),
                        'Content-Range': f'bytes {chunk_start}-{chunk_end}/{file_size}'
                    }

                    response = requests.put(upload_url, headers=headers, data=chunk_data)

                    if response.status_code not in [200, 201, 202]:
                        self.logger.error(f"Upload chunk failed: {response.status_code} - {response.text[:200]}")
                        return False

                    chunk_start = chunk_end + 1
                    self.logger.info(f"Uploaded chunk: {chunk_start}/{file_size} bytes")

            self.logger.info(f"Successfully uploaded {filename}")
            return True

        except Exception as e:
            self.logger.error(f"Error uploading large attachment: {e}")
            return False

    def save_attachment(self, attachment: Dict, folder_path: str) -> Optional[str]:
        """Save attachment to disk, returns filepath"""
        import base64
        
        filename = attachment.get('filename', 'unknown')
        data = attachment.get('data')
        
        if not data:
            self.logger.warning(f"No data for attachment: {filename}")
            return None
        
        try:
            # Decode base64 content
            file_content = base64.b64decode(data)
            
            # Ensure folder exists
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            
            # Save file
            filepath = os.path.join(folder_path, filename)
            with open(filepath, 'wb') as f:
                f.write(file_content)
            
            self.logger.info(f"Saved attachment: {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"Error saving attachment {filename}: {e}")
            return None
    
    def create_draft(self, to_email: str, subject: str, body: str, 
                     html: bool = False, reply_to_message_id: str = None, signature: str = None) -> Optional[str]:
        """
        Create a draft email (saves to Drafts folder for review).
        Returns the draft message ID if successful.
        
        Args:
            signature: Optional - "claude" or "nick" to append signature
        """
        # Append signature if requested
        final_body = body
        if signature:
            try:
                from signatures import get_signature_html_body
                sig_html = get_signature_html_body(signature)
                if sig_html:
                    if html:
                        final_body = body + "<br><br>" + sig_html
                    else:
                        html_body = body.replace('\n', '<br>')
                        final_body = f"<div>{html_body}</div><br><br>{sig_html}"
                    html = True
            except Exception as e:
                self.logger.warning(f"Failed to load signature '{signature}': {e}")
        
        message = {
            "subject": subject,
            "body": {
                "contentType": "HTML" if html else "Text",
                "content": final_body
            },
            "toRecipients": [
                {"emailAddress": {"address": to_email}}
            ]
        }
        
        # If replying, set the conversation reference
        if reply_to_message_id:
            # Get the original message to get conversation ID
            original = self._make_graph_call(f"/me/messages/{reply_to_message_id}")
            if original:
                message["conversationId"] = original.get("conversationId")
        
        result = self._make_graph_call("/me/messages", method="POST", data=message)
        
        if result and result.get('id'):
            self.logger.info(f"Created draft: {subject[:50]}...")
            return result['id']
        return None
    
    def reply_to_email(self, message_id: str, reply_body: str,
                       html: bool = False, send_immediately: bool = True, signature: str = None,
                       attachment_path: str = None) -> bool:
        """
        Reply to an email in the same thread.
        Uses Graph API 'comment' field which automatically preserves the conversation thread.
        If send_immediately=False, creates a draft reply instead.

        Args:
            signature: Optional - "claude" or "nick" to append signature
            attachment_path: Optional - path to file to attach to the reply
        """
        import base64
        import mimetypes

        # Build the reply content with signature
        final_body = reply_body
        if signature:
            try:
                from signatures import get_signature_html_body
                sig_html = get_signature_html_body(signature)
                self.logger.info(f"Loaded signature '{signature}': {len(sig_html) if sig_html else 0} bytes")
                if sig_html:
                    # Convert plain text to HTML and append signature
                    html_body = reply_body.replace('\n', '<br>')
                    final_body = f"<div>{html_body}</div><br><br>{sig_html}"
                    html = True
            except Exception as e:
                self.logger.warning(f"Failed to load signature '{signature}': {e}")

        # If there's an attachment, we MUST use the draft approach
        if attachment_path:
            if not os.path.exists(attachment_path):
                return {"success": False, "error": f"Attachment not found: {attachment_path}"}
            send_immediately = False  # Force draft approach for attachments

        if send_immediately:
            # Get the original message subject for tracking sent message ID later
            original_msg = self._make_graph_call(f"/me/messages/{message_id}?$select=subject")
            original_subject = original_msg.get('subject', '') if original_msg else ''

            # Use 'comment' field - Graph API automatically includes the thread history
            reply_data = {
                "comment": final_body
            }
            endpoint = f"/me/messages/{message_id}/reply"
            result = self._make_graph_call(endpoint, method="POST", data=reply_data)
            if result is not None:
                self.logger.info(f"Sent reply to message {message_id[:20]}...")
                # Try to get the sent message ID from Sent Items
                # Reply subject: use original if already starts with RE:, else prepend RE:
                if original_subject.upper().startswith('RE:'):
                    reply_subject = original_subject
                else:
                    reply_subject = f"RE: {original_subject}" if original_subject else ""
                sent_msg_id = self._get_recent_sent_message_id(reply_subject, seconds_ago=30) if reply_subject else None
                return {"success": True, "message_id": sent_msg_id}
            return {"success": False}
        else:
            # Create reply draft - this preserves thread automatically
            endpoint = f"/me/messages/{message_id}/createReply"
            draft = self._make_graph_call(endpoint, method="POST")
            if draft and draft.get('id'):
                draft_id = draft['id']
                # Get original body from draft (includes thread) and prepend our reply
                original_body = draft.get('body', {}).get('content', '')

                # Build new body: our reply + signature + original thread
                if signature:
                    try:
                        from signatures import get_signature_html_body
                        sig_html = get_signature_html_body(signature)
                        if sig_html:
                            html_reply = reply_body.replace('\n', '<br>')
                            new_body = f"<div>{html_reply}</div><br><br>{sig_html}<br><br>{original_body}"
                            html = True
                        else:
                            new_body = f"{reply_body}<br><br>{original_body}"
                    except:
                        new_body = f"{reply_body}<br><br>{original_body}"
                else:
                    new_body = f"{reply_body}<br><br>{original_body}"

                update_data = {
                    "body": {
                        "contentType": "HTML",
                        "content": new_body
                    }
                }
                self._make_graph_call(f"/me/messages/{draft_id}", method="PATCH", data=update_data)

                # Add attachment if provided
                if attachment_path:
                    filename = os.path.basename(attachment_path)
                    file_size = os.path.getsize(attachment_path)
                    mime_type, _ = mimetypes.guess_type(attachment_path)
                    if not mime_type:
                        mime_type = 'application/octet-stream'

                    try:
                        if file_size <= 3 * 1024 * 1024:
                            # Small file - direct attachment
                            with open(attachment_path, 'rb') as f:
                                file_content = f.read()
                            file_base64 = base64.b64encode(file_content).decode('utf-8')

                            attach_data = {
                                "@odata.type": "#microsoft.graph.fileAttachment",
                                "name": filename,
                                "contentType": mime_type,
                                "contentBytes": file_base64
                            }
                            result = self._make_graph_call(f"/me/messages/{draft_id}/attachments", method="POST", data=attach_data)
                            if not result:
                                self._make_graph_call(f"/me/messages/{draft_id}", method="DELETE")
                                return {"success": False, "error": "Failed to attach file to reply"}
                        else:
                            # Large file - upload session
                            upload_success = self._upload_large_attachment(draft_id, attachment_path, filename, mime_type, file_size)
                            if not upload_success:
                                self._make_graph_call(f"/me/messages/{draft_id}", method="DELETE")
                                return {"success": False, "error": "Failed to upload large attachment to reply"}
                        self.logger.info(f"Attached '{filename}' ({file_size / 1024:.1f}KB) to reply draft")
                    except Exception as e:
                        self._make_graph_call(f"/me/messages/{draft_id}", method="DELETE")
                        return {"success": False, "error": f"Failed to attach file: {e}"}

                    # Send the draft with attachment
                    original_msg = self._make_graph_call(f"/me/messages/{message_id}?$select=subject")
                    original_subject = original_msg.get('subject', '') if original_msg else ''

                    result = self._make_graph_call(f"/me/messages/{draft_id}/send", method="POST")
                    if result is not None:
                        self.logger.info(f"Sent reply with attachment to message {message_id[:20]}...")
                        # Reply subject: use original if already starts with RE:, else prepend RE:
                        if original_subject.upper().startswith('RE:'):
                            reply_subject = original_subject
                        else:
                            reply_subject = f"RE: {original_subject}" if original_subject else ""
                        sent_msg_id = self._get_recent_sent_message_id(reply_subject, seconds_ago=60) if reply_subject else None
                        return {"success": True, "message_id": sent_msg_id, "attachment": filename}
                    return {"success": False, "error": "Failed to send reply with attachment"}

                self.logger.info(f"Created reply draft for message {message_id[:20]}...")
                return {"success": True, "draft_id": draft_id}
            return {"success": False}
    
    def send_draft(self, draft_id: str) -> bool:
        """Send a previously created draft"""
        result = self._make_graph_call(f"/me/messages/{draft_id}/send", method="POST")
        if result is not None:
            self.logger.info(f"Sent draft {draft_id[:20]}...")
            return True
        return False
    
    def get_email_history_with_contact(self, email_address: str, max_results: int = 10) -> list:
        """
        Get recent email history with a specific contact.
        Returns list of {date, subject, snippet, direction} dicts.
        """
        # Search for emails from or to this address
        filter_query = f"from/emailAddress/address eq '{email_address}' or toRecipients/any(r:r/emailAddress/address eq '{email_address}')"
        
        params = f"$filter={filter_query}&$top={max_results}&$orderby=receivedDateTime desc&$select=subject,receivedDateTime,from,bodyPreview"
        
        result = self._make_graph_call(f"/me/messages?{params}")
        
        history = []
        if result and result.get('value'):
            for msg in result['value']:
                from_addr = msg.get('from', {}).get('emailAddress', {}).get('address', '')
                direction = 'received' if from_addr.lower() == email_address.lower() else 'sent'
                
                history.append({
                    'date': msg.get('receivedDateTime', '')[:10],
                    'subject': msg.get('subject', ''),
                    'snippet': msg.get('bodyPreview', '')[:100],
                    'direction': direction
                })
        
        return history
    
    def get_email_by_id(self, message_id: str) -> Optional[EmailMessage]:
        """Get a specific email by its ID."""
        result = self._make_graph_call(f"/me/messages/{message_id}?$expand=attachments")
        
        if not result:
            return None
        
        return self._parse_email(result)
    
    def get_unread_emails(self, folder: str = "Inbox", max_results: int = 20) -> List[EmailMessage]:
        """Get unread emails from a folder."""
        # Get folder ID
        folder_id = self._get_folder_id(folder)
        if not folder_id:
            folder_id = "inbox"
        
        endpoint = f"/me/mailFolders/{folder_id}/messages?$filter=isRead eq false&$top={max_results}&$orderby=receivedDateTime desc&$expand=attachments"
        
        result = self._make_graph_call(endpoint)
        
        emails = []
        if result and result.get('value'):
            for msg in result['value']:
                emails.append(self._parse_email(msg))
        
        return emails
    
    def search_emails(self, query: str = None, max_results: int = 20, folder: str = None) -> List[EmailMessage]:
        """Search emails using Microsoft Graph search."""
        # URL-encode the query to handle special characters like quotes, colons, apostrophes
        encoded_query = quote(query, safe='')
        if folder:
            folder_id = self._get_folder_id(folder)
            endpoint = f"/me/mailFolders/{folder_id}/messages?$search=\"{encoded_query}\"&$top={max_results}&$orderby=receivedDateTime desc&$expand=attachments"
        else:
            endpoint = f"/me/messages?$search=\"{encoded_query}\"&$top={max_results}&$orderby=receivedDateTime desc&$expand=attachments"
        
        result = self._make_graph_call(endpoint)
        
        emails = []
        if result and result.get('value'):
            for msg in result['value']:
                emails.append(self._parse_email(msg))
        
        return emails
    
    def mark_as_unread(self, message_id: str) -> bool:
        """Mark an email as unread."""
        data = {"isRead": False}
        result = self._make_graph_call(f"/me/messages/{message_id}", method="PATCH", data=data)
        return result is not None
    
    def flag_email(self, message_id: str, flag_type: str = "flagged") -> bool:
        """Flag an email for follow-up."""
        data = {"flag": {"flagStatus": flag_type}}
        result = self._make_graph_call(f"/me/messages/{message_id}", method="PATCH", data=data)
        return result is not None
    
    def get_attachments(self, message_id: str) -> List[Dict]:
        """Get list of attachments for an email."""
        result = self._make_graph_call(f"/me/messages/{message_id}/attachments")
        
        attachments = []
        if result and result.get('value'):
            for att in result['value']:
                attachments.append({
                    "id": att.get('id'),
                    "name": att.get('name'),
                    "size": att.get('size'),
                    "content_type": att.get('contentType')
                })
        
        return attachments
    
    def save_attachment_by_id(self, message_id: str, attachment_id: str, save_path: str) -> bool:
        """Save a specific attachment by ID to a path."""
        import base64
        
        result = self._make_graph_call(f"/me/messages/{message_id}/attachments/{attachment_id}")
        
        if not result:
            return False
        
        try:
            content = base64.b64decode(result.get('contentBytes', ''))
            
            # Create directory if needed
            dir_path = os.path.dirname(save_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            with open(save_path, 'wb') as f:
                f.write(content)
            
            self.logger.info(f"Saved attachment to {save_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving attachment: {e}")
            return False
    
    def get_recent_sent_mail(self, hours: int = 24, max_results: int = 50) -> List[EmailMessage]:
        """
        Get recently sent emails from Sent Items folder.

        Used to capture Nick's manual replies and link them to jobs.

        Args:
            hours: How many hours back to look (default 24)
            max_results: Maximum emails to return

        Returns:
            List of EmailMessage objects from Sent Items
        """
        # Calculate cutoff time
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Query Sent Items folder specifically
        filter_query = f"$filter=sentDateTime ge {cutoff_str}"
        endpoint = f"/me/mailFolders/sentitems/messages?{filter_query}&$top={max_results}&$orderby=sentDateTime desc"

        result = self._make_graph_call(endpoint, prefer_text_body=True)
        if not result or 'value' not in result:
            return []

        emails = []
        for msg in result['value']:
            try:
                email = self._parse_email_message(msg)
                emails.append(email)
            except Exception as e:
                self.logger.error(f"Error parsing sent email: {e}")
                continue

        self.logger.info(f"Fetched {len(emails)} sent emails from last {hours} hours")
        return emails

    def list_folders(self) -> List[Dict]:
        """List all mail folders."""
        result = self._make_graph_call("/me/mailFolders?$top=50")
        
        folders = []
        if result and result.get('value'):
            for f in result['value']:
                folders.append({
                    "id": f.get('id'),
                    "name": f.get('displayName'),
                    "unread_count": f.get('unreadItemCount', 0),
                    "total_count": f.get('totalItemCount', 0)
                })
        
        return folders
    
    def create_folder(self, folder_name: str, parent_folder: str = None) -> Optional[str]:
        """Create a new mail folder. Returns folder ID."""
        data = {"displayName": folder_name}
        
        if parent_folder:
            parent_id = self._get_folder_id(parent_folder)
            endpoint = f"/me/mailFolders/{parent_id}/childFolders"
        else:
            endpoint = "/me/mailFolders"
        
        result = self._make_graph_call(endpoint, method="POST", data=data)
        
        if result and result.get('id'):
            self.logger.info(f"Created folder: {folder_name}")
            return result['id']
        return None
    
    def _get_folder_id(self, folder_name: str) -> Optional[str]:
        """Get folder ID by name."""
        # Common folder mappings
        well_known = {
            "inbox": "inbox",
            "drafts": "drafts",
            "sent": "sentitems",
            "deleted": "deleteditems",
            "archive": "archive"
        }
        
        lower_name = folder_name.lower()
        if lower_name in well_known:
            return well_known[lower_name]
        
        # Search for folder by name
        folders = self.list_folders()
        for f in folders:
            if f['name'].lower() == lower_name:
                return f['id']
        
        return None
    
    def get_email_history_with_contact(self, email_address: str, max_results: int = 10) -> list:
        """
        Get recent email history (both sent and received) with a specific contact.
        Returns list of simplified email info.
        
        NOTE: Graph API doesn't allow $search with $orderby, so we sort manually.
        """
        results = []
        
        # Search for emails FROM this contact
        from_query = f"from:{email_address}"
        from_result = self._make_graph_call(
            f"/me/messages?$search=\"{from_query}\"&$top={max_results}&$select=subject,receivedDateTime,from,bodyPreview"
        )
        
        if from_result and from_result.get('value'):
            for msg in from_result['value']:
                results.append({
                    'direction': 'received',
                    'subject': msg.get('subject'),
                    'date': msg.get('receivedDateTime'),
                    'preview': msg.get('bodyPreview', '')[:200]
                })
        
        # Search for emails TO this contact (sent mail)
        to_query = f"to:{email_address}"
        to_result = self._make_graph_call(
            f"/me/messages?$search=\"{to_query}\"&$top={max_results}&$select=subject,receivedDateTime,toRecipients,bodyPreview"
        )
        
        if to_result and to_result.get('value'):
            for msg in to_result['value']:
                results.append({
                    'direction': 'sent',
                    'subject': msg.get('subject'),
                    'date': msg.get('receivedDateTime'),
                    'preview': msg.get('bodyPreview', '')[:200]
                })
        
        # Sort by date, most recent first (manual sort since we can't use $orderby with $search)
        results.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        return results[:max_results]
    
    def _parse_email(self, msg: Dict) -> EmailMessage:
        """Parse a Graph API message into EmailMessage."""
        from_data = msg.get('from', {}).get('emailAddress', {})
        
        # Get body - prefer text, convert HTML if needed
        body_data = msg.get('body', {})
        html_body = body_data.get('content', '') if body_data.get('contentType') == 'html' else None
        
        if body_data.get('contentType') == 'html':
            body = html_to_text(body_data.get('content', ''))
        else:
            body = body_data.get('content', '')
        
        # Parse attachments
        attachments = []
        for att in msg.get('attachments', []):
            attachments.append({
                'id': att.get('id'),
                'name': att.get('name'),
                'size': att.get('size'),
                'contentType': att.get('contentType'),
                'data': att.get('contentBytes')
            })
        
        # Parse date
        received_str = msg.get('receivedDateTime', '')
        try:
            received_date = datetime.fromisoformat(received_str.replace('Z', '+00:00'))
        except:
            received_date = datetime.now()
        
        return EmailMessage(
            message_id=msg.get('id', ''),
            subject=msg.get('subject', ''),
            sender=from_data.get('name', ''),
            sender_email=from_data.get('address', ''),
            body=body,
            html_body=html_body,
            attachments=attachments,
            received_date=received_date,
            is_read=msg.get('isRead', False),
            conversation_id=msg.get('conversationId')
        )
