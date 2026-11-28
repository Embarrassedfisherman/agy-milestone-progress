# Milestone Progress (`milestone-progress`)

[English](./README.md) | **简体中文**

[![Status: Archived](https://img.shields.io/badge/Status-Archived-6B7280.svg)](#项目已光荣归档推荐全面回归-antigravity-原生能力)
[![CI](https://github.com/Embarrassedfisherman/agy-milestone-progress/actions/workflows/ci.yml/badge.svg)](https://github.com/Embarrassedfisherman/agy-milestone-progress/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-3776AB.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/Final%20Version-1.2.1-10B981.svg)](./CHANGELOG.zh-CN.md)

> [!NOTE]
> ### 项目已光荣归档：推荐全面回归 Antigravity 原生能力
>
> **归档日期：2026-11-28（终版验证：`v1.2.1` on Antigravity `2.36.0`）**
>
> 本项目已圆满完成历史使命并转为只读归档。随着 Antigravity 客户端（`2.34`–`2.36`）密集演进，官方已原生补齐核心进度可视化、步骤清单、规划工作流与桌面提醒能力；回归原生可免除每次工具调用的同步 Hook 进程开销与常驻规则上下文占用。
>
> | 原插件能力 | 推荐使用的 Antigravity 原生能力 |
> | :--- | :--- |
> | 折叠态实时进展与步骤播报 | 原生 `update_focus` + `update_steps` 步骤完成摘要 |
> | 任务进度清单（`task.md`） | 官方原生 **Checklists**（`update_steps`） |
> | 先出方案确认与需求对齐 | 内置 `/plan` 与 `/grill-me` 命令 |
> | 长程执行与多 Agent 协作 | 内置 `/goal`、`/teamwork`、`/swarm`、`/boost` 及 `2.36.0` 自动续跑 |
> | 切窗完成系统通知 | 客户端原生 **Settings → Notifications** |
>
> 本仓库将永久保留作为 **Antigravity Lifecycle Hooks**、跨平台 Python (`3.9+`) 文件锁（`fcntl` / `msvcrt`）、多语言一致性测试与 `agy plugin validate --strict` 工程化打包的开源参考范本（详见 [docs/RETROSPECTIVE.md](./docs/RETROSPECTIVE.md) 与 [docs/BUG_LOG.md](./docs/BUG_LOG.md)）。

---

面向 **Google Antigravity（AGY）** 的**原生优先、增量增强型**分阶段里程碑控场与桌面通知插件（终版：`v1.2.1`）。本插件以 AGY 官方原生能力（Checklists / `update_steps`、`update_focus`、`/plan`、`/goal`）为第一优先级，仅在其上做加法与补充，并原生支持**多语言自动适配**（规则层自动跟随任意对话语言，Hook 内置 `en` / `zh` / `ja` 语言包并支持轻松扩展）。

用于解决大型项目任务中「黑盒思考很久、缺少阶段验收刹车与切窗完成提醒」的核心痛点，同时在用户使用 `/goal` 或明确要求连续跑完时自动退让给官方原生 Checklists，不强行中断。

---

## 1. 快速开始（安装与升级）

### 环境要求
- **Antigravity 2.x**（终版已实测桌面端 `2.36.0` & `agy` CLI `1.5.13`，详见 [兼容性矩阵](./docs/COMPATIBILITY.md)）
- **Python 3.9+**（仅使用标准库，零第三方依赖，直接兼容 macOS 自带 `python3`）
- **操作系统**：
  - **macOS**：完整支持（含 `osascript` 系统桌面通知）
  - **Linux**：核心功能完整支持；系统安装 `notify-send` 时自动支持桌面通知
  - **Windows**：核心功能完整支持（自动跳过桌面通知；请确保 `PATH` 中的 `python3` 指向真实 Python 3.9+）

### 方式 A：源码一键安装与更新（推荐）

```bash
git clone https://github.com/Embarrassedfisherman/agy-milestone-progress.git
cd agy-milestone-progress
python3 scripts/sync.py --clean
```

*（macOS / Linux 也可继续运行 `./scripts/sync.sh --clean`，底层已统一委托给跨平台 `sync.py`。）*

脚本会自动完成四步：
1. 运行全部单元测试（含多语言一致性与仓库合规守护）；
2. 自动调用 `agy plugin validate --strict` 校验插件规范（若已安装 `agy`）；
3. **仅将运行态插件文件**同步到 `~/.gemini/config/plugins/milestone-progress`（可通过 `--target` 或环境变量 `MILESTONE_PLUGIN_DIR` 自定义），运维文档与测试文件不会污染运行态目录；
4. 对每个同步文件进行 SHA-256 哈希校验（即时生效，无需重启）。

后续升级只需 `git pull` 后重新执行 `python3 scripts/sync.py --clean`，用户在 `$PLUGIN_DATA/config.json` 中的个人配置会自动保留、绝不覆盖。

### 方式 B：从 GitHub Releases 下载 `.zip` 安装

前往 [GitHub Releases](https://github.com/Embarrassedfisherman/agy-milestone-progress/releases) 下载 `milestone-progress-vX.Y.Z.zip`，直接解压至：

```text
~/.gemini/config/plugins/milestone-progress/
```

### 启停与卸载
- **桌面端 UI**：在左侧 **Skills & Customizations → Plugins** 中找到 **Milestone Progress** 一键开关。
- **CLI 命令**：
  ```bash
  agy plugin disable milestone-progress
  agy plugin enable milestone-progress
  ```
- **彻底卸载**：
  ```bash
  rm -rf ~/.gemini/config/plugins/milestone-progress
  ```

---

## 2. 核心四层协同机制

| 层级 | 组件 | 解决的问题 | 实际表现 |
| :--- | :--- | :--- | :--- |
| **规则层** | [rules/AGENTS.md](./rules/AGENTS.md) | 原生优先分流 & 增量式阶段验收控制 | 1. **官方原生优先**：将 AGY 原生 `update_steps` 清单、`update_focus`、`/plan`、`/goal`、`/teamwork` 作为第一优先级；用户要求连续执行或使用 `/goal` 时自动退让，不强行中途刹车。<br>2. **语言自适应与智能分流**：自动匹配对话语言；`<= 2` 文件或简单问答直接完成，`>= 3` 文件或跨模块任务默认进入里程碑模式。<br>3. **单阶段暂停汇报**：每回合最多执行 1 个子模块，结束输出 5 项标准进度卡片等待确认。 |
| **技能层** | [skills/milestone-mode/SKILL.md](./skills/milestone-mode/SKILL.md) | 需要随时手动强制开启严格分阶段控制 | 在聊天框输入 `/milestone-mode` 即可显式激活，在原生 `update_steps` / `update_focus` 之上叠加每回合 1 里程碑确认节奏。 |
| **守护层** | [hooks/progress_hook.py](./hooks/progress_hook.py)、[hooks/i18n.py](./hooks/i18n.py)、[hooks/locales/](./hooks/locales/) | 防止模型黑盒盲跑或单阶段失控死循环 | 1. **原生感知静默提醒**：识别 `update_focus` / `update_steps` 为有效进度同步（不与官方 UI 冲突），并倒序分块扫描 `transcript.jsonl`（上限 `512 KB`）；连续 `3` 轮既无正文又无原生进度更新时注入本地化 `[Progress Reminder]`。<br>2. **协同式 12 轮护栏**：单回合连续调用达 `12` 轮（之后每 `4` 轮）时注入 `[Progress Guardian]`，提示同步原生 `update_steps` 并在非连续执行模式下安全收尾汇报。 |
| **通知层** | [hooks/progress_hook.py](./hooks/progress_hook.py) (`Stop`) | 切走窗口时第一时间获悉真实阶段进度 | 自动读取本回合最新 `update_steps` 快照，桌面通知直接显示步数与已完成步骤（如 `⏸️ 阶段完成 (2/4 步)` + `已完成「...」`）；仅在非平凡回合或出错暂停时弹出，短问答零打扰。 |

---

## 3. 多语言策略与持久化用户配置

### 语言解析优先级
1. 环境变量 `MILESTONE_PROGRESS_LANG`（如 `zh`、`en`、`ja`）
2. 持久化配置文件 `$PLUGIN_DATA/config.json` 中的 `language` 字段
3. **自动识别模式**（`"auto"`，默认）：根据用户输入脚本特征自动判断（含假名→日语、含汉字→中文、其余文本→英文），并在会话状态中持久化记忆，确保 `Stop` 通知语言与对话完全一致；空输入时回退系统 `LANG` / 英文。

### 持久化自定义配置（升级不丢失）
无需修改插件源码，直接创建或编辑以下可选配置文件即可覆盖任意阈值与语言偏好：

```text
~/.gemini/antigravity/plugin_data/milestone-progress/config.json
```

所有字段均可选，非法值会自动安全回退到默认值：

```json
{
  "language": "auto",
  "silent_nudge_interval": 3,
  "safeguard_first_invocation": 12,
  "safeguard_repeat_interval": 4,
  "notify_enabled": true,
  "notify_min_invocations": 3,
  "notify_min_tools": 3,
  "notify_min_elapsed_sec": 15.0,
  "state_retention_days": 14
}
```

---

## 4. 本地化运维台账与文档导航

运维文档仅保留在源码仓库中，**不会**同步到全局插件目录，零运行时与上下文开销：

- **版本更新日志**：[CHANGELOG.zh-CN.md](./CHANGELOG.zh-CN.md) | [CHANGELOG.md](./CHANGELOG.md)
- **AGY 兼容性矩阵**：[docs/COMPATIBILITY.md](./docs/COMPATIBILITY.md)
- **Bug 与上游避坑台账**：[docs/BUG_LOG.md](./docs/BUG_LOG.md)
- **高频迭代发版 SOP**：[docs/RELEASE_PROCESS.md](./docs/RELEASE_PROCESS.md)
- **历史架构复盘**：[docs/RETROSPECTIVE.md](./docs/RETROSPECTIVE.md)
- **贡献指南与安全策略**：[CONTRIBUTING.md](./CONTRIBUTING.md) | [SECURITY.md](./SECURITY.md)

---

## 5. 常用开发、体检与发版命令

```bash
# 运行全部 31 项单元测试（Hook、多语言一致性、仓库完整性与 Python 3.9 语法守卫）
python3 -m unittest discover -s tests -v

# 一键体检本地环境、同步状态与 AGY 兼容性
python3 scripts/doctor.py --with-tests
python3 scripts/doctor.py --markdown

# 使用 AGY 官方校验器严格检查插件
agy plugin validate . --strict

# 跨平台一键测试、校验并同步至全局插件目录
python3 scripts/sync.py --clean

# 发版预检与纯净运行态 zip 打包（默认 dry-run 安全模式）
python3 scripts/release.py --package
```

---

## 6. 参与贡献与开源协议

欢迎提交 Issue、Antigravity 客户端升级兼容性报告或新增语种语言包！详见 [CONTRIBUTING.md](./CONTRIBUTING.md)。

本项目基于 [MIT License](./LICENSE) 开源。
