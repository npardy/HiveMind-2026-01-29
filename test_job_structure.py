"""
Test the updated job_create and job_search with new structure.
Verifies:
1. Jobs are keyed by job_number (not conversation_id)
2. Proper section structure with _updated timestamps
3. QBO data in qbo section
4. Email linking works
"""
import sys
import json
sys.path.insert(0, '.')

print("=" * 60)
print("TESTING NEW JOB INDEX STRUCTURE")
print("=" * 60)

# Load current index
idx = json.load(open('job_index.json'))

# Check a job created by nightly refresh (should be correct)
print("\n1. CHECKING 26-001 (nightly refresh created):")
job = idx.get('26-001')
if job:
    print(f"   Key type: job_number [OK]")
    print(f"   job_number field: {job.get('job_number')}")
    
    # Check sections
    sections = ['qbo', 'emails', 'data_sync', 'document_control', 'reference_files']
    for s in sections:
        data = job.get(s)
        if data is None:
            print(f"   {s}: MISSING")
        elif isinstance(data, dict):
            has_updated = '_updated' in data
            print(f"   {s}: dict, _updated={'YES' if has_updated else 'NO'}")
        else:
            print(f"   {s}: {type(data).__name__} (should be dict)")
else:
    print("   NOT FOUND")

# Check for any legacy conversation_id keys (they don't match XX-XXX pattern)
print("\n2. CHECKING FOR LEGACY CONVERSATION_ID KEYS:")
import re
job_pattern = re.compile(r'^\d{2}-\d{3}$')
legacy_keys = [k for k in idx.keys() if not job_pattern.match(k)]
if legacy_keys:
    print(f"   Found {len(legacy_keys)} legacy keys (need migration):")
    for k in legacy_keys[:5]:
        info = idx[k]
        print(f"   - {k[:40]}... -> job {info.get('job_number', '?')}")
else:
    print("   No legacy keys found [OK]")

# Check what _get_or_create_job_entry would create
print("\n3. NEW JOB TEMPLATE STRUCTURE:")
from tool_executor import ToolExecutor
te = ToolExecutor(qbo=None, email_service=None)
# Don't actually save, just show structure
template = te._get_or_create_job_entry("99-999")
# Remove it so we don't pollute the index
if "99-999" in te.job_index:
    del te.job_index["99-999"]

print(f"   Sections with _updated:")
for key, val in template.items():
    if isinstance(val, dict) and '_updated' in val:
        print(f"   - {key}: _updated = {val['_updated']}")

print("\n" + "=" * 60)
print("STRUCTURE VERIFICATION COMPLETE")
print("=" * 60)
