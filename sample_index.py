"""Sample the job index"""
import json

with open('job_index.json', 'r') as f:
    idx = json.load(f)

print(f'Total jobs: {len(idx)}')
print()

# Sample jobs
samples = ['25-001', '25-100', '25-200', '25-248']
for job_num in samples:
    if job_num not in idx:
        print(f'{job_num}: NOT FOUND')
        continue
    job = idx[job_num]
    addr = job.get('property_address', 'N/A')
    if addr:
        addr = addr[:45]
    print(f'{job_num}: {addr}')
    print(f'  Client: {job.get("client_business", "N/A")}')
    
    ref = job.get('reference_files', {})
    ref_count = sum(len(v) if isinstance(v, list) else 0 for v in ref.values())
    folders = list(ref.keys())
    print(f'  Reference files: {ref_count} in {folders}')
    
    dc = job.get('document_control', {})
    if dc:
        docs = dc.get('total_documents', 0)
        sent = dc.get('total_sent', 0)
        all_sent = dc.get('all_sent', False)
        status = 'ALL SENT' if all_sent else f'{sent}/{docs} sent'
        print(f'  Documents: {docs} - {status}')
    else:
        print(f'  Documents: none')
    
    cj = job.get('data_sync', [])
    print(f'  Data Sync: {len(cj)}')
    for c in cj[:2]:  # Show first 2
        fd = 'YES' if c.get('field_data_complete') else 'no'
        print(f'    - {c.get("folder_name")}: field_data={fd}')
    
    print()
