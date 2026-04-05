# OpenCode 免费模型动态维护 Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把 `evo-skill-creator` 中会变化的 OpenCode 免费模型信息从 `SKILL.md` 挪到 memory/周期学习机制里，并建立“扫描 -> 学习 -> 评审 -> 报告/提醒”的动态维护闭环。

**Architecture:** `SKILL.md` 只保留稳定的方法论和流程，不再硬编码当前免费模型名单。动态信息进入 `memory/knowledge/ai-models/`、`learning-plan.md`、`watchlist.md` 和周期性报告，由 `scan` 负责发现变化，`learn` 负责深入比较，`review` 负责更新推荐策略与框架设计。

**Tech Stack:** Markdown knowledge base, `opencode models` CLI, WebSearch, evo-skills scheduler YAML

---

### Task 1: 清理 SKILL 中的动态模型名单

**Files:**
- Modify: `skills/evo-skill-creator/SKILL.md`
- Modify: `skills/evo-skill-creator/references/evo-agent-model.md`

**Step 1: 删除 `SKILL.md` 中当前写死的 OpenCode 模型名单**

把 `opencode/minimax-m2.5-free`、`opencode/mimo-v2-pro-free`、`opencode/nemotron-3-super-free`、`opencode/mimo-v2-omni-free` 这些具体模型 ID 从创建流程中移除。

**Step 2: 保留稳定原则**

在 `SKILL.md` 中仅保留：
- 如果用户选择 `OpenCode`，需要进一步确认模型策略
- 当前可用模型清单应通过本地命令和周期学习动态获取
- 推荐路由以 memory 中最新知识为准

**Step 3: 同步通用模型**

在 `references/evo-agent-model.md` 中也改成同样原则，避免通用模型再次硬编码当前名单。

**Step 4: 自查**

确认 `SKILL.md` 和 `evo-agent-model.md` 都只保留“怎么决策”，不保留“当前有哪些免费模型”的易变事实。

### Task 2: 建立动态模型知识分层

**Files:**
- Modify: `skills/evo-skill-creator/memory/knowledge/ai-models/opencode-free-model-routing.md`
- Create or Modify: `skills/evo-skill-creator/memory/knowledge/ai-models/opencode-model-inventory.md`
- Create or Modify: `skills/evo-skill-creator/memory/watchlist.md`

**Step 1: 拆分“稳定路由”与“动态库存”**

将现有知识拆成两类：
- `opencode-free-model-routing.md`：保留相对稳定的路由思想与评估维度
- `opencode-model-inventory.md`：记录当前通过 `opencode models` 和外部扫描得到的模型清单、时间戳、是否免费、备注

**Step 2: 设计 inventory 结构**

建议字段：
- 更新时间
- 获取方式（`opencode models` / WebSearch / 官方说明）
- 当前模型列表
- 疑似新增模型
- 疑似失效模型
- 待进一步学习项

**Step 3: watchlist 记录变化线索**

在 `watchlist.md` 中专门增加一个主题：`OpenCode 免费模型与免费策略变化`，用于放扫描时发现但尚未学透的线索。

### Task 3: 把“免费模型周检”加入学习计划

**Files:**
- Modify: `skills/evo-skill-creator/memory/learning-plan.md`

**Step 1: 新增周期性学习项**

新增一个明确的计划项，例如：
- `OpenCode 免费模型周检与推荐更新（P1）`

**Step 2: 写清节奏**

计划项中明确：
- 每周至少扫描一次当前免费模型是否变化
- 扫描后若有新增/变化，则安排一次学习
- 学习后更新 inventory、routing 建议、相关报告

**Step 3: 写清学习问题**

至少包含：
- 本周 `opencode models` 是否出现新增模型
- 是否有模型变成免费或取消免费
- 当前推荐是否需要调整
- 是否需要提醒老板关注工具升级或模型变化

### Task 4: 重新定义 scan / learn / review 的分工

**Files:**
- Modify: `skills/evo-skill-creator/SKILL.md`
- Modify: `skills/evo-skill-creator/references/evo-agent-model.md`

**Step 1: scan 负责“发现变化”**

scan 中增加一个固定子流程：
- 运行 `opencode models`
- 扫描新闻/官方信息/相关资料
- 对比 inventory 是否变化
- 将变化写入 `watchlist.md` 和 scan 报告

**Step 2: learn 负责“深入比较”**

learn 不再只泛泛地学 Agent/Skill 设计，也负责在发现新免费模型后：
- 补充模型定位
- 判断适合哪些命令
- 更新 routing 知识

**Step 3: review 负责“刷新推荐”**

review 负责从框架角度看：
- 当前推荐路由是否还合理
- 当前 scheduler 设计是否需要跟随调整
- 是否要把新模型引入某些命令的默认策略

### Task 5: 设计报告与提醒机制

**Files:**
- Modify: `skills/evo-skill-creator/SKILL.md`
- Modify: `skills/evo-skill-creator/output/report/` 下相关报告模板或说明文档（如需要）

**Step 1: scan 报告体现“是否有变化”**

每次模型周检扫描报告至少输出：
- 当前本地 `opencode models` 清单
- 与上次相比的变化
- 是否发现新的免费模型线索

**Step 2: learn 报告体现“是否值得采用”**

学习报告至少输出：
- 新模型/变化模型的定位
- 对 `go/learn/scan/plan/review/suggest/status` 的适配判断
- 是否建议修改默认推荐

**Step 3: review 报告体现“是否提醒老板”**

如果发现值得关注的变化，review 报告中应明确：
- 是否建议提醒老板
- 是否建议升级 opencode
- 是否建议调整某角色的默认模型

### Task 6: 规划 scheduler 后续演进

**Files:**
- Modify: `skills/evo-skill-creator/memory/backlog.md`
- Modify: `skills/evo-skill-creator/references/evo-agent-model.md`
- Reference: `scheduler/configs/evo-skill-creator.yaml`

**Step 1: 确认命令级配置方向**

继续坚持这条方向：
- `agent` 级默认 `executor/model/tools`
- `schedules` 级命令覆盖 `executor/model/tools`

**Step 2: 明确当前过渡方案**

在 scheduler 代码尚未升级前：
- 不把动态模型名单写死到配置策略说明里
- 只保留“默认模型 + memory 中最新推荐”的方式

**Step 3: 预留自动化扩展**

后续可以增加：
- scan 前先执行 `opencode models`
- 必要时检测是否需要升级 opencode
- 但自动升级本身应默认要求老板确认，不建议一开始全自动

### Task 7: 验证与收尾

**Files:**
- Review: `skills/evo-skill-creator/SKILL.md`
- Review: `skills/evo-skill-creator/references/evo-agent-model.md`
- Review: `skills/evo-skill-creator/memory/learning-plan.md`
- Review: `skills/evo-skill-creator/memory/knowledge/ai-models/*.md`
- Review: `skills/evo-skill-creator/memory/backlog.md`

**Step 1: 一致性检查**

确认以下边界清晰：
- `SKILL.md` 只写稳定流程
- memory 写动态知识
- reports 写当次发现与建议

**Step 2: 周期闭环检查**

确认已经形成：
- 周扫描
- 变化后学习
- review 刷新推荐
- 报告提醒老板

**Step 3: 调度策略检查**

确认未来实现 scheduler 命令级 `executor/model/tools` 覆盖时，不需要再回头大改 `evo-skill-creator` 的方法论描述。
