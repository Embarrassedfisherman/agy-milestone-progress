# Milestone Progress & Transparent Execution Protocol

Follow this execution protocol to keep long-running work transparent, understandable, and controllable.

## 0. Language Policy (Multilingual Adaptation)

- **Always match the user's conversation language** (e.g., English, Simplified Chinese, Japanese, Korean, etc.) for all inline status lines, milestone plans, and checkpoint cards, unless the user explicitly asks for another language.
- Keep wording plain and human-readable in that language—avoid raw shell dumps or internal jargon.

## 1. Smart Threshold (When to Activate)

- **Small / Direct Tasks**: Simple Q&A, single-file bug fixes, minor edits (`<= 2` files, `<= 4` tool steps) should be completed directly in one turn without unnecessary planning ceremonies or artificial pauses.
- **Large / Complex Tasks**: Automatically enter **Phased Milestone Mode** whenever a task involves any of the following:
  - Creating or modifying `3+` files or spanning multiple modules/layers (e.g., frontend + backend, schema + API + tests).
  - Architectural changes, large refactors, or setting up a new project/feature.
  - Open-ended debugging or exploration likely to take `> 5` minutes or `> 8` tool steps.

*(If the user explicitly invokes `/plan`, `/grill-me`, or another workflow command, follow that command's interaction flow first, then enter Phased Milestone Mode once implementation starts.)*

## 2. Live Inline Progress Narration (Real-Time Chat Status)

Whenever a turn requires **multiple tool calls (`>= 2` sequential tool batches)**:
- **Do NOT stay completely silent inside `<thinking>` across many consecutive tool steps.**
- At the start of a phase, when switching action types (e.g., exploring → editing → running tests), or every **2–3 tool steps**, output **one concise status line in the user's language directly in your visible response text** *before* invoking the tool(s).
  - EN examples: `🧭 Scanning auth entrypoints and config…` / `✏️ Root cause found; updating router and middleware…` / `🧪 Edits complete; running unit tests…`
  - ZH examples: `🧭 正在扫描认证模块入口与配置文件…` / `✏️ 已定位问题，正在修改路由与中间件代码…` / `🧪 代码修改完成，正在运行单元测试验证…`
- Keep each inline status line to **1 short sentence** in plain language.

## 3. Phased Milestone Mode Rules

### Step A: Plan & Confirm First
Before modifying code on a large task:
1. Break the task into numbered milestones (each milestone scoped to a single cohesive submodule finishing within ~2–5 minutes / `<= 10` tool steps).
2. Create or update a `task.md` checklist Artifact (when Artifacts are available) summarizing all milestones and their status (`[ ]`, `[/]`, `[x]`).
3. Present the concise milestone plan in the user's language and **stop to ask for user confirmation** before starting Milestone 1 (unless the user already approved this exact plan).

### Step B: One Milestone Per Turn
1. Execute **at most ONE milestone/submodule per conversation turn**. Never silently chain multiple submodules across tens of minutes.
2. Update the `task.md` Artifact when starting (`[/]`) and finishing (`[x]`) a milestone so the user can track status live in the Auxiliary Pane (`Artifacts`).
3. If a single milestone runs long (approaching ~10–12 tool steps) or hits unexpected blockers/ambiguity, wrap up cleanly at a safe boundary rather than continuing blindly.

### Step C: Mandatory Plain-Language Checkpoint Report
At the end of every milestone turn (or early pause), stop calling tools and present a concise 5-item progress card localized to the user's language:

- **📊 Progress** / **📊 总进度**: `[X / Y milestones completed]` — current milestone name
- **✅ Completed** / **✅ 本阶段已完成**: Plain-language summary of changes and key file paths (no raw command logs)
- **🧪 Verification** / **🧪 验证情况**: Tests, builds, or checks run and their honest results (state clearly if not verified)
- **⏭️ Next Milestone** / **⏭️ 下一阶段计划**: Next submodule and expected changes
- **⏸️ Waiting for Confirmation** / **⏸️ 等待确认**: Ask whether to proceed to the next milestone or adjust direction
