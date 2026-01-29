import json

idx = json.load(open('job_index.json'))
job = [v for k,v in idx.items() if v.get('job_number')=='26-001'][0]

print("=== 26-001 Section Timestamps ===")
print(f"last_updated: {job.get('last_updated', 'MISSING')}")
print(f"last_refresh: {job.get('last_refresh', 'MISSING')}")

sections = ['qbo', 'emails', 'data_sync', 'document_control', 'field_summary']
for s in sections:
    data = job.get(s)
    if data is None:
        print(f"{s}: [not present]")
    elif isinstance(data, dict):
        print(f"{s}: {data.get('_updated', 'NO _updated')}")
    elif isinstance(data, list):
        print(f"{s}: [list - {len(data)} items, no _updated]")
    else:
        print(f"{s}: [{type(data).__name__}]")
