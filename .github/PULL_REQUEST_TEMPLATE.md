## Summary

<!-- Briefly describe what this PR changes and why. Reference any BUG-NNN or Issue # if applicable. -->

## Type of Change

- [ ] Bug fix (`fix:`)
- [ ] New feature (`feat:`)
- [ ] Antigravity client compatibility update (`compat:`)
- [ ] Localization / new locale (`i18n:`)
- [ ] Documentation / ops ledger (`docs:`)
- [ ] CI / tooling (`chore:`)

## Checklist

- [ ] `python3 -m unittest discover -s tests -v` passes
- [ ] `python3 scripts/doctor.py --ci --strict` passes
- [ ] `agy plugin validate . --strict` passes with 0 errors and 0 warnings (if `agy` is installed locally)
- [ ] Python `3.9+` syntax compatibility preserved (no runtime `match/case` or `isinstance(x, A | B)`)
- [ ] If adding/changing user-facing hook strings, all files in `hooks/locales/*.json` keep matching keys and placeholders
- [ ] Updated `CHANGELOG.md` / `CHANGELOG.zh-CN.md` (under `[Unreleased]`) and `docs/BUG_LOG.md` / `docs/COMPATIBILITY.md` if applicable
