#!/usr/bin/env python3
"""Antigravity lifecycle hook for silent-step progress nudges, safeguards, and notifications."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
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

TOOL_LABELS: dict[str, tuple[str, str]] = {
    "read_file": ("read", "📖 读取"),
    "view_file": ("read", "📖 查看"),
    "view_file_outline": ("read", "📖 查看结构"),
    "view_code_item": ("read", "📖 查看符号"),
    "write_file": ("write", "✏️ 写入"),
    "write_to_file": ("write", "✏️ 写入"),
    "edit_file": ("write", "✏️ 修改"),
    "replace_file_content": ("write", "✏️ 修改"),
    "multi_replace_file_content": ("write", "✏️ 批量修改"),
    "run_command": ("exec", "⚙️ 执行"),
    "command_status": ("exec", "⚙️ 检查命令"),
    "send_command_input": ("exec", "⚙️ 命令交互"),
    "grep_search": ("search", "🔍 搜索代码"),
    "find_by_name": ("search", "🔍 查找文件"),
    "list_dir": ("search", "🔍 浏览目录"),
    "codebase_search": ("search", "🔍 语义检索"),
    "search_web": ("web", "🌐 搜索网页"),
    "read_url_content": ("web", "🌐 读取网页"),
    "invoke_subagent": ("agent", "🤝 启动子代理"),
    "send_message": ("agent", "🤝 联系子代理"),
    "swarm": ("agent", "🤝 协同 Swarm"),
    "run_workflow": ("agent", "🤝 执行工作流"),
    "ask_question": ("ui", "❓ 等待用户选择"),
}

ARTIFACT_NAMES = {"task.md", "implementation_plan.md", "walkthrough.md", "PROGRESS.md"}


def _state_dir() -> Path:
    base = os.environ.get("PLUGIN_DATA")
    if base:
        path = Path(base) / "milestone-progress-state"
    else:
        path = Path(tempfile.gettempdir()) / "agy-milestone-progress"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _conversation_digest(conversation_id: str) -> str:
    return hashlib.sha256(conversation_id.encode("utf-8")).hexdigest()[:24]


def _state_path(conversation_id: str) -> Path:
    return _state_dir() / f"{_conversation_digest(conversation_id)}.json"


def _lock_path(conversation_id: str) -> Path:
    return _state_dir() / f"{_conversation_digest(conversation_id)}.lock"


@contextlib.contextmanager
def _conversation_lock(conversation_id: str) -> Iterator[None]:
    if fcntl is None:
        yield
        return
    lock_file = _lock_path(conversation_id)
    fh = None
    locked = False
    try:
        fh = lock_file.open("a+", encoding="utf-8")
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        locked = True
    except OSError:
        if fh is not None:
            try:
                fh.close()
            except OSError:
                pass
            fh = None
    try:
        yield
    finally:
        if fh is not None:
            try:
                if locked:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                fh.close()
            except OSError:
                pass


def _cleanup_stale_state_files(current_conv_id: str, now: float) -> None:
    keep_prefix = _conversation_digest(current_conv_id)
    cutoff = now - STATE_RETENTION_SEC
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
        tmp_path.replace(path)
    except OSError:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


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


def _describe_tool(tool_call: dict[str, Any], artifact_dir: str, error: str) -> tuple[str, str]:
    name = str(tool_call.get("name") or "").strip()
    args = tool_call.get("args")
    if not isinstance(args, dict):
        args = {}

    if name.startswith("browser_"):
        category, prefix = "browser", "🖥️ 浏览器操作"
    else:
        category, prefix = TOOL_LABELS.get(name, ("other", f"🔧 {name or '工具调用'}"))

    detail = ""
    if category in ("read", "write"):
        raw_path = _extract_file_path(args)
        fname = os.path.basename(raw_path) if raw_path else ""
        if category == "write" and (
            (artifact_dir and raw_path.startswith(artifact_dir)) or fname in ARTIFACT_NAMES
        ):
            category = "artifact"
            prefix = "📋 更新进度清单"
        if fname:
            detail = f" `{fname}`"
    elif name == "run_command":
        summary = args.get("toolSummary") or args.get("CommandLine") or ""
        if isinstance(summary, str) and summary.strip():
            detail = f" `{_short_text(summary, 32)}`"
    elif category == "search":
        query = args.get("Query") or args.get("Pattern") or args.get("query") or ""
        if isinstance(query, str) and query.strip():
            detail = f" `{_short_text(query, 24)}`"
    elif name == "invoke_subagent":
        role = args.get("Role") or ""
        if isinstance(role, str) and role.strip():
            detail = f" `{_short_text(role, 24)}`"

    label = f"{prefix}{detail}"
    if error:
        category = "error"
        label = f"⚠️ {prefix}{detail}（出错）"
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


def _dedupe_recent_labels(actions: list[dict[str, str]]) -> str:
    labels: list[str] = []
    for item in actions:
        label = item.get("label", "")
        if label and (not labels or labels[-1] != label):
            labels.append(label)
    if len(labels) > MAX_PENDING_DISPLAY:
        extra = len(labels) - MAX_PENDING_DISPLAY
        labels = labels[-MAX_PENDING_DISPLAY:]
        return f"等前 {extra} 步后 → " + " → ".join(labels)
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


def _handle_session_start(payload: dict[str, Any], now: float) -> dict[str, Any]:
    conv_id = str(payload.get("conversationId") or "default")
    with _conversation_lock(conv_id):
        _save_state(conv_id, _default_state())
    _cleanup_stale_state_files(conv_id, now)
    return {}


def _handle_post_tool_use(payload: dict[str, Any], now: float) -> dict[str, Any]:
    conv_id = str(payload.get("conversationId") or "default")
    tool_call = payload.get("toolCall")
    if not isinstance(tool_call, dict):
        tool_call = {}
    artifact_dir = str(payload.get("artifactDirectoryPath") or "")
    error = str(payload.get("error") or "")
    category, label = _describe_tool(tool_call, artifact_dir, error)

    with _conversation_lock(conv_id):
        state = _load_state(conv_id)
        if not state.get("turn_active"):
            state["turn_active"] = True
            state["input_hash"] = _input_hash(payload)
        if not state["turn_start_ts"]:
            state["turn_start_ts"] = now

        state["total_tools"] = int(state.get("total_tools", 0)) + 1
        pending = state.get("pending_actions")
        if not isinstance(pending, list):
            pending = []
        pending.append({"category": category, "label": label})
        state["pending_actions"] = pending[-20:]
        _save_state(conv_id, state)
    return {}


def _should_safeguard(state: dict[str, Any]) -> bool:
    inv = int(state.get("turn_invocations", 0))
    if inv < SAFEGUARD_FIRST_INVOCATION:
        return False
    last_warned = int(state.get("last_warned_inv", 0))
    if last_warned == 0:
        return True
    return (inv - last_warned) >= SAFEGUARD_REPEAT_INTERVAL


def _handle_pre_invocation(payload: dict[str, Any], now: float) -> dict[str, Any]:
    conv_id = str(payload.get("conversationId") or "default")
    in_hash = _input_hash(payload)
    host_inv = _parse_optional_int(payload.get("invocationNum"))
    transcript_path = str(payload.get("transcriptPath") or "")

    with _conversation_lock(conv_id):
        state = _load_state(conv_id)
        if _is_new_turn(state, in_hash, host_inv):
            state = _default_state()
            state["turn_active"] = True
            state["input_hash"] = in_hash
            state["turn_start_ts"] = now

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

        # Note: Do NOT include `metadata` inside `systemMessage` due to an upstream Antigravity
        # Go scrubber bug (`type mismatch: cannot convert string to message`) that drops the payload.
        if _should_safeguard(state):
            state["last_warned_inv"] = inv_count
            state["silent_invocations"] = 0
            state["pending_actions"] = []
            model_instruction = (
                f"[Progress Guardian] 本回合已连续执行 {inv_count} 轮模型调用。"
                "请不要继续无休止链式调用工具。请立即在当前安全边界收尾本子模块，"
                "更新 task.md（如有）进度清单，并用通俗易懂的中文向用户输出阶段进度汇报卡片"
                "（总进度、本阶段已完成、验证情况、下一步计划），然后暂停等待用户确认。"
            )
            inject_steps.append({"systemMessage": {"systemMessage": model_instruction}})
        elif int(state.get("silent_invocations", 0)) >= SILENT_NUDGE_INTERVAL and state.get("pending_actions"):
            summary = _dedupe_recent_labels(state["pending_actions"])
            elapsed = _format_duration(now - float(state["turn_start_ts"] or now))
            state["silent_invocations"] = 0
            state["pending_actions"] = []
            nudge = (
                f"[Progress Reminder] 你已连续 {SILENT_NUDGE_INTERVAL} 轮静默调用工具（已耗时 {elapsed}，"
                f"近期操作：{summary}）。如果接下来仍需调用工具，请务必在本次调用工具之前，"
                "先在正文（非 thinking）中输出简短的一句话中文进度（如 `🧭 正在…`），让用户在聊天界面实时看清进展。"
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


def _handle_stop(payload: dict[str, Any], now: float) -> dict[str, Any]:
    conv_id = str(payload.get("conversationId") or "default")
    with _conversation_lock(conv_id):
        state = _load_state(conv_id)
        elapsed = (now - float(state.get("turn_start_ts") or now)) if state.get("turn_start_ts") else 0.0
        inv_count = int(state.get("turn_invocations", 0))
        tool_count = int(state.get("total_tools", 0))
        _save_state(conv_id, _default_state())

    reason = str(payload.get("terminationReason") or "")

    is_error = reason in {
        "ERROR",
        "MAX_INVOCATIONS",
        "MAX_FORCED_INVOCATIONS",
        "MAX_TOKEN_BUDGET_EXCEEDED",
    }
    is_nontrivial = (
        inv_count >= NOTIFY_MIN_INVOCATIONS
        or tool_count >= NOTIFY_MIN_TOOLS
        or elapsed >= NOTIFY_MIN_ELAPSED_SEC
        or is_error
    )

    if is_nontrivial and reason != "USER_CANCELED":
        cwd = str(payload.get("cwd") or "")
        project_name = os.path.basename(cwd.rstrip("/")) if cwd else "当前会话"
        title = f"Antigravity · {project_name}"
        subtitle = "⚠️ 任务异常或达到上限已暂停" if is_error else "⏸️ 阶段完成 · 请查看汇报或确认"
        message = f"累计 {tool_count} 次操作，耗时 {_format_duration(elapsed)}。"
        _send_macos_notification(title, subtitle, message)

    return {"decision": "allow"}


def process_event(payload: dict[str, Any], now: float | None = None) -> dict[str, Any]:
    """Dispatch an Antigravity lifecycle hook payload and return its JSON response."""
    current_time = time.time() if now is None else now
    event = str(payload.get("hookEventName") or "")

    if event == "SessionStart":
        return _handle_session_start(payload, current_time)
    if event == "PostToolUse":
        return _handle_post_tool_use(payload, current_time)
    if event == "PreInvocation":
        return _handle_pre_invocation(payload, current_time)
    if event == "Stop":
        return _handle_stop(payload, current_time)
    return {}


def main() -> int:
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
