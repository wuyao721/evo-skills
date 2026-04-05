# 智能体注册表

> 记录所有纳管到 evo-skills 项目的智能体

## 已注册智能体

### evo-skill-creator

- **角色**：能力创建者（核心 skill）
- **目标**：创建具有自我学习、持续进化能力的领域专家智能体 Skill
- **执行后端**：Claude Code
- **数据目录**：
  - Memory: `~/.claude/skills/evo-skill-creator/memory/`
  - Output: `~/.claude/skills/evo-skill-creator/output/`
- **调度配置**：`scheduler/configs/evo-skill-creator.yaml`
- **状态**：活跃

---

## 注册流程

1. 创建智能体 SKILL.md（通过 /evo-skill-creator）
2. 生成 scheduler 配置文件（`scheduler/configs/<name>.yaml`）
3. 在此文件注册基本信息
4. 测试调度执行
5. 标记为"活跃"状态
