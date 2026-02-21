# RESOLVED: Bug: Junk Analysis False Positives

**Status:** Fixed
**Fixed in:** Refactor Phase 2.2 (junk detection improvements)
**Resolution:** Removed overly broad patterns from the built-in junk detection rules in `src/proton_mcp/services/junk.py`:
- Removed `admin@.*` sender pattern (flagged legitimate services like Uber)
- Removed `support@.*` sender pattern (flagged legitimate services like Experian)
- Removed `re:.*re:.*re:` subject pattern (flagged normal reply chains)
- Raised exclamation mark threshold from 3 to 10 (most HTML emails exceeded the old threshold)
- Added persistent whitelist/blacklist support so users can customize detection

---

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

The heuristic rules were too broad. All four problematic patterns have been removed or narrowed, and configurable whitelist/blacklist support was added for user customization.
