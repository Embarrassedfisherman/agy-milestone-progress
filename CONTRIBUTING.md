# Contributing to Milestone Progress

Thank you for helping make **Milestone Progress (`milestone-progress`)** better for Antigravity users worldwide!

---

## 1. Engineering Principles

- **Zero third-party dependencies**: Everything under `hooks/` and `scripts/` must use the Python standard library only.
- **Strict Python 3.9+ compatibility**: Stock macOS ships Python `3.9.6`. Always start Python files with `from __future__ import annotations` and avoid Python 3.10+ runtime-only constructs (`match/case`, `isinstance(x, A | B)`). This is automatically enforced by `tests/test_repo_integrity.py` and GitHub Actions CI.
- **Metadata-free `systemMessage` payloads**: Never attach `metadata` to `PreInvocation` `systemMessage` responses (see `UPSTREAM-002` in [docs/BUG_LOG.md](./docs/BUG_LOG.md)).
- **Lean rules budget**: Keep `rules/AGENTS.md` concise and well under Antigravity's `24,000`-byte cap, with no YAML frontmatter.
- **Clean runtime separation**: Only files returned by `scripts/sync.py:discover_runtime_files()` are synced to `~/.gemini/config/plugins/milestone-progress`.

---

## 2. Local Setup & Verification

```bash
git clone https://github.com/Embarrassedfisherman/agy-milestone-progress.git
cd agy-milestone-progress

# 1. Run full unit, i18n parity, and repo integrity test suite
python3 -m unittest discover -s tests -v

# 2. Run strict CI diagnostics
python3 scripts/doctor.py --ci --strict

# 3. Validate against Antigravity's official plugin loader (if `agy` is installed)
agy plugin validate . --strict

# 4. Sync to your local Antigravity plugin directory for live testing
python3 scripts/sync.py --clean
```

---

## 3. Adding a New Language (3 Steps)

Want to add Korean (`ko`), French (`fr`), German (`de`), Spanish (`es`), or another locale to the Hook runtime?

1. Copy [hooks/locales/en.json](./hooks/locales/en.json) to `hooks/locales/<code>.json` (lowercase ISO 639-1 code, e.g., `ko.json`, `fr.json`).
2. Update `"meta": {"code": "<code>", "name": "<Native Language Name>"}` and translate every string while preserving all `{placeholder}` tokens verbatim (such as `{inv_count}`, `{interval}`, `{elapsed}`, `{summary}`, `{project}`, `{tool_count}`, `{extra}`, `{name}`).
3. Run the automated parity tests—they automatically discover your new file and verify exact key & placeholder parity:
   ```bash
   python3 -m unittest discover -s tests -v
   ```

*(Optional)* If your language uses a distinct script not yet detected in `hooks/i18n.py:detect_text_language()`, add detection tests in `tests/test_i18n.py`.

---

## 4. Commit & PR Guidelines

- Follow **Conventional Commits**: `feat:`, `fix:`, `compat:`, `i18n:`, `docs:`, `test:`, `chore:`.
- For bug fixes or Antigravity client update adaptations:
  - Add or update an entry in [docs/BUG_LOG.md](./docs/BUG_LOG.md) and/or [docs/COMPATIBILITY.md](./docs/COMPATIBILITY.md).
  - Add a bullet under `## [Unreleased]` in [CHANGELOG.md](./CHANGELOG.md) (and [CHANGELOG.zh-CN.md](./CHANGELOG.zh-CN.md) if comfortable with Chinese; maintainers can assist with translation).
  - Include a regression test in `tests/`.
