#!/usr/bin/env python3
"""Unit tests for the milestone-progress Antigravity hook (v1.0.3)."""

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
        self.env_patch = mock.patch.dict(os.environ, {"PLUGIN_DATA": self.tmp_dir.name})
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

        with mock.patch.object(progress_hook, "_send_macos_notification") as notify_mock:
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

        with mock.patch.object(progress_hook, "_send_macos_notification") as notify_mock:
            self._event("Stop", 320.0, terminationReason="NO_TOOL_CALL")
        notify_mock.assert_called_once()
        title, subtitle, body = notify_mock.call_args.args
        self.assertEqual(title, "Antigravity · my-project")
        self.assertIn("阶段完成", subtitle)
        self.assertIn("3 次操作", body)

        self._event("PreInvocation", 400.0, invocationNum=1, initialNumSteps=20)
        with mock.patch.object(progress_hook, "_send_macos_notification") as notify_mock:
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
        self.assertEqual(plugin_data["version"], "1.0.3")

        hooks_data = json.loads(HOOKS_JSON_PATH.read_text(encoding="utf-8"))
        spec = hooks_data["milestone-progress"]
        for key in ("SessionStart", "PostToolUse", "PreInvocation", "Stop"):
            self.assertIn(key, spec)

        proc = subprocess.run(
            [sys.executable, str(HOOK_PATH)],
            input=json.dumps({**self.base_payload, "hookEventName": "PreInvocation", "invocationNum": 1}),
            text=True,
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

        # Two silent rounds first
        for idx in range(1, 3):
            self._append_planner_step("")
            self._event("PostToolUse", 800.0 + idx, toolCall={"name": "read_file", "args": {"Path": f"/repo/s{idx}.py"}})
            self.assertEqual(self._event("PreInvocation", 800.5 + idx, invocationNum=idx), {"injectSteps": []})

        # Third round has visible narration, followed by >64KB of tool output steps across chunk boundaries
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

        # Single >40KB PLANNER_RESPONSE line split across chunk boundary
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


if __name__ == "__main__":
    unittest.main()
