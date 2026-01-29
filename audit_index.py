"""Audit job index structure"""
import json

with open('job_index.json', 'r') as f:
    idx = json.load(f)

print(f'Total jobs in index: {len(idx)}')
print()

# Track issues
issues = []

# Check ALL jobs for structure consistency
for job_num, job in idx.items():
    job_issues = []
    
    # Check if key matches job_number field
    if job.get('job_number') != job_num:
        job_issues.append(f"Key mismatch: key={job_num}, job_number={job.get('job_number')}")
    
    # Check if key looks like conversation_id (old structure)
    if not job_num[0].isdigit():
        job_issues.append(f"Key looks like conversation_id, not job_number: {job_num[:30]}...")
    
    # Check sections
    for section in ['qbo', 'emails', 'data_sync', 'reference_files', 'document_control']:
        val = job.get(section)
        if val is None:
            job_issues.append(f"{section}: MISSING")
        elif isinstance(val, list):
            job_issues.append(f"{section}: LIST (should be dict)")
        elif isinstance(val, dict):
            if '_updated' not in val:
                job_issues.append(f"{section}: missing _updated timestamp")
    
    # Check for old flat fields that should be in qbo section
    old_flat_fields = ['qbo_customer_id', 'qbo_project_id', 'qbo_invoice_id']
    for field in old_flat_fields:
        if field in job:
            job_issues.append(f"Old flat field: {field} (should be in qbo section)")
    
    if job_issues:
        issues.append((job_num, job_issues))

# Report
print("=" * 60)
print("STRUCTURE AUDIT RESULTS")
print("=" * 60)

if not issues:
    print("ALL JOBS HAVE CORRECT STRUCTURE!")
else:
    print(f"FOUND {len(issues)} JOBS WITH ISSUES:")
    print()
    for job_num, job_issues in issues[:20]:  # Show first 20
        print(f"  {job_num}:")
        for issue in job_issues:
            print(f"    - {issue}")
        print()

# Sample a good job
print()
print("=" * 60)
print("SAMPLE CORRECT JOB STRUCTURE (first clean job):")
print("=" * 60)
for job_num, job in idx.items():
    # Check if this job is clean
    is_clean = True
    if job.get('job_number') != job_num:
        is_clean = False
    for section in ['qbo', 'emails', 'data_sync']:
        val = job.get(section)
        if not isinstance(val, dict) or '_updated' not in val:
            is_clean = False
    
    if is_clean:
        print(f"Job: {job_num}")
        print(json.dumps(job, indent=2, default=str)[:2000])
        break
