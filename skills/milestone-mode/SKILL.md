---
name: milestone-mode
description: >-
  Additive phased-milestone workflow layered on top of Antigravity's native update_steps
  checklists and update_focus UI: enforces one-milestone-per-turn execution and plain-language
  pause-and-confirm checkpoints after each submodule. Use when starting a large project or
  whenever the user explicitly wants strict step-by-step milestone control.
---

# Milestone Mode

Use this additive workflow on top of Antigravity's native checklists (`update_steps`) and live status (`update_focus`) whenever the user explicitly requests `/milestone-mode` or wants strict step-by-step confirmation on a multi-module task. Write all plans, step titles, status updates, and checkpoint cards in the user's conversation language.

## Steps

1. **Explore & Scope**: Quickly inspect only the necessary entrypoints to understand the project layout.
2. **Create Milestone Plan**:
   - Split the work into numbered milestones (each `<= 10` tool steps / 1 cohesive submodule).
   - Present the plan concisely in the user's language and wait for user approval before editing code.
   - *(Use AGY's native `update_steps` checklist first once approved; only create a `task.md` Artifact if the user explicitly asks for a persistent cross-session checklist file.)*
3. **Execute One Milestone at a Time**:
   - Mark the active milestone `in_progress` via native `update_steps` and use `update_focus` for intra-milestone phases (adding brief visible text only when completing a step or at meaningful phase transitions).
   - Implement and verify **only** the current milestone—do not chain subsequent milestones in the same turn (unless the user explicitly switches to continuous execution or `/goal`).
   - Mark the completed milestone `done` via `update_steps`.
4. **Pause & Report**:
   - Stop calling tools at the end of the milestone.
   - Output the standardized 5-item progress card in the user's language (`📊 Progress`, `✅ Completed`, `🧪 Verification`, `⏭️ Next Milestone`, `⏸️ Waiting for Confirmation` — e.g. in Chinese: `📊 总进度`, `✅ 本阶段已完成`, `🧪 验证情况`, `⏭️ 下一阶段计划`, `⏸️ 等待确认`) and wait for the user's reply before starting the next milestone.
