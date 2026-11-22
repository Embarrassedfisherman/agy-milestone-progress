# Milestone Progress (`milestone-progress`)

**English** | [简体中文](./README.zh-CN.md)

[![CI](https://github.com/Embarrassedfisherman/agy-milestone-progress/actions/workflows/ci.yml/badge.svg)](https://github.com/Embarrassedfisherman/agy-milestone-progress/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-3776AB.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/Version-1.1.0-10B981.svg)](./CHANGELOG.md)

A global **Antigravity (AGY)** plugin that brings **transparent execution, phased milestone checkpoints, silent-loop guardrails, and completion notifications** to long-running AI agent tasks—with built-in **multilingual support** (`en`, `zh`, `ja`, and auto-adaptive rules for any conversation language).

It solves a common pain point on large projects: sending a prompt and watching the agent silently chain tool calls for 20+ minutes inside collapsed `<thinking>` blocks with no clear picture of current progress, phase boundaries, or when your input is needed.

---

## 1. Quick Start

### Requirements
- **Antigravity 2.x** (verified on Desktop App `2.34.0` & `agy` CLI `1.5.13`; see [Compatibility Matrix](./docs/COMPATIBILITY.md))
- **Python 3.9+** (standard library only, zero third-party dependencies — works out-of-the-box with stock macOS `python3`)
- **OS**:
  - **macOS**: Full support including native desktop notifications (`osascript`)
  - **Linux**: Full core support + optional desktop notifications when `notify-send` is installed
  - **Windows**: Full core support (notifications safely skipped; ensure `python3` in `PATH` points to Python 3.9+)

### Option A: Install / Update from Source (Recommended)

```bash
git clone https://github.com/Embarrassedfisherman/agy-milestone-progress.git
cd agy-milestone-progress
python3 scripts/sync.py --clean
```

*(macOS / Linux users can also run `./scripts/sync.sh --clean`, which wraps `scripts/sync.py`.)*

The sync script automatically:
1. Runs the full unit test suite;
2. Validates the plugin with `agy plugin validate --strict` (when `agy` is installed);
3. Syncs **only runtime plugin files** to `~/.gemini/config/plugins/milestone-progress` (customizable via `--target` or `MILESTONE_PLUGIN_DIR`), leaving repo docs/CI/tests out of your live plugin directory;
4. Verifies SHA-256 integrity for every synced file (takes effect immediately, no restart required).

To update later, pull the latest commits and re-run `python3 scripts/sync.py --clean`—your personal configuration in `$PLUGIN_DATA/config.json` is preserved across upgrades.

### Option B: Install from GitHub Releases (`.zip`)

Download `milestone-progress-vX.Y.Z.zip` from [GitHub Releases](https://github.com/Embarrassedfisherman/agy-milestone-progress/releases) and extract its contents into:

```text
~/.gemini/config/plugins/milestone-progress/
```

### Enable, Disable & Uninstall

- **Desktop UI**: Open **Skills & Customizations → Plugins → Milestone Progress** to toggle on/off.
- **CLI**:
  ```bash
  agy plugin disable milestone-progress
  agy plugin enable milestone-progress
  ```
- **Uninstall**:
  ```bash
  rm -rf ~/.gemini/config/plugins/milestone-progress
  ```

---

## 2. How It Works (4-Layer Architecture)

| Layer | File(s) | Purpose | Behavior |
| :--- | :--- | :--- | :--- |
| **Rules** | [rules/AGENTS.md](./rules/AGENTS.md) | Smart scoping, live narration & phase boundaries | 1. **Language-Adaptive**: Automatically responds in your conversation language.<br>2. **Smart Threshold**: Quick Q&A / edits (`<= 2` files, `<= 4` steps) run directly; `3+` files or multi-module tasks enter Phased Milestone Mode.<br>3. **Live Narration**: Outputs 1 concise visible status sentence before multi-step tool batches.<br>4. **One Milestone Per Turn**: Maintains `task.md` Artifact and ends each milestone with a 5-item plain-language checkpoint card. |
| **Skill** | [skills/milestone-mode/SKILL.md](./skills/milestone-mode/SKILL.md) | On-demand strict milestone control | Type `/milestone-mode` in chat anytime to enforce strict phased checkpoints. |
| **Guardrail Hook** | [hooks/progress_hook.py](./hooks/progress_hook.py), [hooks/i18n.py](./hooks/i18n.py), [hooks/locales/](./hooks/locales/) | Prevent silent black-box runs & runaway loops | 1. **Silent Nudge** (`PreInvocation` + `PostToolUse`): Reverse-scans up to `512 KB` of `transcript.jsonl` (`32 KB` chunks). After `3` consecutive silent tool-calling invocations, injects a localized `[Progress Reminder]` prompting visible narration.<br>2. **Hard Safeguard**: At invocation `12` (and every `4` thereafter), injects `[Progress Guardian]` instructing the agent to wrap up safely and report. |
| **Notification Hook** | [hooks/progress_hook.py](./hooks/progress_hook.py) (`Stop`) | Alert you when a real milestone pauses while you are in another window | Fires a localized desktop notification only on non-trivial turns (`>= 3` invocations, `>= 3` tool calls, `>= 15s` elapsed, or error stops — never on `USER_CANCELED` or short Q&A). |

---

## 3. Multilingual Support & Persistent User Configuration

### Language Resolution Order
1. Environment variable `MILESTONE_PROGRESS_LANG` (e.g., `en`, `zh`, `ja`)
2. Persistent user config `language` in `$PLUGIN_DATA/config.json`
3. **Automatic detection** (`"auto"`, default): detects language from your prompt (Kana → `ja`, Han → `zh`, other text → `en`), remembers it per conversation so `Stop` notifications match your chat, and falls back to system `LANG` / `en` when empty.

Built-in Hook locale packs live in [hooks/locales/](./hooks/locales/) (`en.json`, `zh.json`, `ja.json`). Adding a new language only takes one JSON file—see [CONTRIBUTING.md](./CONTRIBUTING.md).

### Persistent Threshold & Preference Overrides
Instead of editing plugin source files (which get overwritten on update), create an optional JSON file at:

```text
~/.gemini/antigravity/plugin_data/milestone-progress/config.json
```

All keys are optional and safely validated (invalid values fall back to defaults):

```json
{
  "language": "auto",
  "silent_nudge_interval": 3,
  "safeguard_first_invocation": 12,
  "safeguard_repeat_interval": 4,
  "notify_enabled": true,
  "notify_min_invocations": 3,
  "notify_min_tools": 3,
  "notify_min_elapsed_sec": 15.0,
  "state_retention_days": 14
}
```

---

## 4. Repository Layout & Local Operations Ledgers

Repo maintenance files (`docs/`, `CHANGELOG*.md`, `tests/`, `scripts/`, `.github/`) are strictly excluded from the synced runtime plugin directory so they consume **zero** agent context tokens.

```text
agy-milestone-progress/
├── plugin.json                      # Plugin manifest (AGY-compliant metadata)
├── hooks.json                       # Lifecycle hook bindings
├── assets/logo.svg                  # Vector plugin icon (light/dark theme ready)
├── rules/AGENTS.md                  # Language-adaptive milestone & narration rules
├── skills/milestone-mode/SKILL.md   # /milestone-mode explicit skill
├── hooks/
│   ├── progress_hook.py             # Core lifecycle hook (Python 3.9+, zero deps)
│   ├── i18n.py                      # Locale loader & language auto-detector
│   └── locales/{en,zh,ja}.json      # Extensible Hook message catalogs
├── scripts/
│   ├── sync.py / sync.sh            # Cross-platform test + validate + sync installer
│   ├── doctor.py                    # Local health & AGY compatibility diagnostics
│   └── release.py                   # Safe release preflight, version bump & zip packager
├── tests/                           # 25 unit, i18n-parity & repo-integrity tests
├── CHANGELOG.md / CHANGELOG.zh-CN.md
├── CONTRIBUTING.md / SECURITY.md
└── docs/
    ├── COMPATIBILITY.md             # Antigravity App / CLI / Python / OS matrix
    ├── BUG_LOG.md                   # Structured plugin bug & upstream quirk registry
    ├── RELEASE_PROCESS.md           # Repeatable frequent-release SOP
    └── RETROSPECTIVE.md             # Engineering design & AGY hook lessons (Chinese)
```

---

## 5. Diagnostics, Development & Release Commands

```bash
# Run all unit, i18n parity, and repo integrity tests
python3 -m unittest discover -s tests -v

# Check local health, sync status, and Antigravity compatibility
python3 scripts/doctor.py --with-tests
python3 scripts/doctor.py --markdown

# Validate strictly against Antigravity's official plugin loader
agy plugin validate . --strict

# Sync runtime bundle to global Antigravity plugin folder
python3 scripts/sync.py --clean

# Preview release preflight and build clean runtime zip (dry-run by default)
python3 scripts/release.py --package
```

---

## 6. Contributing & License

Contributions—especially new locale translations and Antigravity version compatibility reports—are very welcome! Please read [CONTRIBUTING.md](./CONTRIBUTING.md) and [SECURITY.md](./SECURITY.md).

Licensed under the [MIT License](./LICENSE).
