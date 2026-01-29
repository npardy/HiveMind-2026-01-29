"""Test nightly refresh timestamps"""
import sys
import json
sys.path.insert(0, '.')
from nightly_refresh import NightlyRefresh

# Run refresh on just 2026 for speed
r = NightlyRefresh(verbose=True)
r.refresh_year(2026)
r._save_index()

print("Refresh done. Checking 26-001 timestamps...")

idx = json.load(open('job_index.json'))
job = None
for k, v in idx.items():
    if v.get('job_number') == '26-001':
        job = v
        break

if not job:
    print('26-001 not found!')
    exit(1)

print(f"last_updated: {job.get('last_updated', 'MISSING')}")
print(f"last_refresh: {job.get('last_refresh', 'MISSING')}")

sections = ['qbo', 'emails', 'data_sync', 'document_control', 'reference_files']
for s in sections:
    data = job.get(s)
    if data is None:
        print(f"{s}: [not present]")
    elif isinstance(data, dict):
        updated = data.get('_updated', 'NO _updated')
        print(f"{s}: {updated}")
    else:
        print(f"{s}: [type: {type(data).__name__}]")

# Show structure of data_sync
ds = job.get('data_sync', {})
if isinstance(ds, dict):
    print(f"\ndata_sync structure:")
    print(f"  jobs: {len(ds.get('jobs', []))} items")
    print(f"  field_summary: {list(ds.get('field_summary', {}).keys())}")
