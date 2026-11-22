#!/usr/bin/env python3
"""Zero-dependency localization loader and language detector for milestone-progress."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

LOCALES_DIR = Path(__file__).resolve().parent / "locales"
DEFAULT_LOCALE = "en"

_CACHE: dict[str, dict[str, Any]] = {}


def available_locales(locales_dir: Path | None = None) -> list[str]:
    directory = locales_dir or LOCALES_DIR
    if not directory.is_dir():
        return [DEFAULT_LOCALE]
    codes = sorted(entry.stem.lower() for entry in directory.glob("*.json") if entry.is_file())
    return codes or [DEFAULT_LOCALE]


def normalize_locale_code(raw: str | None) -> str:
    if not raw or not isinstance(raw, str):
        return ""
    cleaned = raw.strip().split(".")[0].split("@")[0].replace("_", "-").lower()
    if cleaned in ("", "auto", "c", "posix"):
        return ""
    return cleaned


def resolve_supported_locale(raw: str | None, locales_dir: Path | None = None) -> str:
    normalized = normalize_locale_code(raw)
    if not normalized:
        return DEFAULT_LOCALE
    supported = set(available_locales(locales_dir))
    if normalized in supported:
        return normalized
    primary = normalized.split("-")[0]
    if primary in supported:
        return primary
    return DEFAULT_LOCALE


def detect_text_language(text: str | None) -> str | None:
    """Heuristically detect language family from user input text."""
    if not text or not isinstance(text, str):
        return None
    stripped = text.strip()
    if not stripped:
        return None

    has_han = False
    has_hangul = False
    has_letter = False

    for ch in stripped:
        code = ord(ch)
        # Hiragana or Katakana -> Japanese (checked before Han since Japanese mixes Kanji)
        if (0x3040 <= code <= 0x309F) or (0x30A0 <= code <= 0x30FF) or (0x31F0 <= code <= 0x31FF):
            return "ja"
        # Hangul -> Korean
        if (0xAC00 <= code <= 0xD7AF) or (0x1100 <= code <= 0x11FF) or (0x3130 <= code <= 0x318F):
            has_hangul = True
        # CJK Unified Ideographs -> Chinese
        elif (0x4E00 <= code <= 0x9FFF) or (0x3400 <= code <= 0x4DBF):
            has_han = True
        elif ch.isalpha():
            has_letter = True

    if has_hangul:
        return "ko"
    if has_han:
        return "zh"
    if has_letter:
        return "en"
    return None


def detect_system_locale(locales_dir: Path | None = None) -> str:
    for env_key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(env_key)
        normalized = normalize_locale_code(val)
        if normalized:
            return resolve_supported_locale(normalized, locales_dir)
    return DEFAULT_LOCALE


def resolve_locale(
    *,
    env_lang: str | None = None,
    config_lang: str | None = None,
    user_text: str | None = None,
    state_lang: str | None = None,
    locales_dir: Path | None = None,
) -> str:
    """Resolve effective locale with precedence: env > config > auto(text) > state > system > en."""
    env_norm = normalize_locale_code(env_lang)
    if env_norm:
        return resolve_supported_locale(env_norm, locales_dir)

    cfg_norm = normalize_locale_code(config_lang)
    if cfg_norm:
        return resolve_supported_locale(cfg_norm, locales_dir)

    detected = detect_text_language(user_text)
    if detected:
        return resolve_supported_locale(detected, locales_dir)

    state_norm = normalize_locale_code(state_lang)
    if state_norm:
        return resolve_supported_locale(state_norm, locales_dir)

    return detect_system_locale(locales_dir)


def _read_locale_file(code: str, locales_dir: Path) -> dict[str, Any]:
    cache_key = f"{locales_dir}:{code}"
    if cache_key in _CACHE:
        return _CACHE[cache_key]
    path = locales_dir / f"{code}.json"
    data: dict[str, Any] = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, ValueError):
            data = {}
    _CACHE[cache_key] = data
    return data


def clear_cache() -> None:
    _CACHE.clear()


def load_catalog(lang: str, locales_dir: Path | None = None) -> dict[str, Any]:
    """Load locale catalog merged over the English fallback so no key is ever missing."""
    directory = locales_dir or LOCALES_DIR
    base = _read_locale_file(DEFAULT_LOCALE, directory)
    resolved = resolve_supported_locale(lang, directory)
    if resolved == DEFAULT_LOCALE:
        return base

    override = _read_locale_file(resolved, directory)
    merged: dict[str, Any] = {}
    for section in ("meta", "tool_labels", "labels", "messages"):
        base_sec = base.get(section)
        ov_sec = override.get(section)
        sec_dict: dict[str, Any] = {}
        if isinstance(base_sec, dict):
            sec_dict.update(base_sec)
        if isinstance(ov_sec, dict):
            sec_dict.update(ov_sec)
        merged[section] = sec_dict
    return merged


def get_text(
    lang: str,
    section: str,
    key: str,
    *,
    default: str = "",
    locales_dir: Path | None = None,
    **kwargs: Any,
) -> str:
    catalog = load_catalog(lang, locales_dir)
    sec = catalog.get(section)
    template = sec.get(key) if isinstance(sec, dict) else None
    if not isinstance(template, str):
        template = default
    if not kwargs:
        return template
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError, IndexError):
        return template
