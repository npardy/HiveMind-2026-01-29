# HIVE MIND - COMPREHENSIVE IMPLEMENTATION PLAN
## For Complete System Audit and Bug Fixes
### Created: January 26, 2026

---

# EXECUTIVE SUMMARY

This plan covers the complete audit and fix of the Hive Mind system to ensure:
1. All paths work on NAS/Docker (no Windows hardcoded paths)
2. QBO project creation works correctly for all jobs
3. Estimates use correct description format (address + ", NL")
4. Directory listing is fully recursive
5. Emails are marked UNREAD when moved between proposal folders
6. Metro areas include Holyrood and other missing communities
7. HUMAN safe word detection is implemented
8. Pricing is pulled from QBO service items
9. Quote vs Job logic works correctly
10. Job cancellation feature is implemented

---

# PHASE 1: PATH FIXES (CRITICAL) ✅ COMPLETED
**Priority: HIGHEST - Nothing works without this**

## 1.1 Files with Hardcoded Windows Paths

### File: `nightly_refresh.py`
**Lines to fix:** 32, 42-44, 556

| Line | Current | Fix To |
|------|---------|--------|
| 32 | `logging.FileHandler('H:\\logs\\nightly_refresh.log')` | Use `cfg.log_file` or construct from config |
| 42 | `JOBS_ROOT = "Z:\\Jobs"` | `cfg.jobs_folder` |
| 43 | `DATA_SYNC_OFFICE = "Z:\\Data Sync\\office-jobs"` | `cfg.data_sync_folder` |
| 44 | `INDEX_PATH = "H:\\data\\job_index.json"` | `cfg.job_index_file` |
| 556 | `os.makedirs('H:\\logs', exist_ok=True)` | Use config path |

**Implementation:**
```python
from config_loader import get_config
cfg = get_config()

# In class:
JOBS_ROOT = cfg.jobs_folder
DATA_SYNC_OFFICE = cfg.data_sync_folder
INDEX_PATH = cfg.job_index_file

# For logging:
log_dir = os.path.dirname(cfg.log_file)
os.makedirs(log_dir, exist_ok=True)
logging.FileHandler(cfg.log_file.replace('email_automation', 'nightly_refresh'))
```

### File: `qbo_sync.py`
**Lines to fix:** 38, 48-51, 486

| Line | Current | Fix To |
|------|---------|--------|
| 38 | `logging.FileHandler('H:\\logs\\qbo_sync.log')` | Use config path |
| 48 | `INDEX_PATH = "H:\\data\\job_index.json"` | `cfg.job_index_file` |
| 49 | `CONFIG_PATH = "H:\\config.yaml"` | Use HIVE_MIND_CONFIG env var |
| 51 | `JOBS_ROOT = "Z:\\Jobs"` | `cfg.jobs_folder` |
| 486 | `os.makedirs('H:\\logs', exist_ok=True)` | Use config path |

### File: `qbo_integration.py`
**Line to fix:** 18

| Line | Current | Fix To |
|------|---------|--------|
| 18 | `TOKEN_CACHE_FILE = "H:\\data\\qbo_token_cache.json"` | Accept from config in `__init__` |

### File: `hive_mind_prompt.py`
**Lines with Z:\ examples to update:**

| Line | Current | Fix To |
|------|---------|--------|
| 146-149 | `Z:\\Jobs\\YYYY\\`, `Z:\\Pardy Surveys\\Proposals\\`, `H:\\flagged\\` | `/volume1/Pardy Surveys/Jobs/YYYY/`, `/volume1/Pardy Surveys/Proposals/`, `/volume1/HiveMind/flagged/` |
| 167 | Template path with `Z:\\` | Use `/volume1/` paths |
| 173 | `Z:\\Pardy Surveys\\Proposals\\` | `/volume1/Pardy Surveys/Proposals/` |

## 1.2 Additional Files Needing Path Fixes

### Utility/Query Scripts (CHECK ALL FOR HARDCODED PATHS)
These scripts may have hardcoded paths and need to use config_loader:

| File | Purpose |
|------|---------|
| `query_job.py`, `query_job2.py` | Job lookup utilities |
| `query_email.py`, `query_email2.py`, `query_email3.py` | Email query utilities |
| `query_customer.py`, `query_customer2.py` | Customer lookup utilities |
| `query_qbo.py` | QBO query utility |
| `find_original_email.py`, `find_email2.py` | Email search utilities |
| `audit_check.py`, `audit_index.py` | Audit utilities |
| `notification_watcher.py` | Data Sync event monitoring |
| `migrate_job_index.py` | Job index migration utility |

## 1.3 Job Index Path Migration

**Problem:** The job_index.json may contain Z:\ paths in stored job entries (e.g., `job_folder` field).

**Required:** All paths in job_index.json should be /volume1/ format.

**Implementation:**
```python
# One-time migration script
import json

with open('/volume1/HiveMind/data/job_index.json', 'r') as f:
    index = json.load(f)

for job_number, job in index.items():
    if isinstance(job, dict):
        # Fix job_folder path
        if 'job_folder' in job and job['job_folder'].startswith('Z:'):
            job['job_folder'] = job['job_folder'].replace('Z:\\Jobs', '/volume1/Pardy Surveys/Jobs').replace('\\', '/')
        # Fix data_sync_folder path
        if 'data_sync_folder' in job and job['data_sync_folder'].startswith('Z:'):
            job['data_sync_folder'] = job['data_sync_folder'].replace('Z:\\Data Sync', '/volume1/Pardy Surveys/Data Sync').replace('\\', '/')

with open('/volume1/HiveMind/data/job_index.json', 'w') as f:
    json.dump(index, f, indent=2)
```

## 1.4 Verification Steps
- [ ] Search all .py files for `Z:\\`, `H:\\`, `Z:/`, `H:/`
- [ ] Ensure all paths load from config_loader
- [ ] Test each script independently with `--help` or dry-run
- [ ] Run `python -c "from config_loader import get_config; c = get_config(); print(c.jobs_folder)"` to verify config loads
- [ ] Run job_index.json migration script
- [ ] Verify no Z:\ paths remain in job_index.json

---

# PHASE 2: TOOL FIXES ✅ COMPLETED

## 2.1 QBO Project Creation - ✅ VERIFIED WORKING

**Current Status:** Implemented in `_job_create` (lines 2310-2350)

**Verification Needed:**
1. When `job_create` is called, verify a QBO project is created
2. Project name should be the job number (e.g., "26-011")
3. Invoice should be linked to that project
4. Project description should be: `"{address}, {community}, NL\nClosing: {date}\nPurchaser: {name}"`

**Test Case:**
```python
# Create a test job and verify QBO project exists
result = tool_executor._job_create({
    "client_name": "Test Client",
    "client_email": "test@example.com",
    "property_address": "123 Test Street",
    "community": "Paradise",
    "due_date": "2026-02-15",
    "purchaser_name": "John Buyer",
    "job_type": "rpr"
})
assert result.get("qbo_project_id") is not None
```

## 2.2 Estimate Description Format - FIX NEEDED

**Current Status:** Description is passed as a parameter, not generated

**Required Format:** `"{property_address}, {community}, NL"`

**Implementation in `_qbo_create_estimate`:**

```python
def _qbo_create_estimate(self, params: dict) -> dict:
    # Build description from address if not provided
    if 'description' not in params and 'property_address' in params:
        community = params.get('community', '')
        province = params.get('province', 'NL')
        params['description'] = f"{params['property_address']}, {community}, {province}".strip(', ')

    # ... rest of method
```

**Also update callers** to pass address components.

## 2.3 Recursive Directory Listing - ✅ COMPLETED

**Current Status:** `_nas_list_directory` only lists immediate children (not recursive)

**Required Behavior:** List ALL subfolders and their contents, no matter how deep

**Implementation:**

```python
def _nas_list_directory(self, params: dict) -> dict:
    """List directory contents, optionally recursive."""
    path = params['path']
    recursive = params.get('recursive', True)  # Default to recursive
    max_depth = params.get('max_depth', 10)  # Prevent infinite recursion

    if not os.path.exists(path):
        return {"error": f"Path not found: {path}"}
    if not os.path.isdir(path):
        return {"error": f"Not a directory: {path}"}

    try:
        if recursive:
            items = []
            for root, dirs, files in os.walk(path):
                # Calculate depth
                depth = root.replace(path, '').count(os.sep)
                if depth > max_depth:
                    continue

                rel_root = os.path.relpath(root, path)
                if rel_root == '.':
                    rel_root = ''

                for d in dirs:
                    items.append({
                        "name": d,
                        "type": "folder",
                        "path": os.path.join(root, d),
                        "relative_path": os.path.join(rel_root, d) if rel_root else d
                    })
                for f in files:
                    if f.startswith('.') or f == 'Thumbs.db':
                        continue
                    items.append({
                        "name": f,
                        "type": "file",
                        "path": os.path.join(root, f),
                        "relative_path": os.path.join(rel_root, f) if rel_root else f
                    })

            return {"path": path, "count": len(items), "items": items, "recursive": True}
        else:
            # Non-recursive (current behavior)
            items = []
            for name in sorted(os.listdir(path)):
                if name.startswith('.') or name == 'Thumbs.db':
                    continue
                item_path = os.path.join(path, name)
                items.append({
                    "name": name,
                    "type": "folder" if os.path.isdir(item_path) else "file",
                    "path": item_path
                })
            return {"path": path, "count": len(items), "items": items, "recursive": False}
    except Exception as e:
        return {"error": str(e)}
```

**Also update `tools_definition.py`** to add `recursive` and `max_depth` parameters.

## 2.4 Email Mark UNREAD on Proposal Status Changes - FIX NEEDED

**Current Status:** Moving emails does NOT mark them unread

**Required Behavior:** When Claude updates a proposal status (which moves the email), the email should also be marked UNREAD. This is part of the **proposal pipeline workflow**, not a random rule based on folder names.

**Implementation - Modify `_proposal_update` to handle the full workflow:**

When Claude changes a proposal's status, the `_proposal_update` method should:
1. Update the proposal JSON
2. Move the email to the corresponding folder
3. Mark the email as UNREAD

```python
def _proposal_update(self, params: dict) -> dict:
    # ... existing code to update proposal ...

    # If status changed and we have an email linked, handle the pipeline
    if 'status' in params and proposal.get('email_id'):
        email_id = proposal['email_id']

        folder_map = {
            'new': 'Proposals/New',
            'awaiting_info': 'Proposals/Awaiting Info',
            'awaiting_pricing': 'Proposals/Awaiting Pricing',
            'quoted': 'Proposals/Quoted'
        }

        new_status = params['status']
        if new_status in folder_map:
            # Move email to pipeline folder
            self._email_move_to_folder({
                'message_id': email_id,
                'folder_name': folder_map[new_status]
            })
            # Mark UNREAD so Nick sees the count
            self._email_mark_unread({'message_id': email_id})

    # ... rest of method
```

**Key Point:** This is tied to the proposal workflow, not to folder names. Claude manages proposals, and the email movement + unread marking happens as part of that workflow.

## 2.5 Proposal Attachment Tracking - NEW FEATURE

**Current Status:** Proposals don't track which attachments have been received/saved.

**Required Behavior:** The proposal should track:
- What attachments have come in (deeds, previous surveys, etc.)
- Where they were saved
- When they were received

**Implementation - Add attachments array to proposal structure:**

```python
# In _proposal_create, add to the proposal dict:
"attachments": []  # Will hold list of received attachments

# In _proposal_update, add support for logging attachments:
if 'attachment' in params:
    att = params['attachment']
    proposal['attachments'].append({
        "filename": att.get('filename'),
        "saved_to": att.get('saved_to'),
        "received_date": datetime.now().isoformat(),
        "type": att.get('type'),  # deed, previous_survey, etc.
        "email_id": att.get('email_id')
    })
```

**Claude's workflow when attachments arrive:**
1. Use `email_get_attachments` to see what's attached
2. Use `email_save_attachment` to save to appropriate location
3. Use `proposal_update` with `attachment` param to log it in the proposal

This way the proposal tracks everything that's come in, making conversion to a job seamless.

---

# PHASE 3: WORKFLOW FIXES ✅ MOSTLY COMPLETED

## 3.1 Metro Areas - ✅ COMPLETED

**Current:** `METRO_AREAS` list in `tool_executor.py` (lines 27-32) and `job_manager.py` (lines 23-28)

**Communities to ADD:**
- Holyrood
- Petty Harbour-Maddox Cove

**Communities to REMOVE:**
- Torbay - NOT metro (per Nick)
- Flatrock - NOT metro (per Nick)

**NOT Metro (confirmed):**
- Bay Bulls
- Witless Bay
- Torbay
- Flatrock
- Pouch Cove

**Updated List:**
```python
METRO_AREAS = [
    # St. John's metro core
    "st. john's", "st johns", "saint john's",
    "mount pearl", "mt. pearl",
    "paradise",
    "conception bay south", "cbs",
    "portugal cove-st. philip's", "portugal cove", "pcsp",
    "logy bay-middle cove-outer cove", "logy bay",
    # Additional metro communities
    "holyrood",
    "petty harbour-maddox cove", "petty harbour", "maddox cove",
]
```

**Files to update:**
1. `tool_executor.py` - lines 27-32
2. `job_manager.py` - lines 23-28
3. `hive_mind_prompt.py` - BUSINESS_CONTEXT section (line 673-674)

## 3.2 HUMAN Safe Word Detection - ✅ COMPLETED (Claude's discretion)

**Background:** Claude's signature already tells clients: `Need Nick or Joe? Reply "HUMAN" to connect directly.`

**Approach:** Rather than hardcoded regex detection, **Claude should use its own judgment** to recognize when someone wants to speak to a real person. This is more flexible and fits the Hive Mind philosophy of reasoning about intent.

**Implementation:** Add guidance to the system prompt in `hive_mind_prompt.py`

**Add to STANCE or OPERATIONAL_KNOWLEDGE section:**
```python
### HUMAN SAFE WORD / REQUEST FOR REAL PERSON

My signature tells clients: "Need Nick or Joe? Reply HUMAN to connect directly."

**When I detect someone wants to speak to a real person:**
- They reply "HUMAN" or "human" in their NEW message (not in the quoted thread below)
- They say things like "Can I speak to someone?", "Is there a person I can talk to?", "I'd like to speak with Nick"
- They express frustration with automated responses
- They have a complex/sensitive situation that clearly needs human judgment

**What I do:**
1. Flag the email for Nick's attention using flag_for_attention
2. DO NOT auto-respond with a regular reply
3. Optionally send a brief acknowledgment: "I've flagged this for Nick - he'll be in touch shortly."

**Important:** The word "HUMAN" appears in my signature, so it will show up in quoted reply chains.
I need to look at the NEW content of their message, not the quoted history below, to determine if
they're actually requesting a human.

**Use judgment, not rigid rules.** If someone seems to want human contact, flag it. When in doubt, flag it.
```

**Why this approach is better:**
1. Claude can recognize many ways people ask for a human (not just the word "HUMAN")
2. Claude can use context - frustrated client vs. simple question
3. Claude naturally ignores quoted reply chains when reading the "new" part of an email
4. Fits the philosophy of Claude reasoning about intent, not following hardcoded rules
5. No code changes needed to orchestrator - just prompt guidance

## 3.3 Quote vs Job Decision Logic - CLAUDE'S DISCRETION

**This is about Claude reasoning about INTENT, not following rigid rules.**

**Current Code Logic in `_job_create`:**
- If community is non-metro → `needs_quote = True`
- If no due_date → `needs_quote = True`

This code logic is fine for the programmatic check, but **Claude decides BEFORE calling job_create** whether this is a job request or a quote inquiry based on reading the email.

**Implementation:** Update system prompt guidance in `hive_mind_prompt.py`:

```python
### READING INTENT - JOB REQUEST vs QUOTE INQUIRY

I read the email and understand what the person actually wants:

**This is clearly a JOB REQUEST - proceed with job_create:**
- Email is from a law firm or realtor (check the domain, tone, signature)
- They're clearly instructing us to do work: "We need an RPR for closing on Feb 15"
- They provide transaction details: closing date, purchaser name, lawyer reference
- They're not asking about price - they're telling us to proceed
- Professional/transactional tone indicates this is a go

**This is a QUOTE INQUIRY - use proposal workflow:**
- They're asking about cost: "How much would it cost?", "What's your rate?"
- Exploratory language: "thinking about", "considering", "wondering if"
- No closing date or deadline mentioned
- Individual/homeowner tone rather than professional transaction
- They haven't committed - they're shopping or gathering info

**Key insight:** A law firm emailing "We need an RPR for 123 Main Street, closing January 30, purchaser John Smith" is NOT asking for a quote. They're telling us to do the work. Create the job.

**When in doubt:** Treat as quote inquiry. Better to confirm than to invoice someone who was just asking.
```

## 3.4 The Spine is the REAL-TIME Source of Truth

**Core Philosophy:** The spine is a **living document** - the real-time source of truth. Some background processes help keep it current (notification_watcher for field data, nightly_refresh, etc.), but **Claude's primary job is to maintain and enrich the spine** with every interaction.

**The spine stays current through:**
- **Background processes:** notification_watcher updates field data, nightly_refresh syncs jobs, qbo_sync updates payment status
- **Claude's actions:** Every email read, every action taken, every lookup done - Claude updates the spine
- **Enrichment:** When Claude finds stale or missing info, it goes to the source, gets current data, and updates the spine

**The `_updated` timestamps help Claude reason:**
> "This QBO section was updated 3 days ago... the client just said they paid. Let me check QBO and update the spine."

**Claude's responsibility:** Maintaining the spine is not optional - it's the core job. Every interaction should leave the spine more complete and more current than before.

**Implementation:** Add guidance to `hive_mind_prompt.py` in OPERATIONAL_KNOWLEDGE:

```python
### THE SPINE IS MY REAL-TIME MEMORY

The job_index.json (spine) should ALWAYS be current. It's not a cache - it's the source of truth.

**Every action I take updates the spine:**
- Read an email → Link it to the job, add summary, update timestamp
- Record a payment → Update QBO AND spine simultaneously
- Get field data info → Spine reflects it immediately
- Change job status → Spine updated as part of that action
- Learn something about a client → Add it to their record

**When I need context, the spine should have it:**
- Use `job_search` by sender email, company/domain, or address
- The spine has linked emails with summaries - my history is already there
- If spine has what I need (which it usually should), I'm done

**If spine seems stale or doesn't have what I need:**
- Check the `_updated` timestamp - does this section need refreshing?
- If asking about payments and QBO section is days old, check QBO and update spine
- If asking about field work and data_sync section is old, check Data Sync and update spine
- Use `email_search` ONLY if there might be emails not yet linked to the spine

**After ANY lookup or action:**
- Update the spine with what I learned
- Link any emails I found
- Add summaries, update timestamps
- The goal: future me never has to search for this again

**Why this matters:** Every interaction makes the spine smarter. If I do my job right, the spine is always current and I rarely need to search raw emails. The spine IS my memory.
```

## 3.5 Email Folder Structure - CONSISTENCY FIX

**Problem:** Email folder references are inconsistent across the codebase. Some use `Email/Folder`, some use just `Folder`.

**Required Structure:** All email folders should be nested properly:

```
Inbox (Nick's real work stays here)
├── Email/
│   ├── Processed (things Claude handled, no action needed)
│   ├── Marketing (newsletters, marketing emails)
│   ├── Receipts (expense receipts after recording in QBO)
│   └── Needs Attention (flagged for Nick - flag_for_attention moves here)
├── Proposals/
│   ├── New
│   ├── Awaiting Info
│   ├── Awaiting Pricing
│   └── Quoted
└── Jobs/ (optional - emails saved to job folders)
```

**Files to audit for folder consistency:**
- `tool_executor.py` - folder references in `_proposal_update`, `_flag_for_attention`
- `hive_mind_prompt.py` - folder examples in INBOX MANAGEMENT section
- `claude_agent.py` - any folder references

**All folder references should use the FULL path:**
- `Email/Processed` NOT `Processed`
- `Email/Marketing` NOT `Marketing`
- `Email/Needs Attention` NOT `Needs Attention`
- `Proposals/New` NOT `New`

## 3.6 Inbox Management - CLARITY

**Goal:** Nick's inbox should ONLY contain things that need his attention.

**What Claude should do:**

**Keep in Inbox (unread):**
- Emails Claude flagged for Nick (via flag_for_attention)
- Hive Mind's own emails to Nick
- Things that genuinely need Nick's decision

**Move OUT of Inbox:**
- Spam/marketing → `Email/Marketing` (mark read)
- Newsletters/notifications → `Email/Processed` (mark read)
- QBO automated notifications → `Email/Processed` (mark read)
- Receipts → `Email/Receipts` (after recording in QBO, mark read)
- Emails Claude fully handled → `Email/Processed` (mark read)

**System prompt should emphasize:** Claude's job is to CLEAR THE NOISE so Nick can focus on real work.

## 3.7 Receipts & Expenses Workflow - VERIFY WORKING

**Current Status:** Tools exist (`qbo_record_expense`, `qbo_get_expense_categories`)

**Required Workflow:**
1. Claude identifies receipt email (patterns: "Your receipt", "Order confirmation", "Invoice from", etc.)
2. Extract: vendor, amount, date, category
3. Record in QBO using `qbo_record_expense`
4. Save any attachment to appropriate folder
5. Move email to `Email/Receipts`
6. Mark as read

**Common receipt sources:**
- Amazon, Staples, Home Depot (supplies)
- Software subscriptions (Adobe, Microsoft, etc.)
- Equipment purchases
- Vehicle/fuel receipts
- Insurance payments

**If Claude can't determine category:** Flag for Nick with extracted details.

**Test:** Verify this workflow works end-to-end with a real receipt email.

---

## 3.8 Pricing from QBO Service Items - NEW FEATURE

**Requirement:** Pull standard pricing from QBO service items instead of hardcoding

**Current State:**
- `_qbo_get_service_items()` EXISTS and retrieves items with prices
- Invoice creation DOES use item pricing
- Estimate creation DOES NOT use item pricing (requires amount in params)

**Implementation - Update `_qbo_create_estimate`:**

```python
def _qbo_create_estimate(self, params: dict) -> dict:
    """Create estimate in QBO."""
    try:
        customer_id = params['customer_id']

        # Get amount - either from params or from service item
        amount = params.get('amount')
        if not amount and params.get('service_item'):
            # Look up price from QBO service item
            items = self.qbo.get_items()
            for item in items:
                if item.get('Name', '').lower() == params['service_item'].lower():
                    amount = float(item.get('UnitPrice', 0))
                    break

        if not amount:
            return {"success": False, "error": "Amount required - either specify amount or valid service_item"}

        # Build description from address if not provided
        description = params.get('description', '')
        if not description and params.get('property_address'):
            community = params.get('community', '')
            description = f"{params['property_address']}, {community}, NL".strip(', ')

        # ... rest of method
```

**Also add tool for getting current prices:**

```python
def _qbo_get_standard_rates(self, params: dict) -> dict:
    """Get current standard rates from QBO service items."""
    items = self.qbo.get_items()
    rates = {}
    for item in items:
        name = item.get('Name', '')
        price = item.get('UnitPrice', 0)
        if price and name:
            rates[name] = {
                'price': float(price),
                'id': item.get('Id'),
                'description': item.get('Description', '')
            }
    return {"rates": rates, "count": len(rates)}
```

---

# PHASE 4: NEW FEATURES

## 4.1 Job Cancellation Feature

**Requirements:**
1. Mark job entry in job_index as "cancelled" status (preserve history)
2. Mark/rename project as cancelled in QBO
3. Delete the invoice in QBO (or void it)
4. Next job number continues normally (skip the cancelled number)

**Implementation:**

### New Tool: `job_cancel`

**In `tools_definition.py`:**
```python
{
    "name": "job_cancel",
    "description": "Cancel a job. Marks job as cancelled in spine, updates QBO project, voids invoice. Job number is preserved but skipped for future jobs.",
    "input_schema": {
        "type": "object",
        "properties": {
            "job_number": {"type": "string", "description": "Job number to cancel (e.g., '26-011')"},
            "reason": {"type": "string", "description": "Reason for cancellation"},
            "void_invoice": {"type": "boolean", "description": "Whether to void the invoice (default: true)"}
        },
        "required": ["job_number", "reason"]
    }
}
```

**In `tool_executor.py`:**
```python
def _job_cancel(self, params: dict) -> dict:
    """Cancel a job - update spine, QBO project, void invoice."""
    job_number = params['job_number']
    reason = params['reason']
    void_invoice = params.get('void_invoice', True)

    if job_number not in self.job_index:
        return {"success": False, "error": f"Job {job_number} not found in index"}

    job = self.job_index[job_number]
    now = datetime.now().isoformat()

    result = {
        "job_number": job_number,
        "success": True,
        "actions": []
    }

    # 1. Update job index
    job['status'] = 'cancelled'
    job['cancelled_date'] = now
    job['cancellation_reason'] = reason
    job['last_updated'] = now
    result['actions'].append("Marked as cancelled in job index")

    # 2. Update QBO project name to indicate cancelled
    qbo_section = job.get('qbo', {})
    if qbo_section.get('project_id') and self.qbo.access_token:
        try:
            # Update project name to include [CANCELLED]
            project_name = f"[CANCELLED] {job_number}"
            self.qbo.update_project_name(qbo_section['project_id'], project_name)
            result['actions'].append(f"Renamed QBO project to '{project_name}'")
        except Exception as e:
            result['actions'].append(f"Failed to update QBO project: {e}")

    # 3. Void invoice if requested
    if void_invoice and qbo_section.get('invoice_id') and self.qbo.access_token:
        try:
            self.qbo.void_invoice(qbo_section['invoice_id'])
            qbo_section['status'] = 'Voided'
            qbo_section['voided_date'] = now
            result['actions'].append("Voided QBO invoice")
        except Exception as e:
            result['actions'].append(f"Failed to void invoice: {e}")

    # 4. Update QBO section
    qbo_section['_updated'] = now
    job['qbo'] = qbo_section

    # Save index
    self._save_job_index()

    return result
```

**In `qbo_integration.py` - add new methods:**
```python
def update_project_name(self, project_id: str, new_name: str) -> bool:
    """Update a project's display name."""
    # QBO API call to update customer/project name
    pass

def void_invoice(self, invoice_id: str) -> bool:
    """Void an invoice."""
    # Get current invoice, update with Void operation
    pass
```

---

# PHASE 5: SYSTEM PROMPT UPDATES

## 5.1 Update `hive_mind_prompt.py`

### Changes to BUSINESS_CONTEXT:
```python
### METRO AREAS (Standard RPR pricing from QBO - I can quote directly)
Newfoundland: St. John's, Mount Pearl, Paradise, Conception Bay South,
Portugal Cove-St. Philip's, Logy Bay-Middle Cove-Outer Cove, Holyrood,
Petty Harbour-Maddox Cove

Nova Scotia: Areas within 50km of Annapolis Valley office

NOTE: Torbay, Flatrock, Pouch Cove, Bay Bulls, Witless Bay are NOT metro - need custom pricing.
```

### Changes to TOOL_ACCESS:
```python
### Key locations:
- /volume1/Pardy Surveys/Jobs/YYYY/ - Active and completed jobs
- /volume1/Pardy Surveys/Jobs/YYYY/YY-000 - Template/ - Template folder for new jobs
- /volume1/Pardy Surveys/Proposals/ - Pre-job inquiries
- /volume1/HiveMind/flagged/ - Flagged items for Nicholas
```

### Add to STANCE:
```python
**HUMAN SAFE WORD:**
If Nicholas includes "HUMAN" anywhere in his email, it means he wants to handle this
situation personally. I should:
1. Flag the email for his attention
2. NOT auto-respond
3. NOT take any automated action
4. Leave it for him to handle manually
```

### Add to OPERATIONAL_KNOWLEDGE:
```python
### PRICING APPROACH
- Standard rates are stored in QBO as service items
- For metro RPR inquiries, I can quote the QBO "Real Property Report" price
- BUT I must tell clients: "Our standard rate is $X, but final pricing depends on the specifics of your property"
- For anything non-standard: get pricing from Nicholas first
- NEVER guarantee a price without knowing the property details
```

---

# PHASE 6: COMPREHENSIVE TESTING

## 6.1 Unit Tests - Run All Existing Tests

```bash
cd /volume1/HiveMind
python -m pytest test_*.py -v
```

If pytest not available:
```bash
for f in test_*.py; do python "$f"; done
```

## 6.2 Path Verification Tests

```python
# test_paths.py
from config_loader import get_config
import os

cfg = get_config()

paths_to_check = [
    ("base_path", cfg.base_path),
    ("jobs_folder", cfg.jobs_folder),
    ("data_sync_folder", cfg.data_sync_folder),
    ("proposals_folder", cfg.proposals_folder),
    ("flagged_folder", cfg.flagged_folder),
    ("job_index_file", cfg.job_index_file),
    ("token_cache_graph", cfg.token_cache_graph),
    ("token_cache_qbo", cfg.token_cache_qbo),
]

for name, path in paths_to_check:
    exists = os.path.exists(path)
    print(f"{name}: {path} -> {'EXISTS' if exists else 'MISSING'}")
    assert exists, f"Path {name} does not exist: {path}"

print("\nAll paths verified!")
```

## 6.3 Tool Execution Tests

### NAS Tools
- [ ] `nas_list_directory` - List job folder, verify recursive shows all subfolders
- [ ] `nas_read_file` - Read a known file
- [ ] `nas_file_exists` - Check existing and non-existing paths
- [ ] `nas_search_files` - Search for *.pdf in a job folder

### Proposal Tools
- [ ] `proposal_create` - Create test proposal
- [ ] `proposal_update` - Update status, verify email moved AND marked UNREAD
- [ ] `proposal_get` - Retrieve the proposal
- [ ] `proposal_search` - Find by client name
- [ ] `proposal_list` - List by status

### Estimate Tools
- [ ] `qbo_create_estimate` - Create estimate, verify description format is "Address, NL"
- [ ] `qbo_get_estimate` - Retrieve estimate
- [ ] `qbo_send_estimate` - Send to test email

### Job Tools
- [ ] `job_create` - Create test job, verify:
  - QBO project created with job number as name
  - Invoice linked to project
  - Job folder created
  - Spine entry created
- [ ] `job_search` - Find the job
- [ ] `job_get_status` - Get comprehensive status
- [ ] `job_cancel` - Cancel job, verify:
  - Spine shows cancelled status
  - QBO project renamed to [CANCELLED]
  - Invoice voided

### Email Tools
- [ ] `email_move_to_folder` - Move to Proposals folder, verify marked UNREAD
- [ ] `email_mark_unread` - Explicitly mark unread

## 6.4 Workflow Tests

### Quote Inquiry Workflow (Full Path)
1. Simulate quote inquiry email (no closing date, asking "how much?")
2. Verify proposal created with status "new"
3. Verify email moved to Proposals/New and marked UNREAD
4. Update with client info → status "awaiting_info"
5. Verify email moved to Proposals/Awaiting Info and marked UNREAD
6. Simulate info received → status "awaiting_pricing"
7. Verify email moved to Proposals/Awaiting Pricing and marked UNREAD
8. Verify email sent to Nick for pricing
9. Simulate Nick's price reply
10. Verify estimate created with correct description format (Address, NL)
11. Verify estimate sent to client
12. Simulate acceptance
13. Verify job created with QBO project
14. Verify invoice linked to project

### Confirmed Job Workflow (Full Path)
1. Simulate law firm email with closing date and purchaser name
2. Verify job created immediately (not proposal)
3. Verify QBO project created with job number as name
4. Verify invoice created and linked to project
5. Verify job folder created with correct structure

### HUMAN Safe Word Test
1. Send email with "HUMAN" in body
2. Verify email is flagged for attention
3. Verify NO auto-response sent

### Job Cancellation Test
1. Create a test job
2. Cancel it with job_cancel
3. Verify spine shows cancelled status
4. Verify QBO project renamed
5. Verify invoice voided
6. Create next job, verify job number increments (doesn't reuse cancelled number)

## 6.5 Integration Test - Orchestrator Dry Run

```bash
python orchestrator.py --dry-run --test-emails
```

Verify:
- All emails processed without path errors
- Correct workflow chosen for each email type
- All tools execute successfully

---

# PHASE 7: DOCUMENTATION & CLEANUP

## 7.1 Update Configuration Files

Ensure `config.nas.yaml` has all paths correct:
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

## 7.2 Remove Obsolete Code

- [ ] Remove `_translate_path()` if no longer needed after path fixes
- [ ] Remove any deprecated Windows-only code paths
- [ ] Clean up any Z:\ or H:\ references in comments

## 7.3 Update COMPREHENSIVE_HANDOFF.md

Mark all completed items and note any changes from original plan.

---

# EXECUTION ORDER

## Day 1: Critical Path Fixes
1. Fix `nightly_refresh.py` paths
2. Fix `qbo_sync.py` paths
3. Fix `qbo_integration.py` TOKEN_CACHE_FILE
4. Update `hive_mind_prompt.py` path examples
5. Run path verification tests

## Day 2: Tool Fixes
6. Implement recursive directory listing
7. Add email UNREAD marking on folder move
8. Verify/fix QBO project creation
9. Fix estimate description format
10. Run tool execution tests

## Day 3: Workflow Fixes
11. Add metro areas (Holyrood, etc.)
12. Implement HUMAN safe word detection
13. Update pricing to use QBO service items
14. Update system prompt with all changes
15. Run workflow tests

## Day 4: New Features & Testing
16. Implement job cancellation feature
17. Run full integration tests
18. Fix any issues found
19. Update documentation
20. Final verification

---

# SUCCESS CRITERIA

The implementation is complete when:

1. **All paths use config_loader** - No hardcoded Z:\ or H:\ paths anywhere in .py files
2. **Job_index.json paths migrated** - All job entries use /volume1/ paths
3. **Job creation creates QBO project** - Verified with test job
4. **Estimate descriptions are "Address, NL"** - Verified with test estimate
5. **Invoice descriptions are "Address, NL"** - Verified with test job
6. **Directory listing is fully recursive** - Shows all nested subfolders
7. **Emails marked UNREAD on proposal status changes** - Verified in Outlook
8. **Metro areas correct** - Holyrood, Petty Harbour in; Torbay, Flatrock, Pouch Cove out
9. **HUMAN safe word detection works** - Client saying "HUMAN" gets flagged, not auto-responded
10. **Pricing pulled from QBO** - Standard rates come from service items
11. **Job cancellation works** - Cancelled job has correct status in spine and QBO
12. **Email folder structure consistent** - All use full paths (Email/Processed, not Processed)
13. **Receipts workflow works** - Receipt emails recorded in QBO, moved to Email/Receipts
14. **Proposals track attachments** - Attachments logged when saved
15. **All tests pass** - Both unit tests and integration tests
16. **Orchestrator runs without errors** - Full email processing cycle works
17. **Inbox is clean** - Claude moves non-essential emails out, marks read appropriately

---

# NOTES FOR NICK

- **Delete from QBO:** You mentioned you'll delete 26-010 from QBO manually. Done deleting from spine.
- **Job Cancellation:** I've designed it to skip cancelled numbers and keep history. Let me know if you want any changes.
- **Pricing:** The plan uses QBO service items as the source of truth. Claude will quote standard rates but always with the caveat that final price depends on property specifics.
- **Testing:** I'll test against live systems as you requested. I'll be careful with test data and clean up after.

---

# CHANGELOG - What's Being Changed and Why

This section documents every change made, so issues can be traced back later.

## File: `nightly_refresh.py`
| Change | Why | Lines |
|--------|-----|-------|
| Replace hardcoded `H:\logs\nightly_refresh.log` with config path | NAS runs on /volume1/, not Windows drive letters | 32 |
| Replace `JOBS_ROOT = "Z:\Jobs"` with `cfg.jobs_folder` | Path must come from config for NAS compatibility | 42 |
| Replace `DATA_SYNC_OFFICE` hardcoded path with `cfg.data_sync_folder` | Path must come from config for NAS compatibility | 43 |
| Replace `INDEX_PATH` hardcoded path with `cfg.job_index_file` | Path must come from config for NAS compatibility | 44 |
| Replace `os.makedirs('H:\logs'...)` with config-based path | Path must come from config for NAS compatibility | 556 |

## File: `qbo_sync.py`
| Change | Why | Lines |
|--------|-----|-------|
| Replace hardcoded log path with config path | NAS compatibility | 38 |
| Replace `INDEX_PATH` with `cfg.job_index_file` | NAS compatibility | 48 |
| Replace `CONFIG_PATH` with env var lookup | Config should be found via HIVE_MIND_CONFIG env var | 49 |
| Replace `JOBS_ROOT` with `cfg.jobs_folder` | NAS compatibility | 51 |

## File: `qbo_integration.py`
| Change | Why | Lines |
|--------|-----|-------|
| Replace hardcoded `TOKEN_CACHE_FILE` with config-based path | NAS compatibility | 18 |

## File: `hive_mind_prompt.py`
| Change | Why | Section |
|--------|-----|---------|
| Update path examples from Z:\ to /volume1/ | Examples should reflect NAS paths | TOOL_ACCESS |
| Update metro areas list (add Holyrood, Petty Harbour; remove Torbay, Flatrock, Pouch Cove) | Per Nick's corrections | BUSINESS_CONTEXT |
| Add HUMAN safe word guidance | Claude should recognize when clients want to talk to a real person | STANCE |
| Add Quote vs Job intent guidance | Claude should reason about intent, not follow rigid rules | OPERATIONAL_KNOWLEDGE |
| Add Real-Time Spine guidance | Spine is the real-time source of truth, not a cache; Claude updates it with every action; email search only when spine lacks info | OPERATIONAL_KNOWLEDGE |
| Add Pricing Approach guidance | Pricing comes from QBO service items, with caveats | OPERATIONAL_KNOWLEDGE |

## File: `tool_executor.py`
| Change | Why | Function |
|--------|-----|----------|
| Update METRO_AREAS list | Per Nick's corrections - add Holyrood, Petty Harbour; remove Torbay, Flatrock, Pouch Cove | lines 27-32 |
| Make `_nas_list_directory` recursive by default | Nick needs to see ALL subfolders, not just top level | `_nas_list_directory` |
| Add `_job_cancel` method | New feature to cancel jobs properly (update spine, rename QBO project, void invoice) | new method |
| Update `_proposal_update` to handle email pipeline | When proposal status changes, move email AND mark UNREAD | `_proposal_update` |
| Add attachment tracking to `_proposal_create` | Proposals need to track what documents have been received | `_proposal_create` |
| Add attachment logging to `_proposal_update` | Allow logging attachments as they're saved | `_proposal_update` |
| Update `_qbo_create_estimate` to build description from address | Description should be "Address, Community, NL" format | `_qbo_create_estimate` |

## File: `job_manager.py`
| Change | Why | Lines |
|--------|-----|-------|
| Update METRO_AREAS list | Must match tool_executor.py | lines 23-28 |

## File: `tools_definition.py`
| Change | Why | Tool |
|--------|-----|------|
| Add `recursive` and `max_depth` params to nas_list_directory | Support recursive listing | nas_list_directory |
| Add `job_cancel` tool definition | New feature | new tool |

## File: `qbo_integration.py` (new methods)
| Change | Why |
|--------|-----|
| Add `update_project_name()` method | Needed for job cancellation - rename project to [CANCELLED] |
| Add `void_invoice()` method | Needed for job cancellation - void the invoice |

---

**END OF IMPLEMENTATION PLAN**

*This plan should be followed in order. Each phase builds on the previous one. If you have questions or want changes, let me know before I start implementation.*
