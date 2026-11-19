# Milestone Progress (`milestone-progress`)

面向 **Antigravity 2.0 桌面端** 的全局透明执行与分阶段里程碑插件（当前版本：`v1.0.3`）。

用于解决大型项目任务中「发送提示词后黑盒思考几十分钟、点开全是底层工具指令、无法直观判断实时进展与所处阶段」的问题。

---

## 1. 快速开始（安装与启停）

### 环境要求
- **Antigravity 2.0**
- **Python 3.10+**（仅使用标准库，零第三方依赖）
- **操作系统**：macOS 完整支持（含系统桌面通知）；Linux / Windows 自动跳过桌面通知，其余规则、静默提醒与防跑偏硬刹车功能均可正常使用。

### 一键安装（推荐）

```bash
git clone https://github.com/Embarrassedfisherman/agy-milestone-progress.git
cd agy-milestone-progress
chmod +x ./scripts/sync.sh
./scripts/sync.sh
```

脚本会自动完成以下三步：
1. 运行单元测试套件验证 Hook 逻辑；
2. 将插件核心文件同步到全局目录 `~/.gemini/config/plugins/milestone-progress`（可通过环境变量 `MILESTONE_PLUGIN_DIR` 自定义）；
3. 执行 `diff` 校验确保安装完整（即时生效，无需重启）。

> Windows 用户或手动安装方式：直接将 `plugin.json`、`hooks.json`、`rules/`、`skills/`、`hooks/` 复制到 `~/.gemini/config/plugins/milestone-progress/` 即可。

### 开关与卸载
- **UI 启停**：在 Antigravity 2.0 左侧 **Skills & Customizations -> Plugins** 中找到 **Milestone Progress** 一键开关。
- **CLI 启停**：
  ```bash
  agy plugin disable milestone-progress
  agy plugin enable milestone-progress
  ```
- **彻底卸载**：
  ```bash
  rm -rf ~/.gemini/config/plugins/milestone-progress
  ```

---

## 2. 目录结构与关键路径

- **全局生效安装路径**：`~/.gemini/config/plugins/milestone-progress`
- **运行时状态存储**：`~/.gemini/antigravity/plugin_data/milestone-progress/milestone-progress-state/`
- **完整复盘与避坑文档**：[docs/RETROSPECTIVE.md](./docs/RETROSPECTIVE.md)

```text
agy-milestone-progress/
├── plugin.json                      # 插件元信息（v1.0.3）
├── hooks.json                       # 生命周期 Hook 注册（SessionStart / PostToolUse / PreInvocation / Stop）
├── README.md                        # 使用说明与架构速查（不会同步到插件目录，零上下文开销）
├── LICENSE                          # MIT 开源协议
├── docs/
│   └── RETROSPECTIVE.md             # 需求决策复盘与 Antigravity Hook 底层避坑沉淀
├── rules/
│   └── AGENTS.md                    # 智能阈值分流 + 实时正文中文播报 + 分阶段暂停汇报规则
├── skills/
│   └── milestone-mode/
│       └── SKILL.md                 # /milestone-mode 显式技能定义
├── hooks/
│   └── progress_hook.py             # 静默检测提醒、12轮防跑偏硬刹车与 macOS 桌面通知脚本
├── scripts/
│   └── sync.sh                      # 一键执行单测、同步到全局插件目录并做 diff 校验
└── tests/
    └── test_progress_hook.py        # 单元测试套件（覆盖 protojson、并发锁、大日志回溯、过期清理与通知过滤）
```

---

## 3. 核心工作机制

| 层级 | 组件 | 解决的问题 | 实际表现 |
| :--- | :--- | :--- | :--- |
| **规则层** | [rules/AGENTS.md](./rules/AGENTS.md) | 避免大任务一镜到底盲跑 & 全程躲在 `<thinking>` | 1. **智能分流**：`<= 2` 文件或简单问答直接完成；`>= 3` 文件或跨模块任务进入里程碑模式。<br>2. **实时行内播报**：多步工具调用前直接在正文中输出一行简短中文进度（如 `🧭 正在…`）。<br>3. **单阶段暂停汇报**：先确认计划并维护 `task.md` Artifact；每回合最多执行 1 个子模块，结束输出标准化中文进度卡片等待确认。 |
| **技能层** | [skills/milestone-mode/SKILL.md](./skills/milestone-mode/SKILL.md) | 需要随时手动强制开启严格分阶段控制 | 在聊天框输入 `/milestone-mode` 即可显式激活。 |
| **守护层** | [hooks/progress_hook.py](./hooks/progress_hook.py) (`PreInvocation` + `PostToolUse`) | 防止模型忘记播报或单阶段失控长跑 | 1. **3 轮静默提醒**：倒序分块扫描 `transcript.jsonl`（最多回溯 512KB），若模型连续 `3` 轮只调工具未输出可见正文，自动注入系统提醒促使其下一步播报中文状态。<br>2. **12 轮硬刹车**：单回合连续调用达 `12` 轮（及之后每 `4` 轮）时注入收尾指令，要求安全停下并向用户汇报。 |
| **通知层** | [hooks/progress_hook.py](./hooks/progress_hook.py) (`Stop`) | 执行子模块期间切走窗口，不知道何时停下等确认 | 仅当回合满足非平凡条件（`>= 3` 轮调用、`>= 3` 次工具操作、`>= 15s` 耗时或异常停止，且非 `USER_CANCELED`）时触发 macOS 系统通知；日常短问答零打扰。 |

---

## 4. 常用阈值调整

如需调整灵敏度，编辑 [hooks/progress_hook.py](./hooks/progress_hook.py) 顶部常量后重新运行 `./scripts/sync.sh` 即可生效：

- `SILENT_NUDGE_INTERVAL = 3`：连续多少轮静默工具调用后提醒模型输出正文进度
- `SAFEGUARD_FIRST_INVOCATION = 12`：单回合首次触发“防跑偏收尾汇报”的轮数阈值
- `SAFEGUARD_REPEAT_INTERVAL = 4`：首次触发后每隔多少轮再次提醒
- `NOTIFY_MIN_INVOCATIONS = 3` / `NOTIFY_MIN_TOOLS = 3` / `NOTIFY_MIN_ELAPSED_SEC = 15.0`：触发 macOS 桌面通知的最低门槛

---

## 5. 开发与测试指令

1. **运行单元测试**
   ```bash
   python3 tests/test_progress_hook.py -v
   ```

2. **一键测试并同步至全局插件目录**
   ```bash
   ./scripts/sync.sh
   ```
