#!/usr/bin/env python3
"""Unit tests for i18n locale parity, language detection, and fallback safety."""

from __future__ import annotations

import json
import os
import string
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT_DIR = Path(__file__).resolve().parents[1]
HOOKS_DIR = ROOT_DIR / "hooks"
LOCALES_DIR = HOOKS_DIR / "locales"

if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

import i18n  # noqa: E402
import progress_hook  # noqa: E402


def _extract_placeholders(template: str) -> set[str]:
    formatter = string.Formatter()
    return {field_name for _, field_name, _, _ in formatter.parse(template) if field_name is not None}


class I18nTests(unittest.TestCase):
    def tearDown(self) -> None:
        i18n.clear_cache()

    def test_all_locale_files_match_english_schema_keys_and_placeholders(self) -> None:
        en_path = LOCALES_DIR / "en.json"
        self.assertTrue(en_path.is_file(), "en.json baseline locale must exist")
        en_data = json.loads(en_path.read_text(encoding="utf-8"))

        # Ensure en.json tool_labels exactly align with progress_hook.TOOL_CATEGORIES
        self.assertEqual(
            set(en_data["tool_labels"].keys()),
            set(progress_hook.TOOL_CATEGORIES.keys()),
            "en.json tool_labels keys must match progress_hook.TOOL_CATEGORIES",
        )

        locale_files = sorted(LOCALES_DIR.glob("*.json"))
        self.assertGreaterEqual(len(locale_files), 3, "Expected at least en, zh, ja locales")

        for locale_path in locale_files:
            code = locale_path.stem
            data = json.loads(locale_path.read_text(encoding="utf-8"))
            self.assertEqual(set(data.keys()), {"meta", "tool_labels", "labels", "messages"}, code)
            self.assertEqual(data["meta"]["code"], code, f"meta.code mismatch in {locale_path.name}")
            self.assertTrue(data["meta"]["name"].strip(), f"meta.name empty in {locale_path.name}")

            for section in ("tool_labels", "labels", "messages"):
                self.assertEqual(
                    set(data[section].keys()),
                    set(en_data[section].keys()),
                    f"Key mismatch in {locale_path.name} -> {section}",
                )
                for key, en_val in en_data[section].items():
                    val = data[section][key]
                    self.assertIsInstance(val, str, f"{locale_path.name}:{section}.{key}")
                    self.assertTrue(val.strip(), f"Empty string in {locale_path.name}:{section}.{key}")
                    self.assertEqual(
                        _extract_placeholders(val),
                        _extract_placeholders(en_val),
                        f"Placeholder mismatch in {locale_path.name}:{section}.{key}",
                    )

    def test_language_detection_heuristics(self) -> None:
        self.assertEqual(i18n.detect_text_language("Refactor the payment gateway"), "en")
        self.assertEqual(i18n.detect_text_language("重构支付网关并补充单测"), "zh")
        self.assertEqual(i18n.detect_text_language("Fix README.md 中的错别字"), "zh")
        self.assertEqual(i18n.detect_text_language("認証モジュールをリファクタリング"), "ja")
        self.assertEqual(i18n.detect_text_language("テストを実行して"), "ja")
        self.assertEqual(i18n.detect_text_language("인증 모듈을 수정해 주세요"), "ko")
        self.assertIsNone(i18n.detect_text_language(""))
        self.assertIsNone(i18n.detect_text_language("   12345 !@#  "))

    def test_locale_resolution_precedence_and_normalization(self) -> None:
        # Environment variable beats config and user text
        self.assertEqual(
            i18n.resolve_locale(env_lang="ja_JP.UTF-8", config_lang="zh-CN", user_text="Hello"),
            "ja",
        )
        # Config beats user text
        self.assertEqual(
            i18n.resolve_locale(env_lang="auto", config_lang="zh-CN", user_text="Hello"),
            "zh",
        )
        # Auto user text beats state_lang and system locale
        with mock.patch.dict(os.environ, {"LANG": "zh_CN.UTF-8"}, clear=False):
            self.assertEqual(
                i18n.resolve_locale(config_lang="auto", user_text="Fix login bug", state_lang="zh"),
                "en",
            )
        # Empty user text falls back to persisted state_lang
        self.assertEqual(
            i18n.resolve_locale(config_lang="auto", user_text="", state_lang="ja"),
            "ja",
        )
        # Unsupported detected language (ko) gracefully falls back to en
        self.assertEqual(
            i18n.resolve_locale(config_lang="auto", user_text="안녕하세요"),
            "en",
        )
        # Empty user text and empty state falls back to system LANG
        with mock.patch.dict(os.environ, {"LC_ALL": "", "LC_MESSAGES": "", "LANG": "zh_CN.UTF-8"}, clear=False):
            self.assertEqual(i18n.resolve_locale(config_lang="auto", user_text=""), "zh")

    def test_partial_locale_and_malformed_template_fallback_safely(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_locales = Path(td)
            (tmp_locales / "en.json").write_text(
                (LOCALES_DIR / "en.json").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            # Partial locale missing most keys and containing a bad format placeholder
            (tmp_locales / "fr.json").write_text(
                json.dumps(
                    {
                        "meta": {"code": "fr", "name": "Français"},
                        "labels": {"default_session": "Session en cours"},
                        "messages": {"notify_body": "{missing_placeholder} ops"},
                    }
                ),
                encoding="utf-8",
            )
            i18n.clear_cache()

            self.assertEqual(
                i18n.get_text("fr", "labels", "default_session", locales_dir=tmp_locales),
                "Session en cours",
            )
            # Missing key falls back to English
            self.assertEqual(
                i18n.get_text("fr", "tool_labels", "edit_file", locales_dir=tmp_locales),
                "✏️ Edit",
            )
            # Broken placeholder returns raw template instead of raising KeyError
            self.assertEqual(
                i18n.get_text(
                    "fr",
                    "messages",
                    "notify_body",
                    locales_dir=tmp_locales,
                    tool_count=5,
                    elapsed="10s",
                ),
                "{missing_placeholder} ops",
            )


if __name__ == "__main__":
    unittest.main()
