# Proton MCP Server: Modular Refactor Plan

## Summary

Refactor a 2,500-line monolithic Python MCP server (`proton-email-server.py`) into a modular, testable Python package. The server provides ProtonMail email operations via Proton Bridge (IMAP/SMTP). The refactor will:

- Break the single file into focused modules with clean service boundaries
- Switch from sequence numbers to IMAP UIDs (fixes data corruption bug)
- Reclassify MCP primitives: move read-only listings to resources, static templates to prompts, consolidate duplicate tools
- Add persistent JSON-backed state for junk detection (rules, whitelist) and unsubscribe management (preferences, tracker patterns, history) — matching the existing filter rules pattern
- Fix known bugs and add comprehensive unit + integration tests

## Complexity Assessment

- **Systems affected:** 7 (IMAP client, SMTP client, junk detection, unsubscribe logic, filter rules, bulk operations, MCP tool/resource/prompt layer)
- **Classification:** Complex
- **Reasoning:** 2,500 lines of tightly coupled code with 27 MCP tools, IMAP connection management threaded through everything, known data corruption bug (unstable IDs), and no existing tests. Every change risks breaking the live email workflow.

## Current State Analysis

**File:** `proton-email-server.py` (2,500 lines, single file)

**Class:** `ProtonEmailClient` (~1,493 lines) containing:
- IMAP/SMTP connection management (lines 77-98)
- Email parsing utilities (lines 99-184)
- Single + bulk email retrieval (lines 186-398)
- Email sending (lines 399-421)
- Junk detection heuristics (lines 423-518)
- Folder CRUD operations (lines 520-812)
- Filter rules engine (lines 814-1212)
- Unsubscribe detection + execution (lines 1214-1492)
- Validation helpers (lines 46-75)

**MCP Surface:** 27 tool functions (lines 1499-2482), 1 resource (lines 2484-2495), 0 prompts

**Target MCP Surface:**
- **Tools: 29** (was 27; -5 removed/merged, +7 new CRUD tools)
- **Resources: 6** (was 1; +5 new: mailboxes, filter-rules, junk-config, unsubscribe/config, unsubscribe/history)
- **Prompts: 2** (was 0; create-filter-rule, email-triage)

**Known Bugs:**
1. BUG-imap-starttls -- FIXED in code, but STARTTLS bug doc still present
2. BUG-unstable-email-ids -- Sequence numbers shift on expunge, causes silent data corruption
3. BUG-junk-false-positives -- `admin@`, `support@`, `re:` chain patterns too broad
4. BUG-unsubscribe-detection -- Misses anchor-text-based unsubscribe links (Klaviyo, SendGrid)

**Enhancement:**
1. ENHANCEMENT-lightweight-search -- `include_body=False` parameter to skip body fetching

## Target Architecture

```
proton-mcp/
├── pyproject.toml              # Package config, dependencies, tool configs
├── requirements.txt            # Runtime deps (generated/pinned)
├── requirements-dev.txt        # Dev/test deps
├── .github/workflows/ci.yml   # Updated CI with test step
├── .env.example                # Template environment file
├── CLAUDE.md                   # Updated for new structure
├── README.md                   # Updated docs
├── plans/                      # Project management
│   ├── roadmap.md
│   ├── refactor-plan.md
│   └── completed/
│       └── roadmap-archive.md
│
├── src/
│   └── proton_mcp/
│       ├── __init__.py         # Package init, version
│       ├── __main__.py         # Entry point: `python -m proton_mcp`
│       ├── server.py           # FastMCP server setup, tool/resource/prompt registration
│       ├── config.py           # Configuration management (env vars, defaults, data_dir)
│       │
│       ├── clients/
│       │   ├── __init__.py
│       │   ├── imap.py         # IMAPClient: connection, UID operations, mailbox mgmt
│       │   └── smtp.py         # SMTPClient: connection, send
│       │
│       ├── models/
│       │   ├── __init__.py
│       │   └── email.py        # Data classes: EmailSummary, FullEmail, EmailWithHtml,
│       │                       #   JunkAnalysis, JunkRule, JunkConfig,
│       │                       #   UnsubscribeMethod, UnsubscribePreference,
│       │                       #   DetectionPattern, UnsubscribeHistoryEntry,
│       │                       #   FilterRule
│       │
│       ├── services/
│       │   ├── __init__.py
│       │   ├── email_ops.py    # Core email operations (search, get, send, recent)
│       │   ├── junk.py         # Junk detection engine + JSON-backed config
│       │   ├── unsubscribe.py  # Unsubscribe detection + execution + JSON-backed config
│       │   ├── filter_rules.py # Rule storage, matching, bulk application
│       │   ├── folders.py      # Folder CRUD
│       │   └── bulk.py         # Bulk operations (move, mark, delete, retrieve)
│       │
│       ├── tools/
│       │   ├── __init__.py     # Tool registration helper
│       │   ├── core.py         # search_emails, get_email_content, send_email, get_recent
│       │   ├── junk.py         # filter_junk, analyze_junk, junk config CRUD
│       │   ├── unsubscribe.py  # find_links, unsubscribe, bulk_find, mailing_list_senders,
│       │   │                   #   sender preference CRUD, detection pattern CRUD
│       │   ├── folders.py      # create_folder, delete_folder, move_email
│       │   ├── filter_rules.py # CRUD + apply
│       │   └── bulk.py         # bulk_move, bulk_mark, bulk_delete, bulk_get
│       │
│       ├── resources/
│       │   ├── __init__.py
│       │   ├── inbox.py        # proton://inbox-summary (enriched: unread, folder counts, recent senders)
│       │   ├── mailboxes.py    # proton://mailboxes (folder list)
│       │   ├── filter_rules.py # proton://filter-rules (rule listing)
│       │   ├── junk.py         # proton://junk-config (rules, whitelist, blacklist, thresholds)
│       │   └── unsubscribe.py  # proton://unsubscribe/config, proton://unsubscribe/history
│       │
│       ├── prompts/
│       │   ├── __init__.py
│       │   ├── create_filter_rule.py  # Guided workflow: gather rule details -> call create_filter_rule
│       │   └── email_triage.py        # Multi-step: recent -> filter junk -> find unsub -> summarize
│       │
│       ├── data/
│       │   ├── junk_config.json       # Default junk detection config (shipped with package)
│       │   └── unsubscribe_config.json # Default unsubscribe config (shipped with package)
│       │
│       └── utils/
│           ├── __init__.py
│           ├── json_store.py   # Shared JSON storage: atomic writes, schema versioning, file locking
│           ├── mime.py         # MIME decoding, body extraction, HTML extraction
│           ├── validation.py   # Email ID, folder name, URL validation
│           └── url_safety.py   # SSRF protection for unsubscribe URLs
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Shared fixtures: mock IMAP, mock SMTP, sample emails
│   │
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_config.py
│   │   ├── test_json_store.py
│   │   ├── test_mime.py
│   │   ├── test_validation.py
│   │   ├── test_url_safety.py
│   │   ├── test_imap_client.py
│   │   ├── test_smtp_client.py
│   │   ├── test_email_ops.py
│   │   ├── test_junk.py
│   │   ├── test_unsubscribe.py
│   │   ├── test_filter_rules.py
│   │   ├── test_folders.py
│   │   ├── test_bulk.py
│   │   └── test_models.py
│   │
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── conftest.py         # Integration fixtures (real or mock IMAP server)
│   │   ├── test_imap_flow.py   # Full IMAP connect -> search -> fetch -> move flow
│   │   ├── test_smtp_flow.py   # Full SMTP connect -> send flow
│   │   └── test_tool_e2e.py    # End-to-end MCP tool invocation tests
│   │
│   └── fixtures/
│       ├── sample_emails/      # .eml files for parsing tests
│       ├── sample_html/        # HTML bodies with unsubscribe links
│       ├── sample_rules.json           # Test filter rules
│       ├── sample_junk_config.json     # Test junk detection config
│       └── sample_unsubscribe_config.json  # Test unsubscribe config
│
└── proton-email-server.py      # DEPRECATED: kept temporarily for rollback
```

## Design Decisions

### 1. src Layout
Using `src/proton_mcp/` layout (PEP 517/518 compliant). Prevents accidental imports from the source tree during testing -- tests always import the installed package.

### 2. IMAP UIDs Over Sequence Numbers
All IMAP operations will use `mail.uid()` instead of `mail.fetch()`/`mail.store()`. UIDs are stable within a UIDVALIDITY epoch, solving the silent data corruption bug (BUG-unstable-email-ids).

### 3. Dataclasses for Email Models
Replace raw dicts with typed dataclasses (`EmailSummary`, `FullEmail`, `EmailWithHtml`, `JunkRule`, `JunkConfig`, `UnsubscribePreference`, `DetectionPattern`, `UnsubscribeHistoryEntry`). Enables IDE completion, type checking, and clear contracts between layers.

### 4. Service Layer Pattern
Services depend on clients (IMAP/SMTP) and models. Tools depend on services. No tool should directly touch IMAP. This gives us clean seams for mocking.

### 5. Configuration Object
Replace scattered `os.getenv()` calls with a single `Config` dataclass loaded once at startup. `Config` includes a `data_dir` field -- the directory where JSON config files live (`junk_config.json`, `unsubscribe_config.json`, `filter_rules.json`). Default: same directory as the server script (backward compatible). All three services that use JSON storage reference `Config.data_dir`.

### 6. MCP Primitive Reclassification
Properly use MCP primitives -- tools, resources, and prompts -- based on their semantics:
- **Resources** (read-only context, no parameters): `proton://mailboxes`, `proton://filter-rules`, `proton://junk-config`, `proton://unsubscribe/config`, `proton://unsubscribe/history`, enriched `proton://inbox-summary`
- **Prompts** (user-invoked workflow templates): `create-filter-rule` (guided rule creation), `email-triage` (structured multi-step triage workflow)
- **Tool consolidation**: `search_emails` + `search_emails_filtered` merge into single `search_emails` with `exclude_junk: bool = False`; `apply_filter_rules` + `apply_filter_rules_optimized` merge into single `apply_filter_rules` with optional `chunk_size` parameter (default: 50)

### 7. Persistent State for Junk Detection
Currently 100% stateless with hardcoded regex patterns. Adding JSON-backed configuration (`junk_config.json`) following the same pattern as `filter_rules.json`:
- Custom patterns (field, regex, score, enabled)
- Whitelist (domains, senders) -- checked FIRST, skips scoring entirely
- Blacklist (domains, senders) -- auto-scores high
- Configurable thresholds (low/medium/high)
- Built-in patterns remain as defaults but can be overridden

### 8. Persistent State for Unsubscribe Management
Currently 100% stateless with no record of attempts. Adding JSON-backed configuration (`unsubscribe_config.json`):
- Sender preferences (always_unsubscribe, never_unsubscribe per sender/domain)
- Configurable detection patterns (tracker domains like Klaviyo, SendGrid)
- History log of unsubscribe attempts (sender, method, URL, date, success)
- Can detect re-subscribe (sender in history keeps sending)

### 9. Shared JSON Storage Utility
Filter rules, junk config, and unsubscribe config all follow the same pattern (JSON file, schema version, CRUD, atomic writes). A shared `utils/json_store.py` provides:
- Atomic writes (write to temp file, rename)
- Schema version checking
- File locking for concurrent access
- All three services use this instead of raw `json.load`/`json.dump`

## Dependencies (New)

**Runtime (add to requirements.txt):**
- No new runtime deps needed. Existing: `mcp`, `requests`, `python-dotenv`

**Dev/Test (add to requirements-dev.txt):**
- `pytest>=8.0`
- `pytest-cov>=5.0`
- `pytest-asyncio>=0.24` (if MCP tools use async)

## Assumptions

1. Proton Bridge IMAP server supports UID commands (standard IMAP4rev1 -- confirmed)
2. The MCP `FastMCP` framework supports registering tools, resources, and prompts from multiple modules
3. No async is needed -- current code is synchronous and MCP server handles tool calls sequentially
4. `filter_rules.json` format can be versioned (add a schema version field)
5. JSON config files (`junk_config.json`, `unsubscribe_config.json`) can live alongside `filter_rules.json` in the same `data_dir`
6. Atomic file writes (write to temp + rename) are sufficient for concurrency safety -- no multi-process access expected

## Risks

1. **UID migration breaks existing saved email IDs** -- Any agent that cached sequence-number IDs from a previous session will have invalid references. Mitigation: UIDs are already different numbers, so old IDs would fail cleanly (not silently corrupt). Document the breaking change.
2. **Monolith has implicit coupling** -- Methods call each other freely. Extracting to services may reveal circular dependencies. Mitigation: Map all call chains before extracting (done below).
3. **No test infrastructure exists** -- First tests require building fixtures from scratch. Mitigation: Start with pure-function tests (validation, MIME, junk scoring) that need zero mocking.

## Call Chain Analysis

```
MCP Tools -> ProtonEmailClient methods -> IMAP/SMTP directly

Key internal dependencies:
- search_emails -> connect_imap, get_email_body, decode_mime_words
- get_bulk_emails -> connect_imap, get_email_body, decode_mime_words
- get_bulk_emails_with_html -> connect_imap (duplicates body extraction logic)
- filter_junk_emails (tool) -> search_emails, get_bulk_emails, is_junk_email, bulk_move_emails
- apply_filter_rules -> search_emails, get_bulk_emails, email_matches_rule, bulk_move_emails, bulk_mark_emails
- bulk_find_unsubscribe -> search_emails, get_bulk_emails_with_html, find_unsubscribe_links
- execute_unsubscribe -> _is_safe_url (standalone HTTP)
- move_email_to_folder -> connect_imap (COPY+DELETE+EXPUNGE)
- bulk_move_emails -> connect_imap (batch COPY+DELETE, single EXPUNGE)
```

## Batch Execution Plan

### Batch 0: Foundation (Sequential -- must complete first)
| Phase | Goal | Effort | Depends On |
|-------|------|--------|------------|
| 0.1 | Break upstream, project scaffolding | S | None |
| 0.2 | Package structure + config + entry point | S | 0.1 |
| 0.3 | Test infrastructure + CI update + coverage config | S | 0.2 |
| 0.4 | Create interface contracts for Batch 1 modules | S | 0.3 |

### Batch 1: Pure Extractions (Parallel -- 4 agents, each in own git worktree)
| Phase | Goal | Effort | Depends On |
|-------|------|--------|------------|
| 1.1 | Extract utils: validation, MIME, URL safety, JSON store | S | 0.4 |
| 1.2 | Extract models (dataclasses including junk + unsubscribe config models) | M | 0.4 |
| 1.3 | Extract config module (with data_dir) | S | 0.4 |
| 1.4 | Extract SMTP client | S | 0.4 |

### Batch 2: Core IMAP + Services (Parallel -- 3 agents, each in own git worktree)
| Phase | Goal | Effort | Depends On |
|-------|------|--------|------------|
| 2.1 | Extract IMAP client with UID migration | M | Batch 1 gate, contracts |
| 2.2 | Extract junk detection service + persistent config + fix false positives | M | Batch 1 gate, contracts |
| 2.3 | Extract filter rules service | M | Batch 1 gate, contracts |

### Batch 3: Remaining Services (Parallel -- 3 agents, each in own git worktree)
| Phase | Goal | Effort | Depends On |
|-------|------|--------|------------|
| 3.1 | Extract email operations service | M | Batch 2 gate, contracts |
| 3.2 | Extract unsubscribe service + persistent config + fix detection bug | M | Batch 2 gate, contracts |
| 3.3 | Extract bulk operations service | M | Batch 2 gate, contracts |

### Batch 4: MCP Layer + Integration (Parallel -- 3 agents, each in own git worktree)
| Phase | Goal | Effort | Depends On |
|-------|------|--------|------------|
| 4.1 | Extract MCP tools, resources, and prompts (29 tools + 6 resources + 2 prompts) | M | Batch 3 gate, contracts |
| 4.2 | Extract folder service + tools | S | Batch 3 gate |
| 4.3 | Lightweight search enhancement | S | Batch 3 gate, 4.1 |

### Batch 5: Finalization (Sequential)
| Phase | Goal | Effort | Depends On |
|-------|------|--------|------------|
| 5.1 | Integration tests | M | 4.1, 4.2, 4.3 |
| 5.2 | Documentation, cleanup, deprecation | S | 5.1 |

## Detailed Phases

### Phase 0.1: Break Upstream + Project Scaffolding
- **Tasks:**
  - [ ] Remove upstream git remote (`git remote remove upstream`)
  - [ ] Create `src/proton_mcp/__init__.py` with version string
  - [ ] Create `src/proton_mcp/__main__.py` with entry point
  - [ ] Update `pyproject.toml` with full package metadata, build system, entry points
  - [ ] Add `pytest`, `pytest-cov` to `requirements-dev.txt`
  - [ ] Update `.gitignore` for new structure
- **Effort:** S
- **Done When:** `python -m proton_mcp` imports cleanly (even if it does nothing yet). Old monolith still works.

### Phase 0.2: Package Structure + Config + Entry Point
- **Tasks:**
  - [ ] Create all directories: `clients/`, `models/`, `services/`, `tools/`, `resources/`, `prompts/`, `data/`, `utils/`
  - [ ] Create all `__init__.py` files
  - [ ] Create `config.py` with `Config` dataclass (loads from env, has defaults)
  - [ ] Create `server.py` with FastMCP instantiation
  - [ ] Wire `__main__.py` to create Config -> create server -> run
  - [ ] Verify `python -m proton_mcp` starts (with empty tool set)
- **Effort:** S
- **Done When:** Server starts with `python -m proton_mcp`, logs "ProtonEmailServer started", has zero tools registered.

### Phase 0.3: Test Infrastructure + CI Update + Coverage Config
- **Tasks:**
  - [ ] Create `tests/conftest.py` with basic fixtures (mock Config, temp directories)
  - [ ] Create `tests/fixtures/` directory with sample .eml files (2-3 samples)
  - [ ] Create sample HTML bodies with various unsubscribe patterns
  - [ ] Create `tests/fixtures/sample_rules.json`
  - [ ] Create `tests/fixtures/sample_junk_config.json` (custom patterns, whitelist, blacklist, thresholds)
  - [ ] Create `tests/fixtures/sample_unsubscribe_config.json` (sender preferences, detection patterns, history)
  - [ ] Write a trivial passing test to verify pytest works
  - [ ] Update `.github/workflows/ci.yml` to add pytest step with coverage: `pytest tests/unit/ --cov=src/proton_mcp --cov-fail-under=90`
  - [ ] Update `pyproject.toml` with coverage configuration:
    - `[tool.pytest.ini_options]` with `testpaths = ["tests"]`, `addopts = "--cov=src/proton_mcp --cov-report=term-missing"`
    - `[tool.coverage.run]` with `source = ["src/proton_mcp"]`, `omit = ["proton-email-server.py"]`
    - `[tool.coverage.report]` with `fail_under = 90`
  - [ ] Verify `pytest` runs and passes locally
- **Effort:** S
- **Done When:** `pytest` runs with coverage reporting. CI runs `pytest tests/unit/ --cov --cov-fail-under=90`. All fixtures exist (including junk and unsubscribe config). Coverage excludes old monolith.
- **Files Affected:** `tests/`, `.github/workflows/ci.yml`, `pyproject.toml`

### Phase 0.4: Create Interface Contracts for Batch 1
- **Tasks:**
  - [ ] Create `src/proton_mcp/utils/__init__.py` with stub imports defining the public API:
    - `validation.py`: `validate_email_id(email_id: str) -> str`, `validate_folder_name(folder_name: str) -> str`, `quote_mailbox(name: str) -> str`
    - `mime.py`: `decode_mime_words(text: str) -> str`, `get_email_body(msg: email.message.Message) -> str`, `get_html_body(msg: email.message.Message) -> str`, `get_text_and_html(msg: email.message.Message) -> tuple[str, str]`
    - `url_safety.py`: `is_safe_url(url: str) -> bool`
    - `json_store.py`: `class JsonStore` with `__init__(self, file_path: str, schema_version: int)`, `load() -> dict`, `save(data: dict) -> None`
  - [ ] Create `src/proton_mcp/models/__init__.py` with stub imports for all model classes (`EmailSummary`, `FullEmail`, `EmailWithHtml`, `JunkAnalysis`, `UnsubscribeMethod`, `FilterRule`, `JunkRule`, `JunkConfig`, `UnsubscribePreference`, `DetectionPattern`, `UnsubscribeHistoryEntry`)
  - [ ] Create `src/proton_mcp/clients/__init__.py` with stub imports for `IMAPClient`, `SMTPClient`
  - [ ] Create `src/proton_mcp/services/__init__.py` with stub imports for all service classes (`EmailService`, `JunkDetector`, `UnsubscribeService`, `FilterRuleEngine`, `FolderService`, `BulkOperations`)
  - [ ] Create `src/proton_mcp/config.py` interface: `class Config` with `from_env() -> Config` classmethod, fields: `imap_host`, `imap_port`, `smtp_host`, `smtp_port`, `email`, `password`, `data_dir`
- **Effort:** S
- **Done When:** All `__init__.py` stubs and `config.py` interface exist with correct type annotations. `raise NotImplementedError` in all method bodies. Each agent in Batch 1 can import the interfaces they need.
- **Note:** These are NOT full implementations. Function signatures, class definitions with `pass` or `raise NotImplementedError`, and type annotations only. They define the contracts that all Batch 1 agents must implement.

### Phase 1.1: Extract Utils (Validation, MIME, URL Safety, JSON Store)
- **Worktree:** `../proton-mcp-phase-1.1` (branch: `phase/1.1`)
- **Implements contracts from:** Phase 0.4 (`utils/__init__.py` stubs)
- **Tasks:**
  - [ ] Create `src/proton_mcp/utils/validation.py` -- extract `_validate_email_id()`, `_validate_folder_name()`, `_quote_mailbox()`
  - [ ] Create `src/proton_mcp/utils/mime.py` -- extract `decode_mime_words()`, `get_email_body()`, add `get_html_body()`, `get_text_and_html()`
  - [ ] Create `src/proton_mcp/utils/url_safety.py` -- extract `_is_safe_url()`
  - [ ] Create `src/proton_mcp/utils/json_store.py` -- shared JSON storage utility:
    - `JsonStore` class with `load()`, `save()`, `atomic_write()` methods
    - Atomic writes: write to temp file, then `os.rename()` to target
    - Schema version checking on load (raise on version mismatch)
    - File locking via `fcntl.flock()` for concurrent access safety
    - Used by filter_rules, junk, and unsubscribe services
  - [ ] Write `tests/unit/test_validation.py` (edge cases: empty strings, SQL injection attempts, path traversal)
  - [ ] Write `tests/unit/test_mime.py` (multipart, single-part, encoded headers, empty payloads)
  - [ ] Write `tests/unit/test_url_safety.py` (localhost, private IPs, valid URLs, redirects)
  - [ ] Write `tests/unit/test_json_store.py` (atomic writes, schema version mismatch, file locking, missing file creates default)
  - [ ] All utils must be pure functions or stateless classes (no IMAP/SMTP dependency)
- **Effort:** S
- **Done When:** All 4 util modules have >90% test coverage. No changes to monolith yet.

### Phase 1.2: Extract Models (Dataclasses)
- **Worktree:** `../proton-mcp-phase-1.2` (branch: `phase/1.2`)
- **Implements contracts from:** Phase 0.4 (`models/__init__.py` stubs)
- **Tasks:**
  - [ ] Create `src/proton_mcp/models/email.py` with:
    - `EmailSummary` (id, subject, from_addr, date, body_preview)
    - `FullEmail` (id, subject, from_addr, to_addr, date, body)
    - `EmailWithHtml` (extends FullEmail with html_body, text_body, list_unsubscribe, list_unsubscribe_post)
    - `JunkAnalysis` (is_likely_junk, junk_score, likelihood, indicators, email_id)
    - `UnsubscribeMethod` (type, url/address, method, source, one_click)
    - `FilterRule` (id, name, conditions, actions, enabled, created_at, last_applied, emails_processed)
    - `JunkRule` (id, name, field: subject|sender|body, pattern: regex, score: int, enabled: bool)
    - `JunkConfig` (schema_version, custom_patterns: list[JunkRule], whitelist: dict with domains/senders lists, blacklist: dict with domains/senders lists, thresholds: dict with low/medium/high)
    - `UnsubscribePreference` (domain or sender, action: always_unsubscribe|never_unsubscribe)
    - `DetectionPattern` (id, name, pattern: regex, type: tracker_domain, enabled: bool)
    - `UnsubscribeHistoryEntry` (sender, method, url, date, success: bool)
  - [ ] Add `to_dict()` and `from_dict()` methods for JSON serialization
  - [ ] Write `tests/unit/test_models.py` (including round-trip serialization for all config models)
- **Effort:** M
- **Done When:** All models import cleanly, have type annotations, serialize/deserialize correctly. Config models round-trip through JSON.

### Phase 1.3: Extract Config Module
- **Worktree:** `../proton-mcp-phase-1.3` (branch: `phase/1.3`)
- **Implements contracts from:** Phase 0.4 (`config.py` interface)
- **Tasks:**
  - [ ] Create `src/proton_mcp/config.py` with `Config` dataclass
  - [ ] Fields: imap_host, imap_port, smtp_host, smtp_port, email, password, rules_file, data_dir
  - [ ] `data_dir` field: directory where JSON config files live (`junk_config.json`, `unsubscribe_config.json`, `filter_rules.json`). Default: same directory as the server script (backward compatible).
  - [ ] Factory method: `Config.from_env()` that calls `load_dotenv()` and reads env vars
  - [ ] Validation: raise on missing email/password
  - [ ] Write `tests/unit/test_config.py` (default values, env override, missing credentials error, data_dir resolution)
- **Effort:** S
- **Done When:** `Config.from_env()` works, `data_dir` resolves correctly, tests pass, no `os.getenv` calls remain in any other new module.

### Phase 1.4: Extract SMTP Client
- **Worktree:** `../proton-mcp-phase-1.4` (branch: `phase/1.4`)
- **Implements contracts from:** Phase 0.4 (`clients/__init__.py` stubs)
- **Tasks:**
  - [ ] Create `src/proton_mcp/clients/smtp.py` with `SMTPClient` class
  - [ ] Constructor takes `Config`
  - [ ] `connect()` method: SMTP + STARTTLS + login
  - [ ] `send_email(to, subject, body, reply_to_id=None)` method
  - [ ] Context manager support for connection lifecycle
  - [ ] Write `tests/unit/test_smtp_client.py` with mock SMTP server
- **Effort:** S
- **Done When:** SMTP client sends email in tests with mocked SMTP. Monolith untouched.

### Phase 2.1: Extract IMAP Client with UID Migration
- **Worktree:** `../proton-mcp-phase-2.1` (branch: `phase/2.1`)
- **Implements contracts from:** Batch 1 gate (updated `clients/__init__.py`)
- **Tasks:**
  - [ ] Create `src/proton_mcp/clients/imap.py` with `IMAPClient` class
  - [ ] Constructor takes `Config`
  - [ ] `connect()` method: IMAP4 + STARTTLS + login
  - [ ] Context manager: auto-selects mailbox, auto-close+logout on exit
  - [ ] ALL operations use `mail.uid()` instead of sequence numbers (BUG-unstable-email-ids fix)
  - [ ] Methods: `search(query, mailbox)`, `fetch_one(uid, mailbox)`, `fetch_batch(uids, mailbox)`, `copy(uids, target)`, `store_flags(uids, flags, action)`, `expunge()`, `list_mailboxes()`, `create_mailbox(name)`, `delete_mailbox(name)`
  - [ ] Deferred expunge pattern for bulk operations
  - [ ] Write `tests/unit/test_imap_client.py` with mock imaplib
  - [ ] Test UID stability: mock a sequence of operations and verify no ID shifting
- **Effort:** M
- **Done When:** IMAP client passes all tests using UIDs. Every operation uses `mail.uid()`. Context manager handles cleanup. Monolith still works independently.
- **Critical bug fixed:** BUG-unstable-email-ids

### Phase 2.2: Extract Junk Detection Service + Persistent Config + Fix False Positives
- **Worktree:** `../proton-mcp-phase-2.2` (branch: `phase/2.2`)
- **Implements contracts from:** Batch 1 gate (updated `services/__init__.py` for `JunkDetector`)
- **Tasks:**
  - [ ] Create `src/proton_mcp/services/junk.py` with `JunkDetector` class
  - [ ] Extract `is_junk_email()` logic
  - [ ] Add `load_config()` and `save_config()` methods using `JsonStore` utility
  - [ ] Create `src/proton_mcp/data/junk_config.json` with default config:
    ```json
    {
      "schema_version": 1,
      "custom_patterns": [],
      "whitelist": {"domains": [], "senders": []},
      "blacklist": {"domains": [], "senders": []},
      "thresholds": {"low": 1, "medium": 2, "high": 4}
    }
    ```
  - [ ] Whitelist check happens FIRST -- whitelisted senders/domains skip scoring entirely
  - [ ] Blacklist entries auto-score high
  - [ ] Custom patterns evaluated alongside built-in patterns
  - [ ] Built-in patterns remain as defaults but can be overridden
  - [ ] Thresholds are configurable via config
  - [ ] FIX BUG-junk-false-positives:
    - Remove `admin@.*` and `support@.*` sender patterns
    - Remove or raise threshold for `re:.*re:.*re:` pattern
    - Raise exclamation mark threshold from 3 to 10+
    - Consider header-based signals (SPF/DKIM indicators if available)
  - [ ] Return `JunkAnalysis` model instead of raw dict
  - [ ] Write `tests/unit/test_junk.py` with:
    - Known spam samples (should detect)
    - Known legitimate samples that previously false-positived (Uber admin@, Experian support@, mortgage re: chains)
    - Whitelist bypass (whitelisted sender skips scoring)
    - Blacklist auto-score (blacklisted domain scores high)
    - Custom pattern evaluation
    - Configurable threshold tests
    - Edge cases (empty emails, very long subjects)
- **Effort:** M
- **Done When:** All BUG-junk-false-positives test cases pass. False positive rate for documented cases = 0. Config loads/saves via JsonStore. Whitelist/blacklist logic verified.

### Phase 2.3: Extract Filter Rules Service
- **Worktree:** `../proton-mcp-phase-2.3` (branch: `phase/2.3`)
- **Implements contracts from:** Batch 1 gate (updated `services/__init__.py` for `FilterRuleEngine`)
- **Tasks:**
  - [ ] Create `src/proton_mcp/services/filter_rules.py` with `FilterRuleEngine` class
  - [ ] Extract: `load_filter_rules()`, `save_filter_rules()`, `create_filter_rule()`, `delete_filter_rule()`, `update_filter_rule()`, `email_matches_rule()`, `apply_rule_actions()`
  - [ ] Migrate to `JsonStore` utility for atomic writes and schema versioning
  - [ ] Use `FilterRule` model
  - [ ] File path resolved via `Config.data_dir`
  - [ ] Dependency: takes IMAPClient for move/mark operations
  - [ ] Write `tests/unit/test_filter_rules.py` with:
    - Rule CRUD (create, list, update, delete)
    - Matching logic for each condition type
    - Action execution (mocked IMAP)
    - Duplicate rule name rejection
    - Invalid condition/action rejection
- **Effort:** M
- **Done When:** All rule CRUD and matching tests pass. Rules file uses JsonStore with schema version.

### Phase 3.1: Extract Email Operations Service
- **Worktree:** `../proton-mcp-phase-3.1` (branch: `phase/3.1`)
- **Implements contracts from:** Batch 2 gate (updated `services/__init__.py` for `EmailService`)
- **Tasks:**
  - [ ] Create `src/proton_mcp/services/email_ops.py` with `EmailService` class
  - [ ] Extract: `search_emails()`, `get_full_email()`, `send_email()`, `get_recent_emails()`
  - [ ] Depends on: `IMAPClient`, `SMTPClient`, MIME utils
  - [ ] Returns model objects (`EmailSummary`, `FullEmail`)
  - [ ] ENHANCEMENT: Add `include_body: bool = True` parameter to `search_emails()` (ENHANCEMENT-lightweight-search)
  - [ ] Write `tests/unit/test_email_ops.py`
- **Effort:** M
- **Done When:** Core email operations work through service layer with mocked clients. Lightweight search enhancement implemented.
- **Enhancement addressed:** ENHANCEMENT-lightweight-search

### Phase 3.2: Extract Unsubscribe Service + Persistent Config + Fix Detection Bug
- **Worktree:** `../proton-mcp-phase-3.2` (branch: `phase/3.2`)
- **Implements contracts from:** Batch 2 gate (updated `services/__init__.py` for `UnsubscribeService`)
- **Tasks:**
  - [ ] Create `src/proton_mcp/services/unsubscribe.py` with `UnsubscribeService` class
  - [ ] Extract: `find_unsubscribe_links()`, `execute_unsubscribe()`
  - [ ] Add `load_config()`, `save_config()`, `log_attempt()` methods using `JsonStore` utility
  - [ ] Create `src/proton_mcp/data/unsubscribe_config.json` with default config:
    ```json
    {
      "schema_version": 1,
      "sender_preferences": [],
      "detection_patterns": [
        {"id": "builtin-klaviyo", "name": "Klaviyo tracker", "pattern": "ctrk\\.klclick\\.com", "type": "tracker_domain", "enabled": true},
        {"id": "builtin-sendgrid", "name": "SendGrid tracker", "pattern": "ct\\.sendgrid\\.net", "type": "tracker_domain", "enabled": true}
      ],
      "history": []
    }
    ```
  - [ ] `find_unsubscribe_links()` uses configurable `detection_patterns` alongside built-in patterns
  - [ ] `execute_unsubscribe()` logs attempts to history automatically via `log_attempt()`
  - [ ] `bulk_find_unsubscribe_opportunities()` skips senders with `never_unsubscribe` preference and flags senders with `always_unsubscribe`
  - [ ] Add re-subscribe detection: flag senders in history that keep sending
  - [ ] FIX BUG-unsubscribe-detection:
    - Add anchor-text-based link detection (look for link text containing "unsubscribe", "opt out", "no longer receive", "click here" near unsubscribe context)
    - Handle tracker-wrapped URLs (Klaviyo `ctrk.klclick.com`, SendGrid `ct.sendgrid.net`)
    - Add surrounding-text pattern matching
  - [ ] Return `UnsubscribeMethod` models
  - [ ] Write `tests/unit/test_unsubscribe.py` with:
    - RFC 2369 List-Unsubscribe header parsing
    - RFC 8058 one-click detection
    - Klaviyo HTML body (anchor text says "click here", URL is tracker)
    - SendGrid HTML body (anchor text says "here", context says "to unsubscribe")
    - URL-based detection (existing patterns)
    - SSRF protection (URL safety integration)
    - Deduplication
    - Sender preference filtering (never_unsubscribe skipped, always_unsubscribe flagged)
    - History logging (attempt recorded after execute)
    - Re-subscribe detection
- **Effort:** M
- **Done When:** BUG-unsubscribe-detection test cases pass (Klaviyo + SendGrid samples detected). Existing header-based detection still works. Config loads/saves via JsonStore. Sender preferences and history logging verified.

### Phase 3.3: Extract Bulk Operations Service
- **Worktree:** `../proton-mcp-phase-3.3` (branch: `phase/3.3`)
- **Implements contracts from:** Batch 2 gate (updated `services/__init__.py` for `BulkOperations`)
- **Tasks:**
  - [ ] Create `src/proton_mcp/services/bulk.py` with `BulkOperations` class
  - [ ] Extract: `get_bulk_emails()`, `get_bulk_emails_with_html()`, `bulk_move_emails()`, `bulk_mark_emails()`, `bulk_delete_emails()`
  - [ ] Merge `apply_filter_rules()` + `apply_filter_rules_optimized()` into single `apply_filter_rules()` with optional `chunk_size` parameter (default: 50)
  - [ ] Uses UID-based operations from IMAPClient
  - [ ] Deferred expunge for all batch operations
  - [ ] Write `tests/unit/test_bulk.py` with:
    - Batch move (verify single expunge at end)
    - Batch mark (read/important flags)
    - Fallback to individual on batch failure
    - Chunked processing for large volumes
    - Merged apply_filter_rules with/without chunk_size
- **Effort:** M
- **Done When:** All bulk operations work with UID-based IMAP client. Deferred expunge pattern verified in tests. Single `apply_filter_rules` handles both chunked and non-chunked modes.

### Phase 4.1: Extract MCP Tools, Resources, and Prompts
- **Worktree:** `../proton-mcp-phase-4.1` (branch: `phase/4.1`)
- **Tasks:**
  - [ ] **Tool consolidation:**
    - Merge `search_emails` + `search_emails_filtered` into single `search_emails` with `exclude_junk: bool = False` parameter
    - Merge `apply_filter_rules` + `apply_filter_rules_optimized` into single `apply_filter_rules` with optional `chunk_size` parameter (default: 50)
    - Remove `get_filter_rule_examples` as tool (becomes a prompt)
    - Remove `get_mailboxes` as tool (becomes a resource)
    - Remove `list_filter_rules` as tool (becomes a resource)
  - [ ] **Tools (29 total):**
    - `src/proton_mcp/tools/core.py` -- 4 tools: search_emails (with exclude_junk), get_email_content, send_email, get_recent_emails
    - `src/proton_mcp/tools/junk.py` -- 5 tools: filter_junk_emails, analyze_email_for_junk, create_junk_rule, update_junk_rule, delete_junk_rule
    - `src/proton_mcp/tools/unsubscribe.py` -- 8 tools: find_unsubscribe_links, unsubscribe_from_email, bulk_find_unsubscribe_opportunities, get_mailing_list_senders, add_sender_preference, remove_sender_preference, add_detection_pattern, remove_detection_pattern
    - `src/proton_mcp/tools/folders.py` -- 2 tools: create_folder, delete_folder
    - `src/proton_mcp/tools/filter_rules.py` -- 4 tools: create_filter_rule, delete_filter_rule, update_filter_rule, apply_filter_rules (with chunk_size)
    - `src/proton_mcp/tools/bulk.py` -- 6 tools: bulk_move_emails, bulk_mark_emails_as_read, bulk_mark_emails_as_important, bulk_delete_emails, bulk_get_emails, move_email_to_folder
  - [ ] **Resources (6 total):**
    - `src/proton_mcp/resources/inbox.py` -- `proton://inbox-summary` (enriched: unread count, folder counts, recent senders)
    - `src/proton_mcp/resources/mailboxes.py` -- `proton://mailboxes` (folder list)
    - `src/proton_mcp/resources/filter_rules.py` -- `proton://filter-rules` (rule listing)
    - `src/proton_mcp/resources/junk.py` -- `proton://junk-config` (rules, whitelist, blacklist, thresholds)
    - `src/proton_mcp/resources/unsubscribe.py` -- `proton://unsubscribe/config` (sender preferences, detection patterns) + `proton://unsubscribe/history` (attempt history)
  - [ ] **Prompts (2 total):**
    - `src/proton_mcp/prompts/create_filter_rule.py` -- guided workflow: show examples, gather rule details, call create_filter_rule
    - `src/proton_mcp/prompts/email_triage.py` -- multi-step workflow: get recent -> filter junk -> find unsubscribe opportunities -> summarize
  - [ ] Wire all tool, resource, and prompt modules into `server.py`
  - [ ] Tool functions are thin: validate input -> call service -> format response
  - [ ] Verify all 29 tools + 6 resources + 2 prompts register correctly with FastMCP
- **Effort:** M
- **Done When:** `python -m proton_mcp` starts and all 29 tools, 6 resources, and 2 prompts are registered. Each module imports only from services.

### Phase 4.2: Extract Folder Service + Tools
- **Worktree:** `../proton-mcp-phase-4.2` (branch: `phase/4.2`)
- **Tasks:**
  - [ ] Create `src/proton_mcp/services/folders.py` with `FolderService` class
  - [ ] Extract: `get_mailbox_list()`, `create_folder()`, `delete_folder()`, `move_email_to_folder()`
  - [ ] Uses `IMAPClient`
  - [ ] Write `tests/unit/test_folders.py`
- **Effort:** S
- **Done When:** Folder operations work through service with mocked IMAP client.

### Phase 4.3: Lightweight Search Enhancement
- **Worktree:** `../proton-mcp-phase-4.3` (branch: `phase/4.3`)
- **Tasks:**
  - [ ] Add `include_body: bool = True` parameter to consolidated `search_emails` MCP tool
  - [ ] When `False`, use IMAP FETCH for headers only (ENVELOPE or BODY[HEADER])
  - [ ] Write tests for both modes (with body, without body, combined with exclude_junk)
- **Effort:** S
- **Done When:** `search_emails(include_body=False)` returns results without body, significantly faster. Works correctly with `exclude_junk` parameter.

### Phase 5.1: Integration Tests
- **Tasks:**
  - [ ] Create `tests/integration/conftest.py` with integration test markers and fixtures
  - [ ] Create `tests/integration/test_imap_flow.py` -- full connect -> search -> fetch -> move flow with mock IMAP
  - [ ] Create `tests/integration/test_smtp_flow.py` -- full send flow with mock SMTP
  - [ ] Create `tests/integration/test_tool_e2e.py` -- invoke MCP tools through FastMCP test client
  - [ ] Create `tests/integration/test_resources_e2e.py` -- invoke MCP resources through FastMCP test client
  - [ ] Create `tests/integration/test_prompts_e2e.py` -- invoke MCP prompts through FastMCP test client
  - [ ] Verify all 29 tools, 6 resources, and 2 prompts work end-to-end with mocked backends
  - [ ] Add integration test target to CI
- **Effort:** M
- **Done When:** Integration tests cover all tools, resources, and prompts. CI runs both unit and integration tests.

### Phase 5.2: Documentation + Cleanup + Deprecation
- **Tasks:**
  - [ ] Update `CLAUDE.md` to reflect new module structure
  - [ ] Update `README.md` with new installation/usage (package install vs script)
  - [ ] Archive bug files (BUG-*.md) -- move to `plans/completed/` with resolution notes
  - [ ] Archive enhancement file (ENHANCEMENT-*.md) -- move to `plans/completed/`
  - [ ] Remove or rename old `proton-email-server.py` (keep as `proton-email-server.py.deprecated` for one release)
  - [ ] Ensure `pyproject.toml` has proper entry point: `proton-mcp = "proton_mcp.__main__:main"`
  - [ ] Final CI run: lint + typecheck + test + security scan all pass
- **Effort:** S
- **Done When:** Old monolith is gone. New package structure is the only way to run the server. All CI checks pass. Bug/enhancement docs archived.

---

## Critical Path

```
0.1 -> 0.2 -> 0.3 -> 0.4 -> [Batch 1 gate] -> [Batch 2 gate] -> [Batch 3 gate] -> [Batch 4 gate] -> 5.1 -> 5.2
                       |         |                   |                  |                  |
                       |    1.1  1.2  1.3  1.4  2.1  2.2  2.3    3.1  3.2  3.3    4.1  4.2  4.3
                       |    (parallel)           (parallel)        (parallel)       (parallel)
                       |
                       └── contracts created before each batch
```

The IMAP client extraction (2.1) is the bottleneck -- it blocks all services that need IMAP access. Prioritize it. Each verification gate also updates interface contracts for the next batch.

## Parallelization Strategy

- **Batch 0:** Sequential, 1 agent. Foundation work + interface contracts that everything depends on.
- **Batch 1:** 4 agents in parallel (git worktrees). Pure extractions with no cross-dependencies. Agents code against Phase 0.4 contracts.
- **Batch 2:** 3 agents in parallel (git worktrees). Each depends only on Batch 1 gate + updated contracts.
- **Batch 3:** 3 agents in parallel (git worktrees). Each depends on Batch 2 gate + updated contracts.
- **Batch 4:** 3 agents in parallel (git worktrees). Depends on Batch 3 gate + updated contracts. Phase 4.1 is the largest (29 tools + 6 resources + 2 prompts).
- **Batch 5:** Sequential. Final integration and cleanup.

Estimated total: 18 phases. With parallelization: ~8-9 sequential work segments (including verification gates).
At 15 minutes per segment: ~2-2.5 hours of focused work.

## Agent Execution Protocol

### Git Worktrees for Parallel Agents

Each parallel agent in a batch gets its own git worktree (branch), eliminating file conflicts entirely. No file ownership rules needed -- agents work in isolated directory trees.

**Execution protocol for each parallel batch:**
1. Orchestrator creates one worktree per agent: `git worktree add ../proton-mcp-phase-X.Y phase/X.Y` (branched from main)
2. Each agent receives the worktree path as its working directory
3. Agent does all work in its worktree, commits when done
4. After ALL agents in the batch complete, orchestrator merges all branches back to main sequentially
5. Orchestrator runs verification gate (tests + coverage) on main after merge
6. Worktrees are cleaned up: `git worktree remove ../proton-mcp-phase-X.Y`

**Branch naming:** `phase/X.Y` (e.g., `phase/1.1`, `phase/1.2`, `phase/2.1`)

**Merge strategy:** Since parallel phases in the same batch touch different files/directories, merges should be clean. If conflicts arise, the orchestrator resolves them before proceeding to the verification gate.

**Example -- Batch 1 (4 parallel agents):**
```bash
# Orchestrator creates worktrees
git worktree add ../proton-mcp-phase-1.1 phase/1.1
git worktree add ../proton-mcp-phase-1.2 phase/1.2
git worktree add ../proton-mcp-phase-1.3 phase/1.3
git worktree add ../proton-mcp-phase-1.4 phase/1.4

# Agents work in parallel in their worktrees...

# After all complete, orchestrator merges
git merge phase/1.1
git merge phase/1.2
git merge phase/1.3
git merge phase/1.4

# Run verification gate on merged main
pytest tests/unit/ --cov=src/proton_mcp --cov-fail-under=90

# Clean up
git worktree remove ../proton-mcp-phase-1.1
git worktree remove ../proton-mcp-phase-1.2
git worktree remove ../proton-mcp-phase-1.3
git worktree remove ../proton-mcp-phase-1.4
```

### Interface Contracts Before Each Batch

Before any parallel batch starts, the orchestrator creates interface stubs/contracts that define the public API of each module being created in that batch. This ensures all agents code against the same signatures.

**Contract creation cadence:**
- **Phase 0.4** creates contracts for Batch 1 outputs (utils, models, config, SMTP client)
- **Before Batch 2** starts, orchestrator updates contracts for Batch 2 outputs (IMAP client methods, JunkDetector API, FilterRuleEngine API) -- done as a step in the Batch 1 verification gate
- **Before Batch 3** starts, same pattern for Batch 3 outputs
- **Before Batch 4** starts, same pattern for Batch 4 outputs

Contracts are NOT full implementations -- just function signatures, class definitions with `pass` or `raise NotImplementedError`, and type annotations. They define the interfaces that all agents must implement.

## Verification Gates

Each batch has a verification gate that runs on the merged main branch after all agents in the batch have been merged back. No batch proceeds until its gate passes.

**Gate protocol:**
1. `pytest tests/unit/ --cov=src/proton_mcp --cov-fail-under=90 --cov-report=term-missing` -- all tests pass, 90% minimum coverage for new code
2. Coverage exclusion: `proton-email-server.py` is excluded from coverage requirements (it is the old monolith being deprecated)
3. Import smoke test: `python -c "from proton_mcp import ..."` for all modules created in that batch
4. If any gate fails, fix before proceeding to next batch
5. Update interface contracts for the next batch's outputs (if applicable)

**Per-batch gate specifics:**

| Gate | Criteria |
|------|----------|
| After Batch 0 | `pytest` runs green (trivial test), package imports |
| After Batch 1 | Utils, models, config, SMTP client all have >90% coverage. `python -c "from proton_mcp.utils.validation import validate_email_id; from proton_mcp.models.email import EmailSummary; from proton_mcp.config import Config; from proton_mcp.clients.smtp import SMTPClient"` |
| After Batch 2 | IMAP client, junk detector, filter rules all have >90% coverage. All Batch 1 tests still pass. |
| After Batch 3 | Email ops, unsubscribe, bulk ops all have >90% coverage. All previous tests still pass. |
| After Batch 4 | All 29 tools, 6 resources, 2 prompts register. All previous tests still pass. |
| After Batch 5 | Integration tests pass. Full coverage report generated. |

## Testing Strategy

### Unit Tests
- Mock `imaplib.IMAP4` and `smtplib.SMTP` at the client boundary
- Pure functions (validation, MIME, junk scoring) need no mocking
- Use sample `.eml` files from `tests/fixtures/` for parsing tests
- Each service gets its own test file with mocked client dependencies

### Integration Tests
- Use a higher-level mock that simulates IMAP server state (message store, mailbox list)
- Test full workflows: search -> fetch -> analyze -> move
- Test FastMCP tool, resource, and prompt registration and invocation using MCP test utilities
- Test JSON config persistence: create config -> restart -> verify config loaded

### Coverage Target
- Unit tests: 90%+ coverage per module
- Integration tests: Cover every MCP tool, resource, and prompt at least once
- CI enforces coverage thresholds

## Suggested First Action

Start with Phase 0.1: Break the upstream remote and set up the package scaffolding. This is a clean 15-minute task that establishes the foundation for everything else.

```bash
# Break upstream
git remote remove upstream

# Create package structure
mkdir -p src/proton_mcp/{clients,models,services,tools,resources,prompts,data,utils}
mkdir -p tests/{unit,integration,fixtures/sample_emails,fixtures/sample_html}

# Create initial files
touch src/proton_mcp/__init__.py
touch src/proton_mcp/__main__.py
```
