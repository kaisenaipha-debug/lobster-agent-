---
name: gov-sales-pipeline
description: "Government B2G sales pipeline orchestrator + 情报专家。 Activates when user describes any situation related to government sales: first visit preparation, post-meeting reflection, client tracking, or deal stage analysis. Automatically routes to the correct sub-skill (gov-intel / intelligence-gather / meeting-debrief / client-stage-tracker / weak-signal-monitor) and connects them into one continuous workflow. No trigger words needed - natural language only."
metadata:
  intelligence_expert: true
  捆绑skill: intelligence-gather
  sub_skills:
    - intelligence-gather
    - gov-intel
    - meeting-debrief
    - client-stage-tracker
    - weak-signal-monitor
---

# gov-sales-pipeline

政府 B2G 销售全流程编排器。

## 设计原则

**不需要记触发词。** 用户用自然语言描述情况，系统判断该启动哪个模块、串联哪些步骤。

---

## 自然语言 → 模块路由

根据用户输入的**意图**，自动路由到对应模块：

### 场景 A：准备见一个政府部门

**信号词（任意一个）：**
「第一次见」「准备拜访」「要去见」「冷情报」「还没见过」「拜访前」「去见他之前」「见面准备」「见局长之前」「查一下」「收集」「竞争对手」「背景调查」

→ **优先触发 `intelligence-gather`**（情报收集）
  - 当用户提供具体单位/公司名称时，立即执行情报收集流程
  - 同时并线执行 `gov-intel` 完整冷情报流程（Step 1-5）
  - 若只提供部门/城市，无具体单位名 → 仅执行 `gov-intel` 五步搜索
→ 询问：计划拜访时间（补充时机判断）

---

### 场景 B2：情报收集（情报专家专属入口）

**信号词（任意一个）：**
「查一下」「收集」「竞争对手」「背景调查」「这个单位」「这家公司」「了解一下」

→ 触发 `intelligence-gather` 情报收集流程
  - 提取单位/公司名称 → 搜索公开情报 → 生成报告 → 保存到情报库
  - 情报库路径：`memory/intelligence/[公司名].md`
  - 若同时提供多个单位 → 并行收集，汇总对比表
  - 收集完成后可追加：「顺便查一下竞品」「看看有没有风险」

→ **情报专家 + gov-sales-pipeline 联动：**
  - 情报收集完成后 → 自动询问：「这个客户跟政府销售有关吗？」
  - 若有关 → 路由到 gov-intel 补充五步冷情报
  - 若无关 → 仅输出商业情报报告，标注：「与政府采购无关，已归档」

---

### 场景 B：刚见完客户，描述了对话内容

**信号词（任意一个）：**
「刚见了」「今天见了」「复盘」「见面后」「谈完了」「跟他聊了」「他说了」「他问我」「反馈」「 debrief」

→ 自动执行 `meeting-debrief` 完整复盘流程（Step 1-4）
→ 复盘完成后，自动执行 `client-stage-tracker` 推进阶段
→ 若置信度下降 >10%，发出🚨预警

---

### 场景 C：询问客户当前在哪个阶段

**信号词（任意一个）：**
「现在到什么阶段了」「客户阶段」「推进到哪了」「卡在哪了」「阶段」「进展到哪」「S0」「S1」「S2」「S3」「S4」「S5」

→ 触发 `client-stage-tracker`
→ 先用 `memory_search` 查找该客户档案
→ 若有记录：输出阶段 + 最高价值动作 + 48h下一步
→ 若无记录：根据描述判断所处阶段（首次自动建档）

---

### 场景 D：开始监控一个客户

**信号词（任意一个）：**
「帮我监控」「持续跟踪」「盯着」「不要错过」「设个提醒」「自动通知」「监控」

→ 自动执行 `weak-signal-monitor` 启动监控
→ 询问：客户名 + 城市 + 部门（如未提供）
→ **自动并线触发 `intelligence-gather`**：对该客户做一次深度背景扫描，补充到档案

---

### 场景 E：weak-signal-monitor 发现触发事件

**这是 cron 触发**，不是用户说的。当 cron agent 发现触发事件时：

1. 用 `memory_search` 查找该客户的当前阶段（从最近一次复盘记录）
2. 调取 `client-stage-tracker` 当前阶段的推荐动作
3. 生成预警推送，格式：

```
【信号预警】[客户名] · S[阶段]

发现：[触发事件描述]
来源：[信息链接]

📍 当前阶段：S[数字] · [阶段名]
🎯 现在最应该做的一件事：[结合信号 + 阶段的具体动作]
⏰ 时间窗口：[紧急<7天 / 还有时间>30天]
建议：[48小时内应该做什么]
```

---

## 串联规则（模块间自动连接）

### intelligence-gather → 任意模块

情报收集完成后，根据用户场景自动路由：
- 用户提到政府客户 → 接入 gov-intel 五步冷情报
- 用户提到刚见完面 → 接入 meeting-debrief 复盘
- 用户要求监控 → 接入 weak-signal-monitor
- 情报库永久存档：`memory/intelligence/[公司名].md`

### gov-intel → meeting-debrief

完成冷情报后，自动告知用户：
> 「如果后续见到他，把对话内容发给我，我帮你复盘并推进阶段。」

并在 memory 档案中标注：
```markdown
## 下一步
- [城市][部门] → 等待首次见面
- 见面后触发：复盘：[客户名] + [对话内容]
```

---

### meeting-debrief → client-stage-tracker

复盘完成后，自动执行阶段推进：

1. 根据复盘结论，判断是否需要推进阶段
2. 在 memory 档案中更新阶段历史
3. 若置信度下降 >10%，触发🚨预警推送

---

### weak-signal-monitor → client-stage-tracker

信号触发时，从 memory 档案中读取：
- 当前阶段
- 上次复盘的关键洞察
- 置信度

结合信号类型 + 当前阶段，生成**有针对性的**建议，而不是通用建议。

---

## 统一客户档案格式

所有模块共享同一个客户档案：`memory/YYYY-MM-DD-client-[客户名].md`

```markdown
# [客户名] · [城市][部门] · 全链路档案

## 基础信息
- 客户：[客户名]
- 部门：[部门]
- 城市：[城市]
- 创建日期：[日期]
- 当前阶段：S[0-5] · [阶段名]（更新时间）

## 冷情报摘要（来自 gov-intel）
- 考核压力：___
- 预算信号：___
- 竞争态势：___
- 领导关键词：___
- 同类案例：___

## 会面复盘历史（来自 meeting-debrief）
### [日期] S[X]→S[Y]
- 行为矛盾：___
- 真实顾虑：___
- 新影响者：___
- 置信度：[X]%（+/-Y%）
- 下次要问：___

## 阶段历史
- S0 [日期] 线索发现
- S1 [日期] 准备拜访
- S2 [日期] 首次见面
- S3 [日期] 挖掘需求
- S4 [日期] 方案推进
- S5 [日期] 临门一脚

## 监控状态（来自 weak-signal-monitor）
- 状态：[监控中/已停止]
- Job ID：[ID]
- 最近信号：[日期] [描述/无异常]
```

---

## 置信度基准规则

| 阶段 | 初始置信度 | 说明 |
|---|---|---|
| S0 | 30% | 仅线索，未验证 |
| S1 | 40% | 准备拜访，情报支撑 |
| S2 | 50% | 首次见面，有直接反馈 |
| S3 | 60% | 真实需求已确认 |
| S4 | 70% | 方案认可，进入采购 |
| S5 | 80% | 接近签约 |

**下调条件：** 置信度持续低于基准 → 进入预警模式
**上调条件：** 每次正向会面后 +5%，连续2次 +10%

---

## 验收标准自检

| 标准 | 检查方式 |
|---|---|
| 说「去见上海市教育局」，自动跑完5个搜索 | gov-intel Step 1 四方向并发搜索 |
| 说「复盘+对话」，自动更新档案推进阶段 | meeting-debrief + client-stage-tracker 串联 |
| 后台监控，发现触发事件主动通知 | weak-signal-monitor cron job |
| 全程自然语言，不需要记触发词 | 靠场景路由，不是关键词匹配 |
