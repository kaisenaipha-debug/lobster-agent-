---
name: weak-signal-monitor
description: "Government B2G weak signal monitor for early-mover advantage. Trigger: when user says '监控：[客户名]' to start continuous monitoring of a government client. Automatically runs daily searches for leadership changes, procurement notices, policy shifts, and competitor activity. Sends WeChat notification immediately when trigger events are detected. Also triggered by '停止监控：[客户名]' to cancel monitoring."
---

# weak-signal-monitor

政府 B2G 弱信号监控器。捕捉窗口期，不错过最佳行动时机。

## 触发

```
监控：[客户名] + [城市] + [部门]
```

例如：`监控：上海市教育局 + 上海 + 教育局`

---

## 启动流程

### 第一步：确认客户信息

如果用户没有提供城市+部门，AI 必须追问：
> 「请告诉我这个客户所在的[城市]和[部门]，我才能设置监控。」

### 第二步：查询现有档案

用 `memory_search` 搜索该客户是否已有记录：
- 若有：调出城市、部门、历史阶段等关键信息
- 若无：直接使用用户提供的信息

### 第三步：创建每日监控 cron job

使用 `cron` 工具创建每日定时任务：

```json
{
  "name": "[客户名]弱信号监控",
  "schedule": {
    "kind": "cron",
    "expr": "0 8 * * *",
    "tz": "Asia/Shanghai"
  },
  "payload": {
    "kind": "agentTurn",
    "message": "执行弱信号监控任务：\n客户：[客户名]\n城市：[城市]\n部门：[部门]\n检查以下触发事件是否发生：\n1. 领导换届或调整\n2. 新的专项资金下拨通知\n3. 相关领域的上级检查通知\n4. 竞争对手中标公告\n5. 部门发布新的采购需求\n\n如发现任何触发事件，立即通过 message 工具发送微信预警通知（channel=wecom 或对应配置渠道）。\n如无异常，不发送任何消息。\n\n完成后将本次监控结果写入 memory/weak-signal-YYYY-MM-DD.md"
  },
  "delivery": {
    "mode": "announce"
  },
  "sessionTarget": "isolated",
  "enabled": true
}
```

**注意：**
- cron expression `0 8 * * *` = 每天早上 8:00 执行（上海时区）
- `sessionTarget` 必须为 `"isolated"`，不能用 `"main"`
- `payload.kind` 必须为 `"agentTurn"`，不能用 `"systemEvent"`

### 第四步：记录监控状态

将以下内容写入 `memory/weak-signal-[客户名].md`：

```markdown
# [客户名] 弱信号监控 · 创建于 [日期]

## 监控对象
- 客户：[客户名]
- 城市：[城市]
- 部门：[部门]
- 状态：✅ 监控中

## 触发事件列表
1. 领导换届或调整
2. 新的专项资金下拨通知
3. 相关领域的上级检查通知
4. 竞争对手中标公告
5. 部门发布新的采购需求

## 监控 cron
- Job ID：[来自 cron add 的返回结果]
- 执行时间：每天 08:00（上海时区）

## 最近一次检查：[日期] — 无异常/发现信号
```

### 第五步：告知用户

```
✅ 监控已启动：[客户名] · [城市][部门]
每日自动检查：每天 08:00（上海时区）
监控触发事件：
  1. 领导换届或调整
  2. 专项资金下拨通知
  3. 上级检查通知
  4. 竞争对手中标公告
  5. 新采购需求

发现信号 → 立即微信通知你
无异常 → 静默，不打扰
```

---

## 每日监控执行逻辑（cron 触发）

当 cron job 触发时，agent 执行以下逻辑：

### 搜索三个方向（并发）

```
搜索1（新闻动态）：
[城市] [部门] 新闻 通知 公告 2026

搜索2（领导变动）：
[城市] 政府 领导 调整 换届 2026

搜索3（招标采购）：
[城市] [部门] 招标 采购 新项目 2026
```

### 判断是否触发

对照触发事件列表：
- 若**没有发现触发事件** → 静默结束，不发送任何通知
- 若**发现触发事件** → 立即发送预警通知

### 预警通知格式

```
【信号预警】[客户名]

发现：[一句话描述发现的内容]
来源：[信息链接或页面]
建议：[48小时内应该做什么]
时间窗口：[这个窗口大概还有多久]
时间：[发现时间]
```

---

## 停止监控

触发：`停止监控：[客户名]`

执行：
1. 用 `cron list` 找到该客户的监控 job
2. 用 `cron remove [jobId]` 删除 job
3. 更新 `memory/weak-signal-[客户名].md`，标注「已停止」
4. 告知用户：「已停止监控：[客户名]」

---

## 查看当前监控列表

触发：`查看监控`

执行：
1. 用 `cron list` 查看所有 cron jobs
2. 筛选名称包含「弱信号监控」的 jobs
3. 输出当前监控中的客户列表

---

## 重要约束

- **无异常不打扰**：没有发现触发事件时，绝对不发送任何消息
- **只推送有价值信号**：每次通知都必须有具体的「建议动作」，不能只说「发现了XX」
- **时间窗口意识**：每个预警都必须标注时间窗口，区分「紧急（<7天）」和「还有时间（>30天）」
