# Changelog

[English](./CHANGELOG.md) | [简体中文](./CHANGELOG.zh-CN.md)

All notable changes to **Milestone Progress (`milestone-progress`)** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Archived] - 2026-11-28

### Status
- **Project honorably archived (read-only)**: Antigravity `2.34`–`2.36` now natively covers the core progress visibility (`update_focus` / `update_steps` Checklists), workflow commands (`/plan`, `/grill-me`, `/goal`, `/teamwork`, `/swarm`, `/boost`), and desktop notifications that motivated this plugin.
- Added bilingual archive/migration notices to `README.md` and `README.zh-CN.md`, and recorded final compatibility verification on **Antigravity Desktop App `2.36.0`** (`agy` CLI `1.5.13`, `Python 3.9.6`) in `docs/COMPATIBILITY.md`.

---

## [1.2.1] - 2026-11-24

### Added
- **Official Antigravity JSON Schema v1 manifest alignment**: Added `$schema` (`https://antigravity.google/schemas/v1/plugin.json`), `license`, and `keywords` to `plugin.json`, converted `repository` to a plain `https://` URL string, expanded `ALLOWED_PLUGIN_FIELDS` + `repository` URL check in `scripts/doctor.py`, and added strict schema assertions in `tests/test_repo_integrity.py`.
- **Additional official `hooks.md` tool labels**: Added `list_permissions`, `ask_permission` (with `Target`/`Action` detail), and `generate_image` (with `ImageName`/`Prompt` detail) categories and localized labels across `en` / `zh` / `ja`.
- Added 2 regression test suites in `tests/test_progress_hook.py` (growing the suite from 29 to **31 tests**).

### Changed
- **Official native features first (additive-only positioning)**: Refined `rules/AGENTS.md` (`3,655` B), `skills/milestone-mode/SKILL.md`, and localized `[Progress Guardian]` prompts (`en` / `zh` / `ja`) so the plugin explicitly yields to native continuous/workflow modes (`/goal`, `/teamwork`, or user-requested uninterrupted runs on native `update_steps` checklists) instead of forcing unwanted mid-run pauses.
- Hardened `Stop` hook error classification in `hooks/progress_hook.py` with case-insensitive `terminationReason` matching and `MAX_STEPS_EXCEEDED` coverage alongside non-empty `error` detection.

### Compatibility
- Verified zero breaking incompatibilities on **Antigravity Desktop App `2.35.0`** (including official native Checklists / `update_steps` UI and unlimited conversation history), `agy` CLI `1.5.13`, and macOS `Python 3.9.6`.

---

## [1.2.0] - 2026-11-23

### Added
- **Step-aware desktop notifications**: `PostToolUse` now captures the latest `update_steps` progress snapshot (including newly completed out-of-order step detection), upgrading `Stop` notifications across `en` / `zh` / `ja` to display `(done/total)` progress counts and the completed or active step title (with safe fallback when `update_steps` is unused or malformed).
- **AGY native progress tool support (`BUG-012`)**: Added `update_focus` and `update_steps` categories, localized labels (`en`/`zh`/`ja`), and argument detail extraction (`focus` truncation and `done/total` ratio) in `hooks/progress_hook.py`.
- Added 3 regression test suites in `tests/test_progress_hook.py` (growing the suite from 26 to **29 tests**).

### Changed
- **Native-first rule & skill slim-down**: Refactored `rules/AGENTS.md` (trimmed from `4,255` B to `3,023` B, ~29% lighter on AGY's global rules budget) and `skills/milestone-mode/SKILL.md` to delegate routine live status/checklists to AGY's native `update_focus` / `update_steps` instead of double-spamming chat or forcing default `task.md` writes, while keeping one-milestone-per-turn pacing and the 5-item checkpoint card front and center.
- Updated `[Progress Reminder]` and `[Progress Guardian]` prompts across `en` / `zh` / `ja` to recognize and guide `update_focus` / `update_steps`.

### Fixed
- Exempted successful `update_focus` / `update_steps` tool calls from `silent_invocations` counting in `hooks/progress_hook.py` so agents using AGY's native progress UI without redundant chat prose no longer receive false `[Progress Reminder]` nudges (`BUG-012`).

---

## [1.1.1] - 2026-11-22

### Fixed
- Added native Windows exclusive file locking (`msvcrt.locking` with non-blocking retry) and transient `PermissionError` replace retry in `hooks/progress_hook.py` so concurrent `PostToolUse` updates are never lost on Windows (`BUG-010`).
- Reconfigured stdio to UTF-8 (`errors="replace"`) in `hooks/progress_hook.py`, `scripts/doctor.py`, `scripts/sync.py`, and `scripts/release.py` to prevent Windows console encoding errors on emoji/multilingual output (`BUG-011`).
- Updated GitHub Actions CI matrix to run Linux Python `3.9` on `ubuntu-24.04` (since `ubuntu-latest` / Ubuntu 26.04 no longer publishes prebuilt Python `3.9`), achieving `15/15` green CI across macOS, Linux, and Windows.

---

## [1.1.0] - 2026-11-22

### Added
- **Multilingual / i18n architecture (`BUG-009`)**:
  - Upgraded `rules/AGENTS.md` and `skills/milestone-mode/SKILL.md` to a language-adaptive protocol that automatically matches the user's conversation language.
  - Added zero-dependency `hooks/i18n.py` and extensible JSON locale packs (`hooks/locales/en.json`, `zh.json`, `ja.json`) with automatic prompt language detection, per-conversation language memory, and safe English fallback.
- **Persistent user configuration**: Support optional `$PLUGIN_DATA/config.json` (plus `MILESTONE_PROGRESS_LANG` env override) for customizing language, nudge/safeguard intervals, notification thresholds/toggle, and state retention days across plugin upgrades.
- **Linux desktop notifications**: Added optional best-effort `notify-send` support on Linux with graceful no-op fallback.
- **Plugin polish**: Added theme-adaptive vector icon `assets/logo.svg` and enriched `plugin.json` metadata (`logo`, `suggestedPrompts`, `author`, `homepage`, `repository`), achieving `0 errors / 0 warnings / 0 notes` on `agy plugin validate . --strict`.
- **Cross-platform ops & release tooling**:
  - Added `scripts/doctor.py` (local health, sync diff, state inspection, and AGY compatibility checker with `--markdown`, `--json`, `--ci`, `--skip-tests`, and `--strict`).
  - Added cross-platform `scripts/sync.py` (`--check`, `--clean`, SHA-256 verification, strict runtime-only file allowlist) and simplified `scripts/sync.sh` into a compatible wrapper.
  - Added `scripts/release.py` (safe dry-run preflight, version bump, and clean runtime `.zip` packager with `agy plugin validate` verification).
- **Local operations ledgers & GitHub open-source governance**:
  - Added `CHANGELOG.md`, `CHANGELOG.zh-CN.md`, `docs/COMPATIBILITY.md`, `docs/BUG_LOG.md`, `docs/RELEASE_PROCESS.md`, `README.zh-CN.md`, `CONTRIBUTING.md`, and `SECURITY.md`.
  - Added GitHub Actions CI matrix (`.github/workflows/ci.yml`: `ubuntu`/`macos`/`windows` × Python `3.9`–`3.13`), automated tag-driven GitHub Release packaging (`.github/workflows/release.yml`), and structured Issue / PR templates.
- **Expanded automated tests**: Grew the test suite from 9 to **25 tests** across `tests/test_progress_hook.py`, `tests/test_i18n.py` (strict key & placeholder parity across all locales), and `tests/test_repo_integrity.py` (manifest whitelist, rules byte budget, sync isolation, and Python 3.9 AST syntax guard).

### Changed
- Made `README.md` English-primary with a prominent language switcher linking to `README.zh-CN.md`.
- Corrected documented Python requirement from `3.10+` to `3.9+` to match stock macOS `python3` (`BUG-008`).

### Compatibility
- Verified zero breaking incompatibilities on Antigravity Desktop App `2.34.0`, `agy` CLI `1.5.13`, and stock macOS `Python 3.9.6`.
- Added localized tool labels and argument details for newer Antigravity `2.34.0` native tools (`manage_task`, `manage_subagents`, `define_subagent`, `schedule`, `call_mcp_tool`, `list_resources`, `read_resource`, `search_marketplace`, `list_plugin_accounts`) (`BUG-006`).
- Hardened `Stop` hook error classification to inspect non-empty `payload["error"]` alongside known termination reason enums (`BUG-007`).

---

## [1.0.3] - 2026-11-20

### Added
- Per-conversation exclusive file locking (`fcntl.flock` with non-POSIX fallback) and atomic temp-file replacement (`Path.replace`) to prevent concurrent `PostToolUse` write races (`BUG-003`).
- Automatic 14-day stale state cleanup (`.json`, `.lock`, `.tmp`) on `SessionStart` (`BUG-004`).
- One-command sync script `scripts/sync.sh` with unit test gating and `diff` verification.
- Expanded unit test coverage for concurrent `PostToolUse`, large multi-chunk transcripts, and stale state pruning.

### Changed
- Upgraded `transcript.jsonl` tail scanning from fixed `24 KB` to chunked reverse scanning (`32 KB` chunks up to `512 KB`) to survive huge tool outputs (`BUG-005`).

---

## [1.0.2] - 2026-11-18

### Fixed
- Removed `metadata.user_markdown` from `PreInvocation` `systemMessage` payloads to work around an upstream Antigravity Go scrubber bug (`UPSTREAM-002`) that silently dropped injected steps (`BUG-002`).

### Added
- Switched live progress updates to native model streaming narration in `rules/AGENTS.md` (`Live Inline Progress Narration`).
- Added `transcript.jsonl` silence detection: injects `[Progress Reminder]` after 3 consecutive silent tool-calling invocations without visible content, and `[Progress Guardian]` starting at invocation 12 (repeating every 4 invocations).

---

## [1.0.1] - 2026-11-18

### Fixed
- Replaced `initialNumSteps`-based turn detection (which increments within a single turn in Antigravity, `UPSTREAM-001`) with a `turn_active` state flag + `lastUserInput` hash + `invocationNum` rollback check supporting protojson `None`/int/string encodings (`BUG-001`).

---

## [1.0.0] - 2026-11-18

### Added
- Initial plugin architecture bundling `rules/AGENTS.md`, `skills/milestone-mode/SKILL.md`, `hooks.json`, and `hooks/progress_hook.py`.
- Smart task-size threshold separating quick Q&A/minor edits from multi-module phased milestone execution.
- Non-trivial turn completion notifications on macOS via safe `osascript` `on run argv` parameter passing.

[Archived]: https://github.com/Embarrassedfisherman/agy-milestone-progress/compare/v1.2.1...HEAD
[1.2.1]: https://github.com/Embarrassedfisherman/agy-milestone-progress/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/Embarrassedfisherman/agy-milestone-progress/compare/v1.1.1...v1.2.0
[1.1.1]: https://github.com/Embarrassedfisherman/agy-milestone-progress/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/Embarrassedfisherman/agy-milestone-progress/compare/v1.0.3...v1.1.0
[1.0.3]: https://github.com/Embarrassedfisherman/agy-milestone-progress/releases/tag/v1.0.3
[1.0.2]: https://github.com/Embarrassedfisherman/agy-milestone-progress/commits/main
[1.0.1]: https://github.com/Embarrassedfisherman/agy-milestone-progress/commits/main
[1.0.0]: https://github.com/Embarrassedfisherman/agy-milestone-progress/commits/main
