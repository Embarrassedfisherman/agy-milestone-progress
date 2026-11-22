#!/usr/bin/env python3
"""Repository integrity, AGY manifest compliance, and Python 3.9+ AST guards."""

from __future__ import annotations

import ast
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import doctor  # noqa: E402
import release  # noqa: E402
import sync  # noqa: E402


class RepoIntegrityTests(unittest.TestCase):
    def test_plugin_json_strict_agy_compliance(self) -> None:
        manifest = json.loads((ROOT_DIR / "plugin.json").read_text(encoding="utf-8"))
        unknown = set(manifest.keys()) - doctor.ALLOWED_PLUGIN_FIELDS
        self.assertEqual(unknown, set(), f"Disallowed plugin.json top-level fields: {unknown}")
        self.assertEqual(manifest["name"], "milestone-progress")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")

        logo = manifest.get("logo")
        self.assertIsInstance(logo, str)
        self.assertTrue((ROOT_DIR / logo).is_file(), f"Declared logo missing: {logo}")

        prompts = manifest.get("suggestedPrompts")
        self.assertIsInstance(prompts, list)
        self.assertGreaterEqual(len(prompts), 1)
        self.assertLessEqual(len(prompts), 3)
        for prompt in prompts:
            self.assertIsInstance(prompt, str)
            self.assertTrue(prompt.strip())

    def test_hooks_json_structure_and_script_target(self) -> None:
        hooks_data = json.loads((ROOT_DIR / "hooks.json").read_text(encoding="utf-8"))
        spec = hooks_data["milestone-progress"]
        for event in ("SessionStart", "PostToolUse", "PreInvocation", "Stop"):
            self.assertIn(event, spec)
            self.assertIsInstance(spec[event], list)
            self.assertGreaterEqual(len(spec[event]), 1)

        # PostToolUse must use grouped matcher + hooks wrapper
        post_entry = spec["PostToolUse"][0]
        self.assertIn("matcher", post_entry)
        self.assertIn("hooks", post_entry)
        self.assertTrue((ROOT_DIR / "hooks" / "progress_hook.py").is_file())

    def test_rules_budget_and_no_frontmatter(self) -> None:
        rules_path = ROOT_DIR / "rules" / "AGENTS.md"
        raw = rules_path.read_bytes()
        self.assertLess(len(raw), doctor.MAX_RULE_BYTES)
        text = raw.decode("utf-8")
        self.assertFalse(text.lstrip("\ufeff").startswith("---\n"))
        self.assertFalse(text.lstrip("\ufeff").startswith("---\r\n"))

    def test_skill_md_frontmatter(self) -> None:
        skill_text = (ROOT_DIR / "skills" / "milestone-mode" / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(skill_text.startswith("---\n"))
        self.assertIn("\nname: milestone-mode\n", skill_text)
        self.assertIn("\ndescription:", skill_text)

    def test_sync_allowlist_covers_runtime_and_excludes_repo_ops(self) -> None:
        runtime = set(sync.discover_runtime_files(ROOT_DIR))
        expected_present = {
            "plugin.json",
            "hooks.json",
            "assets/logo.svg",
            "rules/AGENTS.md",
            "skills/milestone-mode/SKILL.md",
            "hooks/progress_hook.py",
            "hooks/i18n.py",
        }
        self.assertTrue(expected_present.issubset(runtime))

        # Every hooks/*.py and hooks/locales/*.json must be in the runtime allowlist
        for py_file in (ROOT_DIR / "hooks").glob("*.py"):
            self.assertIn(py_file.relative_to(ROOT_DIR).as_posix(), runtime)
        for loc_file in (ROOT_DIR / "hooks" / "locales").glob("*.json"):
            self.assertIn(loc_file.relative_to(ROOT_DIR).as_posix(), runtime)

        # Repo ops/docs/CI files must NEVER leak into the synced plugin directory
        forbidden_prefixes = ("docs/", "tests/", "scripts/", ".github/", "CHANGELOG", "README")
        for rel in runtime:
            self.assertFalse(
                rel.startswith(forbidden_prefixes),
                f"Non-runtime file leaked into sync allowlist: {rel}",
            )

    def test_doctor_ci_and_release_package_roundtrip(self) -> None:
        report = doctor.collect_report(ROOT_DIR, ci_mode=True, with_tests=False)
        self.assertEqual(report["counts"]["error"], 0, report)

        with tempfile.TemporaryDirectory() as td:
            out_zip = Path(td) / "test-pkg.zip"
            packed = release.build_package(ROOT_DIR, "9.9.9", out_zip)
            self.assertTrue(out_zip.is_file())
            with zipfile.ZipFile(out_zip, "r") as zf:
                names = zf.namelist()
                self.assertEqual(names, packed)
                zip_manifest = json.loads(zf.read("plugin.json").decode("utf-8"))
                self.assertEqual(zip_manifest["version"], "9.9.9")

    def test_python_39_runtime_syntax_guard(self) -> None:
        """Ensure all Python modules stay compatible with stock macOS Python 3.9."""
        py_files = [
            *sorted((ROOT_DIR / "hooks").glob("*.py")),
            *sorted((ROOT_DIR / "scripts").glob("*.py")),
            *sorted((ROOT_DIR / "tests").glob("*.py")),
        ]
        self.assertGreaterEqual(len(py_files), 6)

        for path in py_files:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))

            # Must enable PEP 563 postponed annotations
            has_future_annotations = any(
                isinstance(node, ast.ImportFrom)
                and node.module == "__future__"
                and any(alias.name == "annotations" for alias in node.names)
                for node in tree.body[:6]
            )
            self.assertTrue(
                has_future_annotations,
                f"{path.relative_to(ROOT_DIR)} must import `from __future__ import annotations` for Python 3.9",
            )

            # Disallow Python 3.10+ match statements and runtime `isinstance(x, A | B)`
            for node in ast.walk(tree):
                self.assertNotEqual(
                    type(node).__name__,
                    "Match",
                    f"Python 3.10+ match statement found in {path.relative_to(ROOT_DIR)}",
                )
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in {"isinstance", "issubclass"}
                    and len(node.args) >= 2
                ):
                    second_arg = node.args[1]
                    self.assertFalse(
                        isinstance(second_arg, ast.BinOp) and isinstance(second_arg.op, ast.BitOr),
                        f"Python 3.10+ union in isinstance/issubclass found in {path.relative_to(ROOT_DIR)}",
                    )


if __name__ == "__main__":
    unittest.main()
