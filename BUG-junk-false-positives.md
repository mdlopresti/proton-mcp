# BUG: Junk Analysis False Positives

## Summary

The `filter_junk_emails` and `analyze_email_for_junk` tools use regex-based heuristics that produce frequent false positives on legitimate emails.

## Observed False Positives (2025-10-08 triage)

| Email ID | From | Subject | Flagged Indicator | Why It's Wrong |
|----------|------|---------|-------------------|----------------|
| 2429 | bills@vilo.network | Re: RE: RE: Closing Disclosure... | `re:.*re:.*re:` subject pattern | User's own sent email (mortgage closing) |
| 2438 | support@s.usa.experian.com | Your monthly account statement | `support@.*` sender pattern | Legitimate Experian credit monitoring |
| 2408 | admin@uber.com | Your Uber account verification code | `admin@.*` sender pattern | Legitimate Uber 2FA code |
| 2406 | admin@uber.com | Your Uber account password was updated | `admin@.*` sender pattern | Legitimate Uber security notification |

## Root Cause

The heuristic rules are too broad:

1. **`admin@.*` pattern** flags all `admin@` senders as suspicious. Many legitimate services (Uber, etc.) use `admin@` for transactional emails.
2. **`support@.*` pattern** flags all `support@` senders. Experian and many financial services use `support@` prefixes.
3. **`re:.*re:.*re:` pattern** flags deep reply chains as suspicious. Legitimate email threads (especially forwarded mortgage docs) hit this.
4. **Exclamation mark counting** flags nearly every HTML marketing email. Not useful for distinguishing junk from newsletters/promos.

## Suggested Fixes

- Remove or significantly narrow `admin@.*` and `support@.*` patterns
- Remove the `re:` chain pattern or increase the threshold
- Consider a whitelist for known legitimate sender domains
- Exclamation mark threshold is too low — most HTML emails exceed it
- Consider replacing heuristics with header-based signals (SPF/DKIM pass, List-Unsubscribe presence, etc.)
