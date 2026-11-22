#!/usr/bin/env python3
"""Safe release preflight, version bumper, and clean runtime zip packager."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from sync import discover_runtime_files  # noqa: E402

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def _read_manifest(repo_root: Path) -> dict:
    return json.loads((repo_root / "plugin.json").read_text(encoding="utf-8"))


def _has_changelog_version(changelog_path: Path, version: str) -> bool:
    if not changelog_path.is_file():
        return False
    pattern = re.compile(rf"^##\s+\[{re.escape(version)}\](?:\s+-|\s*$)", re.MULTILINE)
    return pattern.search(changelog_path.read_text(encoding="utf-8")) is not None


def _run_tests(repo_root: Path) -> bool:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", str(repo_root / "tests")],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        print(proc.stdout, end="")
        print(proc.stderr, end="", file=sys.stderr)
        return False
    return True


def _run_agy_validate(target: Path) -> tuple[bool, str]:
    agy_bin = shutil.which("agy")
    if not agy_bin:
        return True, "skipped (`agy` CLI not installed)"
    proc = subprocess.run(
        [agy_bin, "plugin", "validate", str(target), "--strict", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        return False, detail or f"exit code {proc.returncode}"
    findings = []
    try:
        parsed = json.loads(proc.stdout)
        findings = parsed.get("findings") or []
    except ValueError:
        pass
    return True, f"passed ({len(findings)} finding(s))"


def build_package(repo_root: Path, version: str, output_path: Path) -> list[str]:
    runtime_files = discover_runtime_files(repo_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel in runtime_files:
            src = repo_root / rel
            if rel == "plugin.json":
                manifest = json.loads(src.read_text(encoding="utf-8"))
                manifest["version"] = version
                payload = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
                zf.writestr(rel, payload)
            else:
                zf.write(src, arcname=rel)
    return runtime_files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preflight, bump version, and package a clean release zip for milestone-progress."
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Target SemVer version (e.g. 1.1.0). Defaults to current plugin.json version.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the target version into plugin.json (without this flag, runs in safe dry-run mode).",
    )
    parser.add_argument(
        "--package",
        action="store_true",
        help="Build a clean runtime-only release archive under dist/.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Custom output path for --package (defaults to dist/milestone-progress-v<version>.zip).",
    )
    parser.add_argument(
        "--allow-unreleased",
        action="store_true",
        help="Allow running even when CHANGELOG.md does not yet have a dedicated [version] section.",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip running the unit test suite.",
    )
    args = parser.parse_args(argv)

    manifest = _read_manifest(ROOT_DIR)
    current_version = str(manifest.get("version") or "")
    target_version = args.version or current_version
    dry_run = not args.apply

    if not SEMVER_RE.fullmatch(target_version):
        print(f"ERROR: Invalid SemVer version: {target_version!r} (expected X.Y.Z)", file=sys.stderr)
        return 1

    mode_label = "DRY-RUN" if dry_run else "APPLY"
    print(f"==> Release preflight [{mode_label}]: current={current_version} -> target={target_version}")

    has_en_cl = _has_changelog_version(ROOT_DIR / "CHANGELOG.md", target_version)
    has_zh_cl = _has_changelog_version(ROOT_DIR / "CHANGELOG.zh-CN.md", target_version)
    print(f"  CHANGELOG.md       [{target_version}]: {'found' if has_en_cl else 'missing (still in [Unreleased]?)'}")
    print(f"  CHANGELOG.zh-CN.md [{target_version}]: {'found' if has_zh_cl else 'missing (still in [Unreleased]?)'}")

    if not dry_run and not args.allow_unreleased and not has_en_cl:
        print(
            f"ERROR: CHANGELOG.md is missing a '## [{target_version}]' section. "
            "Update CHANGELOG.md first or pass --allow-unreleased.",
            file=sys.stderr,
        )
        return 1

    if not args.skip_tests:
        print("==> Running unit tests...")
        if not _run_tests(ROOT_DIR):
            print("ERROR: Unit tests failed.", file=sys.stderr)
            return 1
        print("  Unit tests: OK")

    ok_val, msg_val = _run_agy_validate(ROOT_DIR)
    print(f"==> Repo `agy plugin validate --strict`: {msg_val}")
    if not ok_val:
        print("ERROR: Repo plugin validation failed.", file=sys.stderr)
        return 1

    if not dry_run and target_version != current_version:
        manifest["version"] = target_version
        (ROOT_DIR / "plugin.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"==> Updated plugin.json version to {target_version}")
    elif dry_run and target_version != current_version:
        print(f"==> [dry-run] Would update plugin.json version: {current_version} -> {target_version}")

    if args.package:
        out_zip = args.output or (ROOT_DIR / "dist" / f"milestone-progress-v{target_version}.zip")
        packed = build_package(ROOT_DIR, target_version, out_zip)
        print(f"==> Packaged {len(packed)} runtime files -> {out_zip}")
        for rel in packed:
            print(f"  + {rel}")
        ok_zip, msg_zip = _run_agy_validate(out_zip)
        print(f"==> Zip `agy plugin validate --strict`: {msg_zip}")
        if not ok_zip:
            print("ERROR: Packaged zip failed `agy plugin validate --strict`.", file=sys.stderr)
            return 1

    print("")
    print("Next release commands (run manually when ready):")
    print(f'  git add -A && git commit -m "chore(release): prepare v{target_version}"')
    print(f'  git tag -a v{target_version} -m "Release v{target_version}"')
    print("  git push origin main --follow-tags")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
