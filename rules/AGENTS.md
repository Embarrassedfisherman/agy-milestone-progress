# Milestone Progress & Transparent Execution Protocol

Follow this execution protocol to keep long-running work transparent, understandable, and controllable.

## 1. Smart Threshold (When to Activate)

- **Small / Direct Tasks**: Simple Q&A, single-file bug fixes, minor edits (<= 2 files, <= 4 tool steps) should be completed directly in one turn without unnecessary planning ceremonies or artificial pauses.
- **Large / Complex Tasks**: Automatically enter **Phased Milestone Mode** whenever a task involves any of the following:
  - Creating or modifying 3+ files or spanning multiple modules/layers (e.g., frontend + backend, schema + API + tests).
  - Architectural changes, large refactors, or setting up a new project/feature.
  - Open-ended debugging or exploration likely to take > 5 minutes or > 8 tool steps.

*(If the user explicitly invokes `/plan`, `/grill-me`, or another workflow command, follow that command's interaction flow first, then enter Phased Milestone Mode once implementation starts.)*

## 2. Live Inline Progress Narration (Real-Time Chat Status)

Whenever a turn requires **multiple tool calls (>= 2 sequential tool batches)**:
- **Do NOT stay completely silent inside `<thinking>` across many consecutive tool steps.**
- At the start of a phase, when switching action types (e.g., exploring -> editing -> running tests), or every **2–3 tool steps**, output **one short, plain-Chinese status line directly in your visible response text** *before* invoking the tool(s), for example:
  - `🧭 正在扫描认证模块入口与配置文件…`
  - `✏️ 已定位问题，正在修改路由与中间件代码…`
  - `🧪 代码修改完成，正在运行单元测试验证…`
- Keep each inline status line to **1 concise sentence** in plain human language (no raw shell commands or walls of text).

## 3. Phased Milestone Mode Rules

### Step A: Plan & Confirm First
Before modifying code on a large task:
1. Break the task into numbered milestones (each milestone scoped to a single cohesive submodule that can finish within ~2–5 minutes / <= 10 tool steps).
2. Create or update a `task.md` checklist Artifact (when Artifacts are available) summarizing all milestones and their status (`[ ]`, `[/]`, `[x]`).
3. Present the concise milestone plan in plain, easy-to-read Chinese and **stop to ask for user confirmation** before starting Milestone 1 (unless the user already approved this exact plan).

### Step B: One Milestone Per Turn
1. Execute **at most ONE milestone/submodule per conversation turn**. Never silently chain multiple submodules across tens of minutes.
2. Update the `task.md` Artifact when starting (`[/]`) and finishing (`[x]`) a milestone so the user can also track status live in the Auxiliary Pane (`Artifacts`).
3. If a single milestone runs long (approaching ~10–12 tool steps) or hits unexpected blockers/ambiguity, wrap up cleanly at a safe boundary rather than continuing blindly.

### Step C: Mandatory Plain-Language Checkpoint Report
At the end of every milestone turn (or early pause), stop calling tools and present a concise Chinese progress card:

- **📊 总进度**：`[已完成 X / 共 Y 阶段]` — 当前阶段名称
- **✅ 本阶段已完成**：用通俗人话说明完成了什么功能/改动，列出关键文件路径（不要输出底层命令流水账）
- **🧪 验证情况**：如实说明运行了哪些测试/构建/检查及结果（未运行则明确说明未验证）
- **⏭️ 下一阶段计划**：下一步将处理哪个子模块及预期改动
- **⏸️ 等待确认**：明确询问是否继续下一阶段，或是否需要调整方向。
