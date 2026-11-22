# Antigravity 透明进度与分阶段控制系统 —— 工程复盘与避坑沉淀

- **复盘日期**：2026-11-18（`v1.0.3` 工程加固更新于 2026-11-20）
- **适用环境**：Antigravity 2.0 Desktop App（macOS 完整支持，Linux/Windows 核心功能兼容）
- **沉淀产物**：全局插件 `milestone-progress`

> **文档分工说明（自 `v1.1.0` 起）**：本文档保留项目早期（`v1.0.0`–`v1.0.3`）的设计决策与避坑复盘；后续持续迭代记录已迁移至结构化运维台账：[CHANGELOG.zh-CN.md](../CHANGELOG.zh-CN.md)（版本变更）、[BUG_LOG.md](./BUG_LOG.md)（Bug 与上游缺陷编号台账）、[COMPATIBILITY.md](./COMPATIBILITY.md)（Antigravity 客户端兼容矩阵）及 [RELEASE_PROCESS.md](./RELEASE_PROCESS.md)（发版 SOP）。

---

## 一、背景痛点与机制拆解

### 1.1 原始痛点
在使用 Antigravity 处理较大型项目时，发出一句提示词后，Agent 往往连续思考并执行工具数十分钟，聊天主界面长时间没有可读的状态反馈；点开折叠的 Thinking 区域看到的全是底层推理与命令行参数，难以快速判断「现在做到了哪一步、是否跑偏、还要多久」。

### 1.2 根本原因
1. **单回合多步循环（Agent Loop）**：一次用户输入后，系统内部会循环执行 `PreInvocation → 模型推理 → 工具调用 → PostToolUse → 下一轮推理`，默认直到模型不再发起工具调用时才结束回合并展示最终总结。
2. **模型默认静默调工具**：推理模型在中间工具步骤习惯把全部分析写入 `<thinking>`，而可见响应字段 `PLANNER_RESPONSE.content` 为空字符串 `""`，导致主聊天画布在回合结束前没有任何人话进展。
3. **缺少里程碑边界约束**：在没有外部规则和步数护栏时，模型倾向于“一次性把所有模块全部改完”，拉长了单次黑盒运行时间。

---

## 二、方案设计决策树（`/grill-me` 共识记录）

围绕实际使用体验，逐层收敛出以下关键架构取舍：

1. **运行端定位 → Antigravity 2.0 桌面端**
   结合右上角原生 **Auxiliary Pane**（`Artifacts` 任务清单、`Files Changed` 代码变更、`Background Tasks / Terminals`）与自定义扩展协同。
2. **执行与汇报节奏 → 强制分阶段里程碑暂停**
   放弃 30 分钟无人值守盲跑，改为「先出方案确认 → 每回合仅执行 1 个子模块 → 输出通俗中文进度卡 → 等待确认后再进入下一阶段」。
3. **触发范围 → 智能阈值分流**
   小问答与单文件微调（`<= 2` 文件、`<= 4` 步）直接执行不打断；涉及 `3+` 文件、跨模块改造或复杂排查时自动进入分阶段里程碑模式，兼顾日常流畅度与大项目可控性。
4. **保障手段 → Rules + Skills + Lifecycle Hooks + macOS 系统通知**
   软规则负责规划格式与实时正文播报，底层 Hook 负责静默监控、超步数硬刹车与切屏时的系统弹窗提醒。
5. **生效范围与降噪策略 → 全局插件 + 智能降噪**
   打包安装至 `~/.gemini/config/plugins/milestone-progress/`，支持 UI 一键启停；短对话零插播、零弹窗，避免日常噪音。

---

## 三、实战排障与底层避坑记录（核心经验）

在从 `v1.0.0` 迭代到 `v1.0.3` 的实测与加固过程中，沉淀出以下 Antigravity 运行时细节与工程避坑经验：

### 坑点 1：`PreInvocation` 的 `initialNumSteps` 并非回合常量（`v1.0.0 → v1.0.1`）

- **问题现象**：重启客户端实测时，插件的持久化状态文件已正常生成，但 `turn_invocations` 始终停留在 `1`，`PostToolUse` 记录的工具计数也被不断清空。
- **根因分析**：
  - 初版使用 `f"{initialNumSteps}:{hash(lastUserInput)}"` 作为识别新回合的 `turn_key`。
  - 实测发现 Antigravity 在**同一回合内**每次调用模型前，`initialNumSteps` 都会随当前轨迹总步数递增（如 `74 → 76 → … → 93`），导致每次 `PreInvocation` 都误判为新回合而重置状态。
  - 同时，Hook 输入采用 Protobuf `protojson` 编码：首轮 `invocationNum == 0` 时字段会被省略（`None`），而 `int64` 类型在部分场景下可能编码为数字字符串（如 `"1"`）。
- **最终解法**：
  - 使用 `turn_active` 布尔标记（由回合结束的 `Stop` Hook 精确归零）+ `lastUserInput` 哈希作为主判定。
  - 配合兼容 `None`/整数/数字字符串的 `invocationNum` 回退检测，即使客户端中途异常退出未触发 `Stop`，重发相同提示词（如“继续”）也能准确重置新回合。

### 坑点 2：`systemMessage.metadata.user_markdown` 触发 Go 后端反射丢包（`v1.0.1 → v1.0.2`）

- **问题现象**：`v1.0.1` 修复状态累计后，`Stop` 的 macOS 桌面通知正常弹出，状态文件也显示 `PreInvocation` 已输出 `injectSteps`，但聊天界面看不到行内状态条，且检查 `transcript_full.jsonl` 发现步骤索引连续（如 `125 → 126`），没有任何步骤写入轨迹。
- **根因分析**：
  - 虽然内置文档记载可在 `systemMessage` 中设置 `metadata: {"user_markdown": "..."}` 来内嵌渲染用户可见 Markdown，但当前版本 Antigravity 的 Go 后端（`hookcaller.callHookAs` 调用的 `utils.ScrubInternalFields`）在遍历 `metadata` 字典时假设其值为嵌套 Protobuf Message 并调用 `protoreflect.Value.Message()`。
  - 传入字符串值会触发 `type mismatch: cannot convert string to message`，后端捕获恢复后**静默丢弃整次 Hook 返回结果**（不仅吞掉了状态条，还会连带吞掉附带了 `metadata` 的硬刹车指令）。
- **最终解法**：
  1. **主通道改为模型原生正文流式播报**：在 `rules/AGENTS.md` 中新增 `Live Inline Progress Narration` 规范，要求模型在多步工具调用前直接在 `PLANNER_RESPONSE.content`（非 `<thinking>`）输出一句中文状态（如 `🧭 正在…`），由聊天主界面原生实时流式展示。
  2. **Hook 彻底移除 `metadata` 字段**：`PreInvocation` 仅返回纯 `{"systemMessage": {"systemMessage": "..."}}`。
  3. **新增 `transcript.jsonl` 尾部静默检测**：`PreInvocation` 从文件末尾按 `32KB` 分块倒序回溯（上限 `512KB`，可跨过超长工具输出与大段 `thinking`）查找最近一条 `PLANNER_RESPONSE`；若模型连续 `3` 轮 `content` 为空（静默调工具），自动注入 `[Progress Reminder]` 强制提醒其在下一步前输出中文进度；第 `12` 轮起注入 `[Progress Guardian]` 强制收尾（实测第 `16` 轮现场成功注入 `<SYSTEM_MESSAGE>`）。

### 坑点 4：并行工具调用竞态与历史状态文件堆积（`v1.0.2 → v1.0.3`）

- **问题现象**：模型单轮并行发起多个工具调用时，多个 `PostToolUse` 进程同时读写同一会话的状态 JSON 文件，可能发生写入覆盖导致工具计数或近期操作记录丢失；此外长期使用后状态目录会持续积累旧会话文件。
- **最终解法**：
  1. **会话级排他锁 + 原子落盘**：通过 `fcntl.flock`（`.lock`，非 POSIX 环境安全回退）串行化同一 `conversationId` 的状态读写，并先写入带 `PID + 纳秒时间戳` 的 `.tmp` 文件再 `Path.replace` 原子替换。
  2. **大日志分块倒序扫描**：将 `transcript.jsonl` 尾部扫描从固定 `24KB` 升级为 `32KB` 分块、最多 `512KB` 的边界拼接扫描，避免单次大体积工具输出淹没之前的可见播报。
  3. **自动过期清理**：在 `SessionStart` 顺带清理 `14` 天前遗留的 `.json/.lock/.tmp` 状态文件，保持插件数据目录长期整洁。

### 坑点 3：macOS 沙盒与 `osascript` 安全传参

- **现象与细节**：
  - 在标准终端沙盒（`sandbox-exec`）中，`osacompile` 无法加载 `/System/Library/ScriptingAdditions/StandardAdditions.osax`，直接编译 `display notification` 会报语法错误（`-2740` / `-2741`）；而插件 Hook 由宿主进程在沙盒外调用，可正常发送系统通知。
  - 若将任务摘要或目录名直接拼接到 AppleScript 字符串中，遇到双引号或换行极易报错。
- **最佳实践**：
  - 使用 `on run argv ... item 1 of argv ... end run` 通过命令行参数列表向 `osascript` 安全传值，设置 `timeout=2` 并捕获全部子进程异常，确保通知逻辑绝不阻塞主执行循环；单元测试中对 `_send_macos_notification` 进行 mock 隔离。

---

## 四、日常高效使用搭配清单

在大型项目中，推荐将本插件与 Antigravity 2.0 原生功能配合使用：

1. **需求还不清晰时**：先用 `/grill-me` 一问一答把技术选型和边界条件锁死，再开始写代码。
2. **进入多模块开发时**：
   - 直接发提示词（插件智能阈值会自动介入），或显式加 `/plan` / `/milestone-mode`。
   - 打开右上角 **Auxiliary Pane**：切到 **Artifacts** 看 `task.md` 勾选进度，切到 **Files Changed** 看实时代码改动。
3. **执行过程中**：
   - 留在窗口时：直接看聊天流中每隔 2–3 步自动流式打印的单行中文状态（`🧭` / `✏️` / `🧪`）。
   - 切走窗口处理别的事时：等右上角弹出 `Antigravity · 项目名 — ⏸️ 阶段完成` 桌面通知，再切回来看阶段中文汇报卡片并回复“继续”或调整方向。

---

## 五、CI 漏验与跨平台发布复盘（`v1.1.0 → v1.1.1`，2026-11-22）

### 5.1 发生了什么
首次推送 `v1.1.0`（`b176a4b`）后，Agent 在 `git push` 返回成功即宣布完成，把检查 GitHub Actions 留给了用户。随后用户在远端发现 **6 / 15 项 CI 失败**（全部 5 个 Windows 任务因缺少 `msvcrt` 文件锁导致并发测试丢计数；`ubuntu-latest / Python 3.9` 因 Ubuntu 26.04 无预编译 Python 3.9 失败），且因 `release.yml` 与 `v1.1.0` 标签同批首次推送，GitHub 未自动触发 Release。

### 5.2 为什么当时没有主动确认 CI（根因分析）
1. **过早沿用旧的权限假设**：早期在沙盒里测 `gh --version` 曾报 `config.yml: operation not permitted`，导致后续误以为无法调用 `gh`，推送后没有主动尝试 `gh run list` / `gh run watch`。
2. **本地 macOS 通过带来虚假安全感**：本地仅在 macOS（`fcntl` + UTF-8 默认终端 + Python 3.9.6）通过 25 项测试，未把远端跨平台 CI 绿灯视为交付完成的必要条件。
3. **受步数上限提醒影响仓促收尾**：推送时已触发 12–16 轮收尾提醒，未坚持「宁可显式标注远端 CI 待验证，也不在未确认绿灯前宣布完成」。
4. **原有发版 SOP 缺少推后门禁**：初版 `docs/RELEASE_PROCESS.md` 止步于 `git push --follow-tags`，既未要求先推 `main` 等 CI 全绿再打 Tag，也未强制要求执行 `gh run watch` 与 `gh release view` 闭环验收。

### 5.3 已落盘的防复发机制
1. **本机工作区级强制 Agent 规则（第三层，本地私有不入 Git）**：在 `.agents/rules/repo-ops.md` 中硬性规定每次推送后必须主动运行 `gh run watch` 验收全部 CI 矩阵，打标签后必须验收 `Release` 流水线与 Release 产物；无法验证时必须如实声明「未验证」，禁止报喜。
2. **升级发版 SOP 与三层边界隔离**：更新 [`docs/RELEASE_PROCESS.md`](./RELEASE_PROCESS.md)，明确运行态本体 / 开源公共工程 / 本机私有台账（`.agents/`、`.local-ops/`）三层边界，并将发布固化为「先推 `main` 验 CI 全绿 → 再打并推送 Tag → 验 `Release` 与附件」两步门禁。
3. **跨平台工程加固（已在 `v1.1.1` 修复并实测 15/15 绿灯）**：补齐 Windows 原生 `msvcrt.locking` 并发锁（`BUG-010`）、全脚本 UTF-8 `stdio`（`BUG-011`）及 `ubuntu-24.04` Python 3.9 矩阵测试。
