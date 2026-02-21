# BUG: Unstable Email IDs Cause Silent Data Corruption During Multi-Move Operations

## Problem

The MCP server uses IMAP sequence numbers as email IDs. These are positional indices, not stable identifiers. When `move_email_to_folder` or `bulk_move_emails` executes a COPY+DELETE+EXPUNGE, the sequence numbers of all remaining emails in the mailbox can shift.

This means:
- Moving email ID `5110` causes IDs `5101`, `5003`, etc. to potentially shift
- A second move using the original IDs may silently target the wrong email
- There is no error — the wrong email gets moved without any indication

## How It Happens

1. Agent fetches inbox: email A=5110, email B=5101, email C=5003
2. Agent moves A (5110) to `Folders/House Stuff` — COPY, DELETE, EXPUNGE
3. After expunge, B might now be 5109 and C might be 5002
4. Agent moves B using old ID 5101 — this might now point to a completely different email
5. No error is raised; the wrong email is silently moved

## Impact

- During email triage, an agent processes 5-20 dismissals per session
- Each move invalidates all remaining IDs
- The agent must re-fetch after every move, which is slow and wasteful
- If it doesn't re-fetch (the common mistake), emails get misfiled silently

## Possible Solutions

### Option A: Use IMAP UIDs Instead of Sequence Numbers

IMAP UIDs are stable within a mailbox session and don't shift on expunge. Python's `imaplib` supports UID mode:

```python
# Instead of:
mail.copy(sequence_num, folder)
mail.store(sequence_num, "+FLAGS", "\\Deleted")

# Use:
mail.uid('COPY', uid, folder)
mail.uid('STORE', uid, '+FLAGS', '\\Deleted')
```

All search, fetch, copy, store, and expunge operations have UID equivalents. This would require changing all IMAP operations throughout the server to use `mail.uid()` instead of the convenience methods.

**Pros:** UIDs are stable, well-supported, standard IMAP behavior
**Cons:** Requires updating every IMAP call site; UIDs can change between sessions (UIDVALIDITY)

### Option B: Deferred Expunge

Separate the COPY+DELETE from the EXPUNGE step. Do all copies and flag-as-deleted first, then expunge once at the end:

```python
def bulk_move_multi_folder(self, moves: list[dict]):
    """Move emails to multiple folders in a single session without intermediate expunges."""
    mail = self.connect_imap()
    mail.select(source_folder)

    for move in moves:
        mail.copy(move["email_id"], move["target_folder"])
        mail.store(move["email_id"], "+FLAGS", "\\Deleted")

    # Single expunge at the end — IDs were stable throughout
    mail.expunge()
```

**Pros:** Minimal code change, IDs stay stable during the batch
**Cons:** Only solves multi-move batches, not cross-session instability; requires new tool endpoint

### Option C: Message-ID Based Addressing

Use the `Message-ID` header (RFC 2822) as the stable identifier instead of IMAP sequence numbers. Search for the Message-ID to resolve the current sequence number before each operation.

**Pros:** Stable across sessions and mailbox changes
**Cons:** Extra SEARCH per operation, slower, Message-ID could theoretically be non-unique

## Recommendation

**Option A (UIDs)** is the correct long-term fix. It's how IMAP is designed to work for programmatic access. Option B is a good quick fix for the immediate multi-move problem while Option A is being implemented.

## Current Workaround

The email-triage skill documents this issue and instructs agents to:
- Collect all dismissals before executing any moves
- Re-fetch IDs after every round of moves
- Never reuse IDs across move operations
