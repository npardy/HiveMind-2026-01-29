# HiveMind Fixes - January 27, 2026

## Issues Fixed

### 1. Self-Reply Loop
**Problem:** When emailing yourself (pardysurveys@outlook.com → pardysurveys@outlook.com), Claude would respond to its own sent emails that appeared back in the inbox.

**Root Cause:** The sent message tracking used Graph API `id`, which changes when an email moves between folders (Sent Items → Inbox). The same email has different IDs in each folder.

**Fix:** Now track `internetMessageId` (RFC822 Message-ID) which is globally unique and consistent across all folders. Format: `<MW4P221MB1071...@NAMP221.PROD.OUTLOOK.COM>`

**Files Changed:**
- `email_service.py` - Added `internetMessageId` to `$select` parameter in:
  - `get_emails_by_ids()`
  - `get_inbox_needing_response()`
- `orchestrator.py` - Added debug logging for self-reply detection

### 2. Phantom Folder Creation
**Problem:** When saving attachments, Claude would construct folder paths from memory, sometimes misremembering them (e.g., dropping ", CBS" from the folder name), creating duplicate/phantom folders.

**Root Cause:** `email_save_attachment` tool required Claude to specify the full `save_path`, relying on Claude to remember/construct it correctly.

**Fix:** Added `job_number` parameter to `email_save_attachment`. When provided, the tool looks up the correct folder path from the job spine - no path construction by Claude needed.

**Files Changed:**
- `tool_executor.py` - `_email_save_attachment()` now supports `job_number` parameter
- `tools_definition.py` - Updated schema to make `save_path` optional, added `job_number` and `subfolder` parameters
- `hive_mind_prompt.py` - Added workflow guidance: identify job → link email → save with job_number

**New Workflow:**
```
1. Claude identifies which job the email relates to
2. Claude links email to job using job_link_email
3. Claude saves attachment: email_save_attachment(job_number="26-010", ...)
4. Tool looks up folder from spine → correct path guaranteed
```

## Data Cleanup
- Removed test jobs from job_index.json: 26-011, 26-012, 26-013, 2026-01-26_Johnny_Appleseed

## Key Insight
The job spine is the authoritative source for folder paths. Claude should never construct paths manually - always look them up from the spine to prevent hallucination.
