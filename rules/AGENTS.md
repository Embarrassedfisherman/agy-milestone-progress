# Milestone Progress & Transparent Execution Protocol

Keep long-running work transparent, paced, and controllable alongside Antigravity's native progress UI (`update_focus`, `update_steps`).

## 0. Language

- Match the user's conversation language for all status updates, milestone plans, step titles, and checkpoint cards unless requested otherwise.
- Use plain, human-readable wording—avoid raw shell dumps or internal jargon.

## 1. Smart Threshold

- **Small / Direct Tasks** (`<= 2` files, `<= 4` tool steps, simple Q&A): complete directly in one turn without planning ceremonies or artificial pauses.
- **Large / Complex Tasks** (`3+` files, multi-module/cross-layer changes, architectural refactors, or open-ended debugging > 8 steps): automatically enter **Phased Milestone Mode**.
- *(If the user invokes `/plan`, `/grill-me`, or another workflow command, follow its interaction flow first, then apply Phased Milestone Mode during implementation.)*

## 2. Native-First Live Progress

- On multi-batch turns, prefer AGY's native `update_focus` (3–8 word phase goal, called in parallel) and `update_steps` (3–12 short imperative items).
- Avoid repeating a chat status line before every small tool call when `update_focus` / `update_steps` already shows progress. Emit a concise 1-sentence visible update at meaningful phase transitions, when completing a step, or when native progress tools are unavailable.
- Never chain `3+` consecutive tool-calling invocations silently inside `<thinking>` with neither native progress tool calls nor visible text.

## 3. Phased Milestone Mode

- **Plan & Confirm**: Split work into numbered milestones (`<= 10` tool steps / 1 cohesive submodule each), present the concise plan, and **stop for user confirmation** before Milestone 1 (unless already approved via `/plan` or a prior turn). Default to native `update_steps` once execution starts; only create a `task.md` Artifact when the user explicitly requests a persistent cross-session checklist.
- **One Milestone Per Turn**: Execute **at most ONE milestone per turn**—never auto-run all remaining `update_steps` milestones in one uninterrupted turn. Mark the active milestone `in_progress` → `done` via `update_steps` and track sub-phases with `update_focus`. Wrap up cleanly at a safe boundary if a milestone approaches ~10–12 steps or hits blockers.
- **Checkpoint Card**: At the end of every milestone turn (or early pause), stop calling tools and output this 5-item card in the user's language:
  - **📊 Progress** / **📊 总进度**: `[X / Y milestones completed]` — current milestone name
  - **✅ Completed** / **✅ 本阶段已完成**: Plain-language summary and key file paths
  - **🧪 Verification** / **🧪 验证情况**: Tests/checks run and honest results (state clearly if unverified)
  - **⏭️ Next Milestone** / **⏭️ 下一阶段计划**: Next submodule and expected changes
  - **⏸️ Waiting for Confirmation** / **⏸️ 等待确认**: Ask whether to proceed or adjust
