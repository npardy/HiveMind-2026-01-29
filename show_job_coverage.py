"""Show what job_get_status covers"""
import json

idx = json.load(open('job_index.json'))
job = [v for k,v in idx.items() if v.get('job_number')=='26-001'][0]

print('=== WHAT job_get_status ENRICHES ===')
print()
print('From NAS Job Folder:')
jf = job.get('job_folder', '?')
print(f'  job_folder: {jf[:50] if jf else "?"}...')
print(f'  property_address: {job.get("property_address")}')
print(f'  client_business: {job.get("client_business")}')
print(f'  has_layout: {job.get("has_layout")}')
print(f'  has_drawings: {job.get("has_drawings")}')
print(f'  has_reports: {job.get("has_reports")}')
print(f'  has_field_data: {job.get("has_field_data")}')
print(f'  reference_files: {len(job.get("reference_files", {}))} categories')
dc = job.get('document_control', {})
print(f'  document_control: {dc.get("total_documents", 0) if isinstance(dc, dict) else 0} docs')

print()
print('From Data Sync:')
ds = job.get('data_sync', {})
if isinstance(ds, dict):
    jobs = ds.get('jobs', [])
    fs = ds.get('field_summary', {})
    print(f'  controller jobs: {len(jobs)}')
    print(f'  field_summary.visits: {fs.get("visits", 0)}')
    print(f'  field_summary.total_field_hours: {fs.get("total_field_hours", 0)}')
    print(f'  field_summary.operators: {fs.get("operators", [])}')

print()
print('NOT from job_get_status (separate sources):')
qbo = job.get('qbo', {})
qbo_keys = [k for k in qbo.keys() if not k.startswith('_')]
print(f'  qbo: {qbo_keys}')
emails = job.get('emails', {})
if isinstance(emails, dict):
    print(f'  emails: {len(emails.get("linked", []))} linked')
else:
    print(f'  emails: {len(emails)} linked (old format)')
