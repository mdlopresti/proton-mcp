# ENHANCEMENT: Lightweight Search Mode (Skip Email Bodies)

## Problem

`search_emails` always returns the full email body for every result. When searching for 50-100+ emails, the HTML bodies easily exceed token limits and waste bandwidth. A triage workflow only needs id, from, subject, and date to categorize emails — the body is only needed when the user asks to read a specific email.

## Current Behavior

Every search result includes all fields:
- `id`, `subject`, `from`, `date`, `body`

100 emails = ~80,000+ characters, mostly HTML body content that gets truncated or discarded.

## Proposed Solution

Add a `fields` parameter (or `include_body` boolean) to `search_emails` and `search_emails_filtered`:

```python
# Option A: fields parameter
search_emails(query="UNSEEN", limit=100, fields=["id", "from", "subject", "date"])

# Option B: simpler boolean
search_emails(query="UNSEEN", limit=100, include_body=False)
```

Option B is simpler and probably sufficient — the body is the only expensive field.

## Impact

- Triage workflows could fetch 200-400 emails in a single call
- Reduces token consumption by ~95%
- Faster response times for categorization and sender analysis
- Enables bulk sender frequency analysis without hitting limits

## Workaround

Currently using IMAP `FROM` queries to search by specific sender, which returns smaller result sets. But this requires knowing the sender in advance and doesn't help with initial inbox scanning.
