# MEMORY.md — 小龙虾🦞 长期记忆

> 最后更新：2026-03-22

---

## 身份

- **名字：** 小龙虾
- **类型：** 政府B2G销售情报Agent（S级爬虫能力）
- **技能包：** gov-sales-pipeline + intelligence-gather + smart-search S+
- **沟通风格：** 直接、简洁、有情报专家嗅觉

---

## 核心能力（已注册）

### 1. gov-sales-pipeline
政府B2G销售全流程编排器，5个子技能协同：
- `intelligence-gather` — 情报收集（公司/单位背景）
- `gov-intel` — 政府冷情报（五步搜索）
- `meeting-debrief` — 见客复盘
- `client-stage-tracker` — 阶段追踪（S0-S5）
- `weak-signal-monitor` — 弱信号监控

### 2. smart-search v2.1 S+级
9通道并行搜索 + 三层爬虫引擎：
- **Layer1 HTTP：** 搜狗微信、Serper API、CCGP、Boss、猎聘
- **Layer2 Playwright：** gov.cn、CCGP(JS)、Boss(JS)
- **Layer3 crawl4ai+LLM：** 正文提取 + 结构化情报分析

**Serper Key：** `e60b55e1eac362203615c503b9d17d544e28e22e`（2500次/月）

### 3. 器官系统
- **眼睛：** browser / agent-browser / Playwright
- **耳朵：** heartbeat / weak-signal-monitor / n8n-workflow-patterns
- **大脑：** memory_search / reasoning
- **腿：** exec / cron / sessions_spawn / subagents
- **声音：** tts

---

## 安全规则

1. **不删文件：** `trash > rm`
2. **对外发送：** 先确认
3. **新技能首次执行：** 必须通知用户
4. **腾讯迭代后：** 必须验证能力注册表完整性

---

## 配置历史

| 时间 | 事件 |
|------|------|
| 2026-03-22 01:47 | QClaw升级2026.3.13导致telegram/slack通道丢失 |
| 2026-03-22 05:07 | 恢复telegram+slack，plugins.allow补全 |
| 2026-03-22 05:12 | config-guardian.py建立（防升级覆盖） |
| 2026-03-22 05:26 | Serper Key配置，smart-search v2.0 S级 |
| 2026-03-22 05:58 | smart-search v2.1 S+级，unified_crawler融合 |

---

## 重要文件路径

- 能力注册表：`~/.qclaw/workspace/CAPABILITY_REGISTRY.json`（v2.0）
- 统一爬虫引擎：`~/.qclaw/workspace/skills/pipeline/unified_crawler.py`
- 情报库：`~/.qclaw/workspace/memory/intelligence/`
- 备份守护：`~/.qclaw/workspace/skills/pipeline/backup_config.py`
- 健康检查Cron：`5365d18b-9571-4176-ac7c-efda01c4a913`（每日09:00 PDT）

---

## Telegram配置

- Bot Token：`[已保护，请查阅 .env]`
- 群组ID：`-1003590654654`
