"""Test reading real field_status.json from 26-001"""
from tool_executor import ToolExecutor
import json

te = ToolExecutor(qbo=None, email_service=None)
result = te.execute('job_get_status', {'job_number': '26-001'})

print("Result type:", type(result))
if isinstance(result, str):
    print("Error:", result)
    exit(1)

ds = result.get('data_sync', {})

print("=== FIELD SUMMARY ===")
print(json.dumps(ds.get('field_summary'), indent=2))

print("\n=== UPLOAD DETAILS ===")
for cj in ds.get('data_sync', []):
    print(f"\n{cj['folder_name']}:")
    for u in cj.get('field_uploads', []):
        fs = u.get('field_status', {})
        if fs:
            print(f"  {u['folder']}:")
            print(f"    operator: {fs.get('operator')}")
            print(f"    field_work_done: {fs.get('field_work_done')}")
            print(f"    pins_found: {fs.get('pins_found')}")
            print(f"    pins_placed: {fs.get('pins_placed')}")
            print(f"    time: {fs.get('time_spent')}")
        else:
            print(f"  {u['folder']}: (no field_status.json)")
