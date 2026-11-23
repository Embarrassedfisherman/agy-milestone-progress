#!/usr/bin/env python3
"""Unit tests for the milestone-progress Antigravity lifecycle hook."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT_DIR = Path(__file__).resolve().parents[1]
HOOK_PATH = ROOT_DIR / "hooks" / "progress_hook.py"
HOOKS_JSON_PATH = ROOT_DIR / "hooks.json"
PLUGIN_JSON_PATH = ROOT_DIR / "plugin.json"

sys.path.insert(0, str(HOOK_PATH.parent))
import progress_hook  # noqa: E402


class ProgressHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        clean_env = {"PLUGIN_DATA": self.tmp_dir.name, "MILESTONE_PROGRESS_LANG": ""}
        self.env_patch = mock.patch.dict(os.environ, clean_env, clear=False)
        self.env_patch.start()
        self.conv_id = "conv-test-001"
        self.transcript_file = Path(self.tmp_dir.name) / "transcript.jsonl"
        self.base_payload = {
            "conversationId": self.conv_id,
            "workspacePaths": ["/Users/demo/my-project"],
            "artifactDirectoryPath": "/Users/demo/.gemini/antigravity/brain/conv-test-001",
            "transcriptPath": str(self.transcript_file),
            "lastUserInput": "重构认证模块",
            "cwd": "/Users/demo/my-project",
            "initialNumSteps": 10,
        }

    def tearDown(self) -> None:
        self.env_patch.stop()
        self.tmp_dir.cleanup()

    def _append_planner_step(self, content: str) -> None:
        entry = {"type": "PLANNER_RESPONSE", "content": content}
        with self.transcript_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _event(self, name: str, now: float, **extra: object) -> dict:
        payload = {**self.base_payload, "hookEventName": name, **extra}
        return progress_hook.process_event(payload, now=now)

    def test_quick_qa_produces_no_noise_or_notification(self) -> None:
        self._event("SessionStart", 100.0)
        res = self._event("PreInvocation", 101.0, invocationNum=1)
        self.assertEqual(res, {"injectSteps": []})

        with mock.patch.object(progress_hook, "_send_desktop_notification") as notify_mock:
            stop_res = self._event("Stop", 103.0, terminationReason="NO_TOOL_CALL")
        self.assertEqual(stop_res, {"decision": "allow"})
        notify_mock.assert_not_called()

    def test_silent_tool_steps_trigger_metadata_free_nudge_and_visible_text_resets_it(self) -> None:
        self._event("SessionStart", 100.0)
        self.assertEqual(self._event("PreInvocation", 100.0), {"injectSteps": []})

        self._append_planner_step("")
        self._event("PostToolUse", 101.0, toolCall={"name": "read_file", "args": {"Path": "/repo/a.py"}})
        self.assertEqual(self._event("PreInvocation", 102.0, invocationNum=1), {"injectSteps": []})

        self._append_planner_step("")
        self._event("PostToolUse", 103.0, toolCall={"name": "edit_file", "args": {"Path": "/repo/auth.py"}})
        self.assertEqual(self._event("PreInvocation", 104.0, invocationNum=2), {"injectSteps": []})

        self._append_planner_step("")
        self._event("PostToolUse", 105.0, toolCall={"name": "run_command", "args": {"CommandLine": "pytest"}})
        res4 = self._event("PreInvocation", 106.0, invocationNum=3)
        self.assertEqual(len(res4["injectSteps"]), 1)
        sys_msg = res4["injectSteps"][0]["systemMessage"]
        self.assertNotIn("metadata", sys_msg)
        self.assertIn("Progress Reminder", sys_msg["systemMessage"])
        self.assertIn("✏️ 修改 `auth.py`", sys_msg["systemMessage"])
        self.assertIn("⚙️ 执行 `pytest`", sys_msg["systemMessage"])

        self._append_planner_step("")
        self._event("PostToolUse", 107.0, toolCall={"name": "read_file", "args": {"Path": "/repo/b.py"}})
        self.assertEqual(self._event("PreInvocation", 108.0, invocationNum=4), {"injectSteps": []})

        self._append_planner_step("")
        self._event("PostToolUse", 109.0, toolCall={"name": "read_file", "args": {"Path": "/repo/c.py"}})
        self.assertEqual(self._event("PreInvocation", 110.0, invocationNum=5), {"injectSteps": []})

        self._append_planner_step("🧭 正在验证测试覆盖率…")
        self._event("PostToolUse", 111.0, toolCall={"name": "run_command", "args": {"CommandLine": "coverage"}})
        self.assertEqual(self._event("PreInvocation", 112.0, invocationNum=6), {"injectSteps": []})

    def test_safeguard_fires_without_metadata_and_repeats_at_interval(self) -> None:
        self._event("SessionStart", 200.0)
        for idx in range(1, 12):
            self._append_planner_step("🧭 正常播报")
            res = self._event("PreInvocation", 200.0 + idx, invocationNum=idx)
            self.assertEqual(res["injectSteps"], [])

        res12 = self._event("PreInvocation", 212.0, invocationNum=12)
        self.assertEqual(len(res12["injectSteps"]), 1)
        msg12 = res12["injectSteps"][0]["systemMessage"]
        self.assertNotIn("metadata", msg12)
        self.assertIn("Progress Guardian", msg12["systemMessage"])

        for idx in range(13, 16):
            res = self._event("PreInvocation", 200.0 + idx, invocationNum=idx)
            self.assertEqual(res["injectSteps"], [])

        res16 = self._event("PreInvocation", 216.0, invocationNum=16)
        self.assertEqual(len(res16["injectSteps"]), 1)
        self.assertNotIn("metadata", res16["injectSteps"][0]["systemMessage"])

    def test_stop_notifications_respect_nontrivial_and_cancel(self) -> None:
        self._event("SessionStart", 300.0)
        self._event("PreInvocation", 300.0, invocationNum=1)
        for i in range(3):
            self._event(
                "PostToolUse",
                305.0 + i,
                toolCall={"name": "read_file", "args": {"Path": f"/repo/f{i}.py"}},
            )

        with mock.patch.object(progress_hook, "_send_desktop_notification") as notify_mock:
            self._event("Stop", 320.0, terminationReason="NO_TOOL_CALL")
        notify_mock.assert_called_once()
        title, subtitle, body = notify_mock.call_args.args
        self.assertEqual(title, "Antigravity · my-project")
        self.assertIn("阶段完成", subtitle)
        self.assertIn("3 次操作", body)

        self._event("PreInvocation", 400.0, invocationNum=1, initialNumSteps=20)
        with mock.patch.object(progress_hook, "_send_desktop_notification") as notify_mock:
            self._event("Stop", 430.0, terminationReason="USER_CANCELED")
        notify_mock.assert_not_called()

    def test_changing_initial_num_steps_and_protojson_fields_keep_turn_alive(self) -> None:
        res0 = self._event("PreInvocation", 500.0, initialNumSteps=74)
        self.assertEqual(res0, {"injectSteps": []})

        for step in range(3):
            self._append_planner_step("")
            self._event(
                "PostToolUse",
                501.0 + step,
                initialNumSteps=75 + step * 2,
                toolCall={"name": "run_command", "args": {"toolSummary": f"Step {step}"}},
            )
            res = self._event(
                "PreInvocation",
                502.0 + step,
                initialNumSteps=76 + step * 2,
                invocationNum=str(step + 1),
            )
            if step < 2:
                self.assertEqual(res, {"injectSteps": []})
            else:
                self.assertEqual(len(res["injectSteps"]), 1)
                self.assertNotIn("metadata", res["injectSteps"][0]["systemMessage"])

        res_restart = self._event("PreInvocation", 600.0, initialNumSteps=90)
        self.assertEqual(res_restart, {"injectSteps": []})
        state = progress_hook._load_state(self.conv_id)
        self.assertEqual(state["turn_invocations"], 1)
        self.assertEqual(state["total_tools"], 0)

    def test_cli_entrypoint_and_json_configs(self) -> None:
        plugin_data = json.loads(PLUGIN_JSON_PATH.read_text(encoding="utf-8"))
        self.assertRegex(plugin_data["version"], r"^\d+\.\d+\.\d+$")

        hooks_data = json.loads(HOOKS_JSON_PATH.read_text(encoding="utf-8"))
        spec = hooks_data["milestone-progress"]
        for key in ("SessionStart", "PostToolUse", "PreInvocation", "Stop"):
            self.assertIn(key, spec)

        proc = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=json.dumps({**self.base_payload, "hookEventName": "PreInvocation", "invocationNum": 1}),
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=True,
        )
        self.assertEqual(json.loads(proc.stdout), {"injectSteps": []})

    def test_concurrent_post_tool_use_preserves_all_updates(self) -> None:
        self._event("SessionStart", 700.0)
        self._event("PreInvocation", 700.0, invocationNum=0)

        worker_count = 12
        env = {**os.environ, "PLUGIN_DATA": self.tmp_dir.name}

        def invoke_post_tool(idx: int) -> None:
            payload = {
                **self.base_payload,
                "hookEventName": "PostToolUse",
                "toolCall": {"name": "read_file", "args": {"Path": f"/repo/file_{idx}.py"}},
            }
            subprocess.run(
                [sys.executable, str(HOOK_PATH)],
                input=json.dumps(payload),
                text=True,
                encoding="utf-8",
                capture_output=True,
                env=env,
                check=True,
            )

        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            list(pool.map(invoke_post_tool, range(worker_count)))

        state = progress_hook._load_state(self.conv_id)
        self.assertEqual(state["total_tools"], worker_count)
        self.assertEqual(len(state["pending_actions"]), worker_count)

        state_dir = progress_hook._state_dir()
        leftover_tmps = list(state_dir.glob("*.tmp"))
        self.assertEqual(leftover_tmps, [])

    def test_large_tool_outputs_beyond_24kb_still_detect_visible_planner_text(self) -> None:
        self._event("SessionStart", 800.0)
        self.assertEqual(self._event("PreInvocation", 800.0), {"injectSteps": []})

        for idx in range(1, 3):
            self._append_planner_step("")
            self._event("PostToolUse", 800.0 + idx, toolCall={"name": "read_file", "args": {"Path": f"/repo/s{idx}.py"}})
            self.assertEqual(self._event("PreInvocation", 800.5 + idx, invocationNum=idx), {"injectSteps": []})

        self._append_planner_step("📖 正在读取大日志文件并校验结果…")
        with self.transcript_file.open("a", encoding="utf-8") as fh:
            for idx in range(8):
                tool_entry = {
                    "type": "TOOL_RESULT",
                    "content": f"chunk-{idx}-" + ("x" * 9000),
                }
                fh.write(json.dumps(tool_entry, ensure_ascii=False) + "\n")

        self._event("PostToolUse", 804.0, toolCall={"name": "run_command", "args": {"toolSummary": "Large log dump"}})
        res = self._event("PreInvocation", 805.0, invocationNum=3)
        self.assertEqual(res, {"injectSteps": []})
        state = progress_hook._load_state(self.conv_id)
        self.assertEqual(state["silent_invocations"], 0)

        big_planner = {
            "type": "PLANNER_RESPONSE",
            "thinking": "t" * 45000,
            "content": "🧪 正在执行最终回归测试…",
        }
        with self.transcript_file.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(big_planner, ensure_ascii=False) + "\n")
        self.assertTrue(progress_hook._last_planner_had_visible_text(str(self.transcript_file)))

    def test_session_start_cleans_stale_state_files_only(self) -> None:
        state_dir = progress_hook._state_dir()
        now = 1_700_000_000.0
        stale_ts = now - progress_hook.STATE_RETENTION_SEC - 3600
        fresh_ts = now - 3600

        stale_json = state_dir / "aaaaaaaaaaaaaaaaaaaaaaaa.json"
        stale_lock = state_dir / "aaaaaaaaaaaaaaaaaaaaaaaa.lock"
        fresh_json = state_dir / "bbbbbbbbbbbbbbbbbbbbbbbb.json"
        for p, ts in ((stale_json, stale_ts), (stale_lock, stale_ts), (fresh_json, fresh_ts)):
            p.write_text("{}", encoding="utf-8")
            os.utime(p, (ts, ts))

        self._event("SessionStart", now)

        self.assertFalse(stale_json.exists())
        self.assertFalse(stale_lock.exists())
        self.assertTrue(fresh_json.exists())
        self.assertTrue(progress_hook._state_path(self.conv_id).exists())

    def test_english_and_japanese_auto_detection_end_to_end(self) -> None:
        # English session
        en_conv = "conv-en-001"
        self._event("SessionStart", 900.0, conversationId=en_conv, lastUserInput="Build the billing API")
        self._event("PreInvocation", 900.0, conversationId=en_conv, lastUserInput="Build the billing API")
        for idx in range(1, 4):
            self._append_planner_step("")
            self._event(
                "PostToolUse",
                900.0 + idx,
                conversationId=en_conv,
                lastUserInput="Build the billing API",
                toolCall={"name": "edit_file", "args": {"Path": f"/repo/m{idx}.py"}},
            )
            res = self._event(
                "PreInvocation",
                900.5 + idx,
                conversationId=en_conv,
                lastUserInput="Build the billing API",
                invocationNum=idx,
            )
        msg_en = res["injectSteps"][0]["systemMessage"]["systemMessage"]
        self.assertIn("✏️ Edit `m3.py`", msg_en)
        self.assertIn("in the user's language", msg_en)

        with mock.patch.object(progress_hook, "_send_desktop_notification") as notify_mock:
            self._event(
                "Stop",
                920.0,
                conversationId=en_conv,
                lastUserInput="",  # Verify language persists from session state
                terminationReason="NO_TOOL_CALL",
            )
        notify_mock.assert_called_once()
        _, subtitle_en, body_en = notify_mock.call_args.args
        self.assertIn("Milestone ready", subtitle_en)
        self.assertIn("3 tool calls", body_en)

        # Japanese session (mixed Kanji + Kana)
        ja_conv = "conv-ja-001"
        self._event("SessionStart", 950.0, conversationId=ja_conv, lastUserInput="課金モジュールをリファクタリング")
        self._event("PreInvocation", 950.0, conversationId=ja_conv, lastUserInput="課金モジュールをリファクタリング")
        with mock.patch.object(progress_hook, "_send_desktop_notification") as notify_ja:
            self._event(
                "Stop",
                970.0,
                conversationId=ja_conv,
                lastUserInput="",
                terminationReason="NO_TOOL_CALL",
            )
        notify_ja.assert_called_once()
        _, subtitle_ja, body_ja = notify_ja.call_args.args
        self.assertIn("マイルストーン完了", subtitle_ja)
        self.assertIn("回の操作", body_ja)

    def test_agy_234_native_tool_labels_and_details(self) -> None:
        cases = [
            ({"name": "manage_task", "args": {"Action": "status"}}, "exec", "⚙️ Manage task `status`"),
            ({"name": "manage_subagents", "args": {"Action": "list"}}, "agent", "🤝 Manage subagents"),
            ({"name": "define_subagent", "args": {"Name": "auditor"}}, "agent", "🤝 Define subagent"),
            ({"name": "schedule", "args": {"CronExpression": "*/5 * * * *"}}, "schedule", "⏰ Schedule task `*/5 * * * *`"),
            ({"name": "schedule", "args": {"DurationSeconds": 90}}, "schedule", "⏰ Schedule task `90s`"),
            ({"name": "call_mcp_tool", "args": {"ToolName": "query_docs"}}, "mcp", "🔌 Call MCP tool `query_docs`"),
            ({"name": "list_resources", "args": {"ServerName": "cf"}}, "mcp", "🔌 List MCP resources"),
            ({"name": "read_resource", "args": {"Uri": "docs://1"}}, "mcp", "🔌 Read MCP resource"),
            ({"name": "search_marketplace", "args": {"queries": ["figma"]}}, "plugin", "🧩 Search marketplace `figma`"),
            ({"name": "list_plugin_accounts", "args": {}}, "plugin", "🧩 Check plugin accounts"),
        ]
        for tool_call, expected_cat, expected_label in cases:
            cat, label = progress_hook._describe_tool(tool_call, "", "", "en")
            self.assertEqual(cat, expected_cat)
            self.assertEqual(label, expected_label)

    def test_stop_detects_nonempty_error_field_with_new_termination_reasons(self) -> None:
        self._event("SessionStart", 1000.0, lastUserInput="Run quick check")
        self._event("PreInvocation", 1000.0, lastUserInput="Run quick check")
        with mock.patch.object(progress_hook, "_send_desktop_notification") as notify_mock:
            self._event(
                "Stop",
                1001.0,
                lastUserInput="Run quick check",
                terminationReason="TERMINAL_CUSTOM_HOOK",
                error="blocked by safety hook",
                continuationActive=False,
            )
        notify_mock.assert_called_once()
        _, subtitle, _ = notify_mock.call_args.args
        self.assertIn("error or limit", subtitle)

    def test_persistent_user_config_overrides_and_invalid_config_fallback(self) -> None:
        config_path = Path(self.tmp_dir.name) / "config.json"

        # 1. Valid user overrides
        config_path.write_text(
            json.dumps(
                {
                    "language": "en",
                    "silent_nudge_interval": 1,
                    "safeguard_first_invocation": 4,
                    "safeguard_repeat_interval": 2,
                    "notify_enabled": False,
                    "notify_min_tools": 1,
                    "state_retention_days": 7,
                }
            ),
            encoding="utf-8",
        )
        cfg = progress_hook._load_user_config()
        self.assertEqual(cfg["language"], "en")
        self.assertEqual(cfg["silent_nudge_interval"], 1)
        self.assertEqual(cfg["safeguard_first_invocation"], 4)
        self.assertEqual(cfg["safeguard_repeat_interval"], 2)
        self.assertFalse(cfg["notify_enabled"])
        self.assertEqual(cfg["state_retention_sec"], 7 * 24 * 3600)

        # Verify Chinese prompt respects explicit config language="en" and interval=1
        self._event("SessionStart", 1100.0)
        self._event("PreInvocation", 1100.0)
        self._append_planner_step("")
        self._event("PostToolUse", 1101.0, toolCall={"name": "edit_file", "args": {"Path": "/x/app.py"}})
        res = self._event("PreInvocation", 1102.0, invocationNum=1)
        self.assertEqual(len(res["injectSteps"]), 1)
        self.assertIn("✏️ Edit `app.py`", res["injectSteps"][0]["systemMessage"]["systemMessage"])

        # Verify notify_enabled=False suppresses even error notifications
        with mock.patch.object(progress_hook, "_send_desktop_notification") as notify_mock:
            self._event("Stop", 1130.0, terminationReason="ERROR")
        notify_mock.assert_not_called()

        # 2. Malformed JSON and invalid types safely fall back to defaults
        config_path.write_text("{not valid json", encoding="utf-8")
        cfg_bad = progress_hook._load_user_config()
        self.assertEqual(cfg_bad["silent_nudge_interval"], progress_hook.SILENT_NUDGE_INTERVAL)
        self.assertTrue(cfg_bad["notify_enabled"])

        config_path.write_text(
            json.dumps(
                {
                    "silent_nudge_interval": True,  # bool must not be accepted as int
                    "safeguard_first_invocation": 0,  # below minimum 1
                    "notify_min_elapsed_sec": -5,  # below minimum 0
                    "notify_enabled": "yes",  # non-bool ignored
                    "state_retention_days": False,
                }
            ),
            encoding="utf-8",
        )
        cfg_types = progress_hook._load_user_config()
        self.assertEqual(cfg_types["silent_nudge_interval"], progress_hook.SILENT_NUDGE_INTERVAL)
        self.assertEqual(cfg_types["safeguard_first_invocation"], progress_hook.SAFEGUARD_FIRST_INVOCATION)
        self.assertEqual(cfg_types["notify_min_elapsed_sec"], progress_hook.NOTIFY_MIN_ELAPSED_SEC)
        self.assertTrue(cfg_types["notify_enabled"])
        self.assertEqual(cfg_types["state_retention_sec"], progress_hook.STATE_RETENTION_SEC)

    def test_linux_notify_send_dispatch_and_graceful_noop(self) -> None:
        with mock.patch.object(progress_hook.sys, "platform", "linux"):
            with mock.patch.object(progress_hook.shutil, "which", return_value="/usr/bin/notify-send"):
                with mock.patch.object(progress_hook.subprocess, "run") as run_mock:
                    progress_hook._send_desktop_notification("Title", "Sub", "Body")
                run_mock.assert_called_once()
                self.assertEqual(run_mock.call_args.args[0][0], "/usr/bin/notify-send")

            with mock.patch.object(progress_hook.shutil, "which", return_value=None):
                with mock.patch.object(progress_hook.subprocess, "run") as run_mock:
                    progress_hook._send_desktop_notification("Title", "Sub", "Body")
                run_mock.assert_not_called()

    def test_windows_msvcrt_lock_branch_acquires_and_releases(self) -> None:
        calls: list[tuple[int, int]] = []
        attempts = {"count": 0}

        class FakeMsvcrt:
            LK_NBLCK = 2
            LK_UNLCK = 0

            @staticmethod
            def locking(fd: int, mode: int, nbytes: int) -> None:
                calls.append((mode, nbytes))
                if mode == FakeMsvcrt.LK_NBLCK and attempts["count"] == 0:
                    attempts["count"] += 1
                    raise OSError("contended lock")

        with mock.patch.object(progress_hook, "fcntl", None):
            with mock.patch.object(progress_hook, "msvcrt", FakeMsvcrt):
                with progress_hook._conversation_lock("conv-win-lock"):
                    pass

        self.assertEqual(
            calls,
            [
                (FakeMsvcrt.LK_NBLCK, 1),
                (FakeMsvcrt.LK_NBLCK, 1),
                (FakeMsvcrt.LK_UNLCK, 1),
            ],
        )

    def test_native_progress_tools_labels_and_details(self) -> None:
        focus_call = {"name": "update_focus", "args": {"focus": "Inspecting auth token refresh flow"}}
        cat_en, label_en = progress_hook._describe_tool(focus_call, "", "", "en")
        self.assertEqual(cat_en, "progress")
        self.assertEqual(label_en, "🎯 Update focus `Inspecting auth token refre…`")

        cat_zh, label_zh = progress_hook._describe_tool(
            {"name": "update_focus", "args": {"focus": "核对插件兼容性"}}, "", "", "zh"
        )
        self.assertEqual(cat_zh, "progress")
        self.assertEqual(label_zh, "🎯 更新状态摘要 `核对插件兼容性`")

        steps_call = {
            "name": "update_steps",
            "args": {
                "steps": [
                    {"title": "Refactor rules", "status": "done"},
                    {"title": "Upgrade hook", "status": "done"},
                    {"title": "Update docs", "status": "in_progress"},
                    {"title": "Sync locally", "status": "pending"},
                ]
            },
        }
        cat_s_en, label_s_en = progress_hook._describe_tool(steps_call, "", "", "en")
        self.assertEqual(cat_s_en, "progress")
        self.assertEqual(label_s_en, "📋 Update steps `2/4`")

        cat_s_ja, label_s_ja = progress_hook._describe_tool(steps_call, "", "", "ja")
        self.assertEqual(cat_s_ja, "progress")
        self.assertEqual(label_s_ja, "📋 ステップ更新 `2/4`")

    def test_native_progress_tools_exempt_from_silence_nudge(self) -> None:
        conv_id = "conv-native-progress"
        self._event("SessionStart", 1200.0, conversationId=conv_id)
        self.assertEqual(self._event("PreInvocation", 1200.0, conversationId=conv_id), {"injectSteps": []})

        # Two silent invocations
        for idx in range(1, 3):
            self._append_planner_step("")
            self._event(
                "PostToolUse",
                1200.0 + idx,
                conversationId=conv_id,
                toolCall={"name": "read_file", "args": {"Path": f"/repo/f{idx}.py"}},
            )
            self.assertEqual(
                self._event("PreInvocation", 1200.5 + idx, conversationId=conv_id, invocationNum=idx),
                {"injectSteps": []},
            )

        # Third invocation uses update_focus (no visible text) -> must reset silence instead of nudging
        self._append_planner_step("")
        self._event(
            "PostToolUse",
            1203.0,
            conversationId=conv_id,
            toolCall={"name": "update_focus", "args": {"focus": "Editing hook logic"}},
        )
        self._event(
            "PostToolUse",
            1203.1,
            conversationId=conv_id,
            toolCall={"name": "edit_file", "args": {"Path": "/repo/hook.py"}},
        )
        self.assertEqual(
            self._event("PreInvocation", 1203.5, conversationId=conv_id, invocationNum=3),
            {"injectSteps": []},
        )
        self.assertEqual(progress_hook._load_state(conv_id)["silent_invocations"], 0)

        # update_steps also counts as progress sync
        self._append_planner_step("")
        self._event(
            "PostToolUse",
            1204.0,
            conversationId=conv_id,
            toolCall={
                "name": "update_steps",
                "args": {"steps": [{"title": "Edit hook", "status": "in_progress"}]},
            },
        )
        self.assertEqual(
            self._event("PreInvocation", 1204.5, conversationId=conv_id, invocationNum=4),
            {"injectSteps": []},
        )
        self.assertEqual(progress_hook._load_state(conv_id)["silent_invocations"], 0)

        # A failed update_focus must NOT exempt silence; 3 consecutive truly silent invocations still nudge
        self._append_planner_step("")
        self._event(
            "PostToolUse",
            1205.0,
            conversationId=conv_id,
            error="invalid schema",
            toolCall={"name": "update_focus", "args": {"focus": "bad"}},
        )
        self.assertEqual(
            self._event("PreInvocation", 1205.5, conversationId=conv_id, invocationNum=5),
            {"injectSteps": []},
        )
        self.assertEqual(progress_hook._load_state(conv_id)["silent_invocations"], 1)

        self._append_planner_step("")
        self._event(
            "PostToolUse",
            1206.0,
            conversationId=conv_id,
            toolCall={"name": "edit_file", "args": {"Path": "/repo/a.py"}},
        )
        self.assertEqual(
            self._event("PreInvocation", 1206.5, conversationId=conv_id, invocationNum=6),
            {"injectSteps": []},
        )

        self._append_planner_step("")
        self._event(
            "PostToolUse",
            1207.0,
            conversationId=conv_id,
            toolCall={"name": "run_command", "args": {"CommandLine": "pytest"}},
        )
        res_nudge = self._event("PreInvocation", 1207.5, conversationId=conv_id, invocationNum=7)
        self.assertEqual(len(res_nudge["injectSteps"]), 1)
        msg = res_nudge["injectSteps"][0]["systemMessage"]["systemMessage"]
        self.assertIn("Progress Reminder", msg)
        self.assertIn("update_focus / update_steps", msg)

    def test_stop_notification_enriches_with_update_steps_snapshot(self) -> None:
        # 1. Chinese session with out-of-order newly completed step
        zh_conv = "conv-steps-zh"
        self._event("SessionStart", 1300.0, conversationId=zh_conv, lastUserInput="重构权限模块")
        self._event("PreInvocation", 1300.0, conversationId=zh_conv, lastUserInput="重构权限模块")
        self._event(
            "PostToolUse",
            1302.0,
            conversationId=zh_conv,
            lastUserInput="重构权限模块",
            toolCall={
                "name": "update_steps",
                "args": {
                    "steps": [
                        {"title": "收紧鉴权策略", "status": "done"},
                        {"title": "验证双角色测试", "status": "in_progress"},
                        {"title": "清理旧缓存", "status": "done"},
                    ]
                },
            },
        )
        self._event(
            "PostToolUse",
            1305.0,
            conversationId=zh_conv,
            lastUserInput="重构权限模块",
            toolCall={
                "name": "update_steps",
                "args": {
                    "steps": [
                        {"title": "收紧鉴权策略", "status": "done"},
                        {"title": "验证双角色测试", "status": "done"},
                        {"title": "清理旧缓存", "status": "done"},
                    ]
                },
            },
        )
        self._event(
            "PostToolUse",
            1306.0,
            conversationId=zh_conv,
            lastUserInput="重构权限模块",
            toolCall={"name": "run_command", "args": {"toolSummary": "Run tests"}},
        )
        with mock.patch.object(progress_hook, "_send_desktop_notification") as notify_zh:
            self._event("Stop", 1320.0, conversationId=zh_conv, lastUserInput="", terminationReason="NO_TOOL_CALL")
        notify_zh.assert_called_once()
        _, sub_zh, body_zh = notify_zh.call_args.args
        self.assertEqual(sub_zh, "⏸️ 阶段完成 (3/3 步)")
        self.assertIn("已完成「验证双角色测试」", body_zh)
        self.assertIn("3 次操作", body_zh)

        # 2. English session with only in_progress step (0 done)
        en_conv = "conv-steps-en"
        self._event("SessionStart", 1400.0, conversationId=en_conv, lastUserInput="Audit auth flow")
        self._event("PreInvocation", 1400.0, conversationId=en_conv, lastUserInput="Audit auth flow")
        self._event(
            "PostToolUse",
            1405.0,
            conversationId=en_conv,
            lastUserInput="Audit auth flow",
            toolCall={
                "name": "update_steps",
                "args": {
                    "steps": [
                        {"title": "Verify Console build tests", "status": "in_progress"},
                        {"title": "Merge fix into dev", "status": "pending"},
                    ]
                },
            },
        )
        with mock.patch.object(progress_hook, "_send_desktop_notification") as notify_en:
            self._event("Stop", 1420.0, conversationId=en_conv, lastUserInput="", terminationReason="NO_TOOL_CALL")
        notify_en.assert_called_once()
        _, sub_en, body_en = notify_en.call_args.args
        self.assertEqual(sub_en, "⏸️ Milestone ready (0/2 steps)")
        self.assertIn('In progress: "Verify Console build tests"', body_en)

        # 3. Japanese error stop with step progress
        ja_conv = "conv-steps-ja"
        self._event("SessionStart", 1500.0, conversationId=ja_conv, lastUserInput="テストを修正して")
        self._event("PreInvocation", 1500.0, conversationId=ja_conv, lastUserInput="テストを修正して")
        self._event(
            "PostToolUse",
            1502.0,
            conversationId=ja_conv,
            lastUserInput="テストを修正して",
            toolCall={
                "name": "update_steps",
                "args": {
                    "steps": [
                        {"title": "設定を確認", "status": "done"},
                        {"title": "統合テスト実行", "status": "failed"},
                    ]
                },
            },
        )
        with mock.patch.object(progress_hook, "_send_desktop_notification") as notify_ja:
            self._event("Stop", 1505.0, conversationId=ja_conv, lastUserInput="", terminationReason="ERROR")
        notify_ja.assert_called_once()
        _, sub_ja, body_ja = notify_ja.call_args.args
        self.assertEqual(sub_ja, "⚠️ エラー等で一時停止 (1/2 ステップ)")
        self.assertIn("「設定を確認」完了", body_ja)

        # 4. Malformed update_steps payload safely falls back to classic notification
        bad_conv = "conv-steps-bad"
        self._event("SessionStart", 1600.0, conversationId=bad_conv, lastUserInput="Run build")
        self._event("PreInvocation", 1600.0, conversationId=bad_conv, lastUserInput="Run build")
        self._event(
            "PostToolUse",
            1601.0,
            conversationId=bad_conv,
            lastUserInput="Run build",
            toolCall={"name": "update_steps", "args": {"steps": "not-a-list"}},
        )
        with mock.patch.object(progress_hook, "_send_desktop_notification") as notify_bad:
            self._event("Stop", 1620.0, conversationId=bad_conv, lastUserInput="", terminationReason="NO_TOOL_CALL")
        notify_bad.assert_called_once()
        _, sub_bad, body_bad = notify_bad.call_args.args
        self.assertEqual(sub_bad, "⏸️ Milestone ready · Review & confirm")
        self.assertEqual(body_bad, "1 tool calls in 20s.")


if __name__ == "__main__":
    unittest.main()
