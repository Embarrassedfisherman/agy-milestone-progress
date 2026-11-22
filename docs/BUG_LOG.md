# Bug & Incident Ledger

Structured local tracking registry for all plugin defects (`BUG-NNN`) and upstream Antigravity platform quirks (`UPSTREAM-NNN`).

> **Rule of thumb**: Every bug fixed in code or discovered after an Antigravity client update gets an entry here, linked to its fixing version in [CHANGELOG.md](../CHANGELOG.md) and its regression test in `tests/`.

---

## Status Summary

| ID | Title | Severity | Status | Introduced / Found | Fixed In | Regression Test |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `BUG-001` | `initialNumSteps` caused false new-turn resets on every `PreInvocation` | High | ✅ Fixed | `v1.0.0` | `v1.0.1` | `test_changing_initial_num_steps_and_protojson_fields_keep_turn_alive` |
| `BUG-002` | `metadata.user_markdown` triggered upstream Go scrubber drop of all injected steps | Critical | ✅ Fixed | `v1.0.0` | `v1.0.2` | `test_silent_tool_steps_trigger_metadata_free_nudge_and_visible_text_resets_it` |
| `BUG-003` | Concurrent `PostToolUse` calls raced on per-conversation state JSON writes | High | ✅ Fixed | `v1.0.0` | `v1.0.3` | `test_concurrent_post_tool_use_preserves_all_updates` |
| `BUG-004` | Historical per-conversation state files accumulated indefinitely in `PLUGIN_DATA` | Low | ✅ Fixed | `v1.0.0` | `v1.0.3` | `test_session_start_cleans_stale_state_files_only` |
| `BUG-005` | Fixed `24 KB` transcript tail read missed visible planner text after large tool outputs | Medium | ✅ Fixed | `v1.0.2` | `v1.0.3` | `test_large_tool_outputs_beyond_24kb_still_detect_visible_planner_text` |
| `BUG-006` | Newer AGY `2.34.0` native tool names missing from `TOOL_LABELS` | Low | ✅ Fixed | `v1.0.3` (AGY `2.34.0`) | `v1.1.0` | `test_agy_234_native_tool_labels_and_details` |
| `BUG-007` | `_handle_stop()` did not inspect non-empty `payload["error"]` alongside enum reasons | Low | ✅ Fixed | `v1.0.3` (AGY `2.34.0`) | `v1.1.0` | `test_stop_detects_nonempty_error_field_with_new_termination_reasons` |
| `BUG-008` | `README.md` stated Python `3.10+` while stock macOS `python3` is `3.9.6` (no 3.9 CI guard) | Medium | ✅ Fixed | `v1.0.3` | `v1.1.0` | `test_python_39_runtime_syntax_guard` + CI Python `3.9` matrix |
| `BUG-009` | Hardcoded Chinese strings across Rules, Skill, Hook nudges, and notifications block non-Chinese users | Medium | ✅ Fixed | `v1.0.0` | `v1.1.0` | `test_english_and_japanese_auto_detection_end_to_end` + `tests/test_i18n.py` |
| `BUG-010` | Windows lacked file locking (`fcntl` unavailable), causing concurrent `PostToolUse` state races | High | ✅ Fixed | `v1.0.3` (caught by Windows CI) | Unreleased (`v1.1.1`) | `test_concurrent_post_tool_use_preserves_all_updates` + `test_windows_msvcrt_lock_branch_acquires_and_releases` |
| `BUG-011` | Windows legacy codepage stdio could fail encoding emoji output in hook and CLI scripts | Medium | ✅ Fixed | `v1.1.0` (hardened for Windows CI) | Unreleased (`v1.1.1`) | Windows CI matrix (`doctor.py`, `sync.py`, `release.py`) |
| `UPSTREAM-001` | `initialNumSteps` increments within a turn; protojson omits `0` and may stringify `int64` | Info | 🛡️ Mitigated | AGY `2.x` | Mitigated in `v1.0.1` | `test_changing_initial_num_steps_and_protojson_fields_keep_turn_alive` |
| `UPSTREAM-002` | `systemMessage.metadata` string values rejected by Go `utils.ScrubInternalFields` | High | 🛡️ Mitigated | AGY `2.x` | Mitigated in `v1.0.2` | `test_safeguard_fires_without_metadata_and_repeats_at_interval` |

---

## Detailed Records

### BUG-001 — False Turn Reset from Incrementing `initialNumSteps`
- **Status**: ✅ Fixed in `v1.0.1`
- **Environment**: Antigravity `2.x`
- **Symptom**: `turn_invocations` stayed stuck at `1` and `PostToolUse` counters reset on every invocation.
- **Root Cause**: `initialNumSteps` increases with total trajectory steps inside the same turn (`74 → 76 → 93`), and protojson omits `invocationNum == 0` or encodes `int64` as numeric strings.
- **Resolution**: Switched turn boundary detection to `turn_active` (cleared on `Stop`) + `lastUserInput` hash + tolerant `_parse_optional_int()` rollback check.

### BUG-002 — Silent Drop of `injectSteps` When `systemMessage.metadata` Is Set
- **Status**: ✅ Fixed in `v1.0.2`
- **Environment**: Antigravity `2.x` (Go `hookcaller.callHookAs` / `utils.ScrubInternalFields`)
- **Symptom**: Neither inline progress markdown nor safeguard instructions appeared in the trajectory despite valid JSON output from `PreInvocation`.
- **Root Cause**: Upstream Go scrubber assumes `metadata` map values are nested Protobuf messages and fails with `type mismatch: cannot convert string to message`, discarding the entire hook payload.
- **Resolution**: Removed `metadata` completely from `systemMessage`; moved live narration to model streaming output in `rules/AGENTS.md` and added `transcript.jsonl` silence detection.

### BUG-003 — Concurrent `PostToolUse` State File Race
- **Status**: ✅ Fixed in `v1.0.3`
- **Symptom**: Parallel tool calls in a single turn could overwrite each other's state JSON updates, dropping `total_tools` or `pending_actions`.
- **Resolution**: Added per-conversation `fcntl.flock` `.lock` guard and atomic `.tmp` + `Path.replace` writes.

### BUG-004 — Unbounded Accumulation of Old Conversation State Files
- **Status**: ✅ Fixed in `v1.0.3`
- **Symptom**: Stale `.json` and `.lock` files remained in `$PLUGIN_DATA/milestone-progress-state/` indefinitely.
- **Resolution**: Added 14-day TTL cleanup during `SessionStart`.

### BUG-005 — Large Tool Output Exceeding `24 KB` Masked Prior Visible Narration
- **Status**: ✅ Fixed in `v1.0.3`
- **Symptom**: A large tool result (> `24 KB`) pushed the prior `PLANNER_RESPONSE` beyond the fixed tail window, causing false silence reminders.
- **Resolution**: Upgraded to reverse chunked scanning (`32 KB` chunks up to `512 KB`) with line-boundary carry handling.

### BUG-006 — Missing AGY `2.34.0` Native Tool Labels
- **Status**: ✅ Fixed in `v1.1.0`
- **Environment**: Antigravity App `2.34.0` / CLI `1.5.13`
- **Symptom**: Newer native tools (`manage_task`, `manage_subagents`, `define_subagent`, `schedule`, `call_mcp_tool`, `list_resources`, `read_resource`, `search_marketplace`, `list_plugin_accounts`) rendered as raw names in progress nudges.
- **Resolution**: Added localized labels and argument extraction in `hooks/locales/{en,zh,ja}.json` and `hooks/progress_hook.py` (`test_agy_234_native_tool_labels_and_details`).

### BUG-007 — `Stop` Hook Error Detection Relied Only on Fixed Enum Set
- **Status**: ✅ Fixed in `v1.1.0`
- **Environment**: Antigravity App `2.34.0` (`hooks.md` adds `TERMINAL_CUSTOM_HOOK`, `INJECTED_RESPONSE`, `TERMINAL_STEP_TYPE`, `continuationActive`)
- **Symptom**: If an error stop arrived with a new `terminationReason` value while populating `payload["error"]`, the notification subtitle classified it as a normal milestone pause.
- **Resolution**: Updated `_handle_stop()` to treat non-empty `str(payload.get("error") or "").strip()` as an error state alongside known error reasons (`test_stop_detects_nonempty_error_field_with_new_termination_reasons`).

### BUG-008 — Python `3.10+` Doc Mismatch vs Stock macOS Python `3.9.6`
- **Status**: ✅ Fixed in `v1.1.0`
- **Symptom**: `README.md` documented `Python 3.10+` while stock macOS `/usr/bin/python3` is `3.9.6`; without a `3.9` CI check, future runtime 3.10 syntax could break macOS hooks.
- **Resolution**: Officially standardized on `Python 3.9+`, added `test_python_39_runtime_syntax_guard` AST check, and enabled Python `3.9`–`3.13` cross-OS CI matrix.

### BUG-009 — Chinese-Only Hardcoding Across All Plugin Layers
- **Status**: ✅ Fixed in `v1.1.0`
- **Symptom**: English and other non-Chinese users received forced Chinese inline progress lines, Chinese checkpoint cards, Chinese hook reminders, and Chinese macOS notifications.
- **Resolution**: Made `rules/AGENTS.md` and `SKILL.md` language-adaptive, added `hooks/i18n.py` + `hooks/locales/{en,zh,ja}.json` with automatic prompt detection and key/placeholder parity tests, and added persistent `$PLUGIN_DATA/config.json` overrides.

### BUG-010 — Concurrent `PostToolUse` State Races on Windows (Missing `msvcrt` Locking)
- **Status**: ✅ Fixed in Unreleased (`v1.1.1`)
- **Environment**: Windows Server 2025 / Python `3.9`–`3.13` (caught by GitHub Actions CI run `44972486428`)
- **Symptom**: `test_concurrent_post_tool_use_preserves_all_updates` lost 1–3 of 12 concurrent tool updates on Windows because `fcntl` is unavailable and `_conversation_lock` became a no-op.
- **Root Cause**: `_conversation_lock()` only implemented POSIX `fcntl.flock` and yielded without locking on Windows.
- **Resolution**: Added native Windows `msvcrt.locking(LK_NBLCK)` with backoff retry and `LK_UNLCK` release in `_conversation_lock()`, plus `PermissionError` retry on `_save_state()` atomic replace.

### BUG-011 — Windows Legacy Console Codepage Risk on Emoji Output
- **Status**: ✅ Fixed in Unreleased (`v1.1.1`)
- **Environment**: Windows (`cp1252` / legacy console encoding)
- **Symptom**: Writing emoji/Unicode status lines from `progress_hook.py`, `doctor.py`, `sync.py`, or `release.py` to non-UTF-8 Windows stdio can raise `UnicodeEncodeError`.
- **Resolution**: Explicitly reconfigured `sys.stdin` / `sys.stdout` / `sys.stderr` to UTF-8 (`errors="replace"`) in CLI entrypoints and passed `encoding="utf-8"` in subprocess unit tests.

---

## Entry Template (Copy for New Incidents)

```markdown
### BUG-NNN — <Short Descriptive Title>
- **Status**: 🔴 Open | 🟡 In Progress | ✅ Fixed in `vX.Y.Z` | 🛡️ Mitigated
- **Environment**: Antigravity App `X.Y.Z` / CLI `X.Y.Z` / OS / Python `X.Y`
- **Symptom**: What the user observed.
- **Root Cause**: Verified technical cause.
- **Resolution**: Code/config change + regression test name.
```
