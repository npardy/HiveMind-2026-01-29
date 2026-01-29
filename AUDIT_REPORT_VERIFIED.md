# HiveMind Audit Report - VERIFIED
## January 29, 2026

This report verifies each issue against the current codebase. Every Python file has been read completely.

---

## FILES READ COMPLETELY

| File | Lines | Purpose |
|------|-------|---------|
| tool_executor.py | 5,412 | Core tool implementations |
| qbo_sync.py | 837 | Bidirectional QBO sync |
| qbo_integration.py | 1,674 | QBO API integration |
| email_service.py | 1,562 | Email operations via MS Graph |
| notification_watcher.py | 758 | Real-time event processing |
| job_manager.py | 220 | Job utilities |
| config_loader.py | 160 | Configuration management |
| orchestrator.py | 471 | Email processing orchestration |
| claude_agent.py | 745 | Main agent implementation |
| tools_definition.py | 1,675 | Tool definitions for Claude |
| hive_mind_prompt.py | 1,049 | System prompt |
| timesheet_queue.py | 320 | Timesheet approval workflow |
| nightly_refresh.py | 591 | Nightly job index refresh |
| claude_parser.py | 285 | Email classification |
| signatures.py | 88 | Email signatures |
| diagnostics.py | 205 | API call logging |
| migrate_job_index.py | 113 | Index migration |
| audit_index.py | 80 | Index structure audit |
| audit_check.py | 53 | Tool matching audit |

---

## ISSUE STATUS SUMMARY

| # | Issue | Status | Confidence |
|---|-------|--------|------------|
| 1 | Duplicate Email Problem | **FIXED** | HIGH |
| 2 | Work Products vs Document Control | **NEEDS TESTING** | MEDIUM |
| 3 | Invoice Line Item Checking | **NEEDS TESTING** | MEDIUM |
| 4 | Email Threading (in_reply_to) | **FIXED** | HIGH |
| 5 | Employee Nickname Confusion | **FIXED** | HIGH |
| 6 | Job Number Override | **STILL BROKEN** | HIGH |
| 7 | Metro vs Non-Metro Pricing | **NEEDS TESTING** | MEDIUM |
| 8 | Closing Date Extraction | **NEEDS TESTING** | MEDIUM |
| 9 | Time Entry Auto-Posting | **FIXED** | HIGH |
| 10 | Proposal Status Tracking | **NEEDS TESTING** | LOW |
| 11 | Client vs Purchaser Confusion | **NEEDS TESTING** | MEDIUM |
| 12 | CC/Reply-All Functionality | **STILL BROKEN** | HIGH |
| 13 | Large File Handling | **NEEDS TESTING** | LOW |
| 14 | QBO Customer Matching | **NEEDS TESTING** | MEDIUM |
| 15 | Job Folder Path Issues | **FIXED** | HIGH |

**Summary: 5 FIXED, 2 STILL BROKEN, 8 NEEDS TESTING**

---

## DETAILED ISSUE VERIFICATION

### ISSUE 1: Duplicate Email Problem
**STATUS: FIXED**

**Evidence in Code:**
- `tool_executor.py` lines 2280-2291: Duplicate email guards implemented
  ```python
  # Duplicate guard: Check if we've already sent to this message
  if message_id in self.replied_message_ids:
      return {"success": False, "error": f"Already replied to message {message_id}"}
  ```
- `tool_executor.py` maintains `replied_message_ids` set AND `_sent_emails` list
- `_email_send_reply()` checks both guards before sending

**Additional safeguard in prompt:**
- `hive_mind_prompt.py` contains "NEVER DUPLICATE EMAILS" section

**Verification:** The code-level duplicate prevention exists and is comprehensive. Both session-level tracking (`replied_message_ids`) and persistent tracking (`_sent_emails`) are implemented.

---

### ISSUE 2: Work Products vs Document Control Confusion
**STATUS: NEEDS TESTING**

**Evidence in Code:**
- `hive_mind_prompt.py` lines ~650-680 contains folder structure guidance:
  - "Document Control" = for controlled documents (stamped PDFs with revisions)
  - "Work Products" = for working files (drafts, calculations, CAD files)
- NO code-level enforcement preventing saves to wrong folder
- `nas_write_file` in tool_executor.py accepts any path without validation

**Why NEEDS TESTING:**
- Prompt guidance exists but Claude may still confuse the folders
- No programmatic validation of folder choice
- Need to verify Claude's behavior in practice

---

### ISSUE 3: Invoice Line Item Checking
**STATUS: NEEDS TESTING**

**Evidence in Code:**
- `hive_mind_prompt.py` OPERATIONAL_KNOWLEDGE section (~line 800-850):
  ```
  INVOICE RULES:
  - ALWAYS check if line item already exists before adding
  - Use qbo_get_invoice first to see current line items
  - NEVER add duplicate line items
  ```
- `qbo_integration.py` `get_invoice()` returns full line item details
- NO code-level enforcement - relies on Claude following instructions

**Why NEEDS TESTING:**
- Prompt contains clear instructions
- Need to verify Claude actually checks before adding

---

### ISSUE 4: Email Threading (in_reply_to)
**STATUS: FIXED**

**Evidence in Code:**
- `tools_definition.py` lines ~1100-1130: `email_send_new` tool definition includes:
  ```python
  {
      "name": "in_reply_to",
      "type": "string",
      "description": "Message ID to reply to (for threading). Use this to ensure the email appears in the same thread.",
      "required": False
  }
  ```
- `tool_executor.py` `_email_send_new()` passes `in_reply_to` to email service
- `email_service.py` `send_message()` sets proper threading headers

**Verification:** Full email threading support exists. New emails can be threaded using `in_reply_to` parameter.

---

### ISSUE 5: Employee Nickname Confusion
**STATUS: FIXED**

**Evidence in Code:**
- `qbo_sync.py` lines 45-52:
  ```python
  EMPLOYEE_NICKNAMES = {
      "joe": "joseph",
      "joey": "joseph",
      "nick": "nicholas",
      "al": "allan",
      # ...
  }
  ```
- `timesheet_queue.py` lines 50-56:
  ```python
  self.operator_map = {
      "allan": "Allan Regular",
      "nick": "Nicholas Pardy",
      "joe": "Joseph English",
      "joey": "Joseph English",
  }
  ```
- Both files normalize nicknames to full names

**Verification:** Nickname mapping exists in multiple locations covering the main aliases.

---

### ISSUE 6: Job Number Override
**STATUS: STILL BROKEN**

**Evidence in Code:**
- `tools_definition.py` `job_create` tool has NO `job_number_override` parameter
- `tool_executor.py` `_job_create()` generates numbers automatically:
  ```python
  def _job_create(self, ...):
      # Get next job number from QBO
      next_num = self._qbo_get_next_job_number()
      job_number = f"{year_prefix}-{next_num:03d}"
  ```
- No way to specify a custom job number

**Impact:** Cannot create jobs with specific numbers (e.g., for legacy imports or corrections).

**Recommendation:** Add `job_number_override` parameter to `job_create` tool.

---

### ISSUE 7: Metro vs Non-Metro Pricing
**STATUS: NEEDS TESTING**

**Evidence in Code:**
- `job_manager.py` lines 39-48: Complete METRO_AREAS list:
  ```python
  METRO_AREAS = [
      "st. john's", "st johns", "saint john's",
      "mount pearl", "mt. pearl",
      "paradise",
      "conception bay south", "cbs",
      "portugal cove-st. philip's", "portugal cove", "pcsp",
      "logy bay-middle cove-outer cove", "logy bay",
      "holyrood",
      "petty harbour-maddox cove", "petty harbour", "maddox cove",
  ]
  ```
- `job_manager.py` `is_metro_area()` function for checking
- `claude_parser.py` extracts `is_metro_area` field during classification

**Why NEEDS TESTING:**
- Code infrastructure exists
- Need to verify Claude uses standard pricing for metro, requests quotes for non-metro

---

### ISSUE 8: Closing Date Extraction
**STATUS: NEEDS TESTING**

**Evidence in Code:**
- `claude_parser.py` lines 96-98 (in the classification prompt):
  ```
  CRITICAL RULES:
  1. DUE DATE: Search subject lines AND body for "closing [date]". Convert to YYYY-MM-DD.
  ```
- `hive_mind_prompt.py` contains chain-reading guidance:
  ```
  - Email chains contain quoted replies below separator lines (______ or "From:")
  - Look at ENTIRE body including quoted portions for closing dates
  - Closing dates are often in SUBJECT LINES deep in the chain
  ```

**Why NEEDS TESTING:**
- Prompt guidance is comprehensive
- Need to verify Claude extracts dates from deep in email chains

---

### ISSUE 9: Time Entry Auto-Posting
**STATUS: FIXED**

**Evidence in Code:**
- `timesheet_queue.py` implements full approval workflow:
  - `add_entry()` - queues entry with status="pending"
  - `approve_entry()` - marks entry as approved
  - `reject_entry()` - rejects with reason
  - `mark_posted()` - marks as posted after QBO sync
- `notification_watcher.py` uses TimesheetQueue instead of direct posting:
  ```python
  # Queue for approval instead of auto-posting
  queue = TimesheetQueue()
  queue.add_entry(job_number, operator, hours, ...)
  ```

**Verification:** Time entries now go through approval queue. No automatic posting to QBO without approval.

---

### ISSUE 10: Proposal Status Tracking
**STATUS: NEEDS TESTING**

**Evidence in Code:**
- `hive_mind_prompt.py` lines ~500-550 defines PROPOSAL_WORKFLOW:
  ```
  new → info_gathering → awaiting_pricing → estimate_sent → accepted → converted
  ```
- NO state machine enforcement in code
- Proposal status stored as free-text field in job index

**Why NEEDS TESTING:**
- Workflow documented in prompt
- No code prevents invalid state transitions
- Need to verify Claude follows the workflow correctly

---

### ISSUE 11: Client vs Purchaser Confusion
**STATUS: NEEDS TESTING**

**Evidence in Code:**
- `claude_parser.py` lines 89-92 distinguishes:
  ```python
  "client_name": "person who SENT the email (e.g., 'Debbie Aylward')",
  "purchaser_name": "person BUYING the property (e.g., 'Yvonne Smith')",
  ```
- `hive_mind_prompt.py` contains similar guidance
- Job index stores both `client_name` and `purchaser_name` separately

**Why NEEDS TESTING:**
- Clear definitions exist in prompt
- Need to verify Claude correctly identifies and stores both

---

### ISSUE 12: CC/Reply-All Functionality
**STATUS: STILL BROKEN**

**Evidence in Code:**
- `tools_definition.py` `email_send_reply` definition:
  - Has `to` parameter (single recipient)
  - Has `cc` parameter (missing - not present)
  - No `cc_recipients` or `bcc_recipients` parameters
- `tools_definition.py` `email_send_new` definition:
  - Has `to` parameter only
  - No CC support
- `email_service.py` `send_message()` DOES support cc_recipients parameter, but tools don't expose it

**Impact:** Cannot CC additional recipients on emails. Cannot reply-all to group threads.

**Recommendation:** Add `cc_recipients` parameter to `email_send_reply` and `email_send_new` tools.

---

### ISSUE 13: Large File Handling
**STATUS: NEEDS TESTING**

**Evidence in Code:**
- `email_service.py` has pagination for listing
- `tool_executor.py` `_email_save_attachment()` downloads without size limit
- No explicit large file handling or chunked download
- No failure logging for download issues

**Why NEEDS TESTING:**
- No evidence of failures in code paths
- Need to test with large attachments (>10MB)

---

### ISSUE 14: QBO Customer Matching
**STATUS: NEEDS TESTING**

**Evidence in Code:**
- `qbo_integration.py` `search_customers()` searches by display name
- `qbo_sync.py` has customer deduplication logic:
  ```python
  # Check for existing customer before creating
  existing = self.qbo.search_customers(name)
  if existing:
      return existing[0]
  ```
- Fuzzy matching not implemented (exact match only)

**Why NEEDS TESTING:**
- Basic deduplication exists
- Need to verify handling of "Van Driel Law" vs "VanDriel Law" etc.

---

### ISSUE 15: Job Folder Path Issues
**STATUS: FIXED**

**Evidence in Code:**
- `config_loader.py` centralizes all paths:
  ```python
  self.jobs_folder = config.get('paths', 'jobs_folder')
  self.data_sync_folder = config.get('paths', 'data_sync_folder')
  self.job_index_file = config.get('paths', 'job_index_file')
  ```
- `tool_executor.py` uses `get_config()` for all paths
- `job_manager.py` uses config for paths
- `nightly_refresh.py` uses config for paths

**Verification:** Path configuration is centralized. All modules use config_loader.

---

## ADDITIONAL FINDINGS FROM CODE REVIEW

### Finding A: Tool Count Verification
- `audit_check.py` verifies 43 tools defined and handled
- All tools in `tools_definition.py` have handlers in `tool_executor.py`

### Finding B: Session Statistics
- `diagnostics.py` tracks all API calls, token usage, and costs
- Provides cache hit rate monitoring
- Good visibility into system performance

### Finding C: Nightly Refresh Robustness
- `nightly_refresh.py` creates daily backups before updating index
- Scans all years automatically
- Includes QBO sync as part of nightly run

### Finding D: Index Migration Complete
- `migrate_job_index.py` shows migration from old structure completed
- All jobs now keyed by job_number (not conversation_id)
- Sections have `_updated` timestamps

---

## RECOMMENDATIONS

### High Priority (STILL BROKEN)
1. **Add job_number_override to job_create** - Allow manual job number specification
2. **Add cc_recipients to email tools** - Enable CC and reply-all functionality

### Medium Priority (NEEDS TESTING)
3. **Test Document Control vs Work Products behavior** - Verify Claude uses correct folders
4. **Test invoice line item checking** - Verify no duplicate line items added
5. **Test metro pricing application** - Verify correct pricing rules applied
6. **Test closing date extraction** - Verify dates found in email chains
7. **Test QBO customer fuzzy matching** - Consider adding fuzzy match

### Low Priority
8. **Add large file download logging** - Better visibility into download failures
9. **Add proposal state machine enforcement** - Prevent invalid transitions

---

## CONCLUSION

The HiveMind codebase shows significant improvement since Build 2 discussions. The most critical issues (duplicate emails, time entry auto-posting) have working code fixes. Two features remain unimplemented (job number override, CC recipients). Eight issues depend on Claude's adherence to prompt instructions and require production testing to verify.

**Code Quality Assessment: 7/10**
- Good: Centralized configuration, duplicate guards, approval workflows
- Needs work: Missing CC support, no state machine enforcement, prompt-dependent behaviors

---

*Report generated after complete reading of all 19 Python files totaling ~15,000+ lines of code.*
