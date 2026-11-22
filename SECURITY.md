# Security Policy

## Security Posture

**Milestone Progress (`milestone-progress`)** is designed with minimal privilege and zero external attack surface:

- **Zero network access**: None of the plugin's hooks, scripts, or rules make outbound HTTP/network calls.
- **Zero third-party dependencies**: Pure Python standard library only.
- **Local-only runtime state**: Per-conversation counters and locks are stored strictly under `$PLUGIN_DATA/milestone-progress-state/` (or system temp dir fallback) with atomic writes and 14-day automatic pruning.
- **Safe command invocation**: Desktop notifications use parameterized `osascript` (`on run argv`) or `notify-send` argument lists (never shell string interpolation) with a 2-second timeout.
- **No sensitive content persisted**: State files store only a truncated SHA-256 hash of `lastUserInput`, language code, numeric counters, and short tool labels.

## Supported Versions

| Version | Supported |
| :--- | :--- |
| `1.1.x` | ✅ Active support |
| `1.0.x` | ⚠️ Upgrade to `1.1.x` |

## Reporting a Vulnerability

If you discover a security vulnerability (for example, command injection, unsafe path handling, or state-file privilege issues), please avoid posting public exploit details in a regular issue. Instead:

1. Use **GitHub Private Vulnerability Reporting** under this repository's **Security → Advisories** tab, or
2. Open a minimal issue asking the maintainer for a private contact channel.

We aim to acknowledge reports within 72 hours and ship a patched release promptly.
