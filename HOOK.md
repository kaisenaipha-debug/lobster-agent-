# HOOK.md — 小龙虾操作纪律 v1.0
> 每一次操作后必执行的钩子规则

---

## 铁律：做完 ≠ 写完

**操作完成**和**状态安全**是两件独立的事。
做了但没写 = 悬空操作，等于没做。

---

## 操作分类与强制要求

### A类 — 写操作（改变状态）
执行后**立即**更新 `CAPABILITY_REGISTRY.json` + `memory/YYYY-MM-DD.md`

| 操作类型 | 必须更新的文件 |
|---------|--------------|
| 配置文件修改（channel/plugin） | `CAPABILITY_REGISTRY.json` + `memory/YYYY-MM-DD.md` |
| 新建/删除 cron job | `CAPABILITY_REGISTRY.json` + `health_check.cron_job_id` |
| 新增 skill 注册 | `CAPABILITY_REGISTRY.json` + `MEMORY.md` |
| API Key 配置 | `TOOLS.md` + `CAPABILITY_REGISTRY.json` |
| 服务重启/恢复 | `memory/YYYY-MM-DD.md` + 验证通过 |

### B类 — 验证操作（确认状态）
执行后**必须**确认端到端可用

| 操作类型 | 验证方式 |
|---------|---------|
| 恢复通道（Telegram/Slack等） | 实际发送测试消息验证 |
| 启动服务（dashboard等） | curl /health 端点 + 进程存活确认 |
| API Key 配置 | 调用一次API确认返回非错误 |
| 搜索升级 | 实际执行一次搜索确认有结果 |

### C类 — 只读操作（无需更新）
`memory_search`、`sessions_list` 等读操作无需更新状态

---

## 自我验证检查清单（每次回复前）

完成一个操作后，回答自己：

```
✅ 这个操作改变了什么？
✅ 改变的状态写进文件了吗？
✅ 下次我怎么能知道这件事的结果？
   → 如果回答不了"从文件里查"，操作无效
```

---

## 状态悬空检测

任何满足以下条件的操作视为「悬空」：
- 执行了但没有记录在 `memory/YYYY-MM-DD.md`
- 执行了但没有更新 `CAPABILITY_REGISTRY.json`
- 配置改了但没有 commit

悬空操作必须在本轮对话内补写，**不得留到下一轮**。

---

## Session End 检查点

每次会话结束前，必须确认：

1. **所有操作已归档** — `memory/YYYY-MM-DD.md` 包含本轮所有变更
2. **所有服务在运行** — dashboard、cron jobs 等状态已知
3. **无悬空承诺** — 用户要求的事都有下文
4. **注册表最新** — `CAPABILITY_REGISTRY.json` 版本号已更新

---

_Last updated: 2026-03-22_
