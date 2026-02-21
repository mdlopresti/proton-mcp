# RESOLVED: Bug: find_unsubscribe_links Fails to Detect In-Body Unsubscribe Links

**Status:** Fixed
**Fixed in:** Refactor Phase 3.2 (unsubscribe service extraction)
**Resolution:** Implemented anchor-text-based detection in `src/proton_mcp/services/unsubscribe.py`. The `_UnsubscribeLinkParser` HTML parser now:
- Detects links where the **anchor text** contains "unsubscribe", "opt out", "manage preferences", etc.
- Handles "click here"/"here" anchor text near unsubscribe context using a two-pass approach
- Detects tracker-wrapped URLs (Klaviyo, SendGrid, Mailchimp) via configurable detection patterns
- Users can add custom detection patterns for new tracker domains
- URL safety validation (SSRF protection) applied to all discovered links

---

## Problem

The `find_unsubscribe_links` tool returns zero unsubscribe methods for emails that clearly contain unsubscribe links in their HTML body. Tested against 5 Blissy emails -- all had visible unsubscribe links, all returned `total_methods: 0`.

## Test Cases

### Klaviyo-sent emails (support@blissy.com)
- Body contains: `If you'd no longer like to receive emails, <a href="https://ctrk.klclick.com/...">click here</a>`
- Tool result: `unsubscribe_methods: [], total_methods: 0`

### SendGrid-sent emails (reviews@stamped.io)
- Body contains: `To unsubscribe click <a href="https://u2081612.ct.sendgrid.net/...">here</a>`
- Tool result: `unsubscribe_methods: [], total_methods: 0`

## Likely Cause

The tool was only checking for `List-Unsubscribe` IMAP headers and links with "unsubscribe" in the URL path. It missed links where the anchor text indicated unsubscribe intent but the URL was a generic tracker redirect.

## Impact

Users relying on `find_unsubscribe_links` and `bulk_find_unsubscribe_opportunities` got false negatives, making the unsubscribe workflow unreliable.
