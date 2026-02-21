# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python MCP (Model Context Protocol) server that provides email functionality for ProtonMail via the Proton Bridge. The server acts as a bridge between AI assistants and ProtonMail, allowing programmatic access to email operations.

## Architecture

The codebase follows a layered package structure under `src/proton_mcp/`:

```
src/proton_mcp/
  config.py          # Config dataclass loaded from env vars
  server.py          # FastMCP server creation and registration
  __main__.py        # Entry point (python -m proton_mcp)
  models/email.py    # Dataclass models (EmailSummary, FullEmail, JunkAnalysis, FilterRule, etc.)
  clients/
    imap.py          # IMAPClient — UID-based IMAP operations (context manager)
    smtp.py          # SMTPClient — SMTP with STARTTLS (context manager)
  services/
    email_ops.py     # EmailService — search, fetch, send, get_recent
    junk.py          # JunkDetector — scoring engine with persistent JSON config
    filter_rules.py  # FilterRuleEngine — CRUD + matching with persistent JSON rules
    unsubscribe.py   # UnsubscribeService — detection, execution, persistent config
    folders.py       # FolderService — create/delete/move via IMAPClient
    bulk.py          # BulkOperations — batched move/mark/delete/get
  tools/             # MCP tool registration (one module per feature area)
    core.py          # search_emails, get_email_content, send_email, get_recent_emails
    junk.py          # filter_junk_emails, analyze_email_for_junk, junk rule CRUD
    filter_rules.py  # create/delete/update filter rules, apply_filter_rules
    folders.py       # create_folder, delete_folder
    bulk.py          # bulk_move/mark/delete/get, move_email_to_folder
    unsubscribe.py   # find/execute unsubscribe, preferences, detection patterns
  resources/         # MCP resource registration (one module per feature area)
    inbox.py         # proton://inbox-summary
    mailboxes.py     # proton://mailboxes
    filter_rules.py  # proton://filter-rules
    junk.py          # proton://junk-config
    unsubscribe.py   # proton://unsubscribe/config, proton://unsubscribe/history
  prompts/           # MCP prompt templates
    create_filter_rule.py  # Filter rule creation guide
    email_triage.py        # Multi-step triage workflow
  utils/
    validation.py    # Input validation (email IDs, folder names)
    mime.py          # MIME header decoding, email body extraction
    json_store.py    # Atomic JSON file persistence with schema versioning
    url_safety.py    # SSRF protection for unsubscribe URLs
```

**Dependency flow:** `config` -> `clients` -> `services` -> `tools/resources/prompts`

**MCP surface area:** 29 tools, 6 resources, 2 prompts

**Key design decisions:**
- All IMAP operations use UIDs (not sequence numbers) to prevent silent data corruption during multi-move operations (fixed from BUG-unstable-email-ids)
- IMAP connections use STARTTLS before login (fixed from BUG-imap-starttls)
- Junk detection removed overly broad `admin@.*` and `support@.*` patterns, raised exclamation threshold (fixed from BUG-junk-false-positives)
- Unsubscribe detection includes anchor-text analysis for tracker-wrapped URLs (fixed from BUG-unsubscribe-detection)
- All persistent configs use JsonStore for atomic file operations with schema versioning

## Development Commands

**Running the Server:**
```bash
source venv/bin/activate
python -m proton_mcp
# or: proton-mcp (after pip install -e .)
```

**Running Tests:**
```bash
source venv/bin/activate
pip install -e . && pip install -r requirements-dev.txt

# All tests
pytest tests/ -v

# Unit tests only (with coverage)
pytest tests/unit/ --cov=src/proton_mcp --cov-report=term-missing

# Integration tests only
pytest tests/integration/ -v
```

**Linting:**
```bash
ruff check .
ruff format --check .
```

**Virtual Environment:**
- Uses Python 3 virtual environment in `venv/` directory
- Package defined in `pyproject.toml` with `pip install -e .`
- Dev dependencies in `requirements-dev.txt` (pytest, pytest-cov, pytest-asyncio)

## Configuration

**Required Environment Variables (.env file):**
- `BRIDGE_IMAP_HOST`: Proton Bridge IMAP host (default: 127.0.0.1)
- `BRIDGE_IMAP_PORT`: Proton Bridge IMAP port (default: 1143)
- `BRIDGE_SMTP_HOST`: Proton Bridge SMTP host (default: 127.0.0.1)
- `BRIDGE_SMTP_PORT`: Proton Bridge SMTP port (default: 1025)
- `PROTON_EMAIL`: Your ProtonMail email address (**required**)
- `PROTON_BRIDGE_PASSWORD`: Proton Bridge application password (**required**)
- `PROTON_DATA_DIR`: Directory for persistent JSON configs (default: package directory)

**Persistent JSON Files (in data_dir):**
- `junk_config.json` — custom junk rules, whitelist/blacklist, thresholds
- `filter_rules.json` — email filtering rules
- `unsubscribe_config.json` — sender preferences, detection patterns, history

## Key Features

**Core Email Operations (4 tools):**
- `search_emails` — IMAP search with optional junk filtering and `include_body` parameter for lightweight mode
- `get_email_content` — Full email retrieval by UID
- `send_email` — Send via SMTP with optional reply-to
- `get_recent_emails` — Time-based search with `include_body` option

**Junk Email Detection (5 tools):**
- Pattern-based scoring with built-in + custom rules (persistent)
- Whitelist/blacklist support (domains and senders)
- Configurable thresholds (low/medium/high)
- Bulk analysis with optional spam folder move

**Unsubscribe Management (8 tools):**
- RFC 2369/8058 header parsing + HTML anchor-text detection
- Tracker-wrapped URL detection (Klaviyo, SendGrid, Mailchimp built-in)
- One-click unsubscribe execution with SSRF protection
- Sender preferences and detection patterns (persistent)

**Filter Rules (4 tools):**
- JSON-based rule CRUD with 9 condition types and 6 action types
- Bulk rule application with chunked processing
- First-match-per-email semantics

**Bulk Operations (6 tools):**
- Batched move/mark/delete/get using UID comma-separated lists
- Deferred expunge pattern for efficiency
- Chunked processing for large volumes

**Folder Management (2 tools):**
- Create/delete IMAP mailboxes

## Dependencies

Key external dependencies:
- `mcp` (FastMCP framework)
- `python-dotenv` (environment variable loading)
- `requests` (HTTP client for unsubscribe functionality)
- Standard library: `imaplib`, `smtplib`, `email`, `re`, `json`, `logging`

## Legacy

The original monolithic `proton-email-server.py` is deprecated and kept for reference only. Use `python -m proton_mcp` or `proton-mcp` instead.
