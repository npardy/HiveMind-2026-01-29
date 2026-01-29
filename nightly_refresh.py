"""
Nightly Job Index Refresh
==========================
Runs as scheduled task to keep the hive intelligence fresh.

Scans all job folders and updates the index with:
- New reference files (deeds, plans added)
- Document control changes (new documents stamped/sent)
- Controller job updates from Data Sync
- NAS folder structure changes

Usage:
    python nightly_refresh.py [--year 2025] [--verbose]

Schedule via cron or task scheduler to run at 2 AM daily.
"""

import os
import re
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path

from config_loader import get_config

# Get config for paths
cfg = get_config()

# Setup logging - use config for log path
log_dir = os.path.dirname(cfg.log_file)
os.makedirs(log_dir, exist_ok=True)
log_path = os.path.join(log_dir, 'nightly_refresh.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class NightlyRefresh:
    """Refresh job index from all data sources."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        # Load paths from config
        self.cfg = get_config()
        self.JOBS_ROOT = self.cfg.jobs_folder
        self.DATA_SYNC_OFFICE = self.cfg.data_sync_folder
        self.INDEX_PATH = self.cfg.job_index_file

        self.job_index = self._load_index()
        self.stats = {
            "jobs_scanned": 0,
            "jobs_updated": 0,
            "jobs_added": 0,
            "errors": []
        }
    
    def _load_index(self) -> dict:
        """Load existing job index."""
        if os.path.exists(self.INDEX_PATH):
            with open(self.INDEX_PATH, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_index(self):
        """Save job index."""
        # Backup first
        if os.path.exists(self.INDEX_PATH):
            backup = self.INDEX_PATH.replace('.json', f'_backup_{datetime.now().strftime("%Y%m%d")}.json')
            with open(self.INDEX_PATH, 'r') as f:
                with open(backup, 'w') as b:
                    b.write(f.read())
        
        with open(self.INDEX_PATH, 'w') as f:
            json.dump(self.job_index, f, indent=2)
    
    def refresh_year(self, year: int):
        """Refresh all jobs for a given year."""
        year_folder = os.path.join(self.JOBS_ROOT, str(year))
        
        if not os.path.exists(year_folder):
            logger.warning(f"Year folder not found: {year_folder}")
            return
        
        logger.info(f"Scanning {year_folder}...")
        
        for folder_name in os.listdir(year_folder):
            folder_path = os.path.join(year_folder, folder_name)
            if not os.path.isdir(folder_path):
                continue
            
            # Extract job number from folder name (e.g., "25-180 - Client - Address")
            match = re.match(r'^(\d{2}-\d{3})', folder_name)
            if not match:
                continue
            
            job_number = match.group(1)
            self.stats["jobs_scanned"] += 1
            
            try:
                updated = self._refresh_job(job_number, folder_path, folder_name)
                if updated:
                    self.stats["jobs_updated"] += 1
                    if self.verbose:
                        logger.info(f"  Updated: {job_number}")
            except Exception as e:
                self.stats["errors"].append(f"{job_number}: {str(e)}")
                logger.error(f"Error refreshing {job_number}: {e}")
    
    def _refresh_job(self, job_number: str, folder_path: str, folder_name: str) -> bool:
        """Refresh a single job's index entry. Returns True if updated."""
        
        now = datetime.now().isoformat()
        
        # Get or create entry
        is_new = job_number not in self.job_index
        if is_new:
            self.job_index[job_number] = {
                "job_number": job_number,
                "created": now,
                "emails": {"linked": [], "_updated": now},
                "qbo": {"_updated": None}  # Only set when actually queried
            }
            self.stats["jobs_added"] += 1
        
        job = self.job_index[job_number]
        changes = []
        
        # === MIGRATE OLD STRUCTURE ===
        # Convert list-based emails to dict structure
        if isinstance(job.get("emails"), list):
            job["emails"] = {"linked": job["emails"], "_updated": now}
        
        # === IDENTITY ===
        job["job_folder"] = folder_path
        
        # Parse folder name: "25-180 - Van Driel Law - 9 Rankin Street, St. John's"
        parts = folder_name.split(' - ', 2)
        if len(parts) >= 3:
            job["client_business"] = parts[1].strip()
            address_part = parts[2].strip()
            # Extract community if present (after last comma)
            if ', ' in address_part:
                addr_parts = address_part.rsplit(', ', 1)
                job["property_address"] = address_part
                job["community"] = addr_parts[1] if len(addr_parts) > 1 else None
            else:
                job["property_address"] = address_part
        
        # === REFERENCE FILES ===
        ref_path = os.path.join(folder_path, "Reference & Research")
        old_ref = job.get("reference_files") or {}
        # Remove _updated for comparison (content only)
        old_ref_content = {k: v for k, v in old_ref.items() if k != "_updated"} if isinstance(old_ref, dict) else {}
        new_ref = self._scan_reference_files(ref_path)
        if new_ref != old_ref_content:
            new_ref["_updated"] = now
            job["reference_files"] = new_ref
            changes.append("reference_files")
        elif isinstance(old_ref, dict) and "_updated" not in old_ref:
            # Add timestamp to existing data
            old_ref["_updated"] = now
            job["reference_files"] = old_ref

        # === DOCUMENT CONTROL ===
        doc_path = os.path.join(folder_path, "Document Control")
        old_dc = job.get("document_control") or {}
        old_dc_content = {k: v for k, v in old_dc.items() if k != "_updated"} if isinstance(old_dc, dict) else {}
        new_dc = self._parse_document_control(doc_path, job_number)
        if new_dc and new_dc != old_dc_content:
            new_dc["_updated"] = now
            job["document_control"] = new_dc
            changes.append("document_control")
        elif new_dc and isinstance(old_dc, dict) and "_updated" not in old_dc:
            old_dc["_updated"] = now
            job["document_control"] = old_dc
        
        # === DATA SYNC (Controller Jobs) ===
        old_ds = job.get("data_sync", {})
        old_jobs = old_ds.get("jobs", []) if isinstance(old_ds, dict) else old_ds
        new_jobs = self._scan_data_sync(job_number)
        
        # Build field_summary from field_status.json data
        field_summary = self._build_field_summary(new_jobs)
        
        if new_jobs != old_jobs:
            job["data_sync"] = {
                "jobs": new_jobs,
                "field_summary": field_summary,
                "_updated": now
            }
            changes.append("data_sync")
        elif field_summary:
            # Update field_summary even if jobs list unchanged
            if isinstance(job.get("data_sync"), dict):
                job["data_sync"]["field_summary"] = field_summary
                job["data_sync"]["_updated"] = now
        
        # === NAS FOLDER FLAGS ===
        job["has_layout"] = os.path.exists(os.path.join(folder_path, "Layout"))
        job["has_drawings"] = bool(self._list_files(os.path.join(folder_path, "Drawings")))
        job["has_reports"] = bool(self._list_files(os.path.join(folder_path, "Reports")))
        job["has_field_data"] = any(
            j.get("field_data_complete") or j.get("field_uploads")
            for j in new_jobs
        ) if new_jobs else False
        
        # Track update
        if changes or is_new:
            job["last_updated"] = now
            job["last_refresh"] = now
            return True
        
        # Always update last_refresh even if no changes
        job["last_refresh"] = now
        return False
    
    def _scan_reference_files(self, ref_path: str) -> dict:
        """Scan Reference & Research folder."""
        result = {}
        
        if not os.path.exists(ref_path):
            return result
        
        for item in os.listdir(ref_path):
            item_path = os.path.join(ref_path, item)
            
            if os.path.isdir(item_path):
                # Subfolder (CADO, Plans, etc.)
                files = [f for f in os.listdir(item_path) 
                        if os.path.isfile(os.path.join(item_path, f))
                        and not f.startswith('.') and f != 'Thumbs.db']
                if files:
                    result[item] = sorted(files)
            elif os.path.isfile(item_path):
                # Root-level file
                if not item.startswith('.') and item != 'Thumbs.db':
                    if "root" not in result:
                        result["root"] = []
                    result["root"].append(item)
        
        if "root" in result:
            result["root"] = sorted(result["root"])
        
        return result
    
    def _parse_document_control(self, doc_path: str, job_number: str) -> dict:
        """Parse Document Control folder for stamped/sent status."""
        if not os.path.exists(doc_path):
            return {}
        
        files = [f for f in os.listdir(doc_path) 
                if os.path.isfile(os.path.join(doc_path, f))
                and f.lower().endswith('.pdf')]
        
        if not files:
            return {}
        
        # Patterns
        desc_pattern = re.compile(rf'^{re.escape(job_number)}-(\d+)(?:-R(\d+))?\.pdf$', re.IGNORECASE)
        drawing_pattern = re.compile(rf'^{re.escape(job_number)}--(\d+)(?:-R(\d+))?\.pdf$', re.IGNORECASE)
        sent_pattern = re.compile(rf'\({re.escape(job_number)}-(\d+)\)\.pdf$', re.IGNORECASE)
        
        documents = {}
        other_files = []
        
        for f in files:
            # Check description (stamped)
            m = desc_pattern.match(f)
            if m:
                doc_num = int(m.group(1))
                rev = int(m.group(2)) if m.group(2) else None
                if doc_num not in documents:
                    documents[doc_num] = {"doc_number": doc_num}
                documents[doc_num]["description"] = f
                if rev is not None:
                    documents[doc_num]["latest_revision"] = rev
                continue
            
            # Check drawing (double hyphen)
            m = drawing_pattern.match(f)
            if m:
                doc_num = int(m.group(1))
                if doc_num not in documents:
                    documents[doc_num] = {"doc_number": doc_num}
                documents[doc_num]["drawing"] = f
                continue
            
            # Check sent file (parentheses)
            m = sent_pattern.search(f)
            if m:
                doc_num = int(m.group(1))
                if doc_num not in documents:
                    documents[doc_num] = {"doc_number": doc_num}
                documents[doc_num]["sent_file"] = f
                continue
            
            # Other file
            other_files.append(f)
        
        doc_list = sorted(documents.values(), key=lambda x: x["doc_number"])
        total_sent = sum(1 for d in doc_list if d.get("sent_file"))
        
        return {
            "documents": doc_list,
            "other_files": sorted(other_files),
            "total_documents": len(doc_list),
            "total_sent": total_sent,
            "all_sent": total_sent == len(doc_list) and len(doc_list) > 0
        }
    
    def _scan_data_sync(self, job_number: str) -> list:
        """
        Scan Data Sync office-jobs for controller jobs.
        
        Structure:
        office-jobs/
          └── 25-150-200/              (batch folder)
              └── 25-180/              (job folder)
                  └── 25-180-250918/   (controller job with date)
                      ├── job_info.json
                      └── Field_Data/
        """
        data_sync = []
        
        if not os.path.exists(self.DATA_SYNC_OFFICE):
            return data_sync
        
        # Pattern for controller job folders: 25-180-YYMMDD
        cj_pattern = re.compile(rf'^{re.escape(job_number)}-\d{{6}}$')
        
        # Scan all batch folders
        for batch_folder in os.listdir(self.DATA_SYNC_OFFICE):
            batch_path = os.path.join(self.DATA_SYNC_OFFICE, batch_folder)
            if not os.path.isdir(batch_path):
                continue
            
            # Look for job folder (e.g., 25-180)
            job_folder_path = os.path.join(batch_path, job_number)
            if not os.path.exists(job_folder_path):
                continue
            
            # Scan controller job folders inside
            for item in os.listdir(job_folder_path):
                item_path = os.path.join(job_folder_path, item)
                if not os.path.isdir(item_path):
                    continue
                if not cj_pattern.match(item):
                    continue
                
                cj = {
                    "folder_name": item,
                    "field_data_complete": False,
                    "field_uploads": []
                }
                
                # Check job_info.json
                info_file = os.path.join(item_path, "job_info.json")
                if os.path.exists(info_file):
                    try:
                        with open(info_file, 'r') as f:
                            cj["job_info"] = json.load(f)
                    except:
                        pass
                
                # Check Field_Data and read field_status.json for rich status data
                fd_path = os.path.join(item_path, "Field_Data")
                if os.path.exists(fd_path):
                    # Scan upload folders
                    for fd_item in sorted(os.listdir(fd_path)):
                        fd_item_path = os.path.join(fd_path, fd_item)
                        if os.path.isdir(fd_item_path):
                            files = [f for f in os.listdir(fd_item_path)
                                    if os.path.isfile(os.path.join(fd_item_path, f))]
                            upload_entry = {
                                "folder": fd_item,
                                "file_count": len(files)
                            }
                            
                            # Read field_status.json if present
                            status_file = os.path.join(fd_item_path, "field_status.json")
                            if os.path.exists(status_file):
                                try:
                                    with open(status_file, 'r') as sf:
                                        fs = json.load(sf)
                                        upload_entry["field_status"] = {
                                            "operator": fs.get("operator"),
                                            "job_type": fs.get("job_type"),
                                            "field_work_done": fs.get("field_work_done"),
                                            "estimated_time_remaining": fs.get("estimated_time_remaining"),
                                            "time_spent": fs.get("time_spent"),
                                            "pins_found": fs.get("pins_found"),
                                            "pins_placed": fs.get("pins_placed"),
                                            "notes": fs.get("notes"),
                                            "is_reupload": fs.get("is_reupload", False),
                                            "replaces_folder": fs.get("replaces_folder"),
                                            "construction_tasks_completed": fs.get("construction_tasks_completed", []),
                                            "custom_tasks_completed": fs.get("custom_tasks_completed", []),
                                            "upload_timestamp": fs.get("upload_timestamp"),
                                            "qbo_sync": fs.get("qbo_sync")
                                        }
                                except:
                                    pass
                            
                            cj["field_uploads"].append(upload_entry)
                    
                    # Determine completion from field_status.json
                    non_reupload = [u for u in cj["field_uploads"] 
                                   if not u.get("field_status", {}).get("is_reupload", False)]
                    if non_reupload:
                        latest = non_reupload[-1]
                        fs = latest.get("field_status", {})
                        if fs.get("field_work_done") is not None:
                            cj["field_data_complete"] = fs["field_work_done"]
                        else:
                            cj["field_data_complete"] = True
                        # Bubble up latest status
                        cj["latest_field_status"] = {
                            "operator": fs.get("operator"),
                            "field_work_done": fs.get("field_work_done"),
                            "estimated_time_remaining": fs.get("estimated_time_remaining"),
                            "notes": fs.get("notes"),
                            "pins_found": fs.get("pins_found"),
                            "pins_placed": fs.get("pins_placed")
                        }
                    else:
                        cj["field_data_complete"] = True
                
                data_sync.append(cj)
        
        # Sort by folder name (date order)
        return sorted(data_sync, key=lambda x: x["folder_name"])
    
    def _build_field_summary(self, data_sync_jobs: list) -> dict:
        """
        Build aggregated field summary from all field_status.json uploads.
        Excludes reuploads from counts.
        """
        if not data_sync_jobs:
            return {}
        
        summary = {
            "visits": 0,
            "total_field_hours": 0,
            "total_travel_hours": 0,
            "operators": [],
            "construction_tasks": {},
            "needs_return_visit": False,
            "unsynced_time_entries": 0,
            "pins_status": {"found": None, "placed": None}
        }
        
        latest_upload = None
        
        for cj in data_sync_jobs:
            for upload in cj.get("field_uploads", []):
                fs = upload.get("field_status", {})
                if not fs:
                    continue
                
                # Skip reuploads for counting
                if fs.get("is_reupload"):
                    continue
                
                summary["visits"] += 1
                latest_upload = fs

                # Time
                time_spent = fs.get("time_spent") or {}
                summary["total_field_hours"] += (time_spent.get("field_hours") or 0)
                summary["total_travel_hours"] += (time_spent.get("travel_hours_oneway") or 0)
                
                # Operator
                op = fs.get("operator")
                if op and op not in summary["operators"]:
                    summary["operators"].append(op)
                
                # Construction tasks
                for task in fs.get("construction_tasks_completed", []):
                    summary["construction_tasks"][task] = summary["construction_tasks"].get(task, 0) + 1
                
                # QBO sync status
                qbo_sync = fs.get("qbo_sync", {})
                if not qbo_sync.get("time_synced"):
                    summary["unsynced_time_entries"] += 1
        
        # Return visit based on LATEST upload only
        if latest_upload:
            if latest_upload.get("field_work_done") == False:
                summary["needs_return_visit"] = True
            summary["pins_status"]["found"] = latest_upload.get("pins_found")
            summary["pins_status"]["placed"] = latest_upload.get("pins_placed")
        
        return summary if summary["visits"] > 0 else {}
    
    def _list_files(self, path: str) -> list:
        """List files in directory, excluding hidden/system."""
        if not os.path.exists(path):
            return []
        return [f for f in os.listdir(path) 
                if os.path.isfile(os.path.join(path, f))
                and not f.startswith('.') and f != 'Thumbs.db']
    
    def run(self, years: list = None):
        """Run the nightly refresh."""
        start = datetime.now()
        logger.info("=" * 60)
        logger.info("JOB INDEX REFRESH")
        logger.info(f"Started: {start}")
        logger.info("=" * 60)
        
        # Default: scan ALL years with job folders
        if not years:
            years = []
            for item in os.listdir(self.JOBS_ROOT):
                if item.isdigit() and len(item) == 4:  # Year folders like "2025"
                    years.append(int(item))
            years.sort()
        
        for year in years:
            self.refresh_year(year)
        
        # Save updated index
        self._save_index()
        
        # Report
        elapsed = (datetime.now() - start).total_seconds()
        logger.info("")
        logger.info("=" * 60)
        logger.info("REFRESH COMPLETE")
        logger.info(f"  Jobs scanned: {self.stats['jobs_scanned']}")
        logger.info(f"  Jobs updated: {self.stats['jobs_updated']}")
        logger.info(f"  Jobs added:   {self.stats['jobs_added']}")
        logger.info(f"  Errors:       {len(self.stats['errors'])}")
        logger.info(f"  Elapsed:      {elapsed:.1f}s")
        logger.info(f"  Index size:   {len(self.job_index)} jobs")
        logger.info("=" * 60)
        
        if self.stats["errors"]:
            logger.warning("Errors encountered:")
            for err in self.stats["errors"][:10]:
                logger.warning(f"  {err}")
        
        return self.stats


def main():
    parser = argparse.ArgumentParser(description="Nightly job index refresh")
    parser.add_argument('--year', type=int, action='append',
                       help="Year(s) to scan (default: current + previous)")
    parser.add_argument('--verbose', '-v', action='store_true',
                       help="Verbose output")
    parser.add_argument('--skip-qbo', action='store_true',
                       help="Skip QBO sync (useful if QBO auth is expired)")
    args = parser.parse_args()

    # Log directory already created during logging setup

    # Run NAS/Data Sync refresh
    refresher = NightlyRefresh(verbose=args.verbose)
    stats = refresher.run(years=args.year)

    # Run QBO sync to detect manual invoice changes
    if not args.skip_qbo:
        logger.info("")
        logger.info("Running QBO sync...")
        try:
            from qbo_sync import QBOSync
            qbo_syncer = QBOSync(verbose=args.verbose)
            qbo_stats = qbo_syncer.run(recent_count=200)
            stats["qbo_invoices_updated"] = qbo_stats.get("invoices_updated", 0)
            stats["qbo_payments_detected"] = qbo_stats.get("payments_detected", 0)
        except Exception as e:
            logger.warning(f"QBO sync failed (non-critical): {e}")
            stats["qbo_error"] = str(e)

    # Exit code based on errors
    return 1 if stats["errors"] else 0


if __name__ == "__main__":
    exit(main())
