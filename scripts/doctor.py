#!/usr/bin/env python3
"""Health, integrity, and Antigravity compatibility diagnostic tool for milestone-progress."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import platform
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
MIN_PYTHON = (3, 9)
MAX_RULE_BYTES = 24_000
WARN_RULE_BYTES = 18_000
ALLOWED_PLUGIN_FIELDS = frozenset(
    {
        "name",
        "displayName",
        "description",
        "version",
        "logo",
        "suggestedPrompts",
        "author",
        "homepage",
        "repository",
        "disabled",
    }
)
REQUIRED_HOOK_EVENTS = ("SessionStart", "PostToolUse", "PreInvocation", "Stop")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _discover_runtime_files(repo_root: Path) -> list[str]:
    candidates: list[str] = [
        "plugin.json",
        "hooks.json",
        "rules/AGENTS.md",
        "skills/milestone-mode/SKILL.md",
        "hooks/progress_hook.py",
    ]
    plugin_json = repo_root / "plugin.json"
    if plugin_json.exists():
        try:
            manifest = json.loads(plugin_json.read_text(encoding="utf-8"))
            logo = manifest.get("logo")
            if isinstance(logo, str) and logo.strip():
                candidates.append(logo.strip())
        except (OSError, ValueError):
            pass

    i18n_mod = repo_root / "hooks" / "i18n.py"
    if i18n_mod.exists():
        candidates.append("hooks/i18n.py")

    locales_dir = repo_root / "hooks" / "locales"
    if locales_dir.is_dir():
        for entry in sorted(locales_dir.glob("*.json")):
            candidates.append(entry.relative_to(repo_root).as_posix())

    seen: set[str] = set()
    ordered: list[str] = []
    for rel in candidates:
        if rel not in seen:
            seen.add(rel)
            ordered.append(rel)
    return ordered


def _run_cmd(args: list[str], timeout: int = 10) -> tuple[int | None, str, str]:
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return None, "", str(exc)


def _detect_agy_app_version() -> str | None:
    if sys.platform != "darwin":
        return None
    plist_path = Path("/Applications/Antigravity.app/Contents/Info.plist")
    if not plist_path.exists():
        return None
    try:
        with plist_path.open("rb") as fh:
            data = plistlib.load(fh)
        val = data.get("CFBundleShortVersionString")
        return str(val).strip() if val else None
    except (OSError, ValueError, plistlib.InvalidFileException):
        return None


def _detect_agy_cli_version() -> str | None:
    agy_bin = shutil.which("agy")
    if not agy_bin:
        return None
    code, stdout, _ = _run_cmd([agy_bin, "--version"], timeout=5)
    if code == 0 and stdout:
        return stdout.splitlines()[0].strip()
    return None


def _check_python() -> dict[str, Any]:
    ver = sys.version_info[:3]
    ver_str = f"{ver[0]}.{ver[1]}.{ver[2]}"
    ok = sys.version_info >= MIN_PYTHON
    return {
        "id": "python_version",
        "status": "ok" if ok else "error",
        "summary": f"Python {ver_str} ({'supported >= 3.9' if ok else 'requires >= 3.9'})",
        "details": {"version": ver_str, "executable": sys.executable},
    }


def _check_platform_notify() -> dict[str, Any]:
    os_label = f"{platform.system()} {platform.release()} ({platform.machine()})"
    if sys.platform == "darwin":
        has_osa = shutil.which("osascript") is not None
        backend = "osascript (available)" if has_osa else "osascript (missing)"
        status = "ok" if has_osa else "warn"
    elif sys.platform.startswith("linux"):
        has_ns = shutil.which("notify-send") is not None
        backend = "notify-send (available)" if has_ns else "none (graceful no-op)"
        status = "ok"
    else:
        backend = "skipped on Windows (core hooks unaffected)"
        status = "ok"
    return {
        "id": "platform_notify",
        "status": status,
        "summary": f"{os_label} | notifications: {backend}",
        "details": {"platform": sys.platform, "os": os_label, "backend": backend},
    }


def _check_agy_environment(ci_mode: bool) -> dict[str, Any]:
    app_ver = _detect_agy_app_version()
    cli_ver = _detect_agy_cli_version()
    if ci_mode and not app_ver and not cli_ver:
        return {
            "id": "agy_environment",
            "status": "skip",
            "summary": "Skipped in CI mode (no local Antigravity installation expected)",
            "details": {"app_version": None, "cli_version": None},
        }
    parts: list[str] = []
    if app_ver:
        parts.append(f"App {app_ver}")
    if cli_ver:
        parts.append(f"CLI {cli_ver}")
    if not parts:
        return {
            "id": "agy_environment",
            "status": "warn",
            "summary": "Neither Antigravity.app nor `agy` CLI detected on PATH",
            "details": {"app_version": None, "cli_version": None},
        }
    return {
        "id": "agy_environment",
        "status": "ok",
        "summary": " / ".join(parts),
        "details": {"app_version": app_ver, "cli_version": cli_ver},
    }


def _check_manifest(repo_root: Path) -> dict[str, Any]:
    manifest_path = repo_root / "plugin.json"
    if not manifest_path.exists():
        return {
            "id": "manifest_integrity",
            "status": "error",
            "summary": "plugin.json is missing",
            "details": {},
        }
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {
            "id": "manifest_integrity",
            "status": "error",
            "summary": f"plugin.json invalid JSON: {exc}",
            "details": {},
        }
    if not isinstance(data, dict):
        return {
            "id": "manifest_integrity",
            "status": "error",
            "summary": "plugin.json root must be a JSON object",
            "details": {},
        }

    unknown = sorted(set(data.keys()) - ALLOWED_PLUGIN_FIELDS)
    issues: list[str] = []
    status = "ok"
    if not data.get("name"):
        issues.append("missing 'name'")
        status = "error"
    if not data.get("version"):
        issues.append("missing 'version'")
        status = "warn" if status == "ok" else status
    if unknown:
        issues.append(f"unknown top-level fields (silently dropped by AGY): {', '.join(unknown)}")
        status = "error"
    logo = data.get("logo")
    if isinstance(logo, str) and logo.strip():
        logo_path = repo_root / logo.strip()
        if not logo_path.exists():
            issues.append(f"declared logo not found: {logo}")
            status = "error"

    version = str(data.get("version") or "unknown")
    name = str(data.get("name") or "unknown")
    summary = f"{name} v{version}"
    if issues:
        summary += f" ({'; '.join(issues)})"
    return {
        "id": "manifest_integrity",
        "status": status,
        "summary": summary,
        "details": {"name": name, "version": version, "unknown_fields": unknown, "issues": issues},
    }


def _check_hooks(repo_root: Path) -> dict[str, Any]:
    hooks_path = repo_root / "hooks.json"
    if not hooks_path.exists():
        return {
            "id": "hooks_integrity",
            "status": "error",
            "summary": "hooks.json is missing",
            "details": {},
        }
    try:
        data = json.loads(hooks_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {
            "id": "hooks_integrity",
            "status": "error",
            "summary": f"hooks.json invalid JSON: {exc}",
            "details": {},
        }
    spec = data.get("milestone-progress") if isinstance(data, dict) else None
    if not isinstance(spec, dict):
        return {
            "id": "hooks_integrity",
            "status": "error",
            "summary": "hooks.json missing top-level 'milestone-progress' spec",
            "details": {},
        }

    missing_events = [ev for ev in REQUIRED_HOOK_EVENTS if ev not in spec]
    hook_script = repo_root / "hooks" / "progress_hook.py"
    issues: list[str] = []
    if missing_events:
        issues.append(f"missing events: {', '.join(missing_events)}")
    if not hook_script.exists():
        issues.append("hooks/progress_hook.py missing")

    if issues:
        return {
            "id": "hooks_integrity",
            "status": "error",
            "summary": "; ".join(issues),
            "details": {"missing_events": missing_events},
        }
    return {
        "id": "hooks_integrity",
        "status": "ok",
        "summary": f"All {len(REQUIRED_HOOK_EVENTS)} lifecycle events registered (progress_hook.py present)",
        "details": {"events": list(REQUIRED_HOOK_EVENTS)},
    }


def _check_rules_budget(repo_root: Path) -> dict[str, Any]:
    rules_path = repo_root / "rules" / "AGENTS.md"
    if not rules_path.exists():
        return {
            "id": "rules_budget",
            "status": "error",
            "summary": "rules/AGENTS.md is missing",
            "details": {},
        }
    raw = rules_path.read_bytes()
    size = len(raw)
    text = raw.decode("utf-8", errors="replace")
    has_frontmatter = text.lstrip("\ufeff").startswith("---\n") or text.lstrip("\ufeff").startswith("---\r\n")

    if size > MAX_RULE_BYTES:
        status = "error"
        note = f"exceeds AGY {MAX_RULE_BYTES}B cap"
    elif has_frontmatter:
        status = "error"
        note = "plugin rules/AGENTS.md must not contain YAML frontmatter"
    elif size > WARN_RULE_BYTES:
        status = "warn"
        note = f"approaching AGY {MAX_RULE_BYTES}B cap"
    else:
        status = "ok"
        note = f"within AGY {MAX_RULE_BYTES}B cap"

    return {
        "id": "rules_budget",
        "status": status,
        "summary": f"rules/AGENTS.md is {size} bytes ({note})",
        "details": {"bytes": size, "cap": MAX_RULE_BYTES, "has_frontmatter": has_frontmatter},
    }


def _check_agy_validate(repo_root: Path, ci_mode: bool) -> dict[str, Any]:
    agy_bin = shutil.which("agy")
    if not agy_bin:
        return {
            "id": "agy_validate",
            "status": "skip",
            "summary": "Skipped (`agy` CLI not installed in this environment)",
            "details": {},
        }
    code, stdout, stderr = _run_cmd(
        [agy_bin, "plugin", "validate", str(repo_root), "--strict", "--json"],
        timeout=15,
    )
    findings: list[dict[str, Any]] = []
    parsed: dict[str, Any] = {}
    if stdout:
        try:
            parsed = json.loads(stdout)
            if isinstance(parsed.get("findings"), list):
                findings = parsed["findings"]
        except ValueError:
            pass

    errors = [f for f in findings if f.get("severity") == "error"]
    warnings = [f for f in findings if f.get("severity") == "warning"]
    notes = [f for f in findings if f.get("severity") == "note"]

    if code == 0:
        status = "ok"
        summary = f"Passed ({len(errors)} errors, {len(warnings)} warnings, {len(notes)} notes)"
    else:
        status = "error"
        detail = stderr or stdout or f"exit code {code}"
        summary = f"Failed ({len(errors)} errors, {len(warnings)} warnings): {detail[:120]}"

    return {
        "id": "agy_validate",
        "status": status,
        "summary": summary,
        "details": {
            "exit_code": code,
            "errors": len(errors),
            "warnings": len(warnings),
            "notes": len(notes),
            "findings": findings,
            "components": parsed.get("components"),
        },
    }


def _check_sync_status(repo_root: Path, ci_mode: bool) -> dict[str, Any]:
    if ci_mode:
        return {
            "id": "sync_status",
            "status": "skip",
            "summary": "Skipped in CI mode",
            "details": {},
        }
    installed_dir = Path(
        os.environ.get("MILESTONE_PLUGIN_DIR")
        or (Path.home() / ".gemini" / "config" / "plugins" / "milestone-progress")
    )
    if not installed_dir.exists():
        return {
            "id": "sync_status",
            "status": "warn",
            "summary": f"Plugin not installed at {installed_dir} (run sync script to install)",
            "details": {"installed_dir": str(installed_dir), "installed": False},
        }

    runtime_files = _discover_runtime_files(repo_root)
    missing: list[str] = []
    drifted: list[str] = []
    for rel in runtime_files:
        src = repo_root / rel
        dst = installed_dir / rel
        if not src.exists():
            continue
        if not dst.exists():
            missing.append(rel)
        elif _sha256(src) != _sha256(dst):
            drifted.append(rel)

    if missing or drifted:
        parts = []
        if missing:
            parts.append(f"missing: {', '.join(missing)}")
        if drifted:
            parts.append(f"out-of-sync: {', '.join(drifted)}")
        return {
            "id": "sync_status",
            "status": "warn",
            "summary": f"Installed copy differs from workspace ({'; '.join(parts)})",
            "details": {
                "installed_dir": str(installed_dir),
                "missing": missing,
                "drifted": drifted,
            },
        }
    return {
        "id": "sync_status",
        "status": "ok",
        "summary": f"All {len(runtime_files)} runtime files match {installed_dir}",
        "details": {"installed_dir": str(installed_dir), "checked": len(runtime_files)},
    }


def _check_runtime_state(ci_mode: bool) -> dict[str, Any]:
    if ci_mode:
        return {
            "id": "runtime_state",
            "status": "skip",
            "summary": "Skipped in CI mode",
            "details": {},
        }
    env_override = os.environ.get("MILESTONE_PLUGIN_DATA")
    env_plugin_data = os.environ.get("PLUGIN_DATA")
    if env_override:
        plugin_data_dir = Path(env_override)
    elif env_plugin_data and Path(env_plugin_data).name == "milestone-progress":
        plugin_data_dir = Path(env_plugin_data)
    else:
        plugin_data_dir = Path.home() / ".gemini" / "antigravity" / "plugin_data" / "milestone-progress"
    state_dir = plugin_data_dir / "milestone-progress-state"
    config_file = plugin_data_dir / "config.json"

    issues: list[str] = []
    status = "ok"
    json_count = 0
    lock_count = 0
    tmp_count = 0

    if state_dir.is_dir():
        try:
            for entry in state_dir.iterdir():
                if not entry.is_file():
                    continue
                if entry.suffix == ".json":
                    json_count += 1
                elif entry.suffix == ".lock":
                    lock_count += 1
                elif entry.suffix == ".tmp":
                    tmp_count += 1
        except OSError as exc:
            return {
                "id": "runtime_state",
                "status": "warn",
                "summary": f"Could not inspect {state_dir}: {exc}",
                "details": {"state_dir": str(state_dir)},
            }
        if tmp_count > 0:
            issues.append(f"{tmp_count} leftover .tmp file(s)")
            status = "warn"
    else:
        issues.append("state dir not created yet")

    config_status = "absent (defaults active)"
    if config_file.exists():
        try:
            cfg = json.loads(config_file.read_text(encoding="utf-8"))
            if isinstance(cfg, dict):
                config_status = f"valid ({len(cfg)} key(s))"
            else:
                config_status = "invalid (root must be JSON object)"
                issues.append("config.json root is not an object")
                status = "error"
        except (OSError, ValueError) as exc:
            config_status = f"invalid ({exc})"
            issues.append(f"invalid config.json: {exc}")
            status = "error"

    summary = f"state files: {json_count} json / {lock_count} lock / {tmp_count} tmp | config.json: {config_status}"
    if issues:
        summary += f" ({'; '.join(issues)})"
    return {
        "id": "runtime_state",
        "status": status,
        "summary": summary,
        "details": {
            "state_dir": str(state_dir),
            "json_files": json_count,
            "lock_files": lock_count,
            "tmp_files": tmp_count,
            "config_status": config_status,
        },
    }


def _check_unit_tests(repo_root: Path) -> dict[str, Any]:
    code, stdout, stderr = _run_cmd(
        [sys.executable, "-m", "unittest", "discover", "-s", str(repo_root / "tests")],
        timeout=30,
    )
    combined = "\n".join(part for part in (stderr, stdout) if part).strip()
    last_lines = [line.strip() for line in combined.splitlines() if line.strip()][-2:]
    tail = " | ".join(last_lines) if last_lines else f"exit code {code}"
    return {
        "id": "unit_tests",
        "status": "ok" if code == 0 else "error",
        "summary": tail,
        "details": {"exit_code": code},
    }


def collect_report(
    repo_root: Path, ci_mode: bool = False, with_tests: bool | None = None
) -> dict[str, Any]:
    run_tests = ci_mode if with_tests is None else with_tests
    checks = [
        _check_python(),
        _check_platform_notify(),
        _check_agy_environment(ci_mode),
        _check_manifest(repo_root),
        _check_hooks(repo_root),
        _check_rules_budget(repo_root),
        _check_agy_validate(repo_root, ci_mode),
        _check_sync_status(repo_root, ci_mode),
        _check_runtime_state(ci_mode),
    ]
    if run_tests:
        checks.append(_check_unit_tests(repo_root))

    counts = {"ok": 0, "warn": 0, "error": 0, "skip": 0}
    for chk in checks:
        counts[chk["status"]] = counts.get(chk["status"], 0) + 1

    return {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date": datetime.date.today().isoformat(),
        "repo_root": str(repo_root),
        "counts": counts,
        "checks": checks,
    }


def _format_plain(report: dict[str, Any]) -> str:
    icons = {"ok": "✅", "warn": "⚠️", "error": "❌", "skip": "⏭️"}
    lines = [
        f"Milestone Progress Doctor ({report['timestamp']})",
        f"Repo: {report['repo_root']}",
        "",
    ]
    for chk in report["checks"]:
        icon = icons.get(chk["status"], "•")
        lines.append(f"  {icon} [{chk['id']}] {chk['summary']}")
    c = report["counts"]
    lines.append("")
    lines.append(
        f"Summary: {c['ok']} ok, {c['warn']} warn, {c['error']} error, {c['skip']} skipped"
    )
    return "\n".join(lines)


def _format_markdown(report: dict[str, Any]) -> str:
    by_id = {chk["id"]: chk for chk in report["checks"]}
    plugin_ver = by_id["manifest_integrity"]["details"].get("version", "unknown")
    agy_det = by_id["agy_environment"]["details"]
    app_ver = agy_det.get("app_version") or "—"
    cli_ver = agy_det.get("cli_version") or "—"
    os_name = by_id["platform_notify"]["details"].get("os", platform.system())
    py_ver = by_id["python_version"]["details"].get("version", "unknown")
    val_chk = by_id["agy_validate"]
    val_text = val_chk["summary"]
    overall = "❌ Failed" if report["counts"]["error"] else (
        "⚠️ Warnings" if report["counts"]["warn"] else "✅ Compatible"
    )

    lines = [
        "### Doctor Diagnostic Report",
        "",
        "#### Compatibility Matrix Row (paste into `docs/COMPATIBILITY.md`)",
        "",
        "| Date | Plugin Ver | AGY App | `agy` CLI | OS / Arch | Python | `agy plugin validate --strict` | Status |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        f"| {report['date']} | `{plugin_ver}` | `{app_ver}` | `{cli_ver}` | {os_name} | `{py_ver}` | {val_text} | {overall} |",
        "",
        "#### Check Details",
        "",
    ]
    icons = {"ok": "✅", "warn": "⚠️", "error": "❌", "skip": "⏭️"}
    for chk in report["checks"]:
        lines.append(f"- {icons.get(chk['status'], '•')} **`{chk['id']}`**: {chk['summary']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="Check milestone-progress health, sync state, and Antigravity compatibility."
    )
    parser.add_argument("--ci", action="store_true", help="CI mode (skip local install/state checks, run unit tests unless --skip-tests).")
    parser.add_argument("--with-tests", action="store_true", help="Also execute the unit test suite.")
    parser.add_argument("--skip-tests", action="store_true", help="Do not run unit tests even in --ci mode.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on warnings as well as errors.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--json", action="store_true", help="Output report as JSON.")
    group.add_argument("--markdown", action="store_true", help="Output report as Markdown.")
    args = parser.parse_args(argv)

    with_tests: bool | None = None
    if args.skip_tests:
        with_tests = False
    elif args.with_tests:
        with_tests = True

    report = collect_report(ROOT_DIR, ci_mode=args.ci, with_tests=with_tests)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif args.markdown:
        print(_format_markdown(report))
    else:
        print(_format_plain(report))

    if report["counts"]["error"] > 0:
        return 1
    if args.strict and report["counts"]["warn"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
