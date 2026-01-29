"""
QBO Sync - Synchronize QuickBooks with job index (bidirectional)
=================================================================

This script handles bidirectional sync between QBO and the hive:

INBOUND (QBO → Hive):
- Invoices sent manually
- Payments received
- Invoice amounts changed
- New jobs created manually in QBO

OUTBOUND (Hive → QBO):
- Field time entries from Data Sync uploads
- Travel time from field work

Run periodically to keep everything in sync.

Usage:
    python qbo_sync.py [--verbose] [--recent N] [--sync-time]

Schedule via cron or task scheduler to run every few hours or daily.
"""

import os
import re
import json
import argparse
import logging
from datetime import datetime, timedelta

from config_loader import get_config

# Get config for paths
cfg = get_config()

# Setup logging - use config for log path
log_dir = os.path.dirname(cfg.log_file)
os.makedirs(log_dir, exist_ok=True)
log_path = os.path.join(log_dir, 'qbo_sync.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class QBOSync:
    """Sync QuickBooks invoice status with job index."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        # Load paths from config
        self.cfg = get_config()
        self.INDEX_PATH = self.cfg.job_index_file
        self.JOBS_ROOT = self.cfg.jobs_folder

        self.job_index = self._load_index()
        self.qbo = self._init_qbo()
        self.stats = {
            "invoices_checked": 0,
            "invoices_updated": 0,
            "payments_detected": 0,
            "sends_detected": 0,
            "jobs_discovered": 0,
            "time_entries_synced": 0,
            "time_entries_failed": 0,
            "time_totals_refreshed": 0,
            "errors": []
        }

    def _load_index(self) -> dict:
        """Load job index."""
        if os.path.exists(self.INDEX_PATH):
            with open(self.INDEX_PATH, 'r') as f:
                return json.load(f)
        return {}

    def _save_index(self):
        """Save job index."""
        # Backup first
        if os.path.exists(self.INDEX_PATH):
            backup = self.INDEX_PATH.replace('.json', f'_backup_qbo_{datetime.now().strftime("%Y%m%d_%H%M")}.json')
            with open(self.INDEX_PATH, 'r') as f:
                with open(backup, 'w') as b:
                    b.write(f.read())

        with open(self.INDEX_PATH, 'w') as f:
            json.dump(self.job_index, f, indent=2)

    def _init_qbo(self):
        """Initialize QBO connection."""
        try:
            from qbo_integration import QBOIntegration

            qbo = QBOIntegration(
                client_id=self.cfg.qbo_client_id,
                client_secret=self.cfg.qbo_client_secret,
                redirect_uri=self.cfg.qbo_redirect_uri,
                environment=self.cfg.qbo_environment,
                token_cache_file=self.cfg.token_cache_qbo
            )

            if not qbo.access_token:
                logger.error("QBO not authenticated. Run authentication first.")
                return None

            return qbo
        except Exception as e:
            logger.error(f"Failed to initialize QBO: {e}")
            return None

    def sync_recent_invoices(self, count: int = 100):
        """
        Sync recent invoices from QBO to detect manual changes.

        Checks invoices against job index and updates:
        - Payment status (balance = 0 means paid)
        - Sent status (if EmailStatus indicates sent)
        - Amount changes
        """
        if not self.qbo:
            logger.error("QBO not connected")
            return

        logger.info(f"Fetching {count} recent invoices from QBO...")

        try:
            invoices = self.qbo.get_recent_invoices(count)
            logger.info(f"Retrieved {len(invoices)} invoices")

            for inv in invoices:
                self._sync_invoice(inv)

        except Exception as e:
            logger.error(f"Error fetching invoices: {e}")
            self.stats["errors"].append(str(e))

    def _sync_invoice(self, inv: dict):
        """Sync a single invoice with the job index."""
        invoice_number = inv.get('DocNumber', '')

        # Only sync invoices that look like job numbers (XX-XXX)
        if not re.match(r'^\d{2}-\d{3}$', invoice_number):
            return

        self.stats["invoices_checked"] += 1

        job_number = invoice_number
        job = self.job_index.get(job_number)

        if not job:
            # Job not in index - try to discover it
            job = self._discover_job_from_invoice(inv, job_number)
            if not job:
                if self.verbose:
                    logger.info(f"  {job_number}: Not in index and no NAS folder found, skipping")
                return

        # Get current QBO section
        qbo_section = job.get('qbo', {})
        if not isinstance(qbo_section, dict):
            qbo_section = {}

        now = datetime.now().isoformat()
        changes = []

        # Check payment status
        balance = float(inv.get('Balance', 0))
        amount = float(inv.get('TotalAmt', 0))
        was_paid = qbo_section.get('paid', False)
        is_paid = balance == 0 and amount > 0

        if is_paid and not was_paid:
            qbo_section['paid'] = True
            qbo_section['paid_date'] = now
            qbo_section['status'] = 'Paid'
            changes.append("PAID")
            self.stats["payments_detected"] += 1

        # Check if invoice was sent (QBO tracks this)
        email_status = inv.get('EmailStatus', '')
        was_sent = qbo_section.get('status') in ['Sent', 'Paid']
        is_sent = email_status in ['EmailSent', 'NeedToSend']

        if is_sent and not was_sent and not is_paid:
            qbo_section['status'] = 'Sent'
            # Try to get send date from metadata
            metadata = inv.get('MetaData', {})
            qbo_section['sent_date'] = metadata.get('LastUpdatedTime', now)
            changes.append("SENT")
            self.stats["sends_detected"] += 1

        # Update amount/balance
        if qbo_section.get('amount') != amount:
            qbo_section['amount'] = amount
            changes.append(f"amount={amount}")

        qbo_section['balance'] = balance
        qbo_section['invoice_id'] = inv.get('Id')
        qbo_section['invoice_number'] = invoice_number
        qbo_section['due_date'] = inv.get('DueDate')
        qbo_section['customer_id'] = inv.get('CustomerRef', {}).get('value')

        if changes:
            qbo_section['_updated'] = now
            job['qbo'] = qbo_section
            job['last_updated'] = now
            self.stats["invoices_updated"] += 1
            logger.info(f"  {job_number}: {', '.join(changes)}")
        elif self.verbose:
            logger.info(f"  {job_number}: No changes")

    def _discover_job_from_invoice(self, inv: dict, job_number: str) -> dict:
        """
        Discover a new job from a QBO invoice that's not in the index.

        This handles the case where you manually create a job in QBO and
        a NAS folder - the hive should learn about it.
        """
        # First, check if there's a NAS folder for this job
        year_prefix = job_number.split('-')[0]
        year = f"20{year_prefix}"
        year_folder = os.path.join(self.JOBS_ROOT, year)

        job_folder = None
        if os.path.exists(year_folder):
            for folder_name in os.listdir(year_folder):
                if folder_name.startswith(job_number + " - "):
                    job_folder = os.path.join(year_folder, folder_name)
                    break

        if not job_folder:
            # No NAS folder yet - skip for now
            # The nightly refresh will pick it up when folder is created
            return None

        # Parse folder name for client and address
        # Format: "26-008 - Client Name - Address, Community"
        folder_name = os.path.basename(job_folder)
        parts = folder_name.split(' - ', 2)
        client_business = parts[1] if len(parts) > 1 else None
        address_part = parts[2] if len(parts) > 2 else None

        property_address = address_part
        community = None
        if address_part and ', ' in address_part:
            addr_parts = address_part.rsplit(', ', 1)
            property_address = address_part
            community = addr_parts[1] if len(addr_parts) > 1 else None

        now = datetime.now().isoformat()

        # Create new job entry
        job = {
            "job_number": job_number,
            "created": now,
            "discovered_from": "qbo_sync",  # Track how we learned about it

            # Identity from folder
            "job_folder": job_folder,
            "property_address": property_address,
            "client_business": client_business,
            "community": community,

            # Sections with _updated timestamps
            "qbo": {"_updated": None},  # Will be populated below
            "emails": {"linked": [], "_updated": now},
            "data_sync": {"jobs": [], "field_summary": {}, "_updated": now},
            "reference_files": {"_updated": now},
            "document_control": {"_updated": None},

            # Status flags (will be updated by nightly refresh)
            "has_layout": False,
            "has_field_data": False,
            "has_drawings": False,
            "has_reports": False,

            "last_updated": now
        }

        # Add to index
        self.job_index[job_number] = job
        self.stats["jobs_discovered"] += 1
        logger.info(f"  {job_number}: DISCOVERED from QBO + NAS folder")

        return job

    def sync_job(self, job_number: str):
        """Sync a specific job's invoice from QBO."""
        if not self.qbo:
            logger.error("QBO not connected")
            return

        inv = self.qbo.find_invoice_by_number(job_number)
        if inv:
            self._sync_invoice(inv)
        else:
            logger.warning(f"Invoice {job_number} not found in QBO")

    # =========================================================================
    # TIME ENTRY SYNC (Data Sync → QBO)
    # =========================================================================

    def sync_time_entries(self):
        """
        Sync unsynced field time entries from Data Sync to QBO.

        Scans job index for field_uploads with qbo_sync.time_synced = false
        and creates corresponding TimeActivity entries in QBO.
        """
        if not self.qbo:
            logger.error("QBO not connected")
            return

        logger.info("Syncing time entries from field uploads to QBO...")

        for job_number, job in self.job_index.items():
            # Skip metadata keys (not actual jobs)
            if job_number.startswith('_') or not isinstance(job, dict):
                continue

            data_sync = job.get('data_sync', {})
            if not isinstance(data_sync, dict):
                continue

            jobs_list = data_sync.get('jobs', [])
            if not jobs_list:
                continue

            for controller_job in jobs_list:
                field_uploads = controller_job.get('field_uploads', [])

                for upload in field_uploads:
                    field_status = upload.get('field_status', {})
                    if not field_status:
                        continue

                    qbo_sync_status = field_status.get('qbo_sync', {})
                    if qbo_sync_status.get('time_synced'):
                        continue  # Already synced

                    # Check if there's time to sync
                    time_spent = field_status.get('time_spent') or {}
                    field_hours = time_spent.get('field_hours') or 0
                    travel_hours = time_spent.get('travel_hours_oneway') or 0

                    if field_hours == 0 and travel_hours == 0:
                        continue  # No time to sync

                    # Get operator and date
                    operator = field_status.get('operator')
                    if not operator:
                        continue  # Can't sync without operator

                    # Parse date from upload folder name or timestamp
                    upload_timestamp = field_status.get('upload_timestamp', '')
                    work_date = None
                    if upload_timestamp:
                        try:
                            work_date = upload_timestamp[:10]  # YYYY-MM-DD
                        except:
                            pass

                    if not work_date:
                        # Try folder name (format: 260120-0938AM)
                        folder = upload.get('folder', '')
                        if folder and len(folder) >= 6:
                            try:
                                yy = folder[:2]
                                mm = folder[2:4]
                                dd = folder[4:6]
                                work_date = f"20{yy}-{mm}-{dd}"
                            except:
                                work_date = datetime.now().strftime('%Y-%m-%d')

                    notes = field_status.get('notes')

                    # Create time entries in QBO
                    self._sync_single_time_entry(
                        job_number=job_number,
                        operator=operator,
                        field_hours=field_hours,
                        travel_hours=travel_hours,
                        work_date=work_date,
                        notes=notes,
                        upload=upload,
                        field_status=field_status
                    )

    def _sync_single_time_entry(self, job_number: str, operator: str,
                                 field_hours: float, travel_hours: float,
                                 work_date: str, notes: str,
                                 upload: dict, field_status: dict):
        """Sync a single field upload's time to QBO."""
        folder = upload.get('folder', 'unknown')

        try:
            result = self.qbo.create_field_time_entry(
                employee_name=operator,
                field_hours=field_hours,
                travel_hours=travel_hours,
                job_number=job_number,
                date=work_date,
                notes=notes
            )

            if result['success']:
                # Update the field_status to mark as synced
                field_status['qbo_sync'] = {
                    'time_synced': True,
                    'field_entry_id': result.get('field_entry_id'),
                    'travel_entry_id': result.get('travel_entry_id'),
                    'synced_at': datetime.now().isoformat()
                }
                self.stats['time_entries_synced'] += 1
                logger.info(f"  {job_number}/{folder}: Synced {field_hours}h field + {travel_hours}h travel for {operator}")
            else:
                self.stats['time_entries_failed'] += 1
                errors = ', '.join(result.get('errors', []))
                logger.warning(f"  {job_number}/{folder}: Failed - {errors}")

        except Exception as e:
            self.stats['time_entries_failed'] += 1
            logger.error(f"  {job_number}/{folder}: Error - {e}")

    # =========================================================================
    # TIME TOTALS REFRESH (QBO → Hive)
    # =========================================================================

    def refresh_time_totals(self, year: int = None):
        """
        Refresh QBO time totals for active jobs.

        Pulls all time entries from QBO for each active job, categorizes them
        (field_auto, travel_auto, drafting, research, etc.), and updates the
        spine with totals and entry breakdown.

        This captures drafting time, manual entries, and any other time that
        wasn't auto-posted from Data Sync uploads.

        Args:
            year: Specific year to refresh (default: current year)
        """
        if year is None:
            year = datetime.now().year

        year_prefix = str(year)[2:]  # e.g., "26" for 2026

        logger.info(f"Refreshing QBO time totals for {year}...")

        # Common nickname mappings (same as qbo_integration.py)
        nickname_map = {
            'joe': ['joseph', 'joey', 'jo'],
            'joey': ['joseph', 'joe'],
            'joseph': ['joe', 'joey'],
            'nick': ['nicholas', 'nic', 'nicky'],
            'nicholas': ['nick', 'nic', 'nicky'],
            'al': ['allan', 'allen', 'alan'],
            'allan': ['al', 'allen', 'alan'],
            'allen': ['al', 'allan', 'alan'],
            'mike': ['michael', 'mick'],
            'michael': ['mike', 'mick'],
            'bob': ['robert', 'rob', 'bobby'],
            'robert': ['bob', 'rob', 'bobby'],
            'bill': ['william', 'will', 'billy'],
            'william': ['bill', 'will', 'billy'],
            'dave': ['david', 'davey'],
            'david': ['dave', 'davey'],
            'dan': ['daniel', 'danny'],
            'daniel': ['dan', 'danny'],
            'tom': ['thomas', 'tommy'],
            'thomas': ['tom', 'tommy'],
            'jim': ['james', 'jimmy'],
            'james': ['jim', 'jimmy'],
            'steve': ['steven', 'stephen'],
            'steven': ['steve', 'stephen'],
            'stephen': ['steve', 'steven'],
        }

        def names_match(name1: str, name2: str) -> str:
            """
            Compare two names accounting for nicknames.
            Uses same logic as qbo_integration.find_employee_by_name.
            Returns 'match', 'partial', or 'different'.
            """
            name1 = name1.lower().strip()
            name2 = name2.lower().strip()

            # Exact match
            if name1 == name2:
                return 'match'

            # One contains the other (e.g., "Joe" in "Joe Smith")
            if name1 in name2 or name2 in name1:
                return 'match'

            # Get all possible variations for both names
            name1_parts = name1.split()
            name2_parts = name2.split()

            # Expand each part with its nickname variations
            name1_variations = set(name1_parts)
            for part in name1_parts:
                if part in nickname_map:
                    name1_variations.update(nickname_map[part])

            name2_variations = set(name2_parts)
            for part in name2_parts:
                if part in nickname_map:
                    name2_variations.update(nickname_map[part])

            # Check if any variation matches
            if name1_variations & name2_variations:  # Set intersection
                return 'partial'

            return 'different'

        # Patterns to identify auto-posted entries
        auto_field_pattern = re.compile(r'^Field work - \d{2}-\d{3}')
        auto_travel_pattern = re.compile(r'^Travel - \d{2}-\d{3}')

        # Service Item IDs from QBO
        FIELD_TIME_ITEM_ID = '2'
        DRAFTING_ITEM_ID = '3'
        RESEARCH_ITEM_ID = '108'
        TRAVEL_ITEM_ID = '111'

        refreshed = 0

        for job_number, job_data in self.job_index.items():
            # Skip metadata keys (not actual jobs)
            if job_number.startswith('_') or not isinstance(job_data, dict):
                continue

            # Only refresh jobs from target year
            if not job_number.startswith(year_prefix + '-'):
                continue

            # Skip jobs without QBO invoice (not yet billable)
            qbo = job_data.get('qbo', {})
            if not qbo.get('invoice_id') and not qbo.get('customer_id'):
                continue

            try:
                entries = self.qbo.get_time_entries_for_job(job_number)

                if entries is None:
                    continue

                # Initialize totals
                totals = {
                    'field_auto': 0, 'travel_auto': 0,
                    'field_manual': 0, 'travel_manual': 0,
                    'drafting': 0, 'research': 0,
                    'other': 0, 'total': 0
                }
                categorized = []

                for entry in entries:
                    hours = float(entry.get('Hours', 0)) + float(entry.get('Minutes', 0)) / 60
                    desc = entry.get('Description', '') or ''
                    item_id = entry.get('ItemRef', {}).get('value')

                    # Determine category
                    if auto_field_pattern.match(desc):
                        category = 'field_auto'
                    elif auto_travel_pattern.match(desc):
                        category = 'travel_auto'
                    elif item_id == DRAFTING_ITEM_ID:
                        category = 'drafting'
                    elif item_id == RESEARCH_ITEM_ID:
                        category = 'research'
                    elif item_id == FIELD_TIME_ITEM_ID:
                        category = 'field_manual'
                    elif item_id == TRAVEL_ITEM_ID:
                        category = 'travel_manual'
                    else:
                        category = 'other'

                    totals[category] += hours
                    totals['total'] += hours

                    categorized.append({
                        'id': entry.get('Id'),
                        'type': category,
                        'hours': round(hours, 2),
                        'employee': entry.get('EmployeeRef', {}).get('name'),
                        'date': entry.get('TxnDate'),
                        'description': desc[:100] if desc else None
                    })

                # Round totals
                for key in totals:
                    totals[key] = round(totals[key], 2)

                # =============================================================
                # DUPLICATE DETECTION
                # Check if manual QBO entries match field form uploads
                # =============================================================
                potential_duplicates = []

                # Get manual entries (field_manual or travel_manual)
                manual_entries = [e for e in categorized if e['type'] in ('field_manual', 'travel_manual')]

                if manual_entries:
                    # Get field upload data from job index
                    job_data = self.job_index.get(job_number, {})
                    data_sync = job_data.get('data_sync', [])

                    # Collect all field uploads with time data
                    # Handle both formats: list (from _job_get_status) or dict with 'jobs' key (from nightly_refresh)
                    field_uploads = []
                    layouts = []
                    if isinstance(data_sync, list):
                        layouts = data_sync
                    elif isinstance(data_sync, dict) and 'jobs' in data_sync:
                        layouts = data_sync['jobs']

                    for layout in layouts:
                        for upload in layout.get('field_uploads', []):
                            fs = upload.get('field_status', {})
                            ts = fs.get('time_spent', {}) if fs else {}
                            if ts and (ts.get('field_hours') or ts.get('travel_hours_oneway')):
                                upload_date = None
                                upload_ts = fs.get('upload_timestamp')
                                if upload_ts:
                                    upload_date = upload_ts[:10]  # YYYY-MM-DD

                                field_uploads.append({
                                    'folder': upload.get('folder'),
                                    'operator': fs.get('operator'),
                                    'field_hours': ts.get('field_hours', 0),
                                    'travel_hours': ts.get('travel_hours_oneway', 0),
                                    'date': upload_date
                                })

                    # Check each manual entry against field uploads
                    HOURS_TOLERANCE = 0.25  # Within 15 minutes
                    DATE_TOLERANCE_DAYS = 2  # Within 2 days

                    for entry in manual_entries:
                        entry_hours = entry['hours']
                        entry_date = entry.get('date')
                        entry_employee = entry.get('employee', '').lower()
                        is_travel = entry['type'] == 'travel_manual'

                        for upload in field_uploads:
                            upload_hours = upload['travel_hours'] if is_travel else upload['field_hours']
                            upload_date = upload.get('date')
                            upload_operator = (upload.get('operator') or '').lower()

                            # Skip if hours don't match (within tolerance)
                            if abs(entry_hours - upload_hours) > HOURS_TOLERANCE:
                                continue

                            # Check date proximity
                            date_match = 'unknown'
                            if entry_date and upload_date:
                                try:
                                    e_date = datetime.strptime(entry_date, '%Y-%m-%d')
                                    u_date = datetime.strptime(upload_date, '%Y-%m-%d')
                                    days_diff = abs((e_date - u_date).days)
                                    date_match = 'exact' if days_diff == 0 else ('close' if days_diff <= DATE_TOLERANCE_DAYS else 'far')
                                except:
                                    pass

                            # Skip if dates are too far apart
                            if date_match == 'far':
                                continue

                            # Check employee match - handle nicknames (Joe/Joseph, etc.)
                            employee_match = 'unknown'
                            if entry_employee and upload_operator:
                                employee_match = names_match(entry_employee, upload_operator)

                            # Skip if employees are clearly different
                            if employee_match == 'different':
                                continue

                            # Determine confidence level
                            if date_match == 'exact' and employee_match == 'match':
                                confidence = 'high'
                            elif date_match in ('exact', 'close') and employee_match != 'different':
                                confidence = 'medium'
                            else:
                                confidence = 'low'

                            potential_duplicates.append({
                                'qbo_entry_id': entry['id'],
                                'qbo_type': entry['type'],
                                'qbo_hours': entry_hours,
                                'qbo_date': entry_date,
                                'qbo_employee': entry.get('employee'),
                                'matching_upload': upload['folder'],
                                'upload_hours': upload_hours,
                                'upload_date': upload_date,
                                'upload_operator': upload.get('operator'),
                                'confidence': confidence
                            })

                # Update job index - merge with existing qbo data
                if 'qbo' not in self.job_index[job_number]:
                    self.job_index[job_number]['qbo'] = {}

                self.job_index[job_number]['qbo']['time_totals'] = totals
                self.job_index[job_number]['qbo']['all_time_entries'] = categorized
                self.job_index[job_number]['qbo']['_time_refreshed_at'] = datetime.now().isoformat()

                if potential_duplicates:
                    self.job_index[job_number]['qbo']['potential_duplicates'] = potential_duplicates
                else:
                    self.job_index[job_number]['qbo']['potential_duplicates'] = None

                refreshed += 1

                if self.verbose and totals['total'] > 0:
                    dupe_msg = f", {len(potential_duplicates)} potential duplicates" if potential_duplicates else ""
                    logger.info(f"  {job_number}: {totals['total']}h total "
                               f"(field={totals['field_auto']}h, drafting={totals['drafting']}h){dupe_msg}")

            except Exception as e:
                logger.warning(f"  {job_number}: Error refreshing time - {e}")

        self.stats['time_totals_refreshed'] = refreshed
        logger.info(f"  Refreshed time totals for {refreshed} jobs")

    def run(self, recent_count: int = 100, sync_time: bool = True, refresh_time: bool = True):
        """
        Run the QBO sync.

        Args:
            recent_count: Number of recent invoices to check
            sync_time: Whether to sync time entries from Data Sync
            refresh_time: Whether to refresh time totals from QBO
        """
        start = datetime.now()
        logger.info("=" * 60)
        logger.info("QBO SYNC")
        logger.info(f"Started: {start}")
        logger.info("=" * 60)

        # Sync invoices (QBO → Hive)
        self.sync_recent_invoices(recent_count)

        # Sync time entries (Hive → QBO)
        if sync_time:
            logger.info("")
            self.sync_time_entries()

        # Refresh time totals (QBO → Hive)
        if refresh_time:
            logger.info("")
            self.refresh_time_totals()

        # Save if changes were made
        changes_made = (
            self.stats["invoices_updated"] > 0 or
            self.stats["jobs_discovered"] > 0 or
            self.stats["time_entries_synced"] > 0 or
            self.stats["time_totals_refreshed"] > 0
        )
        if changes_made:
            self._save_index()

        # Report
        elapsed = (datetime.now() - start).total_seconds()
        logger.info("")
        logger.info("=" * 60)
        logger.info("QBO SYNC COMPLETE")
        logger.info(f"  Invoices checked:    {self.stats['invoices_checked']}")
        logger.info(f"  Invoices updated:    {self.stats['invoices_updated']}")
        logger.info(f"  Jobs discovered:     {self.stats['jobs_discovered']}")
        logger.info(f"  Payments detected:   {self.stats['payments_detected']}")
        logger.info(f"  Sends detected:      {self.stats['sends_detected']}")
        logger.info(f"  Time entries synced: {self.stats['time_entries_synced']}")
        logger.info(f"  Time entries failed: {self.stats['time_entries_failed']}")
        logger.info(f"  Time totals refreshed: {self.stats['time_totals_refreshed']}")
        logger.info(f"  Errors:              {len(self.stats['errors'])}")
        logger.info(f"  Elapsed:             {elapsed:.1f}s")
        logger.info("=" * 60)

        return self.stats


def main():
    parser = argparse.ArgumentParser(description="Sync QBO with job index (bidirectional)")
    parser.add_argument('--recent', type=int, default=100,
                       help="Number of recent invoices to check (default: 100)")
    parser.add_argument('--job', type=str,
                       help="Sync a specific job number")
    parser.add_argument('--no-time', action='store_true',
                       help="Skip time entry sync (invoices only)")
    parser.add_argument('--time-only', action='store_true',
                       help="Only sync time entries to QBO (skip invoices and refresh)")
    parser.add_argument('--refresh-time-only', action='store_true',
                       help="Only refresh time totals from QBO (skip invoices and sync)")
    parser.add_argument('--no-refresh-time', action='store_true',
                       help="Skip refreshing time totals from QBO")
    parser.add_argument('--verbose', '-v', action='store_true',
                       help="Verbose output")
    args = parser.parse_args()

    # Log directory already created during logging setup

    syncer = QBOSync(verbose=args.verbose)

    if args.job:
        syncer.sync_job(args.job)
    elif args.time_only:
        syncer.sync_time_entries()
        if syncer.stats['time_entries_synced'] > 0:
            syncer._save_index()
        logger.info(f"Time entries synced: {syncer.stats['time_entries_synced']}")
    elif args.refresh_time_only:
        syncer.refresh_time_totals()
        if syncer.stats['time_totals_refreshed'] > 0:
            syncer._save_index()
        logger.info(f"Time totals refreshed: {syncer.stats['time_totals_refreshed']}")
    else:
        syncer.run(
            recent_count=args.recent,
            sync_time=not args.no_time,
            refresh_time=not args.no_refresh_time
        )

    return 0


if __name__ == "__main__":
    exit(main())
