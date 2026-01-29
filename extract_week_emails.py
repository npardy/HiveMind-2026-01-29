"""
Extract all emails since Monday for analysis of Claude's interactions.
Compiles into a single document organized by conversation thread.
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from email_service import EmailService
from config_loader import get_config

def main():
    cfg = get_config()
    email = EmailService(
        client_id=cfg.email_client_id,
        client_secret=cfg.email_client_secret,
        redirect_uri=cfg.email_redirect_uri,
        token_cache_file=cfg.token_cache_graph
    )

    # Monday Jan 27, 2026 at midnight UTC
    monday = datetime(2026, 1, 27, 0, 0, 0, tzinfo=timezone.utc)

    print(f"Fetching emails since {monday}...")

    # Get all emails since Monday from inbox
    inbox_emails = email.get_emails_since(monday)
    print(f"  Inbox/received emails: {len(inbox_emails)}")

    # Get sent emails - use Graph API directly for sent items
    sent_endpoint = "/me/mailFolders/sentitems/messages?$top=200&$orderby=receivedDateTime desc"
    sent_result = email._make_graph_call(sent_endpoint)
    sent_emails = []
    if sent_result and 'value' in sent_result:
        for msg in sent_result['value']:
            received = msg.get('receivedDateTime', '')
            if received:
                msg_date = datetime.fromisoformat(received.replace('Z', '+00:00'))
                if msg_date >= monday:
                    sent_emails.append(msg)
    print(f"  Sent emails: {len(sent_emails)}")

    # Group by conversation ID
    conversations = defaultdict(list)

    # Add inbox emails
    for e in inbox_emails:
        conv_id = e.conversation_id or 'no-conversation'
        conversations[conv_id].append({
            'type': 'received',
            'date': e.received_date,
            'from': f"{e.sender} <{e.sender_email}>",
            'to': getattr(e, 'to_recipients', 'N/A'),
            'subject': e.subject,
            'body': e.body,
            'message_id': e.message_id
        })

    # Add sent emails
    for msg in sent_emails:
        conv_id = msg.get('conversationId', 'no-conversation')
        to_list = msg.get('toRecipients', [])
        to_str = ', '.join([r.get('emailAddress', {}).get('address', '') for r in to_list])

        conversations[conv_id].append({
            'type': 'sent',
            'date': datetime.fromisoformat(msg.get('receivedDateTime', '').replace('Z', '+00:00')),
            'from': msg.get('from', {}).get('emailAddress', {}).get('address', 'pardysurveys@outlook.com'),
            'to': to_str,
            'subject': msg.get('subject', ''),
            'body': msg.get('body', {}).get('content', ''),
            'message_id': msg.get('id', '')
        })

    # Sort each conversation by date
    for conv_id in conversations:
        conversations[conv_id].sort(key=lambda x: x['date'])

    # Sort conversations by earliest message date
    sorted_convs = sorted(
        conversations.items(),
        key=lambda x: min(m['date'] for m in x[1])
    )

    # Build output document
    data_folder = os.path.dirname(cfg.job_index_file)
    output_path = os.path.join(data_folder, 'claude_interactions_week.md')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Claude Email Interactions - Week of Jan 27, 2026\n\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Total conversations: {len(conversations)}\n")
        f.write(f"Total emails: {len(inbox_emails) + len(sent_emails)}\n\n")
        f.write("---\n\n")

        for conv_id, messages in sorted_convs:
            # Get first subject for conversation title
            first_subject = messages[0]['subject'] if messages else 'No Subject'

            f.write(f"## Conversation: {first_subject}\n\n")
            f.write(f"*Thread ID: {conv_id[:50]}...*\n\n")

            for msg in messages:
                direction = "📤 SENT" if msg['type'] == 'sent' else "📥 RECEIVED"
                date_str = msg['date'].strftime('%Y-%m-%d %H:%M') if msg['date'] else 'Unknown'

                f.write(f"### {direction} - {date_str}\n\n")
                f.write(f"**From:** {msg['from']}\n\n")
                f.write(f"**To:** {msg['to']}\n\n")
                f.write(f"**Subject:** {msg['subject']}\n\n")
                f.write("**Body:**\n\n")

                # Clean up body - remove excessive HTML if present
                body = msg['body'] or ''
                if '<html' in body.lower():
                    # Basic HTML stripping for readability
                    import re
                    body = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL | re.IGNORECASE)
                    body = re.sub(r'<script[^>]*>.*?</script>', '', body, flags=re.DOTALL | re.IGNORECASE)
                    body = re.sub(r'<[^>]+>', ' ', body)
                    body = re.sub(r'\s+', ' ', body)
                    body = body.strip()

                # Limit body length for readability
                if len(body) > 5000:
                    body = body[:5000] + "\n\n[... TRUNCATED ...]"

                f.write(f"```\n{body}\n```\n\n")
                f.write("---\n\n")

    print(f"\nOutput saved to: {output_path}")
    print(f"Total conversations: {len(conversations)}")
    print(f"Total emails: {len(inbox_emails) + len(sent_emails)}")

if __name__ == "__main__":
    main()
