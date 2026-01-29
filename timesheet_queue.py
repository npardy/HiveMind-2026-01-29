"""
Timesheet Queue System
======================
Queues field time entries for review before posting to QBO.

This provides a semi-automatic approach:
1. Field crew uploads data with time_spent
2. Entry goes into pending queue
3. Nick reviews/approves (via email or CLI)
4. Approved entries post to QBO automatically

Benefits:
- No double-entry risk
- Time validation before billing
- Audit trail
- Still saves manual data entry
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from config_loader import get_config


class TimesheetQueue:
    """
    Manages pending timesheet entries from field data uploads.
    """

    def __init__(self, queue_file: str = None):
        """
        Initialize the timesheet queue.

        Args:
            queue_file: Path to store pending entries (JSON)
        """
        cfg = get_config()
        self.queue_file = queue_file or os.path.join(
            os.path.dirname(cfg.job_index_file),
            "pending_timesheets.json"
        )
        self.logger = logging.getLogger(__name__)
        self.pending = self._load_queue()

        # Operator to QBO employee mapping
        # TODO: Move to config
        self.operator_map = {
            "allan": "Allan Regular",
            "nick": "Nicholas Pardy",
            "joe": "Joseph English",
            "joey": "Joseph English",
            # Add more as needed
        }

    def _load_queue(self) -> List[Dict[str, Any]]:
        """Load pending entries from file."""
        if os.path.exists(self.queue_file):
            try:
                with open(self.queue_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading timesheet queue: {e}")
        return []

    def _save_queue(self):
        """Save pending entries to file."""
        try:
            os.makedirs(os.path.dirname(self.queue_file), exist_ok=True)
            with open(self.queue_file, 'w') as f:
                json.dump(self.pending, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Error saving timesheet queue: {e}")

    def add_entry(
        self,
        job_number: str,
        operator: str,
        hours: float,
        work_type: str = "Field Work",
        notes: str = "",
        source_folder: str = ""
    ) -> str:
        """
        Add a new entry to the pending queue.

        Args:
            job_number: Job number (e.g., "26-004")
            operator: Field operator name
            hours: Time spent in hours
            work_type: Type of work (Field Work, Travel, etc.)
            notes: Optional notes
            source_folder: Data Sync folder that triggered this

        Returns:
            Entry ID for tracking
        """
        entry_id = f"TS-{datetime.now().strftime('%Y%m%d%H%M%S')}-{job_number}"

        entry = {
            "id": entry_id,
            "job_number": job_number,
            "operator": operator,
            "qbo_employee": self._map_operator(operator),
            "hours": hours,
            "work_type": work_type,
            "notes": notes,
            "source_folder": source_folder,
            "created_at": datetime.now().isoformat(),
            "status": "pending",
            "qbo_entry_id": None  # Filled after posting to QBO
        }

        self.pending.append(entry)
        self._save_queue()

        self.logger.info(f"Queued timesheet entry: {entry_id}")
        return entry_id

    def _map_operator(self, operator: str) -> Optional[str]:
        """Map field operator name to QBO employee name."""
        if not operator:
            return None
        return self.operator_map.get(operator.lower().strip())

    def get_pending(self) -> List[Dict[str, Any]]:
        """Get all pending entries."""
        return [e for e in self.pending if e.get('status') == 'pending']

    def get_by_job(self, job_number: str) -> List[Dict[str, Any]]:
        """Get pending entries for a specific job."""
        return [
            e for e in self.pending
            if e.get('job_number') == job_number and e.get('status') == 'pending'
        ]

    def approve_entry(self, entry_id: str) -> bool:
        """
        Mark an entry as approved (ready for QBO posting).

        Args:
            entry_id: The entry ID to approve

        Returns:
            True if found and approved
        """
        for entry in self.pending:
            if entry.get('id') == entry_id:
                entry['status'] = 'approved'
                entry['approved_at'] = datetime.now().isoformat()
                self._save_queue()
                return True
        return False

    def reject_entry(self, entry_id: str, reason: str = "") -> bool:
        """
        Reject an entry (won't be posted to QBO).

        Args:
            entry_id: The entry ID to reject
            reason: Optional reason for rejection

        Returns:
            True if found and rejected
        """
        for entry in self.pending:
            if entry.get('id') == entry_id:
                entry['status'] = 'rejected'
                entry['rejected_at'] = datetime.now().isoformat()
                entry['rejection_reason'] = reason
                self._save_queue()
                return True
        return False

    def mark_posted(self, entry_id: str, qbo_entry_id: str) -> bool:
        """
        Mark an entry as posted to QBO.

        Args:
            entry_id: The entry ID
            qbo_entry_id: The QBO TimeActivity ID

        Returns:
            True if found and updated
        """
        for entry in self.pending:
            if entry.get('id') == entry_id:
                entry['status'] = 'posted'
                entry['posted_at'] = datetime.now().isoformat()
                entry['qbo_entry_id'] = qbo_entry_id
                self._save_queue()
                return True
        return False

    def get_approved_for_posting(self) -> List[Dict[str, Any]]:
        """Get entries that are approved and ready to post to QBO."""
        return [e for e in self.pending if e.get('status') == 'approved']

    def format_for_review(self) -> str:
        """
        Format pending entries for human review.

        Returns a formatted string suitable for email or CLI display.
        """
        pending = self.get_pending()
        if not pending:
            return "No pending timesheet entries."

        lines = ["Pending Timesheet Entries:", "=" * 40, ""]

        for entry in pending:
            lines.append(f"ID: {entry['id']}")
            lines.append(f"  Job: {entry['job_number']}")
            lines.append(f"  Operator: {entry['operator']} -> {entry.get('qbo_employee', '(unmapped)')}")
            lines.append(f"  Hours: {entry['hours']}")
            lines.append(f"  Type: {entry['work_type']}")
            if entry.get('notes'):
                lines.append(f"  Notes: {entry['notes']}")
            lines.append(f"  Created: {entry['created_at']}")
            lines.append("")

        lines.append("To approve, reply with entry IDs (comma-separated)")
        lines.append("To reject, reply with 'reject ID: reason'")

        return "\n".join(lines)


def post_approved_to_qbo(queue: TimesheetQueue, qbo_integration) -> int:
    """
    Post all approved entries to QuickBooks.

    Args:
        queue: TimesheetQueue instance
        qbo_integration: QBOIntegration instance

    Returns:
        Number of entries posted
    """
    approved = queue.get_approved_for_posting()
    if not approved:
        return 0

    posted_count = 0
    logger = logging.getLogger(__name__)

    for entry in approved:
        try:
            # Map operator to QBO employee
            employee_name = entry.get('qbo_employee')
            if not employee_name:
                logger.warning(f"No QBO employee mapping for {entry['operator']}")
                continue

            # Look up employee in QBO
            employee = qbo_integration.find_employee(employee_name)
            if not employee:
                logger.warning(f"Employee not found in QBO: {employee_name}")
                continue

            # Create TimeActivity in QBO
            result = qbo_integration.create_time_activity(
                employee_id=employee['Id'],
                hours=entry['hours'],
                description=f"Field work - {entry['job_number']}",
                date=entry['created_at'][:10],  # YYYY-MM-DD
                notes=entry.get('notes', '')
            )

            if result and result.get('Id'):
                queue.mark_posted(entry['id'], result['Id'])
                posted_count += 1
                logger.info(f"Posted timesheet {entry['id']} to QBO as {result['Id']}")
            else:
                logger.error(f"Failed to post timesheet {entry['id']}")

        except Exception as e:
            logger.error(f"Error posting timesheet {entry['id']}: {e}")

    return posted_count


# Example usage / CLI interface
if __name__ == "__main__":
    import sys

    queue = TimesheetQueue()

    if len(sys.argv) < 2:
        print(queue.format_for_review())
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "list":
        print(queue.format_for_review())

    elif cmd == "approve" and len(sys.argv) >= 3:
        entry_id = sys.argv[2]
        if queue.approve_entry(entry_id):
            print(f"Approved: {entry_id}")
        else:
            print(f"Entry not found: {entry_id}")

    elif cmd == "reject" and len(sys.argv) >= 3:
        entry_id = sys.argv[2]
        reason = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else ""
        if queue.reject_entry(entry_id, reason):
            print(f"Rejected: {entry_id}")
        else:
            print(f"Entry not found: {entry_id}")

    else:
        print("Usage:")
        print("  python timesheet_queue.py              # List pending")
        print("  python timesheet_queue.py list         # List pending")
        print("  python timesheet_queue.py approve ID   # Approve entry")
        print("  python timesheet_queue.py reject ID [reason]  # Reject entry")
