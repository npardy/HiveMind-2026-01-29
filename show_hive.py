"""Show full hive state"""
import json

with open('job_index.json', 'r') as f:
    idx = json.load(f)

print('HIVE INTELLIGENCE - CURRENT STATE')
print('=' * 60)
print(f'Total jobs indexed: {len(idx)}')
print()

for job_num, job in idx.items():
    addr = job.get('property_address', 'N/A')
    print(f'{job_num}: {addr}')
    print(f'  Client: {job.get("client_business", "N/A")}')
    
    # Data Sync
    cj = job.get('data_sync', [])
    print(f'  Data Sync: {len(cj)}')
    for c in cj:
        fd = 'YES' if c.get('field_data_complete') else 'no'
        uploads = len(c.get('field_uploads', []))
        print(f'    - {c.get("folder_name")}: field_data={fd}, uploads={uploads}')
    
    # Reference files
    ref = job.get('reference_files', {})
    if ref:
        total_ref = sum(len(v) if isinstance(v, list) else 0 for v in ref.values())
        folders = [k for k in ref.keys()]
        print(f'  Reference files: {total_ref} files in {folders}')
    
    # Document control
    dc = job.get('document_control', {})
    if dc:
        docs = dc.get('documents', [])
        sent = dc.get('total_sent', 0)
        all_sent = dc.get('all_sent', False)
        status = 'ALL SENT' if all_sent else f'{sent}/{len(docs)} sent'
        print(f'  Documents: {len(docs)} total - {status}')
    
    # Emails
    emails = job.get('emails', [])
    print(f'  Linked emails: {len(emails)}')
    
    print()
