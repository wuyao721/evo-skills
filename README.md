# evo-skills

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

自我进化智能体生态系统。

让 AI Agent 不只是执行任务，还能自主学习、持续进化。每个 skill 都内置 learn、scan、plan、review、cron 等自进化命令，配合 evo-skills-scheduler 调度服务在后台持续进化——学习新知识、扫描新趋势、自省改进。

## 为什么做这个项目

现有的 AI Agent 框架大多关注"执行任务"，但忽略了一个关键问题：**Agent 的知识和能力如何持续更新？**

evo-skills 的核心理念是：
- Agent 应该能**自主学习**，而不是只靠人类更新 prompt
- Agent 应该有**记忆系统**，积累经验而不是每次从零开始
- Agent 应该能**自省改进**，发现自己的不足并主动弥补
- 这一切应该是**自动化的**，通过定时调度在后台静默进行

## 快速开始

```bash
# 安装（注册为系统服务 + 客户端命令到 PATH）
cd scheduler
bash install.sh

# 查看状态
evo-skills-client status

# 查看某个角色的调度配置
evo-skills-client config evo-skill-creator

# 查看唤醒历史
evo-skills-client history evo-skill-creator

# 卸载
bash uninstall.sh
```

## 项目结构

```
evo-skills/
├── scheduler/                     # 调度服务
│   ├── evo_skills_scheduler.py    # 调度服务主程序（纯 Python 标准库，零依赖）
│   ├── evo-skills-client          # 客户端命令
│   ├── evo-skills-cd              # 快速跳转到角色目录
│   ├── configs/                   # 各智能体的调度配置（YAML）
│   │   └── example.yaml           # 配置示例
│   ├── install.sh                 # 安装（支持 macOS launchd / Linux systemd）
│   └── uninstall.sh               # 卸载
├── skills/                        # 自我进化智能体
│   └── evo-skill-creator/         # 创建者（核心 skill，用于创建新的自进化智能体）
└── docs/                          # 文档
```

## 核心概念

- **八大命令**：go / learn / scan / plan / review / suggest / cron / status
- **scheduler**：后台服务，按 cron 表达式定期唤醒各智能体执行自进化任务
- **同角色不并发**：同一个智能体同一时间只能运行一个任务
- **自进化闭环**：plan → learn/scan → 沉淀 memory → 应用到 go → 发现盲点 → 更新 plan
- **零依赖**：scheduler 纯 Python 标准库实现，自带 YAML 解析器和 cron 解析器
- **跨平台**：支持 macOS (launchd) 和 Linux (systemd)

## 用例：创建一个家庭医生角色

以下演示如何用 evo-skill-creator 创建一个自我进化的"家庭医生"智能体。

### 第一步：用一句话创建角色

在 Claude Code 中执行：

```
/evo-skill-creator go 帮我创建一个家庭医生的角色
```

evo-skill-creator 会和你对话，确认角色定位、目标、核心能力等，然后自动生成完整的 skill 目录。

### 第二步：查看生成的结果

创建完成后，你会在 `~/.claude/skills/family-doctor/` 下得到：

```
family-doctor/
├── SKILL.md                      # 角色指令（AI 读取的核心文件）
├── .claude/settings.local.json   # 权限配置
├── references/                   # 参考资料
│   └── evo-agent-model.md        # 自进化模型蓝图
└── memory/                       # 记忆系统
    ├── scene-index.md            # 场景索引（按需加载，避免上下文爆炸）
    ├── learning-plan.md          # 学习计划（自动更新）
    ├── knowledge/                # 知识库（learn/scan 自动积累）
    ├── scenario-sops/            # 各命令的 SOP
    └── private/                  # 个人数据（健康档案等）
```

### 第三步：使用你的家庭医生

```
# 健康咨询
/family-doctor go 最近总是头疼，怎么回事

# 让它自主学习最新医学知识
/family-doctor learn 学习一下偏头痛的最新治疗方法

# 查看它学了什么
/family-doctor status
```

### 第四步：配置自动进化

将 `scheduler/configs/example.yaml` 复制为 `family-doctor.yaml`，配置定时任务：

```yaml
agent:
  name: family-doctor
  executor: claude

schedules:
  - command: learn
    cron: "0 14 * * *"
    description: "每天下午深度学习"
  - command: scan
    cron: "0 10 * * *"
    description: "每天上午扫描医学动态"
  - command: review
    cron: "0 17 * * 5"
    description: "每周五自省评审"
```

之后 scheduler 会在后台自动唤醒家庭医生执行学习、扫描和自省，知识库持续增长，越用越强。

## 支持的执行后端

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (Anthropic)
- [OpenCode](https://github.com/opencode-ai/opencode)

## License

MIT
