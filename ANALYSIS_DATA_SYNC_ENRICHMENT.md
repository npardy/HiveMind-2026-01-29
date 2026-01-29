# Analysis: Data Sync Automatic Enrichment Failure

## Executive Summary

The job index is designed to be a "living document" that stays automatically enriched with data from Data Sync uploads. **This is currently broken.** When field data is uploaded from the controller or when layouts are uploaded from the PC, the notification_watcher attempts to enrich the job index but the data is silently dropped due to structural mismatches in the enrichment pipeline.

Claude can still provide accurate field data because `job_get_status` reads LIVE from the Data Sync folder every time it's called. However, the job index itself is NOT being kept current automatically.

---

## The Problem

### Expected Behavior
1. Field crew uploads data from controller → Job index automatically updated with field_summary, layout_summary, all field_status.json data
2. PC uploads layout to Data Sync → Job index automatically updated with job_info (address, description, operator assignment)

### Actual Behavior
1. Field crew uploads data → notification_watcher fires → Data is **silently dropped** → Index NOT updated
2. PC uploads layout → notification_watcher fires → Data is **silently dropped** → Index NOT updated

### Why Claude Still Works
`job_get_status` (tool_executor.py:2907-3328) reads LIVE from the Data Sync folder every time. It bypasses the index for data_sync information and scans the actual disk. This is why asking Claude always gives accurate data.

---

## Root Cause Analysis

### Issue 1: `enrich_job_index` Ignores Notification Watcher's Data

**Location:** `tool_executor.py`, lines 216-227

**What happens:**
```python
elif section == "data_sync":
    # Data sync has jobs array and field_summary
    if not isinstance(job[section], dict):
        job[section] = {"jobs": [], "field_summary": {}, "_updated": now}
    if "jobs" not in job[section]:
        job[section]["jobs"] = []

    # If data has jobs array, replace it
    if "jobs" in data:
        job[section]["jobs"] = data["jobs"]
    if "field_summary" in data:
        job[section]["field_summary"] = data["field_summary"]
    # NOTHING ELSE - other fields are silently ignored
```

**What notification_watcher passes (field upload):**
```python
# notification_watcher.py:271-276
self.tool_executor.enrich_job_index(job_number, "data_sync", {
    "field_uploads": field_uploads,      # ❌ IGNORED - not "jobs" or "field_summary"
    "last_upload": timestamp,            # ❌ IGNORED
    "last_operator": operator,           # ❌ IGNORED
    "status": status                     # ❌ IGNORED
})
```

**What notification_watcher passes (layout upload):**
```python
# notification_watcher.py:148-153
self.tool_executor.enrich_job_index(job_number, "data_sync", {
    "folder_created": True,              # ❌ IGNORED
    "folder_path": job_path,             # ❌ IGNORED
    "created_at": created_at,            # ❌ IGNORED
    "source": "data_sync_layout"         # ❌ IGNORED
})
```

**Result:** ALL data passed by notification_watcher is silently dropped because `enrich_job_index` only looks for `jobs` and `field_summary` keys.

---

### Issue 2: Notification Watcher Never Reads from Data Sync Folder

**The core problem:** notification_watcher receives an event with minimal metadata, but never goes back to the Data Sync folder to read the actual rich data (`job_info.json`, `field_status.json`).

**What it should do:**
1. Receive event (e.g., field_data_uploaded)
2. Call `_job_get_status(job_number)` to read LIVE from Data Sync folder
3. This automatically triggers `_enrich_job_in_index` with complete data

**What it currently does:**
1. Receive event
2. Try to save basic event metadata
3. Data dropped
4. Never reads from disk

---

### Issue 3: Structural Mismatch Between Enrichment Paths

Three different code paths write to `job["data_sync"]` with **different structures**:

| Code Path | `job["data_sync"]` Structure | `field_summary` Location |
|-----------|------------------------------|--------------------------|
| `nightly_refresh.py` | `{jobs: [...], field_summary: {...}, _updated: ...}` | Inside `data_sync` |
| `_enrich_job_from_data_sync` (Claude's path) | `[...]` (array directly) | Top level: `job["field_summary"]` |
| `enrich_job_index` expects | `{jobs: [...], field_summary: {...}}` | Inside `data_sync` |

**Evidence:**

`nightly_refresh.py:185-189`:
```python
job["data_sync"] = {
    "jobs": new_jobs,
    "field_summary": field_summary,
    "_updated": now
}
```

`_enrich_job_from_data_sync` (tool_executor.py:373-380):
```python
job["data_sync"] = data_sync["data_sync"]  # Saves ARRAY directly
job["data_sync_folder"] = data_sync.get("sync_folder")
# ...
job["field_summary"] = data_sync["field_summary"]  # At TOP LEVEL
```

---

## Data Flow Comparison

### What Claude Gets (Complete - from job_get_status)

```
job_get_status called
    ↓
Reads LIVE from Z:\Data Sync\office-jobs\{range}\{job}\
    ↓
For each controller job folder ({job}-{date}):
    ├── Reads job_info.json → address, description, operator, created, reference_number
    └── For each Field_Data\{upload}\ folder:
        └── Reads field_status.json → operator, job_type, field_work_done,
            time_spent, pins_found, pins_placed, notes, upload_type,
            construction_tasks_completed, custom_tasks_completed,
            qbo_sync, csv_extracted
    ↓
Calculates layout_summary for each controller job:
    - visits, total_field_hours, total_travel_hours
    - operators list
    - field_work_done, needs_return_visit
    - pins_status, construction_tasks, custom_tasks
    - csv_extracted (evidence_found, pins_placed, monument_checks)
    - unsynced_time_entries
    ↓
Rolls up to field_summary (job-wide):
    - total_visits, total_field_hours, total_travel_hours
    - operators, field_complete, needs_return_visit
    - layouts_awaiting_field_data, layouts_with_field_data, layouts_field_complete
    - All aggregated data
    ↓
Returns complete status to Claude
    ↓
Calls _enrich_job_in_index → saves to index
```

### What Notification Watcher Does (Broken)

```
Event received (field_data_uploaded or layout_job_created)
    ↓
Extracts basic info from event payload
    ↓
Calls enrich_job_index with basic metadata
    ↓
enrich_job_index checks for "jobs" and "field_summary" keys
    ↓
Keys not found → DATA DROPPED
    ↓
Index NOT updated
    ↓
Data Sync folder: NEVER READ
```

---

## The Rich Data Being Lost

When notification_watcher fails to trigger proper enrichment, the index misses:

### From field_status.json:
- `operator` - who did the field work
- `job_type` - survey_rpr, survey_boundary, construction, etc.
- `field_work_done` - true/false completion status
- `estimated_time_remaining` - if incomplete, how much more time needed
- `time_spent.field_hours` - actual field time
- `time_spent.travel_hours_oneway` - travel time
- `pins_found` - "yes", "no", "partial", "n/a"
- `pins_placed` - "yes", "no", "partial", "n/a"
- `notes` - operator's notes from the field
- `upload_type` - "complete", "intermediate", "reupload"
- `construction_tasks_completed` - array of completed tasks
- `custom_tasks_completed` - array of custom tasks
- `csv_extracted` - parsed point data:
  - `total_points`
  - `evidence_found` - list of evidence descriptions
  - `pins_placed` - list of placed pins
  - `evidence_not_found` - count
  - `monument_checks` - list

### Calculated Summaries:
- `layout_summary` - per-controller-job aggregation
- `field_summary` - job-wide aggregation with:
  - `total_visits`, `total_field_hours`, `total_travel_hours`
  - `field_complete` status
  - `needs_return_visit` flag
  - `layouts_awaiting_field_data` vs `layouts_field_complete`
  - `unsynced_time_entries` count

---

## Recommended Fix

### The Solution

Have both notification_watcher handlers call `_job_get_status()` after detecting their event. This:

1. Reads LIVE from Data Sync folder (same code path as Claude)
2. Gets ALL rich data from `job_info.json` and `field_status.json`
3. Calculates `layout_summary` for each controller job
4. Rolls up to `field_summary`
5. Calls `_enrich_job_in_index` with complete data

### Implementation Locations

**File:** `notification_watcher.py`

**Handler 1:** `_handle_field_data_uploaded` (around line 157-290)
- After processing the event, add: `self.tool_executor._job_get_status({"job_number": job_number})`

**Handler 2:** `_handle_layout_job_created` (around line 127-155)
- After processing the event, add: `self.tool_executor._job_get_status({"job_number": job_number})`

### Why This Works

- Uses the EXACT same code path Claude uses
- No data loss - all rich data is captured
- No structural mismatches - `_enrich_job_in_index` is called with proper data
- Existing functionality preserved - we're just triggering what already works

---

## Key Files and Line Numbers

| File | Lines | Function | Purpose |
|------|-------|----------|---------|
| `notification_watcher.py` | 127-155 | `_handle_layout_job_created` | Handles PC layout uploads |
| `notification_watcher.py` | 157-290 | `_handle_field_data_uploaded` | Handles field data uploads |
| `notification_watcher.py` | 271-276 | (within above) | Broken enrichment call |
| `tool_executor.py` | 168-286 | `enrich_job_index` | Central enrichment function |
| `tool_executor.py` | 216-227 | (within above) | data_sync handling - drops unknown keys |
| `tool_executor.py` | 332-383 | `_enrich_job_in_index` | Main enrichment called by job_get_status |
| `tool_executor.py` | 368-383 | `_enrich_job_from_data_sync` | Saves data_sync to index |
| `tool_executor.py` | 2618-2743 | `_calculate_layout_summary` | Per-layout summary calculation |
| `tool_executor.py` | 2777-2905 | `_rollup_field_summary` | Job-wide summary rollup |
| `tool_executor.py` | 2907-3328 | `_job_get_status` | The central hub - reads LIVE from disk |
| `nightly_refresh.py` | 181-195 | (within `_refresh_job`) | Correct data_sync structure |

---

## Verification Checklist

Before implementing, verify:

1. [ ] `enrich_job_index` still only handles "jobs" and "field_summary" for data_sync section
2. [ ] `_handle_field_data_uploaded` does NOT call `_job_get_status`
3. [ ] `_handle_layout_job_created` does NOT call `_job_get_status`
4. [ ] `_job_get_status` still calls `_enrich_job_in_index` at the end
5. [ ] `_enrich_job_in_index` still calls `_enrich_job_from_data_sync`

After implementing, verify:

1. [ ] Field upload triggers full index enrichment with field_summary
2. [ ] Layout upload triggers index enrichment with job_info
3. [ ] Existing QBO time posting in `_handle_field_data_uploaded` still works
4. [ ] Existing email linking functionality still works
5. [ ] Nightly refresh still works correctly
6. [ ] Claude's job_get_status still works correctly

---

## Safety Considerations

### Preserve Existing Functionality

The notification_watcher handlers do MORE than just enrichment:

**`_handle_field_data_uploaded` also:**
- Posts time entries to QBO (`self._post_time_to_qbo`)
- Handles operator lookup
- Processes upload metadata

**These must NOT be affected.** The fix should ADD the `_job_get_status` call, not replace existing logic.

### Order of Operations

Call `_job_get_status` AFTER the existing processing, not before. This ensures:
1. QBO time posting happens first (existing behavior)
2. Then full enrichment happens (new behavior)

### Error Handling

Wrap the `_job_get_status` call in try/except to prevent enrichment failures from breaking the notification pipeline:

```python
# After existing processing...
try:
    self.tool_executor._job_get_status({"job_number": job_number})
except Exception as e:
    self.logger.error(f"Failed to enrich job index for {job_number}: {e}")
```

---

## Structural Alignment Consideration

There's a secondary issue: `_enrich_job_from_data_sync` saves the array directly to `job["data_sync"]`, while `nightly_refresh` wraps it in a dict. This creates inconsistent structure.

**Options:**
1. **Accept the inconsistency** - code reading the index should handle both formats
2. **Align the structures** - modify `_enrich_job_from_data_sync` to match nightly_refresh's format

This is a lower priority issue but should be noted for future cleanup.
