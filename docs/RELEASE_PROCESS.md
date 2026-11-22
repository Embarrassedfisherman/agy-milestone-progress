# Release & Maintenance SOP

This document defines the standard workflow for maintaining **Milestone Progress (`milestone-progress`)** through frequent updates and Antigravity client releases.

---

## 1. Versioning & Commit Conventions

- **Semantic Versioning (`SemVer 2.0.0`)**:
  - `MAJOR` (`X.0.0`): Breaking changes to plugin structure, config schema, or minimum AGY/Python support.
  - `MINOR` (`1.X.0`): New features, new locales, new AGY tool/hook support (backward-compatible).
  - `PATCH` (`1.1.X`): Bug fixes, compatibility mitigations, doc/test improvements.
- **Conventional Commits**:
  - `feat:` new feature
  - `fix:` bug fix (reference `BUG-NNN` when applicable)
  - `compat:` Antigravity client compatibility adaptation
  - `i18n:` localization additions or translation fixes
  - `docs:` documentation or ops ledger updates
  - `test:` test additions or refactors
  - `chore:` CI, scripts, release metadata

---

## 2. Routine Workflow on Every Antigravity Client Update

1. Run the local health & compatibility check:
   ```bash
   python3 scripts/doctor.py --markdown
   ```
2. Run the unit test suite:
   ```bash
   python3 -m unittest discover -s tests -v
   ```
3. Verify live execution in a real Antigravity session (confirm state file updates under `$PLUGIN_DATA/milestone-progress-state/`, inline narration works, and `Stop` notification fires on non-trivial turns).
4. Record the verified result in [docs/COMPATIBILITY.md](./COMPATIBILITY.md).
5. If any regression or schema drift is found, log a new `BUG-NNN` / `UPSTREAM-NNN` entry in [docs/BUG_LOG.md](./BUG_LOG.md) before patching.

---

## 3. Standard Release Checklist (Frequent Updates)

1. **Update Ledgers**:
   - Move items from `[Unreleased]` into `[X.Y.Z] - YYYY-MM-DD` in both [CHANGELOG.md](../CHANGELOG.md) and [CHANGELOG.zh-CN.md](../CHANGELOG.zh-CN.md), updating comparison links at the bottom.
   - Mark resolved items in [docs/BUG_LOG.md](./BUG_LOG.md) as `✅ Fixed in vX.Y.Z`.
2. **Run Release Preflight** *(automated helper added in Milestone 3)*:
   ```bash
   python3 scripts/release.py --version X.Y.Z --package --dry-run
   ```
   When clean, apply the version bump and verify:
   ```bash
   python3 scripts/release.py --version X.Y.Z --package --apply
   ```
3. **Run Full Local Gate**:
   ```bash
   python3 -m unittest discover -s tests -v
   agy plugin validate . --strict
   agy plugin validate dist/milestone-progress-vX.Y.Z.zip --strict
   python3 scripts/sync.py
   ```
4. **Commit, Tag & Publish to GitHub**:
   ```bash
   git add -A
   git commit -m "chore(release): prepare vX.Y.Z"
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin main --follow-tags
   ```
   Pushing the `vX.Y.Z` tag triggers `.github/workflows/release.yml`, which re-runs tests, builds the clean runtime `.zip`, extracts release notes from `CHANGELOG.md`, and publishes the GitHub Release automatically.

---

## 4. Separation of Repo Ops Files vs. Runtime Plugin Bundle

To keep users' installed plugin directories clean and avoid wasting Antigravity context budget:

- **Synced / Packaged (Runtime Bundle Only)**: `plugin.json`, `hooks.json`, `assets/`, `rules/`, `skills/`, `hooks/`
- **Repo-Only (Never Synced to `~/.gemini/config/plugins/milestone-progress`)**: `CHANGELOG*.md`, `docs/`, `tests/`, `scripts/`, `.github/`, `README*.md`, `CONTRIBUTING.md`, `SECURITY.md`
