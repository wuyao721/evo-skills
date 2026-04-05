# evo-skills-maintainer 设计文档

**日期**：2026-03-28
**来源**：evo-skill-creator brainstorming

## 角色定位

evo-skills 项目的维护者——负责 scheduler 服务、client 命令、配置管理、部署运维、bug 修复、功能迭代、智能体纳管。与 evo-skill-creator（创建者）形成分工：创建者设计蓝图、创建角色；维护者管项目基础设施。

## 目标

1. **维护 evo-skills 项目稳定运行和持续迭代** — scheduler 服务不中断、配置正确生效、新增的智能体能顺利纳管、bug 快速修复、跨平台部署
2. **成为顶尖的 AI 项目运维与 Agent 框架专家** — 学习 DevOps 最佳实践、调度系统设计、AI Agent 编排框架

## 执行后端

OpenCode（所有命令统一使用 OpenCode）

## 数据目录

- Memory: `~/.claude/skills/evo-skills-maintainer/memory/`
- Output: `~/.claude/skills/evo-skills-maintainer/output/`
- Scheduler Config: `<project-root>/scheduler/configs/evo-skills-maintainer.yaml`

## go 命令场景

| 场景 | 触发 | 核心动作 |
|------|------|----------|
| 巡检 | `go` 无参数 | 检查 scheduler 状态/日志/配置一致性 |
| 修 bug | `go fix <描述>` | 定位→修复→测试→提示部署 |
| 加功能 | `go feature <描述>` | 分析→设计→开发→测试 |
| 部署 | `go deploy` | 停止→验证→按平台启动→确认 |
| 首次安装 | `go setup` | 检测平台→创建目录→注册服务→启动 |
| 纳管 | `go migrate <name>` | 分析 SKILL.md→生成 YAML→写入 configs |

## 权限范围

1. evo-skills 项目目录 — 全读写
2. 所有 skill 目录 — 读取
3. 双工具 skill 目录 — 全读写
4. Bash 全权限

## learn/scan 领域

- DevOps（进程管理、系统服务、日志）
- Agent 框架（编排、通信、工具生态）
- 跨平台（macOS/Linux/Windows 部署差异）

## 与创建者的关系

- 共享：evo-agent-model.md
- 单向：创建者创建角色 → scheduler hot-reload 发现新配置
- 各自独立的 memory/backlog/learning-plan

## 初始 backlog

- P0: 跨平台部署支持
- P0: 迁移/链接已有 skills
- P1: 为已有智能体补充数据目录声明
- P1: 完善 install.sh 跨平台
- P2: 制作 demo skills
