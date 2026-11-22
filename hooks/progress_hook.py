#!/usr/bin/env python3
"""Antigravity lifecycle hook for multilingual progress nudges, safeguards, and notifications."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX fallback
    fcntl = None  # type: ignore[assignment]

try:
    import msvcrt
except ImportError:  # pragma: no cover - POSIX fallback
    msvcrt = None  # type: ignore[assignment]

try:
    from . import i18n  # type: ignore[import-not-found]
except ImportError:
    _HOOK_DIR = str(Path(__file__).resolve().parent)
    if _HOOK_DIR not in sys.path:
        sys.path.insert(0, _HOOK_DIR)
    import i18n  # type: ignore[no-redef]

SILENT_NUDGE_INTERVAL = 3
SAFEGUARD_FIRST_INVOCATION = 12
SAFEGUARD_REPEAT_INTERVAL = 4
NOTIFY_MIN_INVOCATIONS = 3
NOTIFY_MIN_TOOLS = 3
NOTIFY_MIN_ELAPSED_SEC = 15.0
MAX_PENDING_DISPLAY = 4
TRANSCRIPT_CHUNK_BYTES = 32768
TRANSCRIPT_MAX_SCAN_BYTES = 524288
STATE_RETENTION_SEC = 14 * 24 * 3600

ERROR_TERMINATION_REASONS = frozenset(
    {
        "ERROR",
        "MAX_INVOCATIONS",
        "MAX_FORCED_INVOCATIONS",
        "MAX_TOKEN_BUDGET_EXCEEDED",
    }
)

TOOL_CATEGORIES: dict[str, str] = {
    "read_file": "read",
    "view_file": "read",
    "view_file_outline": "read",
    "view_code_item": "read",
    "write_file": "write",
    "write_to_file": "write",
    "edit_file": "write",
    "replace_file_content": "write",
    "multi_replace_file_content": "write",
    "run_command": "exec",
    "command_status": "exec",
    "send_command_input": "exec",
    "manage_task": "exec",
    "grep_search": "search",
    "find_by_name": "search",
    "list_dir": "search",
    "codebase_search": "search",
    "search_web": "web",
    "read_url_content": "web",
    "invoke_subagent": "agent",
    "send_message": "agent",
    "manage_subagents": "agent",
    "define_subagent": "agent",
    "swarm": "agent",
    "run_workflow": "agent",
    "schedule": "schedule",
    "call_mcp_tool": "mcp",
    "list_resources": "mcp",
    "read_resource": "mcp",
    "search_marketplace": "plugin",
    "list_plugin_accounts": "plugin",
    "ask_question": "ui",
}

ARTIFACT_NAMES = frozenset({"task.md", "implementation_plan.md", "walkthrough.md", "PROGRESS.md"})


def _plugin_data_dir() -> Path:
    base = os.environ.get("PLUGIN_DATA")
    if base:
        return Path(base)
    return Path(tempfile.gettempdir()) / "agy-milestone-progress"


def _state_dir() -> Path:
    base = os.environ.get("PLUGIN_DATA")
    if base:
        path = Path(base) / "milestone-progress-state"
    else:
        path = Path(tempfile.gettempdir()) / "agy-milestone-progress"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _config_path() -> Path:
    return _plugin_data_dir() / "config.json"


def _parse_int_in_range(value: Any, default: int, minimum: int = 1) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int) and value >= minimum:
        return value
    return default


def _parse_float_in_range(value: Any, default: float, minimum: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)) and float(value) >= minimum:
        return float(value)
    return default


def _load_user_config() -> dict[str, Any]:
    """Load optional persistent user overrides from $PLUGIN_DATA/config.json."""
    cfg: dict[str, Any] = {
        "language": "auto",
        "silent_nudge_interval": SILENT_NUDGE_INTERVAL,
        "safeguard_first_invocation": SAFEGUARD_FIRST_INVOCATION,
        "safeguard_repeat_interval": SAFEGUARD_REPEAT_INTERVAL,
        "notify_enabled": True,
        "notify_min_invocations": NOTIFY_MIN_INVOCATIONS,
        "notify_min_tools": NOTIFY_MIN_TOOLS,
        "notify_min_elapsed_sec": NOTIFY_MIN_ELAPSED_SEC,
        "state_retention_sec": STATE_RETENTION_SEC,
    }
    path = _config_path()
    if not path.is_file():
        return cfg
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return cfg
    if not isinstance(raw, dict):
        return cfg

    lang_val = raw.get("language")
    if isinstance(lang_val, str) and lang_val.strip():
        cfg["language"] = lang_val.strip()

    cfg["silent_nudge_interval"] = _parse_int_in_range(
        raw.get("silent_nudge_interval"), SILENT_NUDGE_INTERVAL, 1
    )
    cfg["safeguard_first_invocation"] = _parse_int_in_range(
        raw.get("safeguard_first_invocation"), SAFEGUARD_FIRST_INVOCATION, 1
    )
    cfg["safeguard_repeat_interval"] = _parse_int_in_range(
        raw.get("safeguard_repeat_interval"), SAFEGUARD_REPEAT_INTERVAL, 1
    )
    if isinstance(raw.get("notify_enabled"), bool):
        cfg["notify_enabled"] = raw["notify_enabled"]
    cfg["notify_min_invocations"] = _parse_int_in_range(
        raw.get("notify_min_invocations"), NOTIFY_MIN_INVOCATIONS, 1
    )
    cfg["notify_min_tools"] = _parse_int_in_range(
        raw.get("notify_min_tools"), NOTIFY_MIN_TOOLS, 1
    )
    cfg["notify_min_elapsed_sec"] = _parse_float_in_range(
        raw.get("notify_min_elapsed_sec"), NOTIFY_MIN_ELAPSED_SEC, 0.0
    )
    retention_days = raw.get("state_retention_days")
    if not isinstance(retention_days, bool) and isinstance(retention_days, int) and retention_days >= 1:
        cfg["state_retention_sec"] = retention_days * 24 * 3600

    return cfg


def _conversation_digest(conversation_id: str) -> str:
    return hashlib.sha256(conversation_id.encode("utf-8")).hexdigest()[:24]


def _state_path(conversation_id: str) -> Path:
    return _state_dir() / f"{_conversation_digest(conversation_id)}.json"


def _lock_path(conversation_id: str) -> Path:
    return _state_dir() / f"{_conversation_digest(conversation_id)}.lock"


@contextlib.contextmanager
def _conversation_lock(conversation_id: str) -> Iterator[None]:
    if fcntl is None and msvcrt is None:
        yield
        return
    lock_file = _lock_path(conversation_id)
    fh = None
    win_fd: int | None = None
    locked = False
    try:
        if fcntl is not None:
            fh = lock_file.open("a+", encoding="utf-8")
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            locked = True
        elif msvcrt is not None:
            win_fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR)
            deadline = time.monotonic() + 4.0
            delay = 0.005
            while True:
                try:
                    os.lseek(win_fd, 0, os.SEEK_SET)
                    msvcrt.locking(win_fd, msvcrt.LK_NBLCK, 1)
                    locked = True
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        break
                    time.sleep(delay)
                    delay = min(delay * 1.5, 0.03)
    except OSError:
        if fh is not None:
            try:
                fh.close()
            except OSError:
                pass
            fh = None
        if win_fd is not None:
            try:
                os.close(win_fd)
            except OSError:
                pass
            win_fd = None
    try:
        yield
    finally:
        if fh is not None:
            try:
                if locked and fcntl is not None:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                fh.close()
            except OSError:
                pass
        if win_fd is not None:
            try:
                if locked and msvcrt is not None:
                    os.lseek(win_fd, 0, os.SEEK_SET)
                    msvcrt.locking(win_fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            try:
                os.close(win_fd)
            except OSError:
                pass


def _cleanup_stale_state_files(current_conv_id: str, now: float, retention_sec: int) -> None:
    keep_prefix = _conversation_digest(current_conv_id)
    cutoff = now - retention_sec
    try:
        for entry in _state_dir().iterdir():
            if not entry.is_file():
                continue
            if entry.suffix not in {".json", ".lock", ".tmp"}:
                continue
            if entry.name.startswith(keep_prefix):
                continue
            try:
                if entry.stat().st_mtime < cutoff:
                    entry.unlink(missing_ok=True)
            except OSError:
                continue
    except OSError:
        pass


def _default_state() -> dict[str, Any]:
    return {
        "turn_active": False,
        "input_hash": "",
        "lang": "",
        "last_host_inv": None,
        "turn_start_ts": 0.0,
        "turn_invocations": 0,
        "silent_invocations": 0,
        "total_tools": 0,
        "pending_actions": [],
        "last_warned_inv": 0,
    }


def _load_state(conversation_id: str) -> dict[str, Any]:
    path = _state_path(conversation_id)
    if not path.exists():
        return _default_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            merged = _default_state()
            merged.update(data)
            return merged
    except (OSError, ValueError):
        pass
    return _default_state()


def _save_state(conversation_id: str, state: dict[str, Any]) -> None:
    path = _state_path(conversation_id)
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        tmp_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        for attempt in range(5):
            try:
                tmp_path.replace(path)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.01)
    except OSError:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


def _resolve_turn_lang(
    payload: dict[str, Any], state: dict[str, Any], cfg: dict[str, Any]
) -> str:
    return i18n.resolve_locale(
        env_lang=os.environ.get("MILESTONE_PROGRESS_LANG"),
        config_lang=str(cfg.get("language") or "auto"),
        user_text=str(payload.get("lastUserInput") or ""),
        state_lang=str(state.get("lang") or ""),
    )


def _short_text(value: str, max_len: int = 36) -> str:
    compact = " ".join(value.split())
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 1] + "…"


def _extract_file_path(args: dict[str, Any]) -> str:
    for key in ("Path", "AbsolutePath", "TargetFile", "path", "file_path"):
        val = args.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _describe_tool(
    tool_call: dict[str, Any], artifact_dir: str, error: str, lang: str
) -> tuple[str, str]:
    name = str(tool_call.get("name") or "").strip()
    args = tool_call.get("args")
    if not isinstance(args, dict):
        args = {}

    if name.startswith("browser_"):
        category = "browser"
        prefix = i18n.get_text(lang, "labels", "browser_action", default="🖥️ Browser action")
    else:
        category = TOOL_CATEGORIES.get(name, "other")
        prefix = i18n.get_text(lang, "tool_labels", name, default="")
        if not prefix:
            fallback_name = name or i18n.get_text(
                lang, "labels", "fallback_tool_name", default="tool call"
            )
            prefix = i18n.get_text(
                lang,
                "labels",
                "generic_tool",
                default="🔧 {name}",
                name=fallback_name,
            )

    detail = ""
    if category in ("read", "write"):
        raw_path = _extract_file_path(args)
        fname = os.path.basename(raw_path) if raw_path else ""
        if category == "write" and (
            (artifact_dir and raw_path.startswith(artifact_dir)) or fname in ARTIFACT_NAMES
        ):
            category = "artifact"
            prefix = i18n.get_text(
                lang, "labels", "artifact_update", default="📋 Update progress checklist"
            )
        if fname:
            detail = f" `{fname}`"
    elif name == "run_command":
        summary = args.get("toolSummary") or args.get("CommandLine") or ""
        if isinstance(summary, str) and summary.strip():
            detail = f" `{_short_text(summary, 32)}`"
    elif name == "manage_task":
        action = args.get("Action") or ""
        if isinstance(action, str) and action.strip():
            detail = f" `{_short_text(action, 20)}`"
    elif category == "search":
        query = args.get("Query") or args.get("Pattern") or args.get("query") or ""
        if isinstance(query, str) and query.strip():
            detail = f" `{_short_text(query, 24)}`"
    elif name == "search_web":
        query = args.get("query") or args.get("Query") or ""
        if isinstance(query, str) and query.strip():
            detail = f" `{_short_text(query, 24)}`"
    elif name == "invoke_subagent":
        role = args.get("Role") or ""
        if isinstance(role, str) and role.strip():
            detail = f" `{_short_text(role, 24)}`"
    elif name == "call_mcp_tool":
        mcp_target = args.get("ToolName") or args.get("ServerName") or ""
        if isinstance(mcp_target, str) and mcp_target.strip():
            detail = f" `{_short_text(mcp_target, 24)}`"
    elif name == "schedule":
        sched = args.get("CronExpression")
        if isinstance(sched, str) and sched.strip():
            detail = f" `{_short_text(sched, 24)}`"
        elif isinstance(args.get("DurationSeconds"), int):
            detail = f" `{args['DurationSeconds']}s`"
    elif name == "search_marketplace":
        queries = args.get("queries")
        if isinstance(queries, list) and queries and isinstance(queries[0], str) and queries[0].strip():
            detail = f" `{_short_text(queries[0], 24)}`"

    label = f"{prefix}{detail}"
    if error:
        category = "error"
        suffix = i18n.get_text(lang, "labels", "error_suffix", default=" (failed)")
        label = f"⚠️ {prefix}{detail}{suffix}"
    return category, label


def _format_duration(seconds: float) -> str:
    secs = max(0, int(round(seconds)))
    if secs < 60:
        return f"{secs}s"
    mins, rem = divmod(secs, 60)
    if mins < 60:
        return f"{mins}m{rem:02d}s"
    hours, mins = divmod(mins, 60)
    return f"{hours}h{mins:02d}m"


def _dedupe_recent_labels(actions: list[dict[str, str]], lang: str) -> str:
    labels: list[str] = []
    for item in actions:
        label = item.get("label", "")
        if label and (not labels or labels[-1] != label):
            labels.append(label)
    if len(labels) > MAX_PENDING_DISPLAY:
        extra = len(labels) - MAX_PENDING_DISPLAY
        labels = labels[-MAX_PENDING_DISPLAY:]
        prefix = i18n.get_text(
            lang,
            "labels",
            "more_steps_prefix",
            default="after {extra} earlier steps → ",
            extra=extra,
        )
        return prefix + " → ".join(labels)
    return " → ".join(labels)


def _parse_optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _input_hash(payload: dict[str, Any]) -> str:
    last_input = str(payload.get("lastUserInput") or "")
    return hashlib.sha256(last_input.encode("utf-8")).hexdigest()[:12]


def _is_new_turn(state: dict[str, Any], input_hash: str, host_inv: int | None) -> bool:
    if not state.get("turn_active"):
        return True
    if state.get("input_hash") != input_hash:
        return True
    last_inv = state.get("last_host_inv")
    if isinstance(last_inv, int) and last_inv >= 1:
        effective_inv = 0 if host_inv is None else host_inv
        if effective_inv < last_inv:
            return True
        if effective_inv == last_inv and not state.get("pending_actions"):
            return True
    return False


def _last_planner_had_visible_text(transcript_path: str) -> bool:
    if not transcript_path:
        return False
    path = Path(transcript_path)
    if not path.exists():
        return False
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            pos = fh.tell()
            scanned = 0
            carry = b""
            while pos > 0 and scanned < TRANSCRIPT_MAX_SCAN_BYTES:
                read_size = min(
                    TRANSCRIPT_CHUNK_BYTES,
                    pos,
                    TRANSCRIPT_MAX_SCAN_BYTES - scanned,
                )
                pos -= read_size
                fh.seek(pos, os.SEEK_SET)
                data = fh.read(read_size) + carry
                scanned += read_size

                parts = data.split(b"\n")
                if pos > 0:
                    carry = parts[0]
                    complete_lines = parts[1:]
                else:
                    carry = b""
                    complete_lines = parts

                for raw_line in reversed(complete_lines):
                    if b"PLANNER_RESPONSE" not in raw_line:
                        continue
                    try:
                        entry = json.loads(raw_line.decode("utf-8", errors="ignore"))
                    except ValueError:
                        continue
                    if entry.get("type") == "PLANNER_RESPONSE":
                        return bool(str(entry.get("content") or "").strip())
    except OSError:
        pass
    return False


def _handle_session_start(payload: dict[str, Any], now: float, cfg: dict[str, Any]) -> dict[str, Any]:
    conv_id = str(payload.get("conversationId") or "default")
    with _conversation_lock(conv_id):
        _save_state(conv_id, _default_state())
    _cleanup_stale_state_files(conv_id, now, int(cfg["state_retention_sec"]))
    return {}


def _handle_post_tool_use(payload: dict[str, Any], now: float, cfg: dict[str, Any]) -> dict[str, Any]:
    conv_id = str(payload.get("conversationId") or "default")
    tool_call = payload.get("toolCall")
    if not isinstance(tool_call, dict):
        tool_call = {}
    artifact_dir = str(payload.get("artifactDirectoryPath") or "")
    error = str(payload.get("error") or "")

    with _conversation_lock(conv_id):
        state = _load_state(conv_id)
        if not state.get("turn_active"):
            state["turn_active"] = True
            state["input_hash"] = _input_hash(payload)
        if not state["turn_start_ts"]:
            state["turn_start_ts"] = now

        lang = _resolve_turn_lang(payload, state, cfg)
        state["lang"] = lang
        category, label = _describe_tool(tool_call, artifact_dir, error, lang)

        state["total_tools"] = int(state.get("total_tools", 0)) + 1
        pending = state.get("pending_actions")
        if not isinstance(pending, list):
            pending = []
        pending.append({"category": category, "label": label})
        state["pending_actions"] = pending[-20:]
        _save_state(conv_id, state)
    return {}


def _should_safeguard(state: dict[str, Any], cfg: dict[str, Any]) -> bool:
    inv = int(state.get("turn_invocations", 0))
    if inv < int(cfg["safeguard_first_invocation"]):
        return False
    last_warned = int(state.get("last_warned_inv", 0))
    if last_warned == 0:
        return True
    return (inv - last_warned) >= int(cfg["safeguard_repeat_interval"])


def _handle_pre_invocation(payload: dict[str, Any], now: float, cfg: dict[str, Any]) -> dict[str, Any]:
    conv_id = str(payload.get("conversationId") or "default")
    in_hash = _input_hash(payload)
    host_inv = _parse_optional_int(payload.get("invocationNum"))
    transcript_path = str(payload.get("transcriptPath") or "")

    with _conversation_lock(conv_id):
        state = _load_state(conv_id)
        if _is_new_turn(state, in_hash, host_inv):
            prev_lang = str(state.get("lang") or "")
            state = _default_state()
            state["turn_active"] = True
            state["input_hash"] = in_hash
            state["turn_start_ts"] = now
            state["lang"] = prev_lang

        lang = _resolve_turn_lang(payload, state, cfg)
        state["lang"] = lang

        if host_inv is not None:
            state["last_host_inv"] = host_inv
        state["turn_invocations"] = int(state.get("turn_invocations", 0)) + 1

        inv_count = state["turn_invocations"]
        if inv_count > 1:
            if _last_planner_had_visible_text(transcript_path):
                state["silent_invocations"] = 0
                state["pending_actions"] = []
            else:
                state["silent_invocations"] = int(state.get("silent_invocations", 0)) + 1

        inject_steps: list[dict[str, Any]] = []
        nudge_interval = int(cfg["silent_nudge_interval"])

        # Note: Do NOT include `metadata` inside `systemMessage` due to an upstream Antigravity
        # Go scrubber bug (`type mismatch: cannot convert string to message`) that drops the payload.
        if _should_safeguard(state, cfg):
            state["last_warned_inv"] = inv_count
            state["silent_invocations"] = 0
            state["pending_actions"] = []
            model_instruction = i18n.get_text(
                lang,
                "messages",
                "progress_guardian",
                inv_count=inv_count,
            )
            inject_steps.append({"systemMessage": {"systemMessage": model_instruction}})
        elif int(state.get("silent_invocations", 0)) >= nudge_interval and state.get("pending_actions"):
            summary = _dedupe_recent_labels(state["pending_actions"], lang)
            elapsed = _format_duration(now - float(state["turn_start_ts"] or now))
            state["silent_invocations"] = 0
            state["pending_actions"] = []
            nudge = i18n.get_text(
                lang,
                "messages",
                "progress_reminder",
                interval=nudge_interval,
                elapsed=elapsed,
                summary=summary,
            )
            inject_steps.append({"systemMessage": {"systemMessage": nudge}})

        _save_state(conv_id, state)
    return {"injectSteps": inject_steps}


def _send_macos_notification(title: str, subtitle: str, message: str) -> None:
    if sys.platform != "darwin":
        return
    script = (
        "on run argv\n"
        "set msg to item 1 of argv\n"
        "set ttl to item 2 of argv\n"
        "set sub to item 3 of argv\n"
        "display notification msg with title ttl subtitle sub\n"
        "end run"
    )
    try:
        subprocess.run(
            ["osascript", "-e", script, message, title, subtitle],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _send_linux_notification(title: str, subtitle: str, message: str) -> None:
    if not sys.platform.startswith("linux"):
        return
    notify_bin = shutil.which("notify-send")
    if not notify_bin:
        return
    try:
        subprocess.run(
            [notify_bin, title, f"{subtitle}\n{message}"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def _send_desktop_notification(title: str, subtitle: str, message: str) -> None:
    if sys.platform == "darwin":
        _send_macos_notification(title, subtitle, message)
    elif sys.platform.startswith("linux"):
        _send_linux_notification(title, subtitle, message)


def _handle_stop(payload: dict[str, Any], now: float, cfg: dict[str, Any]) -> dict[str, Any]:
    conv_id = str(payload.get("conversationId") or "default")
    with _conversation_lock(conv_id):
        state = _load_state(conv_id)
        elapsed = (now - float(state.get("turn_start_ts") or now)) if state.get("turn_start_ts") else 0.0
        inv_count = int(state.get("turn_invocations", 0))
        tool_count = int(state.get("total_tools", 0))
        lang = _resolve_turn_lang(payload, state, cfg)
        reset_state = _default_state()
        reset_state["lang"] = lang
        _save_state(conv_id, reset_state)

    reason = str(payload.get("terminationReason") or "")
    error_text = str(payload.get("error") or "").strip()

    is_error = bool(error_text) or reason in ERROR_TERMINATION_REASONS
    is_nontrivial = (
        inv_count >= int(cfg["notify_min_invocations"])
        or tool_count >= int(cfg["notify_min_tools"])
        or elapsed >= float(cfg["notify_min_elapsed_sec"])
        or is_error
    )

    if cfg.get("notify_enabled", True) and is_nontrivial and reason != "USER_CANCELED":
        cwd = str(payload.get("cwd") or "")
        default_session = i18n.get_text(lang, "labels", "default_session", default="Current session")
        project_name = os.path.basename(cwd.rstrip("/\\")) if cwd else default_session
        title = i18n.get_text(lang, "messages", "notify_title", project=project_name)
        subtitle_key = "notify_subtitle_error" if is_error else "notify_subtitle_done"
        subtitle = i18n.get_text(lang, "messages", subtitle_key)
        message = i18n.get_text(
            lang,
            "messages",
            "notify_body",
            tool_count=tool_count,
            elapsed=_format_duration(elapsed),
        )
        _send_desktop_notification(title, subtitle, message)

    return {"decision": "allow"}


def process_event(payload: dict[str, Any], now: float | None = None) -> dict[str, Any]:
    """Dispatch an Antigravity lifecycle hook payload and return its JSON response."""
    current_time = time.time() if now is None else now
    event = str(payload.get("hookEventName") or "")
    cfg = _load_user_config()

    if event == "SessionStart":
        return _handle_session_start(payload, current_time, cfg)
    if event == "PostToolUse":
        return _handle_post_tool_use(payload, current_time, cfg)
    if event == "PreInvocation":
        return _handle_pre_invocation(payload, current_time, cfg)
    if event == "Stop":
        return _handle_stop(payload, current_time, cfg)
    return {}


def main() -> int:
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            payload = {}
    except ValueError:
        payload = {}

    result = process_event(payload)
    sys.stdout.write(json.dumps(result, ensure_ascii=False))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
