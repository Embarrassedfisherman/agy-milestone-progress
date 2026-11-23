# Antigravity Compatibility Matrix & Verification Log

This ledger tracks tested compatibility across **Antigravity Desktop App**, **Antigravity CLI (`agy`)**, **Python versions**, and **operating systems**.

After every Antigravity client update, run:

```bash
python3 scripts/doctor.py --markdown
```

and append a new row to the verification log below (plus any discovered regressions to [docs/BUG_LOG.md](./BUG_LOG.md)).

---

## 1. Runtime Support Baseline

| Layer | Minimum / Supported | Notes |
| :--- | :--- | :--- |
| **Antigravity Desktop App** | `2.x` (latest verified: `2.34.0`) | Full support for Rules, Skills, Lifecycle Hooks, Auxiliary Pane Artifacts |
| **Antigravity CLI (`agy`)** | `1.5.x` (latest verified: `1.5.13`) | Used for `agy plugin list`, `agy plugin enable/disable`, `agy plugin validate --strict` |
| **Python** | `3.9+` (tested: `3.9.6` on stock macOS) | Zero third-party dependencies (standard library only). Keep strict `3.9` runtime syntax compatibility (`from __future__ import annotations`, avoid runtime `int \| str` or `match/case`). |
| **macOS** | Full support | Includes native desktop notifications via `osascript` (`on run argv`) and `fcntl.flock` locking |
| **Linux** | Full core support | `fcntl.flock` supported; desktop notification falls back safely (optional `notify-send` in `v1.1.0`) |
| **Windows** | Full core support (with `python3` caveat) | Native `msvcrt.locking` concurrency locking (`v1.1.1+`) and UTF-8 stdio; ensure `python3` resolves to real Python 3.9+ in `PATH` (not the Microsoft Store stub) because `hooks.json` invokes `python3 ./hooks/progress_hook.py` via `cmd /c` |

---

## 2. Verified Environment Matrix

| Date | Plugin Ver | AGY App | `agy` CLI | OS / Arch | Python | `agy plugin validate --strict` | Hook Live Verified | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-11-23 | `1.2.0` | `2.34.0` | `1.5.13` | macOS (Darwin arm64) | `3.9.6` | Pass (`0 err / 0 warn / 0 notes`) | Yes (29/29 local tests + synced live) | ✅ Compatible | Native `update_focus`/`update_steps` synergy, silence-nudge exemption (`BUG-012`), step-aware notifications, ~29% leaner `AGENTS.md` (`3,023` B). |
| 2026-11-22 | `1.1.1` | `2.34.0` | `1.5.13` | macOS / Ubuntu / Windows | `3.9`–`3.13` | Pass (`0 err / 0 warn / 0 notes`) | Yes (26/26 tests + 15/15 CI green) | ✅ Compatible | Added Windows `msvcrt` locking (`BUG-010`) and UTF-8 stdio hardening (`BUG-011`); CI run `44973380299` 15/15 green. |
| 2026-11-22 | `1.1.0` | `2.34.0` | `1.5.13` | macOS (Darwin arm64) | `3.9.6` | Pass (`0 err / 0 warn / 0 notes`) | Yes (25/25 tests + zip validated) | ✅ Compatible | Multilingual i18n, persistent `config.json`, SVG logo, AGY 2.34 tools & `Stop` error hardening verified. |
| 2026-11-22 | `1.0.3` | `2.34.0` | `1.5.13` | macOS (Darwin) | `3.9.6` | Pass (`0 err / 0 warn / 1 note: no logo`) | Yes (`d18b7a10...json` live) | ✅ Compatible | Zero breaking changes. Logged non-breaking gaps `BUG-006`–`BUG-009`, all resolved in `v1.1.0`. |
| 2026-11-20 | `1.0.3` | `2.x` | — | macOS (Darwin) | `3.9+` | — | Yes | ✅ Compatible | Concurrency locking, 512KB reverse scan, 14-day stale cleanup verified. |
| 2026-11-18 | `1.0.2` | `2.x` | — | macOS (Darwin) | `3.9+` | — | Yes | ✅ Compatible | Removed `metadata.user_markdown` (`UPSTREAM-002`); verified live `<SYSTEM_MESSAGE>` safeguard injection. |

---

## 3. Antigravity Hook & Plugin Contract Checklist

Checked against built-in Antigravity customization docs (`agy-customizations` & `plugin` skills) on **2026-11-23** (App `2.34.0` / CLI `1.5.13`):

| Contract Surface | Expected Behavior | Status on AGY `2.34.0` |
| :--- | :--- | :--- |
| Plugin root manifest | `plugin.json` at plugin root; allowed top-level fields: `name`, `displayName`, `description`, `version`, `logo`, `suggestedPrompts`, `author`, `homepage`, `repository`, `disabled` | ✅ Confirmed (`0` findings on `--strict`) |
| Hooks manifest location | `hooks.json` directly at plugin root (native plugins do not stage `hooks/hooks.json`) | ✅ Confirmed |
| Hook env variables | `PLUGIN_ROOT` and `PLUGIN_DATA` injected into hook subprocesses | ✅ Confirmed (`~/.gemini/antigravity/plugin_data/milestone-progress`) |
| Events used | `SessionStart` (flat), `PostToolUse` (grouped with `matcher` + `hooks`), `PreInvocation` (flat), `Stop` (flat) | ✅ Confirmed |
| `PreInvocation` return | `{"injectSteps": [{"systemMessage": {"systemMessage": "..."}}]}` (metadata-free) | ✅ Confirmed |
| `Stop` input / return | Includes `terminationReason`, `error`, `fullyIdle`, `continuationActive`; returns `{"decision": "allow"}` | ✅ Confirmed (`v1.1.0` inspects `payload["error"]`, `BUG-007`) |
| Rules budget & cap | `rules/AGENTS.md` plain Markdown (no frontmatter), `< 24,000` bytes per file, shared `20,000`-token global rules budget | ✅ Confirmed (`3,023` bytes / `~3.0 KB`, trimmed ~29% in `v1.2.0`) |
| `transcript.jsonl` format | JSONL records with `"type": "PLANNER_RESPONSE"` and visible text in `"content"` | ✅ Confirmed in live session |
| Native tool names (`PostToolUse`) | AGY `2.34` tools including `update_focus`, `update_steps`, `manage_task`, `manage_subagents`, `define_subagent`, `schedule`, `call_mcp_tool`, etc. | ✅ Confirmed (`v1.1.0` `BUG-006`; `v1.2.0` adds `update_focus` / `update_steps` synergy & step-aware notifications, `BUG-012`) |

---

## 4. Tracked Upstream Antigravity Quirks

| Upstream ID | Summary | Current Status | Our Mitigation |
| :--- | :--- | :--- | :--- |
| `UPSTREAM-001` | `PreInvocation.initialNumSteps` increments across invocations within the same turn; protojson omits `invocationNum == 0` and may encode `int64` as string | Active (by design / protojson behavior) | Use `turn_active` + `lastUserInput` hash + tolerant `_parse_optional_int()` rollback detection |
| `UPSTREAM-002` | `systemMessage.metadata.user_markdown` causes Go `utils.ScrubInternalFields` panic (`cannot convert string to message`) and silently drops the hook output | Still documented in `hooks.md`; untested whether fixed in `2.34.0` | Keep metadata-free `systemMessage` + native streaming narration in `rules/AGENTS.md` |
