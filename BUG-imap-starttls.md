# Bug: IMAP connection fails — missing STARTTLS before login

## Summary

`connect_imap()` does not call `mail.starttls()` before `mail.login()`. Proton Bridge on port 1143 requires STARTTLS negotiation before accepting credentials. Without it, login fails with the misleading error `b'no such user'`.

## Root Cause

**File:** `proton-email-server.py`, lines 66-74

```python
def connect_imap(self):
    """Connect to IMAP server"""
    try:
        mail = imaplib.IMAP4(self.imap_host, self.imap_port)
        mail.login(self.email, self.password)  # Fails — STARTTLS not negotiated
        return mail
    except Exception as e:
        logger.error(f"IMAP connection failed: {e}")
        raise
```

`connect_smtp()` (lines 76-85) already correctly calls `server.starttls()` before login:

```python
def connect_smtp(self):
    """Connect to SMTP server"""
    try:
        server = smtplib.SMTP(self.smtp_host, self.smtp_port)
        server.starttls()  # Correct
        server.login(self.email, self.password)
        return server
```

## Steps to Reproduce

1. Configure the MCP server with valid Proton Bridge credentials
2. Ensure Proton Bridge is running on port 1143 (IMAP) with STARTTLS required
3. Call any tool that triggers an IMAP connection (e.g., `get_mailboxes()`)
4. Observe error: `b'no such user'`

## Environment

- Proton Bridge (Flatpak: `ch.protonmail.protonmail-bridge`)
- IMAP port: 1143 (STARTTLS)
- SMTP port: 1025 (STARTTLS — works correctly)
- Python `imaplib`

## Proposed Fix

Add `mail.starttls()` between connection and login, matching the SMTP pattern:

```python
def connect_imap(self):
    """Connect to IMAP server"""
    try:
        mail = imaplib.IMAP4(self.imap_host, self.imap_port)
        mail.starttls()
        mail.login(self.email, self.password)
        return mail
    except Exception as e:
        logger.error(f"IMAP connection failed: {e}")
        raise
```

## Impact

All IMAP-dependent tools are non-functional (reading, searching, moving, deleting emails). SMTP (sending) works fine since it already negotiates STARTTLS.
