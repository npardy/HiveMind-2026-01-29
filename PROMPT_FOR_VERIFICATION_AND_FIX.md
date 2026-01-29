# Prompt for Claude Code: Verify and Fix Data Sync Automatic Enrichment

## Context

A previous analysis identified that the job index is NOT being automatically enriched when Data Sync events occur (field uploads from controller, layout uploads from PC). The analysis is documented in `ANALYSIS_DATA_SYNC_ENRICHMENT.md`.

**Your task:** Verify these findings against the CURRENT code, identify any differences, and implement the fix safely.

---

## CRITICAL: Data Preservation Requirement

The `field_status.json` data structure and the `job_info.json` data were **carefully designed** to capture all necessary information for field work tracking. The fix MUST:

1. **Preserve ALL fields** from `field_status.json`:
   - `operator`, `job_type`, `field_work_done`, `estimated_time_remaining`
   - `time_spent` (field_hours, travel_hours_oneway)
   - `pins_found`, `pins_placed`
   - `notes`
   - `upload_type` ("complete", "intermediate", "reupload")
   - `construction_tasks_completed`, `custom_tasks_completed`
   - `qbo_sync` status
   - `csv_extracted` (total_points, evidence_found, pins_placed, monument_checks)

2. **Preserve ALL fields** from `job_info.json`:
   - `address`, `description`, `operator`, `created`, `referenceNumber`

3. **Preserve calculated summaries**:
   - `layout_summary` (per-controller-job aggregation)
   - `field_summary` (job-wide rollup)

4. **No format mismatches** - the data that ends up in the job index must match what `_job_get_status` produces when Claude asks

The whole point is that the job index should contain the SAME rich data that Claude gets when it calls `job_get_status`. There should be no difference in completeness.

---

## Step 1: Examine Real Field Data Examples

**Before looking at any code**, examine actual `field_status.json` files to understand the data you're preserving.

### 1.1 Find a job with completed field data

Look in the Data Sync folder for a job with field uploads. **Do NOT use 26-010** - find another job like 26-001, 26-002, 26-003, or similar that has the field form completed.

```
# Example path structure:
Z:\Data Sync\office-jobs\26-000-050\26-001\26-001-260107\Field_Data\260107-0925AM\field_status.json
```

### 1.2 Read the actual field_status.json

Read at least one real `field_status.json` file and note:
- All the fields present
- The data types and values
- How `time_spent` is structured
- What `csv_extracted` contains (if present)
- The `upload_type` values

### 1.3 Read the job_info.json

Read the corresponding `job_info.json` in the controller job folder (parent of Field_Data) to see:
- Address, description, operator assignment
- Reference number
- Created timestamp

### 1.4 Understand the designed structure

Also read `test_field_status.py` which shows mock examples of the expected data structure and how aggregation is supposed to work. This represents the design intent.

**Document what you find** - this is the data that MUST be preserved in the job index.

---

## Step 2: Read the Analysis Document

Read the complete analysis:
```
Read ANALYSIS_DATA_SYNC_ENRICHMENT.md
```

This contains:
- Detailed explanation of the problem
- Root cause analysis with specific code locations
- Data flow diagrams
- The recommended fix
- Safety considerations

---

## Step 3: Verify Against Current Code

The analysis was based on code that may have been updated. **You must verify each finding against the current code.**

### Verification Tasks

#### 3.1 Check `enrich_job_index` for data_sync handling

Read `tool_executor.py` and find the `enrich_job_index` function. Look for the `elif section == "data_sync":` block.

**Verify:**
- Does it only handle "jobs" and "field_summary" keys?
- Are other keys (like "field_uploads", "last_upload", "status") being ignored/dropped?
- Has this been fixed in the current code?

#### 3.2 Check `_handle_field_data_uploaded` in notification_watcher

Read `notification_watcher.py` and find `_handle_field_data_uploaded`.

**Verify:**
- Does it call `enrich_job_index` with fields that would be dropped?
- Does it call `_job_get_status` to trigger full enrichment? (If yes, the fix may already exist)
- What else does this handler do? (QBO time posting, etc.)

#### 3.3 Check `_handle_layout_job_created` in notification_watcher

Read `notification_watcher.py` and find `_handle_layout_job_created`.

**Verify:**
- Does it call `enrich_job_index` with fields that would be dropped?
- Does it call `_job_get_status`? (If yes, fix may already exist)

#### 3.4 Check `_job_get_status` enrichment chain

Read `tool_executor.py` and find `_job_get_status`.

**Verify:**
- Does it still call `_enrich_job_in_index` at the end?
- Does `_enrich_job_in_index` still call `_enrich_job_from_data_sync`?
- Is the enrichment chain intact?

---

## Step 4: Document Differences

If you find differences between the analysis and current code, document them:

```markdown
## Differences Found

### [Location]
- **Analysis said:** [what the analysis expected]
- **Current code shows:** [what you actually found]
- **Impact:** [does this change the fix approach?]
```

---

## Step 5: Implement the Fix (If Still Needed)

If the issues are confirmed and not already fixed:

### 5.1 Modify `_handle_field_data_uploaded`

**Location:** `notification_watcher.py`, in the `_handle_field_data_uploaded` method

**Add at the END of the method, AFTER all existing processing:**

```python
# Trigger full job index enrichment by reading live from Data Sync
# This ensures field_summary and all rich data are captured
try:
    if self.tool_executor and job_number:
        self.tool_executor._job_get_status({"job_number": job_number})
        self.logger.info(f"Enriched job index for {job_number} after field upload")
except Exception as e:
    self.logger.error(f"Failed to enrich job index for {job_number}: {e}")
```

**Critical:**
- Add this AFTER the existing QBO time posting code
- Do NOT remove or modify any existing functionality
- Wrap in try/except to prevent enrichment failures from breaking the pipeline

### 5.2 Modify `_handle_layout_job_created`

**Location:** `notification_watcher.py`, in the `_handle_layout_job_created` method

**Add at the END of the method, AFTER all existing processing:**

```python
# Trigger full job index enrichment by reading live from Data Sync
# This captures job_info.json data (address, description, operator assignment)
try:
    if self.tool_executor and job_number:
        self.tool_executor._job_get_status({"job_number": job_number})
        self.logger.info(f"Enriched job index for {job_number} after layout creation")
except Exception as e:
    self.logger.error(f"Failed to enrich job index for {job_number}: {e}")
```

---

## Step 6: Verify No Existing Functionality is Broken

After implementing, verify these still work:

### 6.1 QBO Time Posting
- The `_handle_field_data_uploaded` handler posts time to QBO
- This must still work after your changes
- Check that `_post_time_to_qbo` is still being called

### 6.2 Email Linking
- Check if there's email linking functionality in the handlers
- Ensure it's preserved

### 6.3 Existing Enrichment Calls
- The handlers may have existing `enrich_job_index` calls for other sections (emails, time_entries)
- These should remain - only ADD the new `_job_get_status` call

### 6.4 Return Values
- Check what the handlers return
- Ensure return logic is unchanged

---

## Step 7: Test Considerations

Describe how to verify the fix works:

1. **Simulate a field upload event:**
   - Check that job index now contains `field_summary`
   - Verify all `field_status.json` data is captured

2. **Simulate a layout upload event:**
   - Check that job index now contains `job_info` data
   - Verify address, description, operator are captured

3. **Verify existing functionality:**
   - QBO time entries still posted
   - No errors in notification_watcher logs

---

## Step 8: Verify Data Preservation

**CRITICAL STEP** - Before committing, verify that the fix preserves ALL the rich field data.

### 8.1 Compare Claude's output to Index data

For a job with recent field uploads (like 26-001):

1. Call `_job_get_status({"job_number": "26-001"})` and capture the full output
2. Look at what gets written to the job_index for that job
3. Compare field by field:

| Field | In Claude's Response | In Job Index |
|-------|---------------------|--------------|
| `field_summary.total_visits` | ? | ? |
| `field_summary.total_field_hours` | ? | ? |
| `field_summary.operators` | ? | ? |
| `field_summary.field_complete` | ? | ? |
| `field_summary.csv_extracted` | ? | ? |
| Each `layout_summary` | ? | ? |
| Each `field_status` detail | ? | ? |

4. They should match. If anything is missing from the index, investigate why.

### 8.2 Verify no field truncation or format changes

Check that:
- `csv_extracted.evidence_found` arrays are complete (not truncated)
- `construction_tasks_completed` lists are complete
- `notes` text is preserved in full
- `time_spent` structure matches exactly
- All timestamps are preserved

### 8.3 Verify both event types

Test both:
- `layout_job_created` - check `job_info` fields preserved
- `field_data_uploaded` - check `field_status` and summaries preserved

---

## Step 9: Commit with Clear Message

When committing, use a clear message explaining what was fixed:

```
Fix: Enable automatic job index enrichment on Data Sync events

Previously, notification_watcher attempted to enrich the job index when
field data or layouts were uploaded, but the data was silently dropped
because enrich_job_index only handled 'jobs' and 'field_summary' keys.

This fix adds a call to _job_get_status after each event, which:
- Reads live from the Data Sync folder
- Calculates layout_summary and field_summary
- Triggers the full enrichment pipeline

The job index now stays automatically current with field work data.

Existing functionality (QBO time posting, etc.) is preserved.
```

---

## Important Notes

1. **Don't modify `enrich_job_index`** - The fix is to call `_job_get_status` instead, which uses the correct enrichment path

2. **Don't modify `_job_get_status`** - It already works correctly; we're just triggering it from notification_watcher

3. **Preserve all existing code in the handlers** - Only ADD the new enrichment trigger at the end

4. **The structural mismatch is a separate issue** - `_enrich_job_from_data_sync` saves a different structure than `nightly_refresh`. This can be addressed later; the current fix will work despite this.

5. **Error handling is critical** - Wrap the new code in try/except so enrichment failures don't break the notification pipeline

---

## Questions to Answer in Your Response

After completing the verification and fix, please answer:

1. **What field data did you examine?** Which job(s) did you look at, and what was in the `field_status.json` files?

2. **Did you find any differences between the analysis and current code?** If so, what were they?

3. **Was the fix already implemented in the current code?** Does notification_watcher already call `_job_get_status`?

4. **What exactly did you change?** Show the specific code changes.

5. **Data preservation verification:**
   - Did you compare the job_index data to what `_job_get_status` returns?
   - Are ALL fields preserved (no missing data)?
   - Are the data formats identical (no structural mismatches)?

6. **Are there any concerns about the implementation?** Any edge cases or potential issues?

7. **What testing would you recommend?** How can we verify this works correctly in production?

---

## Summary

The goal is simple: **When Data Sync events occur, the job index should be enriched with the SAME complete data that Claude gets when it calls `job_get_status`.**

The carefully designed `field_status.json` structure captures everything needed for field work tracking. The fix must ensure this data flows automatically into the job index, preserving every field, every value, every structure - exactly as designed.
