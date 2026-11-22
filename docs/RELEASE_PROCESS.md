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
4. **Push `main` First & Verify Full CI Green**:
   ```bash
   git add -A
   git commit -m "chore(release): prepare vX.Y.Z"
   git push origin main
   ```
   Wait for the full cross-OS CI matrix (`macOS / Linux / Windows × Python 3.9–3.13`) to pass before tagging:
   ```bash
   RUN_ID="$(gh run list --branch main --limit 1 --json databaseId --jq '.[0].databaseId')"
   gh run watch "$RUN_ID" --exit-status
   ```
   *(Never combine pushing a brand-new `release.yml` and a release tag in one push, and never tag a commit before remote CI is green.)*

5. **Tag, Push Tag & Verify Remote GitHub Release (Mandatory Gate)**:
   ```bash
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   git push origin vX.Y.Z
   REL_ID="$(gh run list --workflow release.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
   gh run watch "$REL_ID" --exit-status
   gh release view vX.Y.Z --json name,tagName,url,assets
   ```
   Do **not** declare a release complete until both `CI` (all matrix jobs) and `Release` (`milestone-progress-vX.Y.Z.zip` + `SHA256SUMS.txt` published) have been verified as `success`.

---

## 4. Three-Layer Architecture Separation & Isolation Rules

To keep the runtime plugin lightweight, the public open-source repo clean, and local maintainer notes private, files in this repository are strictly partitioned into **three isolated layers**:

| Layer | Purpose | Synced to Global Plugin Dir (`~/.gemini/config/plugins/...`) | Committed & Pushed to GitHub | Included Paths |
| :--- | :--- | :--- | :--- | :--- |
| **Layer 1: Runtime Plugin Bundle** | Core plugin executed by Antigravity (exact allowlist in `scripts/sync.py`) | ✅ Yes (10 files) | ✅ Yes | `plugin.json`, `hooks.json`, `assets/logo.svg`, `rules/AGENTS.md`, `skills/milestone-mode/SKILL.md`, `hooks/progress_hook.py`, `hooks/i18n.py`, `hooks/locales/*.json` |
| **Layer 2: Public Open-Source Engineering & Ledgers** | Community docs, version/bug/compat ledgers, tests, scripts, and CI/CD | ❌ Never | ✅ Yes | `README.md`, `README.zh-CN.md`, `CHANGELOG.md`, `CHANGELOG.zh-CN.md`, `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`, `docs/{COMPATIBILITY,BUG_LOG,RELEASE_PROCESS,RETROSPECTIVE}.md`, `scripts/`, `tests/`, `.github/` |
| **Layer 3: Local-Only Dev & Private Ledger** | Local workspace agent rules, personal troubleshooting drafts, build output | ❌ Never | ❌ Never (`.gitignore`) | `.agents/`, `.local-ops/`, `dist/`, local caches & temp files (`*.lock`, `*.tmp`, `__pycache__/`) |

Isolation is enforced automatically by:
1. `.gitignore` blocking all Layer 3 paths from entering Git staging;
2. `scripts/sync.py:discover_runtime_files()` syncing and packaging **only** Layer 1 files;
3. `tests/test_repo_integrity.py` asserting that neither Layer 2 nor Layer 3 paths can leak into the runtime bundle and that `.gitignore` preserves Layer 3 exclusions.
