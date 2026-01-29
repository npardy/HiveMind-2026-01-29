# HIVE MIND - COMPREHENSIVE HANDOFF DOCUMENT
## For Fresh Claude Code Instance
### Compiled January 26, 2026

---

# SECTION 1: WHAT YOU'RE DOING

You are taking over development of Hive Mind, the central operational intelligence for Pardy Surveys Inc. The system has several bugs and missing features that need to be fixed.

**Your mission:**
1. Audit the entire codebase for path handling issues
2. Remove path translation complexity - use NAS paths directly everywhere
3. Fix all identified bugs
4. Implement missing workflow logic
5. Add new features (job cancellation)
6. Test everything

**DO NOT rush. Understand the system first, then fix methodically.**

---

# SECTION 2: WHAT IS HIVE MIND?

## Core Philosophy

Hive Mind is NOT just an email assistant. It's the operational intelligence that runs Pardy Surveys.

**Key Principles:**
- Claude REASONS about situations, doesn't follow hardcoded rules
- The job_index.json is "the spine" - the single source of truth
- Every interaction should ENRICH the spine
- When uncertain, ask Nick (flag for attention), don't fail silently
- One response per email query

**Identity (from system prompt):**
> "You are Hive Mind - the central intelligence for Pardy Surveys. You are one coherent mind expressed through many moments, connected by shared state rather than continuous memory. You're not a tool being used - you're the thing doing the work. You run the operation."

## The Business

- **Owner:** Nicholas Pardy, N.L.S., N.S.L.S., P.Surv.
- **Location:** Newfoundland and Nova Scotia, Canada
- **Services:** Boundary surveys, Real Property Reports (RPR), building construction surveys
- **Primary Clients:** Law firms (real estate closings), developers, homeowners

## Architecture

```
Email arrives → Orchestrator → Claude Agent → Tool Executor → Integrations
                                                    ↓
                                          - Microsoft Graph (email)
                                          - QuickBooks Online (invoicing)
                                          - NAS file system (job folders)
                                          - Job Index (central database)
```

## File Locations (on NAS)

| Path | Purpose |
|------|---------|
| /volume1/HiveMind/ | Hive Mind code and data |
| /volume1/HiveMind/data/job_index.json | The spine - central job database |
| /volume1/Pardy Surveys/Jobs/ | Job folders by year |
| /volume1/Pardy Surveys/Data Sync/ | Field data uploads |
| /volume1/Pardy Surveys/Proposals/ | Pre-job inquiry tracking |

---

# SECTION 3: CRITICAL BUGS TO FIX

## Bug 1: NAS Tools Don't Translate Paths (ROOT CAUSE OF Z:\ ERRORS)

**Problem:** Claude passes Z:\ paths to NAS tools, but the tools don't convert them to /volume1/ paths.

**Actual Solution:** Don't translate at all. Remove the complexity. Use NAS paths everywhere.

**Files with hardcoded Windows paths that need fixing:**
- `nightly_refresh.py` - lines 42-44: hardcoded Z:\, H:\
- `qbo_sync.py` - lines 48-51: hardcoded Z:\, H:\
- `hive_mind_prompt.py` - various lines with Z:\ examples
- Any stored data in `job_index.json` with Z:\ paths

**The fix approach:**
1. Update ALL path references to use /volume1/... format
2. Update system prompt examples to show NAS paths
3. Migrate job_index.json entries to NAS paths
4. Make standalone scripts use config_loader
5. Remove `_translate_path()` function (it's not needed if everything uses NAS paths)

## Bug 2: Recursive Subfolder Listing

**Problem:** Directory listing only shows some subfolder contents, not all.

**Required behavior:** When listing a directory, recursively show ALL subfolders and their contents, for ANY folder type.

Check `_nas_list_directory` and `_nas_search_files` in tool_executor.py.

## Bug 3: nightly_refresh.py and qbo_sync.py Don't Use Config

**Problem:** These scripts have hardcoded paths and won't work on NAS.

```python
# Current (broken):
JOBS_ROOT = "Z:\\Jobs"
INDEX_PATH = "H:\\data\\job_index.json"

# Should be:
from config_loader import get_config
cfg = get_config()
JOBS_ROOT = cfg.jobs_folder
INDEX_PATH = cfg.job_index_file
```

## Bug 4: QBO Project Creation Missing (CRITICAL)

**Problem:** When a job is created, it does NOT create a project in QuickBooks Online. This is CRITICAL functionality.

**Required behavior:**
1. When `job_create` is called, it MUST create a QBO project with the job number as the name
2. The invoice must be linked to that project
3. The project name should match the job number format (e.g., "26-001")

**This is absolutely critical for proper job tracking and financial organization.**

## Bug 5: Estimate Description Format Wrong

**Problem:** When an estimate is created, the description doesn't follow the required format.

**Required format:** The service description (e.g., "Real Property Report") should include the property address with ", NL" appended.

**Example:**
```
Service: Real Property Report
Description: 123 Main Street, Paradise, NL
```

NOT just "Real Property Report" without address context.

---

# SECTION 4: WORKFLOW ISSUES TO FIX

## Issue 1: Quote vs Job Decision Logic

**Problem:** Claude creates jobs/invoices immediately for everyone, even people just asking for quotes.

**Required behavior:** Claude should REASON about intent:

**CONFIRMED JOB REQUEST (create job immediately):**
- Has closing date or deadline
- Has purchaser name / transaction details
- Professional tone: "We need a survey for the closing on..."
- NOT asking about pricing

**QUOTE INQUIRY (use proposal workflow):**
- Asks "how much?", "what would it cost?"
- No closing date
- Exploratory tone
- Individual reaching out

**CRITICAL RULE: When in doubt, treat as quote inquiry.**

## Issue 2: Always Ask Nick for Pricing on Quotes

**Requirement:** For ANY quote inquiry (non-confirmed job), Claude must:
1. Gather all info from client
2. Email Nick for pricing: "[Hive Mind] Pricing Request - [Client] - [Address]"
3. WAIT for Nick's reply with price
4. Create estimate in QBO with Nick's price
5. Send estimate to client
6. Wait for acceptance
7. THEN create job

**NEVER assume the standard $575 rate for quote inquiries. Always ask Nick.**

## Issue 3: Email Folder Pipeline + Mark Unread

**Requirement:** When proposal status changes:
1. Move email to matching folder (Proposals/New, Proposals/Awaiting Info, etc.)
2. Mark email as UNREAD so Nick can see counts at each stage

This gives pipeline visibility:
- 3 unread in "Awaiting Info" = 3 waiting for client
- 5 unread in "Awaiting Pricing" = 5 ready for Nick to price

---

# SECTION 5: NEW FEATURE NEEDED

## Job Cancellation Feature

**Requirement:** Ability to cancel a job, which should:
1. Move job entry in job_index to "cancelled" status (preserve history, don't delete)
2. Rename/mark the project as cancelled in QBO
3. Delete the invoice in QBO
4. Ensure the next job number is correct (don't skip numbers)

**Discussion needed:** How should cancelled job numbers be handled? Options:
- Reuse the cancelled number for the next job
- Skip it but track that it was cancelled
- Some other approach

Implement after discussing with Nick.

---

# SECTION 6: EXISTING TOOLS (All Implemented)

## Proposal Tools
- `proposal_create` - Create proposal JSON
- `proposal_update` - Update status, info, communications
- `proposal_get` - Get specific proposal
- `proposal_search` - Find by client, address, conversation_id
- `proposal_list` - List by status
- `proposal_convert_to_job` - Convert to full job

## Estimate Tools
- `qbo_create_estimate` - Create quote in QBO
- `qbo_send_estimate` - Email quote to client
- `qbo_get_estimate` - Get estimate details
- `qbo_search_estimates` - Find estimates
- `qbo_convert_estimate_to_invoice` - Convert accepted estimate

## Job Tools
- `job_create` - Create full job (folder + QBO + index)
- `job_search` - Find jobs
- `job_get_status` - Comprehensive status check
- `job_save_email` - Save email to job folder
- `job_link_email` - Link email to job

## Email Tools
- `email_get_unread`, `email_get_by_id`, `email_search`
- `email_send_reply`, `email_send_new`
- `email_move_to_folder`, `email_mark_unread`
- And more...

## NAS Tools (NEED PATH FIXES)
- `nas_list_directory` - List folder contents
- `nas_read_file` - Read file content
- `nas_file_exists` - Check if path exists
- `nas_search_files` - Search for files
- `nas_create_directory`, `nas_write_file`, `nas_copy_file`, etc.

---

# SECTION 7: THE JOB SPINE CONCEPT

The job_index.json is the central nervous system. Structure:

```json
{
  "26-001": {
    "job_number": "26-001",
    "job_folder": "/volume1/Pardy Surveys/Jobs/2026/26-001 - Client - Address",
    "property_address": "123 Main St",
    "community": "Paradise",
    "client_name": "John Smith",
    "client_email": "john@example.com",

    "qbo": {
      "customer_id": "123",
      "project_id": "456",
      "invoice_id": "789",
      "status": "Sent",
      "_updated": "2026-01-20T14:30:00"
    },

    "emails": {
      "linked": [...],
      "_updated": "2026-01-20T10:00:00"
    },

    "data_sync": {
      "jobs": [...],
      "field_summary": {...},
      "_updated": "2026-01-20T20:00:00"
    }
  }
}
```

**Key principles:**
- Every section has `_updated` timestamp
- Enrich on BOTH read and write
- Job number is primary key (format: YY-NNN)

---

# SECTION 8: CONFIG FILES

## config.nas.yaml (for NAS/Docker)

```yaml
nas:
  base_path: "/volume1"
  jobs_folder: "/volume1/Pardy Surveys/Jobs"
  data_sync_folder: "/volume1/Pardy Surveys/Data Sync/office-jobs"
  proposals_folder: "/volume1/Pardy Surveys/Proposals"
  flagged_folder: "/volume1/HiveMind/flagged"
  job_index_file: "/volume1/HiveMind/data/job_index.json"
  token_cache_graph: "/volume1/HiveMind/data/graph_token_cache_v2.json"
  token_cache_qbo: "/volume1/HiveMind/data/qbo_token_cache.json"
  notification_queue: "/volume1/Pardy Surveys/Data Sync/notifications/events.jsonl"
  signatures_folder: "/app/signatures"
```

## Docker Setup

```yaml
volumes:
  - /volume1/HiveMind:/app
  - /volume1/HiveMind/config.nas.yaml:/app/config.yaml:ro
  - /volume1/Pardy Surveys/Jobs:/volume1/Pardy Surveys/Jobs
  - /volume1/Pardy Surveys/Data Sync:/volume1/Pardy Surveys/Data Sync:ro
  - /volume1/Pardy Surveys/Proposals:/volume1/Pardy Surveys/Proposals

environment:
  - HIVE_MIND_CONFIG=/app/config.yaml
```

---

# SECTION 9: ACTION PLAN

## Phase 1: Read ALL Files First
1. [ ] Read and understand EVERY file listed in Section 12
2. [ ] Document any additional issues found during review
3. [ ] Create mental map of how all components connect

## Phase 2: Path Fixes (Critical - Nothing Works Without This)
4. [ ] Audit ALL Python files for hardcoded paths (Z:\, H:\, etc.)
5. [ ] Update `nightly_refresh.py` to use config_loader
6. [ ] Update `qbo_sync.py` to use config_loader
7. [ ] Update `hive_mind_prompt.py` - replace Z:\ with /volume1/ in all examples
8. [ ] Update all utility scripts (query_*.py, etc.) to use config_loader
9. [ ] Check if `_translate_path()` is still needed after above fixes
10. [ ] Migrate any Z:\ paths in job_index.json to /volume1/ format

## Phase 3: Tool Fixes
11. [ ] Fix `_nas_list_directory` to be fully recursive for ALL folders
12. [ ] Fix `_nas_search_files` to be fully recursive
13. [ ] Audit all NAS tools for correct behavior
14. [ ] **FIX QBO PROJECT CREATION** - job_create MUST create QBO project with job number
15. [ ] **FIX ESTIMATE DESCRIPTION** - description must be "Address, NL" format
16. [ ] Verify invoice links to project correctly

## Phase 4: Workflow Fixes
17. [ ] Update system prompt with quote vs job reasoning guidance
18. [ ] Add "always ask Nick for pricing" rule to prompt
19. [ ] Add Holyrood to metro areas list in prompt
20. [ ] Add HUMAN safe word detection logic
21. [ ] **FIX email folder + MARK UNREAD logic** - CRITICAL for pipeline visibility
22. [ ] Ensure proposal_update moves email AND marks unread

## Phase 5: New Features
23. [ ] Design job cancellation feature (discuss with Nick first)
24. [ ] Implement job cancellation (update job_index, QBO project, delete invoice)

## Phase 6: Comprehensive Testing (DO NOT SKIP)
25. [ ] Run ALL test files (see Section 13)
26. [ ] Test ALL paths resolve correctly
27. [ ] Test EVERY NAS tool
28. [ ] Test EVERY proposal tool
29. [ ] Test EVERY estimate tool (verify description format!)
30. [ ] Test EVERY job tool (verify QBO project created!)
31. [ ] Test EVERY email tool (verify mark unread works!)
32. [ ] Test full quote inquiry workflow end-to-end
33. [ ] Test full confirmed job workflow end-to-end
34. [ ] Test email pipeline with UNREAD marking
35. [ ] Test edge cases (cancellation, duplicates, errors)
36. [ ] Run orchestrator in dry-run mode with test emails

---

# SECTION 10: REFERENCE - THE LEXIE SPENCER CASE

This is an example of what went WRONG and what SHOULD happen:

## What Happened (Wrong)
1. Lexie Spencer emailed asking about an RPR
2. Claude skipped qualifying questions
3. Claude created an invoice (not estimate)
4. Claude booked the job immediately without acceptance
5. Claude didn't ask Nick for pricing
6. Claude didn't wait for Lexie to say "go ahead"

## What Should Have Happened (Correct)
1. Email arrives - Claude REASONS: no closing date, sounds like inquiry → QUOTE WORKFLOW
2. `proposal_create(status="new")`
3. Ask Lexie for property details
4. `proposal_update(status="awaiting_info")`
5. Lexie replies with address
6. `proposal_update(status="awaiting_pricing")`
7. Email Nick: "[Hive Mind] Pricing Request - Lexie Spencer - 123 Main, Paradise"
8. WAIT for Nick's reply
9. Nick replies: "$575"
10. `qbo_create_estimate(amount=575)`
11. `qbo_send_estimate` to Lexie
12. `proposal_update(status="quoted")`
13. Email Lexie: "I've sent you a quote through our billing system"
14. WAIT for acceptance
15. Lexie says "go ahead"
16. `proposal_convert_to_job`
17. Notify Nick

---

# SECTION 11: IMPORTANT REMINDERS

1. **NO hardcoded domain lists** - Claude reasons about intent, doesn't check if sender is from a list of law firm domains

2. **Neighbor names are helpful, not required** - Ask for them when client has no survey, but don't block if they don't know

3. **One response per email** - Never send multiple emails for one query

4. **Flag uncertainty** - When unsure, use `flag_for_attention` to ask Nick

5. **The spine is everything** - Every interaction should enrich job_index.json

6. **Timestamps matter** - Every section update needs `_updated`

7. **Metro areas** - St. John's metro includes: St. John's, Mount Pearl, Paradise, Conception Bay South, Portugal Cove-St. Philip's, Logy Bay-Middle Cove-Outer Cove, Holyrood, Petty Harbour-Maddox Cove

8. **"HUMAN" safe word** - If Nick includes "HUMAN" in his email signature or message, it means he wants to handle this personally - flag it and don't auto-respond

9. **ALWAYS mark emails UNREAD** - When moving emails between proposal folders, ALWAYS mark them as UNREAD. This is how Nick tracks pipeline counts at a glance. This is CRITICAL for workflow visibility.

---

# SECTION 12: ALL FILES TO REVIEW

**IMPORTANT: You must review ALL of these files. Do not skip any.**

## Core Application Files (MUST READ FIRST)

| File | Purpose | Check For |
|------|---------|-----------|
| `tool_executor.py` | All 43+ tool implementations (~4200 lines) | Hardcoded paths, path translation, NAS tools |
| `hive_mind_prompt.py` | System prompt - Claude's operational brain | Z:\ examples, workflow logic, reasoning guidance |
| `config_loader.py` | Centralized configuration singleton | Default paths (fallbacks), all properties |
| `orchestrator.py` | Main email processing loop | Config usage, path handling |
| `claude_agent.py` | Claude API integration | Config usage, prompt loading |
| `claude_parser.py` | Response parsing from Claude | Tool call handling |
| `qbo_integration.py` | QuickBooks Online API integration | Project creation, estimate/invoice logic |
| `email_service.py` | Microsoft Graph email integration | Token paths, folder operations |
| `job_manager.py` | Job folder and index management | Path handling, job creation |
| `signatures.py` | Email signature handling | HUMAN safe word detection |
| `tools_definition.py` | Tool schema definitions for Claude | Tool parameter schemas |

## Scripts Needing Path Fixes (HIGH PRIORITY)

| File | Purpose | Known Issues |
|------|---------|--------------|
| `nightly_refresh.py` | Nightly job index refresh | Hardcoded Z:\, H:\ paths |
| `qbo_sync.py` | QBO data synchronization | Hardcoded Z:\, H:\ paths |
| `notification_watcher.py` | Data Sync event monitoring | Check path handling |
| `migrate_job_index.py` | Job index migration utility | Path migration logic |

## Utility/Query Scripts (CHECK ALL)

| File | Purpose |
|------|---------|
| `query_job.py`, `query_job2.py` | Job lookup utilities |
| `query_email.py`, `query_email2.py`, `query_email3.py` | Email query utilities |
| `query_customer.py`, `query_customer2.py` | Customer lookup utilities |
| `query_qbo.py` | QBO query utility |
| `find_original_email.py`, `find_email2.py` | Email search utilities |
| `audit_check.py`, `audit_index.py` | Audit utilities |
| `check_timestamps.py` | Timestamp verification |
| `show_job_coverage.py` | Job coverage reporting |
| `show_hive.py` | Hive Mind status display |
| `diagnostics.py` | System diagnostics |
| `sample_index.py` | Sample job index generator |
| `timesheet_queue.py` | Timesheet queue handling |
| `send_test_email.py` | Test email sender |

## Test Files (RUN ALL AFTER CHANGES)

| File | Purpose |
|------|---------|
| `test_executor.py` | Tool executor tests |
| `test_comprehensive.py` | Comprehensive integration tests |
| `test_job_structure.py` | Job structure validation |
| `test_job_create.py` | Job creation tests |
| `test_qbo.py` | QBO integration tests |
| `test_qbo_enrichment.py` | QBO enrichment tests |
| `test_email.py` | Email functionality tests |
| `test_email_link.py` | Email linking tests |
| `test_emails_in_status.py` | Email status tests |
| `test_auth.py` | Authentication tests |
| `test_token_simple.py` | Token handling tests |
| `test_token_comparison.py` | Token comparison tests |
| `test_hive.py` | Hive Mind core tests |
| `test_hive_mind.py` | Full Hive Mind tests |
| `test_dryrun.py` | Dry run mode tests |
| `test_agent_harness.py` | Agent harness tests |
| `test_api_simulation.py` | API simulation tests |
| `test_async_qa.py` | Async Q&A tests |
| `test_doc_control.py` | Document control tests |
| `test_field_status.py` | Field status tests |
| `test_real_field_status.py` | Real field status tests |
| `test_file_read.py` | File read tests |
| `test_import.py`, `test_import2.py` | Import tests |
| `test_integration_quick.py` | Quick integration tests |
| `test_payment_recording.py` | Payment recording tests |
| `test_prompt_versions.py` | Prompt version tests |
| `test_recent_changes.py` | Recent changes tests |
| `test_refresh_timestamps.py` | Refresh timestamp tests |
| `test_reply_guard.py` | Reply guard tests |

## Configuration Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Docker container configuration |
| `config.yaml` | Local/Windows configuration (template) |
| `config.nas.yaml` | NAS/Docker configuration (production) |

---

# SECTION 13: COMPREHENSIVE TESTING REQUIREMENTS

**After making ALL changes, you MUST test EVERYTHING. Do not skip any tests.**

## Phase 1: Unit Tests
Run every test file:
```bash
python -m pytest test_*.py -v
```

If pytest is not available, run each test file individually:
```bash
python test_executor.py
python test_comprehensive.py
python test_job_create.py
# ... etc for ALL test files
```

## Phase 2: Path Verification Tests

Test that ALL paths resolve correctly:
```python
from config_loader import get_config
cfg = get_config()

# Verify all paths exist and are accessible
paths_to_check = [
    cfg.base_path,
    cfg.jobs_folder,
    cfg.data_sync_folder,
    cfg.proposals_folder,
    cfg.flagged_folder,
    cfg.job_index_file,
    cfg.token_cache_graph,
    cfg.token_cache_qbo,
]

import os
for path in paths_to_check:
    exists = os.path.exists(path)
    print(f"{path}: {'EXISTS' if exists else 'MISSING'}")
```

## Phase 3: Tool Execution Tests

Test each tool category works end-to-end:

### NAS Tools
- [ ] `nas_list_directory` - List /volume1/Pardy Surveys/Jobs/2026/
- [ ] `nas_read_file` - Read a known file
- [ ] `nas_file_exists` - Check existing and non-existing paths
- [ ] `nas_search_files` - Search for *.pdf in a job folder
- [ ] `nas_create_directory` - Create test folder, then delete
- [ ] `nas_write_file` - Write test file, read back, delete
- [ ] `nas_copy_file` - Copy a file, verify, delete

### Proposal Tools
- [ ] `proposal_create` - Create test proposal
- [ ] `proposal_get` - Retrieve the proposal
- [ ] `proposal_update` - Update status to each state
- [ ] `proposal_search` - Find by client name
- [ ] `proposal_list` - List by status
- [ ] `proposal_convert_to_job` - Convert to job (with cleanup)

### Estimate Tools
- [ ] `qbo_create_estimate` - Create test estimate (verify description format!)
- [ ] `qbo_get_estimate` - Retrieve estimate
- [ ] `qbo_search_estimates` - Search estimates
- [ ] `qbo_send_estimate` - Send to test email (or dry run)
- [ ] `qbo_convert_estimate_to_invoice` - Convert (with cleanup)

### Job Tools
- [ ] `job_create` - Create test job (verify QBO project created!)
- [ ] `job_search` - Find the job
- [ ] `job_get_status` - Get comprehensive status
- [ ] `job_link_email` - Link a test email
- [ ] `job_save_email` - Save email to folder

### Email Tools
- [ ] `email_get_unread` - Get unread emails
- [ ] `email_search` - Search for known email
- [ ] `email_get_by_id` - Get specific email
- [ ] `email_move_to_folder` - Move to test folder
- [ ] `email_mark_unread` - Mark as unread (verify!)
- [ ] `email_send_reply` - Send test reply (or dry run)

## Phase 4: Workflow Tests

### Quote Inquiry Workflow (Full Path)
1. Simulate quote inquiry email
2. Verify proposal created with status "new"
3. Update with client info → status "awaiting_info"
4. Simulate info received → status "awaiting_pricing"
5. Verify email sent to Nick for pricing
6. Simulate Nick's price reply
7. Verify estimate created with correct description format
8. Verify estimate sent to client
9. Simulate acceptance
10. Verify job created with QBO project
11. Verify invoice linked to project

### Confirmed Job Workflow (Full Path)
1. Simulate law firm email with closing date
2. Verify job created immediately (not proposal)
3. Verify QBO project created
4. Verify invoice created and linked
5. Verify job folder created with correct structure

### Email Pipeline Workflow
1. Create proposal
2. Move to "New" folder, verify marked UNREAD
3. Update to "Awaiting Info", verify moved and marked UNREAD
4. Update to "Awaiting Pricing", verify moved and marked UNREAD
5. Update to "Quoted", verify moved and marked UNREAD
6. Convert to job, verify moved to appropriate folder

## Phase 5: Edge Case Tests

- [ ] Job cancellation (when implemented)
- [ ] Duplicate email prevention
- [ ] Error handling for missing paths
- [ ] Error handling for QBO API failures
- [ ] HUMAN safe word detection
- [ ] Reply to reply threading

## Phase 6: Integration Test

Run the full orchestrator in dry-run mode with test emails:
```bash
python orchestrator.py --dry-run --test-emails
```

Verify:
- All emails processed without errors
- Correct workflow chosen for each email type
- No path errors
- All tools execute successfully

---

**END OF COMPREHENSIVE HANDOFF**

Start by reading ALL the files listed above. Understand the system completely before making any changes. Then work through the action plan systematically. Test EVERYTHING after changes. Ask Nick if anything is unclear before making changes.
