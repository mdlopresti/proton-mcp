# Roadmap

## Batch 0 (Current) -- Foundation

### Phase 0.1: Break Upstream + Project Scaffolding
- **Status:** ⚪ Not Started
- **Tasks:**
  - [ ] Remove upstream git remote (`git remote remove upstream`)
  - [ ] Create `src/proton_mcp/__init__.py` with version string
  - [ ] Create `src/proton_mcp/__main__.py` with entry point stub
  - [ ] Update `pyproject.toml` with full package metadata, build system, entry points
  - [ ] Add `pytest`, `pytest-cov` to `requirements-dev.txt`
  - [ ] Update `.gitignore` for new structure (`src/`, `.pytest_cache/`, `htmlcov/`, etc.)
- **Effort:** S
- **Done When:** `python -c "from proton_mcp import __version__"` works. Upstream remote removed. Old monolith untouched.
- **Plan:** [plans/refactor-plan.md](refactor-plan.md)

### Phase 0.2: Package Structure + Config + Entry Point
- **Status:** ⚪ Not Started
- **Tasks:**
  - [ ] Create all subdirectories: `clients/`, `models/`, `services/`, `tools/`, `resources/`, `prompts/`, `data/`, `utils/`
  - [ ] Create all `__init__.py` files
  - [ ] Create `config.py` with `Config` dataclass (loads from env, has defaults)
  - [ ] Create `server.py` with FastMCP instantiation
  - [ ] Wire `__main__.py` to create Config -> create server -> run
  - [ ] Verify `python -m proton_mcp` starts with zero tools
- **Effort:** S
- **Done When:** Server starts with `python -m proton_mcp`, logs startup message, has zero tools registered.

### Phase 0.3: Test Infrastructure + CI Update + Coverage Config
- **Status:** ⚪ Not Started
- **Tasks:**
  - [ ] Create `tests/conftest.py` with basic fixtures (mock Config, temp dirs)
  - [ ] Create `tests/fixtures/` with sample .eml files (2-3 samples)
  - [ ] Create sample HTML bodies with unsubscribe patterns (Klaviyo, SendGrid, RFC 2369)
  - [ ] Create `tests/fixtures/sample_rules.json`
  - [ ] Create `tests/fixtures/sample_junk_config.json` (custom patterns, whitelist, blacklist, thresholds)
  - [ ] Create `tests/fixtures/sample_unsubscribe_config.json` (sender preferences, detection patterns, history)
  - [ ] Write a trivial passing test
  - [ ] Update `.github/workflows/ci.yml` to add pytest step with coverage: `pytest tests/unit/ --cov=src/proton_mcp --cov-fail-under=90`
  - [ ] Update `pyproject.toml` with coverage configuration:
    - `[tool.pytest.ini_options]` with `testpaths`, `addopts = "--cov=src/proton_mcp --cov-report=term-missing"`
    - `[tool.coverage.run]` with `source = ["src/proton_mcp"]`, `omit = ["proton-email-server.py"]`
    - `[tool.coverage.report]` with `fail_under = 90`
  - [ ] Verify `pytest` runs and passes locally
- **Effort:** S
- **Done When:** `pytest` runs with coverage reporting. CI runs `pytest tests/unit/ --cov --cov-fail-under=90`. All fixtures exist. Coverage excludes old monolith.

### Phase 0.4: Create Interface Contracts for Batch 1
- **Status:** ⚪ Not Started
- **Tasks:**
  - [ ] Create `src/proton_mcp/utils/__init__.py` with stub imports:
    - `validation.py`: `validate_email_id()`, `validate_folder_name()`, `quote_mailbox()`
    - `mime.py`: `decode_mime_words()`, `get_email_body()`, `get_html_body()`, `get_text_and_html()`
    - `url_safety.py`: `is_safe_url()`
    - `json_store.py`: `class JsonStore` with `load()`, `save()`
  - [ ] Create `src/proton_mcp/models/__init__.py` with stub imports for all model classes
  - [ ] Create `src/proton_mcp/clients/__init__.py` with stub imports for `IMAPClient`, `SMTPClient`
  - [ ] Create `src/proton_mcp/services/__init__.py` with stub imports for all service classes
  - [ ] Create `src/proton_mcp/config.py` interface: `class Config` with `from_env()` classmethod, typed fields
- **Effort:** S
- **Done When:** All stubs exist with correct type annotations. `raise NotImplementedError` in all bodies. Agents can import the interfaces.
- **Note:** Stubs only -- function signatures, class definitions, type annotations. NOT full implementations.

**Batch 0 Verification Gate:** `pytest` runs green (trivial test). `python -c "from proton_mcp import __version__"` succeeds. All interface contracts importable.

---

## Batch 1 (Blocked by Batch 0) -- Pure Extractions (4 parallel agents, git worktrees)

### Phase 1.1: Extract Utils (Validation, MIME, URL Safety, JSON Store)
- **Status:** 🔴 Blocked
- **Depends On:** Phase 0.4
- **Worktree:** `../proton-mcp-phase-1.1` (branch: `phase/1.1`)
- **Tasks:**
  - [ ] Create `src/proton_mcp/utils/validation.py` -- `validate_email_id()`, `validate_folder_name()`, `quote_mailbox()`
  - [ ] Create `src/proton_mcp/utils/mime.py` -- `decode_mime_words()`, `get_email_body()`, `get_text_and_html()`
  - [ ] Create `src/proton_mcp/utils/url_safety.py` -- `is_safe_url()`
  - [ ] Create `src/proton_mcp/utils/json_store.py` -- `JsonStore` class: atomic writes, schema version checking, file locking
  - [ ] Write `tests/unit/test_validation.py`
  - [ ] Write `tests/unit/test_mime.py`
  - [ ] Write `tests/unit/test_url_safety.py`
  - [ ] Write `tests/unit/test_json_store.py`
- **Effort:** S
- **Done When:** All 4 util modules have >90% test coverage. Pure functions/stateless classes, no IMAP/SMTP dependency.

### Phase 1.2: Extract Models (Dataclasses)
- **Status:** 🔴 Blocked
- **Depends On:** Phase 0.4
- **Worktree:** `../proton-mcp-phase-1.2` (branch: `phase/1.2`)
- **Tasks:**
  - [ ] Create `src/proton_mcp/models/email.py` with dataclasses: `EmailSummary`, `FullEmail`, `EmailWithHtml`, `JunkAnalysis`, `UnsubscribeMethod`, `FilterRule`, `JunkRule`, `JunkConfig`, `UnsubscribePreference`, `DetectionPattern`, `UnsubscribeHistoryEntry`
  - [ ] Add `to_dict()` and `from_dict()` methods for JSON serialization
  - [ ] Write `tests/unit/test_models.py` (including round-trip serialization for config models)
- **Effort:** M
- **Done When:** All models import cleanly, type-annotated, serialize/deserialize correctly. Config models round-trip through JSON.

### Phase 1.3: Extract Config Module
- **Status:** 🔴 Blocked
- **Depends On:** Phase 0.4
- **Worktree:** `../proton-mcp-phase-1.3` (branch: `phase/1.3`)
- **Tasks:**
  - [ ] Create standalone `src/proton_mcp/config.py` with `Config` dataclass (replaces Phase 0.4 stub)
  - [ ] Fields include `data_dir` for JSON config file location (default: server script directory)
  - [ ] Factory: `Config.from_env()` reads env vars
  - [ ] Write `tests/unit/test_config.py` (default values, env override, missing credentials error, data_dir resolution)
- **Effort:** S
- **Done When:** Config loads from env, validates required fields, `data_dir` resolves correctly, defaults work.

### Phase 1.4: Extract SMTP Client
- **Status:** 🔴 Blocked
- **Depends On:** Phase 0.4
- **Worktree:** `../proton-mcp-phase-1.4` (branch: `phase/1.4`)
- **Tasks:**
  - [ ] Create `src/proton_mcp/clients/smtp.py` with `SMTPClient` class
  - [ ] Constructor takes `Config`. Methods: `connect()`, `send_email()`
  - [ ] Write `tests/unit/test_smtp_client.py` with mock SMTP
- **Effort:** S
- **Done When:** SMTP client sends email in tests with mocked SMTP.

**Batch 1 Verification Gate:** All Batch 0 tests still pass. Utils, models, config, SMTP client all have >90% coverage. Import smoke test: `python -c "from proton_mcp.utils.validation import validate_email_id; from proton_mcp.models.email import EmailSummary; from proton_mcp.config import Config; from proton_mcp.clients.smtp import SMTPClient"`. Orchestrator updates interface contracts for Batch 2 outputs (IMAPClient, JunkDetector, FilterRuleEngine).

---

## Batch 2 (Blocked by Batch 1 gate) -- Core IMAP + Services (3 parallel agents, git worktrees)

### Phase 2.1: Extract IMAP Client with UID Migration
- **Status:** 🔴 Blocked
- **Depends On:** Batch 1 gate + updated contracts
- **Worktree:** `../proton-mcp-phase-2.1` (branch: `phase/2.1`)
- **Tasks:**
  - [ ] Create `src/proton_mcp/clients/imap.py` with `IMAPClient` class
  - [ ] ALL operations use `mail.uid()` (fixes BUG-unstable-email-ids)
  - [ ] Context manager for connection lifecycle
  - [ ] Methods: `search()`, `fetch_one()`, `fetch_batch()`, `copy()`, `store_flags()`, `expunge()`, `list_mailboxes()`, `create_mailbox()`, `delete_mailbox()`
  - [ ] Write `tests/unit/test_imap_client.py`
- **Effort:** M
- **Done When:** All IMAP operations use UIDs. Context manager works. Tests verify no ID shifting.

### Phase 2.2: Extract Junk Detection + Persistent Config + Fix False Positives
- **Status:** 🔴 Blocked
- **Depends On:** Batch 1 gate + updated contracts
- **Worktree:** `../proton-mcp-phase-2.2` (branch: `phase/2.2`)
- **Tasks:**
  - [ ] Create `src/proton_mcp/services/junk.py` with `JunkDetector` class
  - [ ] Add `load_config()`, `save_config()` using `JsonStore` utility
  - [ ] Create `src/proton_mcp/data/junk_config.json` with default config
  - [ ] Implement whitelist (check FIRST, skip scoring), blacklist (auto-score high), custom patterns
  - [ ] Built-in patterns remain as defaults, configurable thresholds
  - [ ] FIX: Remove `admin@.*`, `support@.*` sender patterns
  - [ ] FIX: Remove/raise `re:.*re:.*re:` threshold
  - [ ] FIX: Raise exclamation threshold to 10+
  - [ ] Return `JunkAnalysis` model
  - [ ] Write `tests/unit/test_junk.py` (false-positive regressions, whitelist/blacklist, custom patterns, thresholds)
- **Effort:** M
- **Done When:** All documented false positives no longer trigger. Existing spam still detected. Config loads/saves via JsonStore. Whitelist/blacklist logic verified.

### Phase 2.3: Extract Filter Rules Service
- **Status:** 🔴 Blocked
- **Depends On:** Batch 1 gate + updated contracts
- **Worktree:** `../proton-mcp-phase-2.3` (branch: `phase/2.3`)
- **Tasks:**
  - [ ] Create `src/proton_mcp/services/filter_rules.py` with `FilterRuleEngine` class
  - [ ] Extract all rule CRUD + matching + action logic
  - [ ] Migrate to `JsonStore` utility for atomic writes and schema versioning
  - [ ] File path resolved via `Config.data_dir`
  - [ ] Write `tests/unit/test_filter_rules.py`
- **Effort:** M
- **Done When:** Rule CRUD, matching, and action tests pass. Rules file uses JsonStore with schema version.

**Batch 2 Verification Gate:** All Batch 1 tests still pass. IMAP client, junk detector, filter rules all have >90% coverage. Orchestrator updates interface contracts for Batch 3 outputs (EmailService, UnsubscribeService, BulkOperations).

---

## Batch 3 (Blocked by Batch 2 gate) -- Remaining Services (3 parallel agents, git worktrees)

### Phase 3.1: Extract Email Operations Service
- **Status:** 🔴 Blocked
- **Depends On:** Batch 2 gate + updated contracts
- **Worktree:** `../proton-mcp-phase-3.1` (branch: `phase/3.1`)
- **Tasks:**
  - [ ] Create `src/proton_mcp/services/email_ops.py` with `EmailService` class
  - [ ] Extract: `search_emails()`, `get_full_email()`, `send_email()`, `get_recent_emails()`
  - [ ] ADD: `include_body` parameter (ENHANCEMENT-lightweight-search)
  - [ ] Write `tests/unit/test_email_ops.py`
- **Effort:** M
- **Done When:** Core operations work through service. Lightweight search implemented.

### Phase 3.2: Extract Unsubscribe Service + Persistent Config + Fix Detection
- **Status:** 🔴 Blocked
- **Depends On:** Batch 2 gate + updated contracts
- **Worktree:** `../proton-mcp-phase-3.2` (branch: `phase/3.2`)
- **Tasks:**
  - [ ] Create `src/proton_mcp/services/unsubscribe.py` with `UnsubscribeService`
  - [ ] Add `load_config()`, `save_config()`, `log_attempt()` using `JsonStore` utility
  - [ ] Create `src/proton_mcp/data/unsubscribe_config.json` with default config (built-in Klaviyo/SendGrid tracker patterns)
  - [ ] Implement sender preferences (never_unsubscribe skips, always_unsubscribe flags)
  - [ ] Auto-log unsubscribe attempts to history
  - [ ] Add re-subscribe detection (sender in history keeps sending)
  - [ ] FIX BUG-unsubscribe-detection: anchor-text-based link detection
  - [ ] Handle tracker URLs (Klaviyo, SendGrid) via configurable detection patterns
  - [ ] Write `tests/unit/test_unsubscribe.py` (Klaviyo/SendGrid samples, preferences, history, re-subscribe)
- **Effort:** M
- **Done When:** Tracker-wrapped unsubscribe links detected. RFC header detection preserved. Config loads/saves via JsonStore. Sender preferences and history logging verified.

### Phase 3.3: Extract Bulk Operations Service
- **Status:** 🔴 Blocked
- **Depends On:** Batch 2 gate + updated contracts
- **Worktree:** `../proton-mcp-phase-3.3` (branch: `phase/3.3`)
- **Tasks:**
  - [ ] Create `src/proton_mcp/services/bulk.py` with `BulkOperations` class
  - [ ] Extract all bulk methods. Use UID operations. Deferred expunge.
  - [ ] Merge `apply_filter_rules` + `apply_filter_rules_optimized` into single method with optional `chunk_size` (default: 50)
  - [ ] Write `tests/unit/test_bulk.py` (including merged apply_filter_rules with/without chunk_size)
- **Effort:** M
- **Done When:** Bulk operations use UIDs, single expunge at end verified. Single `apply_filter_rules` handles both modes.

**Batch 3 Verification Gate:** All previous tests still pass. Email ops, unsubscribe, bulk ops all have >90% coverage. Orchestrator updates interface contracts for Batch 4 outputs (tool/resource/prompt modules).

---

## Batch 4 (Blocked by Batch 3 gate) -- MCP Layer (3 parallel agents, git worktrees)

### Phase 4.1: Extract MCP Tools, Resources, and Prompts
- **Status:** 🔴 Blocked
- **Depends On:** Batch 3 gate + updated contracts
- **Worktree:** `../proton-mcp-phase-4.1` (branch: `phase/4.1`)
- **Tasks:**
  - [ ] **Tool consolidation:** merge search_emails + search_emails_filtered (add `exclude_junk`), merge apply_filter_rules + apply_filter_rules_optimized (add `chunk_size`), remove get_filter_rule_examples/get_mailboxes/list_filter_rules as tools
  - [ ] Create 6 tool modules (29 tools total): core (4), junk (5 -- includes junk config CRUD), unsubscribe (8 -- includes preference/pattern CRUD), folders (2), filter_rules (4), bulk (6)
  - [ ] Create 5 resource modules (6 resources total): inbox-summary, mailboxes, filter-rules, junk-config, unsubscribe/config + unsubscribe/history
  - [ ] Create 2 prompt modules (2 prompts total): create-filter-rule, email-triage
  - [ ] Wire all tool, resource, and prompt modules into `server.py`
  - [ ] Verify all 29 tools + 6 resources + 2 prompts register with FastMCP
- **Effort:** M
- **Done When:** `python -m proton_mcp` starts with all 29 tools, 6 resources, and 2 prompts registered.

### Phase 4.2: Extract Folder Service + Tools
- **Status:** 🔴 Blocked
- **Depends On:** Batch 3 gate
- **Worktree:** `../proton-mcp-phase-4.2` (branch: `phase/4.2`)
- **Tasks:**
  - [ ] Create `src/proton_mcp/services/folders.py`
  - [ ] Write `tests/unit/test_folders.py`
- **Effort:** S
- **Done When:** Folder CRUD works through service.

### Phase 4.3: Lightweight Search Enhancement
- **Status:** 🔴 Blocked
- **Depends On:** Batch 3 gate, Phase 4.1
- **Worktree:** `../proton-mcp-phase-4.3` (branch: `phase/4.3`)
- **Tasks:**
  - [ ] Add `include_body` parameter to consolidated `search_emails` tool definition
  - [ ] Use IMAP FETCH for headers-only when `False`
  - [ ] Write tests for both modes (with body, without body, combined with exclude_junk)
- **Effort:** S
- **Done When:** Header-only search works end-to-end. Works correctly with `exclude_junk` parameter.

**Batch 4 Verification Gate:** All previous tests still pass. All 29 tools, 6 resources, 2 prompts register correctly. `python -m proton_mcp` starts cleanly.

---

## Batch 5 (Blocked by Batch 4 gate) -- Finalization

### Phase 5.1: Integration Tests
- **Status:** 🔴 Blocked
- **Depends On:** Batch 4 gate
- **Tasks:**
  - [ ] Write integration tests for full IMAP/SMTP flows
  - [ ] Write end-to-end MCP tool invocation tests
  - [ ] Write end-to-end MCP resource invocation tests
  - [ ] Write end-to-end MCP prompt invocation tests
  - [ ] Test JSON config persistence (create -> restart -> verify loaded)
  - [ ] Add integration test target to CI
- **Effort:** M
- **Done When:** All 29 tools, 6 resources, and 2 prompts tested end-to-end. CI runs both suites.

### Phase 5.2: Documentation + Cleanup
- **Status:** 🔴 Blocked
- **Depends On:** Phase 5.1
- **Tasks:**
  - [ ] Update CLAUDE.md for new structure
  - [ ] Update README.md
  - [ ] Archive BUG-*.md and ENHANCEMENT-*.md to `plans/completed/`
  - [ ] Remove/deprecate old monolith
  - [ ] Final CI verification
- **Effort:** S
- **Done When:** Clean repo. All CI checks pass. Bug docs archived with resolution.

**Batch 5 Verification Gate:** Integration tests pass. Full coverage report generated. All CI checks green. Final sign-off.

---

## Backlog

- [ ] Async IMAP support (if MCP framework supports async tools)
- [ ] Connection pooling for IMAP (avoid connect/disconnect per operation)
- [ ] Rate limiting for unsubscribe HTTP requests
- [ ] Email attachment support (download, list)
- [ ] HTML-to-text conversion for better body previews
- [ ] IMAP IDLE support for real-time notifications
