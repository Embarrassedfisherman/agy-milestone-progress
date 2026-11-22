---
name: milestone-mode
description: >-
  Forces phased milestone planning, live task checklist artifact updates, and mandatory
  plain-language pause-and-confirm checkpoints after each submodule. Use when starting
  a large project or whenever the user wants strict step-by-step milestone visibility.
---

# Milestone Mode

Use this workflow when executing a multi-module task or when the user explicitly requests `/milestone-mode`. Always write all plans, status lines, and checkpoint cards in the user's conversation language.

## Steps

1. **Explore & Scope**: Quickly inspect only the necessary entrypoints to understand the project layout.
2. **Create Milestone Plan**:
   - Split the work into numbered milestones (each `<= 10` tool steps / 1 cohesive submodule).
   - Create or update a user-facing `task.md` Artifact with checkboxes for each milestone.
   - Present the plan concisely in the user's language and wait for user approval before editing code.
3. **Execute One Milestone at a Time**:
   - Mark the active milestone `[/]` in `task.md`.
   - Implement and verify only that milestone, emitting concise live inline progress lines in the user's language before multi-step tool batches.
   - Mark the milestone `[x]` in `task.md`.
4. **Pause & Report**:
   - Stop calling tools at the end of the milestone.
   - Output the standardized 5-item progress card in the user's language (`📊 Progress`, `✅ Completed`, `🧪 Verification`, `⏭️ Next Milestone`, `⏸️ Waiting for Confirmation` — e.g. in Chinese: `📊 总进度`, `✅ 本阶段已完成`, `🧪 验证情况`, `⏭️ 下一阶段计划`, `⏸️ 等待确认`) and wait for the user's reply before starting the next milestone.
