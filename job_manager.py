"""
Job Manager - Utility functions for job operations
===================================================

NOTE: Job creation and most job operations are now handled by tool_executor.py.
This module provides utility functions used by the orchestrator.

The job index is keyed by job_number (e.g., "25-180"), not conversation_id.
All job creation should go through tool_executor._job_create().
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, List

from config_loader import get_config


class JobManager:
    """
    Utility class for job-related operations.

    Primary job operations (create, search, status, link) are in tool_executor.py.
    This class provides:
    - Metro area checking
    - Flag for attention (save emails for manual review)
    - Job index read access (for orchestrator self-test)
    """

    # Paths loaded from config (set in __init__)
    JOB_INDEX_FILE = None
    JOBS_FOLDER = None
    DATA_SYNC_FOLDER = None
    FLAGGED_FOLDER = None

    # Metro areas for standard pricing (St. John's metro)
    METRO_AREAS = [
        "st. john's", "st johns", "saint john's",
        "mount pearl", "mt. pearl",
        "paradise",
        "conception bay south", "cbs",
        "portugal cove-st. philip's", "portugal cove", "pcsp",
        "logy bay-middle cove-outer cove", "logy bay",
        "holyrood",
        "petty harbour-maddox cove", "petty harbour", "maddox cove",
    ]

    def __init__(self, qbo=None):
        """
        Initialize JobManager.

        Args:
            qbo: QBO integration instance (optional, for legacy compatibility)
        """
        self.qbo = qbo
        self.logger = logging.getLogger(__name__)

        # Load paths from config
        cfg = get_config()
        self.JOB_INDEX_FILE = cfg.job_index_file
        self.JOBS_FOLDER = cfg.jobs_folder
        self.DATA_SYNC_FOLDER = cfg.data_sync_folder
        self.FLAGGED_FOLDER = cfg.flagged_folder

        self.job_index = self._load_job_index()

    def _load_job_index(self) -> dict:
        """Load job index from file (read-only for this class)."""
        if os.path.exists(self.JOB_INDEX_FILE):
            try:
                with open(self.JOB_INDEX_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Could not load job index: {e}")
                return {}
        return {}

    def reload_index(self):
        """Reload the job index from disk."""
        self.job_index = self._load_job_index()

    def is_metro_area(self, community: str) -> bool:
        """
        Check if a community is in the metro area (standard pricing).

        Metro areas receive standard RPR pricing (look up from QBO service items).
        Non-metro areas require custom quotes.

        Args:
            community: Community name to check

        Returns:
            True if metro area, False otherwise
        """
        if not community:
            return False
        community_lower = community.lower().strip()
        return any(metro in community_lower or community_lower in metro
                   for metro in self.METRO_AREAS)

    def get_job(self, job_number: str) -> Optional[Dict]:
        """
        Get job by job number (read-only).

        Args:
            job_number: Job number (e.g., "25-180")

        Returns:
            Job dict or None if not found
        """
        return self.job_index.get(job_number)

    def get_job_count(self) -> int:
        """Get total number of jobs in the index."""
        return len(self.job_index)

    def get_recent_jobs(self, count: int = 10) -> List[Dict]:
        """
        Get most recently created jobs.

        Args:
            count: Number of jobs to return

        Returns:
            List of job dicts, sorted by creation date (newest first)
        """
        jobs = list(self.job_index.values())
        jobs.sort(key=lambda x: x.get('created', ''), reverse=True)
        return jobs[:count]

    def flag_for_attention(self, email_context: dict, reason: str):
        """
        Save email to Needs Attention folder for manual review.

        Use this when an email needs human attention but isn't a job request
        or when Claude is uncertain how to proceed.

        Args:
            email_context: Dict with sender, sender_email, subject, body, received_date
            reason: Why this email needs attention
        """
        self.logger.info(f"Flagged for attention: {reason}")

        os.makedirs(self.FLAGGED_FOLDER, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        safe_sender = "".join(
            c for c in email_context.get('sender_email', 'unknown')[:40]
            if c.isalnum() or c in '@._-'
        )
        flag_file = os.path.join(self.FLAGGED_FOLDER, f"{timestamp}_{safe_sender}.txt")

        with open(flag_file, 'w', encoding='utf-8') as f:
            f.write(f"REASON: {reason}\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"From: {email_context.get('sender', '')} <{email_context.get('sender_email', '')}>\n")
            f.write(f"Subject: {email_context.get('subject', '')}\n")
            f.write(f"Date: {email_context.get('received_date', '')}\n\n")
            f.write(email_context.get('body', '')[:5000])

        return flag_file

    # =========================================================================
    # DEPRECATED METHODS - Kept for backwards compatibility but should not be used
    # =========================================================================

    def create_full_job(self, *args, **kwargs):
        """
        DEPRECATED: Use tool_executor._job_create() instead.

        This method used the old structure (keyed by conversation_id).
        All job creation should now go through the tool executor.
        """
        raise NotImplementedError(
            "JobManager.create_full_job() is deprecated. "
            "Job creation is handled by tool_executor._job_create() which is called "
            "when Claude uses the job_create tool. This ensures proper index structure "
            "(keyed by job_number with section timestamps)."
        )

    def find_by_conversation_id(self, conversation_id: str) -> Optional[Dict]:
        """
        DEPRECATED: Jobs are now keyed by job_number, not conversation_id.

        For backwards compatibility, this searches origin_conversation_id field.
        """
        # Direct lookup (legacy keys)
        if conversation_id in self.job_index:
            return self.job_index[conversation_id]

        # Search as field (new structure)
        for job_num, job in self.job_index.items():
            if job.get('origin_conversation_id') == conversation_id:
                return job

        return None

    def find_by_job_number(self, job_number: str) -> Optional[Dict]:
        """Find job by job number."""
        return self.job_index.get(job_number)

    def find_by_address(self, address: str) -> Optional[Dict]:
        """Find job by property address (partial match)."""
        address_lower = address.lower().strip()
        for job_num, job in self.job_index.items():
            job_addr = job.get('property_address', '').lower()
            if address_lower in job_addr or job_addr in address_lower:
                return job
        return None

    def find_by_client_email(self, email: str) -> Optional[Dict]:
        """Find job by client email."""
        email_lower = email.lower()
        for job_num, job in self.job_index.items():
            if job.get('client_email', '').lower() == email_lower:
                return job
        return None
