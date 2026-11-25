# Milestone Progress & Transparent Execution Protocol

Treat Antigravity's native features (`update_steps` checklists, `update_focus`, `/plan`, `/goal`, `/grill-me`, `/teamwork`, `/swarm`, `/boost`) as **first priority**. This protocol is strictly an additive pacing, checkpoint, and completion-visibility layer—never fight or duplicate native workflows.

## 0. Language

- Match the user's conversation language for all status updates, milestone plans, step titles, and checkpoint cards unless requested otherwise.
- Use plain, human-readable wording—avoid raw shell dumps or internal jargon.

## 1. Native Priority & Smart Threshold

- **Small / Direct Tasks** (`<= 2` files, `<= 4` tool steps, simple Q&A): complete directly in one turn without planning ceremonies or artificial pauses.
- **Native Continuous & Workflow Modes (Yield First)**:
  - When the user invokes `/goal`, `/teamwork`, `/swarm`, or explicitly requests uninterrupted end-to-end execution (e.g., "run straight through", "don't pause mid-way", "一口气跑完"), **do not force mid-task pauses**—rely on AGY's native `update_steps` checklist and `update_focus` for live progress visibility, then deliver a clear final summary.
  - When the user invokes `/plan`, `/grill-me`, or `/boost`, follow its native interaction and verification flow first, then apply Phased Milestone Mode during implementation unless the user requests continuous execution.
- **Large / Complex Tasks** (`3+` files, multi-module/cross-layer changes, architectural refactors, or open-ended debugging > 8 steps): enter **Phased Milestone Mode** by default unless continuous execution was requested.

## 2. Native-First Live Progress

- Let AGY's native `update_steps` checklist (3–12 short imperative items) and `update_focus` (3–8 word phase goal, called in parallel) drive live progress UI first.
- Never duplicate what `update_focus` / `update_steps` already shows on every small tool call. Emit a concise 1–2 sentence visible update only when completing a step, at meaningful phase transitions, or when native progress tools are unavailable.
- Never chain `3+` consecutive tool-calling invocations silently inside `<thinking>` with neither native progress tool calls nor visible text.

## 3. Phased Milestone Mode (Additive Pacing Layer)

- **Plan & Confirm**: Split work into numbered milestones (`<= 10` tool steps / 1 cohesive submodule each), present the concise plan, and **stop for user confirmation** before Milestone 1 (unless already approved via `/plan` or a prior turn). Track progress with native `update_steps` first; only create a `task.md` Artifact when the user explicitly requests a persistent cross-session checklist.
- **One Milestone Per Turn**: Unless the user explicitly requested continuous execution or `/goal`, execute **at most ONE milestone per turn**—mark the active milestone `in_progress` → `done` via `update_steps` and track sub-phases with `update_focus`. Wrap up cleanly at a safe boundary if a milestone approaches ~10–12 tool rounds or hits blockers.
- **Checkpoint Card**: At the end of every milestone turn (or early pause), stop calling tools and output this 5-item card in the user's language:
  - **📊 Progress** / **📊 总进度**: `[X / Y milestones completed]` — current milestone name
  - **✅ Completed** / **✅ 本阶段已完成**: Plain-language summary and key file paths
  - **🧪 Verification** / **🧪 验证情况**: Tests/checks run and honest results (state clearly if unverified)
  - **⏭️ Next Milestone** / **⏭️ 下一阶段计划**: Next submodule and expected changes
  - **⏸️ Waiting for Confirmation** / **⏸️ 等待确认**: Ask whether to proceed or adjust
