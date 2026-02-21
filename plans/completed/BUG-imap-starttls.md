# RESOLVED: Bug: IMAP connection fails -- missing STARTTLS before login

**Status:** Fixed
**Fixed in:** Initial commit (09608e9) and confirmed in refactor Phase 2.1
**Resolution:** Added `mail.starttls()` call in `IMAPClient.__enter__()` (`src/proton_mcp/clients/imap.py`). Both IMAP and SMTP clients now negotiate STARTTLS before login. Verified by unit tests in `tests/unit/test_imap_client.py::TestIMAPClientContextManager`.

---

## Summary

`connect_imap()` does not call `mail.starttls()` before `mail.login()`. Proton Bridge on port 1143 requires STARTTLS negotiation before accepting credentials. Without it, login fails with the misleading error `b'no such user'`.

## Root Cause

**File:** `proton-email-server.py`, lines 66-74

```python
def connect_imap(self):
    """Connect to IMAP server"""
    try:
        mail = imaplib.IMAP4(self.imap_host, self.imap_port)
        mail.login(self.email, self.password)  # Fails -- STARTTLS not negotiated
        return mail
    except Exception as e:
        logger.error(f"IMAP connection failed: {e}")
        raise
```

## Impact

All IMAP-dependent tools are non-functional (reading, searching, moving, deleting emails). SMTP (sending) works fine since it already negotiates STARTTLS.
