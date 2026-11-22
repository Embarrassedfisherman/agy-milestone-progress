# 更新日志（Changelog）

[English](./CHANGELOG.md) | [简体中文](./CHANGELOG.zh-CN.md)

本文档记录 **Milestone Progress (`milestone-progress`)** 的全部重要版本变更。

格式遵循 [Keep a Changelog 1.1.0](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本 2.0.0（SemVer）](https://semver.org/lang/zh-CN/)。

## [Unreleased]

---

## [1.1.0] - 2026-11-22

### 新增
- **全链路多语言 / i18n 架构（`BUG-009`）**：
  - 将 `rules/AGENTS.md` 与 `skills/milestone-mode/SKILL.md` 升级为语言自适应协议，自动匹配用户当前对话语言输出播报与进度卡片。
  - 新增零依赖 `hooks/i18n.py` 与可扩展 JSON 语言包（`hooks/locales/en.json`、`zh.json`、`ja.json`），支持自动语种识别、会话语言记忆与缺失文案英文安全回退。
- **持久化用户配置**：支持通过 `$PLUGIN_DATA/config.json`（及 `MILESTONE_PROGRESS_LANG` 环境变量）自定义语言、静默提醒与硬刹车轮数、通知开关/阈值和状态保留天数，插件频繁更新不覆盖用户偏好。
- **Linux 桌面通知降级支持**：在安装 `notify-send` 的 Linux 环境自动支持桌面通知，未安装时静默跳过。
- **插件视觉与清单元数据完善**：新增适配浅/深色主题的矢量图标 `assets/logo.svg`，完善 `plugin.json` 官方允许字段（`logo`、`suggestedPrompts`、`author`、`homepage`、`repository`），达成 `agy plugin validate . --strict` **0 错误 / 0 警告 / 0 提示**。
- **跨平台运维与发版工具链**：
  - 新增 `scripts/doctor.py`（一键本地环境、同步状态、运行态文件与 AGY 兼容性体检，支持 `--markdown` / `--json` / `--ci` / `--skip-tests` / `--strict`）。
  - 新增跨平台 `scripts/sync.py`（支持 `--check`、`--clean`、SHA-256 完整性校验与严格运行态白名单隔离），并将 `scripts/sync.sh` 升级为兼容薄包装。
  - 新增 `scripts/release.py`（默认安全 dry-run 预检、版本号更新、纯净运行态 `.zip` 打包及自动 `agy plugin validate` 验包）。
- **本地化运维台账与 GitHub 开源工程化治理**：
  - 建立 `CHANGELOG.md`、`CHANGELOG.zh-CN.md`、`docs/COMPATIBILITY.md`、`docs/BUG_LOG.md`、`docs/RELEASE_PROCESS.md`、`README.zh-CN.md`、`CONTRIBUTING.md` 与 `SECURITY.md`。
  - 新增 GitHub Actions 全矩阵 CI（`.github/workflows/ci.yml`：`ubuntu`/`macos`/`windows` × Python `3.9`–`3.13`）、Tag 自动发版流水线（`.github/workflows/release.yml`）及标准化 Issue / PR 模板。
- **自动化测试大幅扩充**：单测从 9 项扩充至 **25 项**，覆盖 `tests/test_progress_hook.py`、`tests/test_i18n.py`（所有语言包 key 与占位符严格一致）与 `tests/test_repo_integrity.py`（清单白名单、规则字节上限、同步隔离与 Python 3.9 AST 语法守卫）。

### 变更
- `README.md` 升级为英文主文档，顶部提供显眼切换入口指向简体中文完整版 `README.zh-CN.md`。
- 修正环境文档中的 Python 要求从 `3.10+` 改为 `3.9+`，与 macOS 默认 `python3` 实机一致（`BUG-008`）。

### 兼容性
- 完成 Antigravity 桌面端 `2.34.0`、`agy` CLI `1.5.13` 与 macOS 原生 `Python 3.9.6` 的兼容验收（零破坏性不兼容）。
- 补齐 Antigravity `2.34.0` 新增原生工具的多语言标签与参数摘要（`manage_task`、`manage_subagents`、`define_subagent`、`schedule`、`call_mcp_tool`、`list_resources`、`read_resource`、`search_marketplace`、`list_plugin_accounts`）（`BUG-006`）。
- 强化 `Stop` 异常判定：除终止原因枚举外同步检测非空 `payload["error"]` 字段（`BUG-007`）。

---

## [1.0.3] - 2026-11-20

### 新增
- 引入会话级排他文件锁（`fcntl.flock`，非 POSIX 平台安全回退）与临时文件原子替换（`Path.replace`），彻底消除并发 `PostToolUse` 写入覆盖竞态（`BUG-003`）。
- 在 `SessionStart` 阶段增加 14 天过期状态文件（`.json` / `.lock` / `.tmp`）自动清理机制（`BUG-004`）。
- 新增一键同步脚本 `scripts/sync.sh`，集成单元测试校验与 `diff` 一致性核验。
- 扩充并发 `PostToolUse`、超长分块日志与过期文件清理的单元测试。

### 变更
- 将 `transcript.jsonl` 尾部扫描从固定 `24 KB` 升级为 `32 KB` 分块倒序扫描（上限 `512 KB`），避免超长工具输出淹没模型可见进度播报（`BUG-005`）。

---

## [1.0.2] - 2026-11-18

### 修复
- 从 `PreInvocation` 的 `systemMessage` 中移除 `metadata.user_markdown` 字段，规避 Antigravity 上游 Go 后端字段清洗器（`UPSTREAM-002`）导致的整包静默丢弃问题（`BUG-002`）。

### 新增
- 将实时进度展示主通道切换为 `rules/AGENTS.md` 中的模型原生正文流式播报（`Live Inline Progress Narration`）。
- 新增 `transcript.jsonl` 静默检测：连续 3 轮无可见正文输出时注入 `[Progress Reminder]`，第 12 轮起注入 `[Progress Guardian]` 强制收尾（之后每 4 轮重复）。

---

## [1.0.1] - 2026-11-18

### 修复
- 放弃在单回合内持续递增的 `initialNumSteps` 判定（`UPSTREAM-001`），改用 `turn_active` 状态标记 + `lastUserInput` 哈希 + 兼容 protojson `None`/整数/数字字符串的 `invocationNum` 回退检测（`BUG-001`）。

---

## [1.0.0] - 2026-11-18

### 新增
- 初始版本发布，构建 `rules/AGENTS.md` + `skills/milestone-mode/SKILL.md` + `hooks.json` + `hooks/progress_hook.py` 四层插件架构。
- 实现任务复杂度智能阈值分流（短问答直出，多模块任务自动进入分阶段里程碑暂停模式）。
- 实现 macOS 非平凡回合完成桌面通知（采用 `osascript` `on run argv` 安全传参，短对话零打扰）。

[Unreleased]: https://github.com/Embarrassedfisherman/agy-milestone-progress/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/Embarrassedfisherman/agy-milestone-progress/compare/v1.0.3...v1.1.0
[1.0.3]: https://github.com/Embarrassedfisherman/agy-milestone-progress/releases/tag/v1.0.3
[1.0.2]: https://github.com/Embarrassedfisherman/agy-milestone-progress/commits/main
[1.0.1]: https://github.com/Embarrassedfisherman/agy-milestone-progress/commits/main
[1.0.0]: https://github.com/Embarrassedfisherman/agy-milestone-progress/commits/main
