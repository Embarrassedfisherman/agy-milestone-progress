#!/usr/bin/env python3
"""Cross-platform installer and syncer for the milestone-progress Antigravity plugin."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "plugin.json",
    "hooks.json",
    "rules/AGENTS.md",
    "skills/milestone-mode/SKILL.md",
    "hooks/progress_hook.py",
)
MANAGED_SUBDIRS = ("assets", "hooks", "rules", "skills")


def discover_runtime_files(repo_root: Path = ROOT_DIR) -> list[str]:
    """Return the exact sorted runtime bundle allowlist to sync or package."""
    files: list[str] = list(REQUIRED_FILES)

    manifest_path = repo_root / "plugin.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        logo = manifest.get("logo")
        if isinstance(logo, str) and logo.strip():
            files.append(logo.strip())

    i18n_file = repo_root / "hooks" / "i18n.py"
    if i18n_file.is_file():
        files.append("hooks/i18n.py")

    locales_dir = repo_root / "hooks" / "locales"
    if locales_dir.is_dir():
        for entry in sorted(locales_dir.glob("*.json")):
            if entry.is_file():
                files.append(entry.relative_to(repo_root).as_posix())

    deduped: list[str] = []
    seen: set[str] = set()
    for rel in files:
        norm = Path(rel).as_posix()
        if norm not in seen:
            seen.add(norm)
            if not (repo_root / norm).is_file():
                raise FileNotFoundError(f"Required runtime file not found: {norm}")
            deduped.append(norm)
    return deduped


def default_target_dir() -> Path:
    override = os.environ.get("MILESTONE_PLUGIN_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".gemini" / "config" / "plugins" / "milestone-progress"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_unit_tests(repo_root: Path) -> bool:
    print("==> 1/4 Running unit tests...")
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", str(repo_root / "tests"), "-v"],
        check=False,
    )
    return proc.returncode == 0


def _run_agy_validate(repo_root: Path) -> bool:
    agy_bin = shutil.which("agy")
    if not agy_bin:
        print("==> 2/4 Skipping `agy plugin validate` (`agy` CLI not on PATH).")
        return True
    print("==> 2/4 Validating plugin manifest with `agy plugin validate --strict`...")
    proc = subprocess.run(
        [agy_bin, "plugin", "validate", str(repo_root), "--strict"],
        check=False,
    )
    return proc.returncode == 0


def _check_sync(repo_root: Path, target_dir: Path, runtime_files: list[str]) -> bool:
    print(f"==> Checking sync against {target_dir}...")
    ok = True
    for rel in runtime_files:
        src = repo_root / rel
        dst = target_dir / rel
        if not dst.is_file():
            print(f"  MISSING: {rel}")
            ok = False
        elif _sha256(src) != _sha256(dst):
            print(f"  DRIFTED: {rel}")
            ok = False
        else:
            print(f"  OK: {rel}")
    return ok


def _clean_stale_files(target_dir: Path, expected: set[str]) -> list[str]:
    removed: list[str] = []
    if not target_dir.is_dir():
        return removed
    for subdir_name in MANAGED_SUBDIRS:
        subdir = target_dir / subdir_name
        if not subdir.is_dir():
            continue
        for entry in sorted(subdir.rglob("*")):
            if not entry.is_file():
                continue
            if "__pycache__" in entry.parts or entry.suffix in {".pyc", ".pyo"}:
                continue
            rel = entry.relative_to(target_dir).as_posix()
            if rel not in expected:
                entry.unlink()
                removed.append(rel)
    return removed


def sync_plugin(
    repo_root: Path,
    target_dir: Path,
    *,
    skip_tests: bool = False,
    skip_validate: bool = False,
    check_only: bool = False,
    clean: bool = False,
) -> int:
    runtime_files = discover_runtime_files(repo_root)

    if not skip_tests:
        if not _run_unit_tests(repo_root):
            print("ERROR: Unit tests failed; aborting sync.", file=sys.stderr)
            return 1

    if not skip_validate:
        if not _run_agy_validate(repo_root):
            print("ERROR: `agy plugin validate --strict` failed; aborting sync.", file=sys.stderr)
            return 1

    if check_only:
        return 0 if _check_sync(repo_root, target_dir, runtime_files) else 1

    print(f"==> 3/4 Syncing {len(runtime_files)} runtime files to {target_dir}...")
    for rel in runtime_files:
        src = repo_root / rel
        dst = target_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    if clean:
        removed = _clean_stale_files(target_dir, set(runtime_files))
        for rel in removed:
            print(f"  REMOVED stale file: {rel}")

    print("==> 4/4 Verifying SHA-256 integrity...")
    for rel in runtime_files:
        src = repo_root / rel
        dst = target_dir / rel
        if not dst.is_file() or _sha256(src) != _sha256(dst):
            print(f"ERROR: Verification failed for {rel}", file=sys.stderr)
            return 1
        print(f"  OK: {rel}")

    manifest = json.loads((repo_root / "plugin.json").read_text(encoding="utf-8"))
    version = manifest.get("version", "unknown")
    print(f"Done: milestone-progress v{version} synced and verified at {target_dir}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Test, validate, and sync milestone-progress runtime files to the Antigravity plugin directory."
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Destination plugin directory (defaults to MILESTONE_PLUGIN_DIR or ~/.gemini/config/plugins/milestone-progress).",
    )
    parser.add_argument("--skip-tests", action="store_true", help="Skip running the unit test suite.")
    parser.add_argument("--skip-validate", action="store_true", help="Skip running `agy plugin validate --strict`.")
    parser.add_argument("--check", action="store_true", help="Check whether destination matches workspace without copying.")
    parser.add_argument("--clean", action="store_true", help="Remove stale files from managed subdirectories at target.")
    args = parser.parse_args(argv)

    target = args.target.expanduser() if args.target else default_target_dir()
    return sync_plugin(
        ROOT_DIR,
        target,
        skip_tests=args.skip_tests,
        skip_validate=args.skip_validate,
        check_only=args.check,
        clean=args.clean,
    )


if __name__ == "__main__":
    raise SystemExit(main())
