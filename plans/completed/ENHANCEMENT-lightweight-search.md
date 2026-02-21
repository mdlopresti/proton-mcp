# RESOLVED: Enhancement: Lightweight Search Mode (Skip Email Bodies)

**Status:** Implemented
**Implemented in:** Refactor Phase 3.1 (EmailService) and Phase 4.1 (tool registration)
**Resolution:** Added `include_body` parameter (default: `True`) to `search_emails` and `get_recent_emails` tools. When `include_body=False`, the body is excluded from results, reducing payload size by ~95% for large searches. Implemented in `src/proton_mcp/services/email_ops.py::EmailService.search_emails()` and exposed through `src/proton_mcp/tools/core.py`.

---

## Problem

`search_emails` always returns the full email body for every result. When searching for 50-100+ emails, the HTML bodies easily exceed token limits and waste bandwidth. A triage workflow only needs id, from, subject, and date to categorize emails -- the body is only needed when the user asks to read a specific email.

## Current Behavior

Every search result includes all fields:
- `id`, `subject`, `from`, `date`, `body`

100 emails = ~80,000+ characters, mostly HTML body content that gets truncated or discarded.

## Solution Applied

Added `include_body: bool = True` parameter (Option B from the proposal). When `False`, the `body_preview` field is returned as an empty string, skipping body extraction entirely. This enables:
- Triage workflows to fetch 200-400 emails in a single call
- ~95% reduction in token consumption
- Faster response times for categorization and sender analysis
