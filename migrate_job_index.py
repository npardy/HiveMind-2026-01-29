"""
One-time migration: Convert job_index.json to new structure
- emails: list → dict with linked array and _updated
- data_sync: list → dict with jobs array, field_summary, and _updated
- Ensure all sections exist with proper structure
"""

import json
from datetime import datetime

INDEX_PATH = "H:\\data\\job_index.json"
BACKUP_PATH = "H:\\data\\job_index_pre_migration.json"

def migrate():
    # Load
    with open(INDEX_PATH, 'r') as f:
        idx = json.load(f)
    
    # Backup
    with open(BACKUP_PATH, 'w') as f:
        json.dump(idx, f, indent=2)
    print(f"Backed up to {BACKUP_PATH}")
    
    now = datetime.now().isoformat()
    
    stats = {
        "total": len(idx),
        "emails_converted": 0,
        "data_sync_converted": 0,
        "data_sync_added": 0,
        "qbo_added": 0,
        "reference_files_fixed": 0,
        "document_control_added": 0
    }
    
    for job_number, job in idx.items():
        
        # === EMAILS: list → dict ===
        emails = job.get("emails")
        if isinstance(emails, list):
            job["emails"] = {
                "linked": emails,
                "_updated": now
            }
            stats["emails_converted"] += 1
        elif emails is None:
            job["emails"] = {"linked": [], "_updated": now}
        elif isinstance(emails, dict) and "_updated" not in emails:
            emails["_updated"] = now
        
        # === DATA_SYNC: list → dict ===
        ds = job.get("data_sync")
        if isinstance(ds, list):
            job["data_sync"] = {
                "jobs": ds,
                "field_summary": {},
                "_updated": now
            }
            stats["data_sync_converted"] += 1
        elif ds is None:
            job["data_sync"] = {
                "jobs": [],
                "field_summary": {},
                "_updated": now
            }
            stats["data_sync_added"] += 1
        elif isinstance(ds, dict) and "_updated" not in ds:
            ds["_updated"] = now
        
        # === QBO: ensure exists ===
        qbo = job.get("qbo")
        if qbo is None:
            job["qbo"] = {"_updated": None}
            stats["qbo_added"] += 1
        elif isinstance(qbo, dict) and "_updated" not in qbo:
            qbo["_updated"] = None
        
        # === REFERENCE_FILES: ensure _updated ===
        ref = job.get("reference_files")
        if ref is None:
            job["reference_files"] = {"_updated": now}
            stats["reference_files_fixed"] += 1
        elif isinstance(ref, dict) and "_updated" not in ref:
            ref["_updated"] = now
            stats["reference_files_fixed"] += 1
        
        # === DOCUMENT_CONTROL: ensure exists ===
        dc = job.get("document_control")
        if dc is None:
            job["document_control"] = {"_updated": None}
            stats["document_control_added"] += 1
        elif isinstance(dc, dict) and "_updated" not in dc:
            dc["_updated"] = None
    
    # Save
    with open(INDEX_PATH, 'w') as f:
        json.dump(idx, f, indent=2)
    
    print()
    print("=== MIGRATION COMPLETE ===")
    print(f"Total jobs: {stats['total']}")
    print(f"emails converted (list→dict): {stats['emails_converted']}")
    print(f"data_sync converted (list→dict): {stats['data_sync_converted']}")
    print(f"data_sync added (missing): {stats['data_sync_added']}")
    print(f"qbo added (missing): {stats['qbo_added']}")
    print(f"reference_files fixed: {stats['reference_files_fixed']}")
    print(f"document_control added: {stats['document_control_added']}")
    
    return stats

if __name__ == "__main__":
    migrate()
