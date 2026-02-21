# RESOLVED: Bug: Unstable Email IDs Cause Silent Data Corruption During Multi-Move Operations

**Status:** Fixed
**Fixed in:** Refactor Phase 2.1 (UID migration)
**Resolution:** Migrated all IMAP operations from sequence numbers to UIDs. The new `IMAPClient` class (`src/proton_mcp/clients/imap.py`) exclusively uses `mail.uid()` for search, fetch, copy, and store operations. UIDs are stable within a mailbox session and do not shift when messages are deleted. Bulk operations use the deferred expunge pattern (copy all, mark deleted, single expunge) for efficiency. Verified by regression tests in `tests/unit/test_imap_client.py::TestUIDStability`.

---

## Problem

The MCP server uses IMAP sequence numbers as email IDs. These are positional indices, not stable identifiers. When `move_email_to_folder` or `bulk_move_emails` executes a COPY+DELETE+EXPUNGE, the sequence numbers of all remaining emails in the mailbox can shift.

This means:
- Moving email ID `5110` causes IDs `5101`, `5003`, etc. to potentially shift
- A second move using the original IDs may silently target the wrong email
- There is no error -- the wrong email gets moved without any indication

## Impact

- During email triage, an agent processes 5-20 dismissals per session
- Each move invalidates all remaining IDs
- The agent must re-fetch after every move, which is slow and wasteful
- If it doesn't re-fetch (the common mistake), emails get misfiled silently

## Solution Applied

Option A (UIDs) was implemented as the correct long-term fix, combined with Option B (deferred expunge) for bulk operations.
