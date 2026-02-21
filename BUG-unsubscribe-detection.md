# BUG: find_unsubscribe_links Fails to Detect In-Body Unsubscribe Links

## Problem

The `find_unsubscribe_links` tool returns zero unsubscribe methods for emails that clearly contain unsubscribe links in their HTML body. Tested against 5 Blissy emails — all had visible unsubscribe links, all returned `total_methods: 0`.

## Test Cases

### Klaviyo-sent emails (support@blissy.com)
- Body contains: `If you'd no longer like to receive emails, <a href="https://ctrk.klclick.com/...">click here</a>`
- Tool result: `unsubscribe_methods: [], total_methods: 0`

### SendGrid-sent emails (reviews@stamped.io)
- Body contains: `To unsubscribe click <a href="https://u2081612.ct.sendgrid.net/...">here</a>`
- Tool result: `unsubscribe_methods: [], total_methods: 0`

## Likely Cause

The tool may only be checking for:
- `List-Unsubscribe` IMAP headers (RFC 2369)
- Links with "unsubscribe" in the URL path

It's missing:
- Links where the anchor text says "unsubscribe" or "click here" but the URL is a generic tracker (Klaviyo, SendGrid)
- Surrounding text patterns like "no longer like to receive" or "to unsubscribe click"
- Links wrapped in tracking redirects where "unsubscribe" doesn't appear in the href

## Expected Behavior

The tool should scan the HTML body for:
1. `List-Unsubscribe` header (already working?)
2. Anchor tags where the **link text** contains "unsubscribe", "opt out", "no longer receive", etc.
3. Anchor tags where the **href** contains "unsubscribe", "opt-out", etc.
4. Text near a link that indicates unsubscribe intent (e.g., "If you'd no longer like to receive emails, [link]")

## Impact

Users relying on `find_unsubscribe_links` and `bulk_find_unsubscribe_opportunities` get false negatives, making the unsubscribe workflow unreliable. During triage, manually reading email bodies was required to find unsubscribe links the tool missed.
