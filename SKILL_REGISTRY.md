# SKILL_REGISTRY.md — 小龙虾技能注册表 v1.0
> 技能即资产，丢失等于犯罪

---

## 核心原则

**技能位置：** `~/.agents/skills/`（源目录）
**备份位置：** `~/.qclaw/workspace/skills-backup/`（GitHub同步）
**注册表：** `~/.qclaw/workspace/SKILL_REGISTRY.md`（实时追踪）

每次 QClaw 升级前：自动把 `~/.agents/skills/` 备份到 workspace → commit → push
每次 QClaw 升级后：对照注册表检查缺失技能，自动从 backup 恢复

---

## 已注册技能（全部，来源不限）

### 用户安装技能（~/.agents/skills/）

| 技能名 | 路径 | 状态 | 描述 | 上次验证 |
|-------|------|------|------|---------|
| gov-sales-pipeline | ~/.agents/skills/gov-sales-pipeline/ | ✅ 正常 | 政府B2G销售全流程编排器 | 2026-03-22 |
| intelligence-gather | ~/.agents/skills/intelligence-gather/ | ✅ 正常 | 情报收集（公司/单位背景调查） | 2026-03-22 |
| smart-search | ~/.agents/skills/smart-search/ | ✅ 正常 | S+级情报搜索（9通道并行） | 2026-03-22 |
| gov-intel | ~/.agents/skills/gov-intel/ | ✅ 正常 | 政府冷情报五步搜索 | 2026-03-22 |
| meeting-debrief | ~/.agents/skills/meeting-debrief/ | ✅ 正常 | 见客复盘对话分析 | 2026-03-22 |
| client-stage-tracker | ~/.agents/skills/client-stage-tracker/ | ✅ 正常 | 客户阶段追踪S0-S5 | 2026-03-22 |
| weak-signal-monitor | ~/.agents/skills/weak-signal-monitor/ | ✅ 正常 | 弱信号监控+每日cron | 2026-03-22 |

### QClaw 内置技能（built-in, 不可改）

| 技能名 | 路径 | 描述 |
|-------|------|------|
| qclaw-env | 内置 | 环境诊断/CLI安装 |
| qclaw-openclaw | 内置 | openclaw命令封装 |
| qclaw-rules | 内置 | 系统基础运行规则 |
| docx | 内置 | Word文档处理 |
| pdf | 内置 | PDF处理 |
| xlsx | 内置 | Excel处理 |
| pptx | 内置 | PPT处理 |
| find-skills | 内置 | 技能发现/安装 |
| weather-advisor | 内置 | 天气查询 |
| news-summary | 内置 | 新闻摘要 |
| web-search (xAI) | 内置 | 搜索引擎（xAI Grok） |
| tts | 内置 | 语音合成 |
| browser | 内置 | 浏览器控制 |

---

## 技能完整性检查流程

```
每次启动时：
1. 读取 SKILL_REGISTRY.md
2. 逐个检查 ~/.agents/skills/ 目录是否存在
3. 缺失 → 从 ~/.qclaw/workspace/skills-backup/ 恢复
4. backup也没有 → 报告用户，标注 BLOCKED
5. 全部存在 → ✅ 注册表完整
```

---

## 技能备份流程（升级前必执行）

```bash
# 升级前自动备份
rsync -av ~/.agents/skills/ ~/.qclaw/workspace/skills-backup/
git add skills-backup/
git commit -m "backup: skills before QClaw upgrade"
git push  # 如果 remote 已配置
```

---

## GitHub 同步规则

- `skills-backup/` 目录 → 自动备份到 GitHub
- 每次 skill 更新 → commit 增量
- QClaw 升级前 → 完整备份 commit
- QClaw 升级后 → 完整性检查 + 恢复

---

## 缺失技能恢复流程

```
检测到技能缺失：
1. 查 SKILL_REGISTRY.md 找到技能路径
2. 查 skills-backup/ 有无备份
3. 有 → rsync 恢复到 ~/.agents/skills/
4. 无 → 标记 BLOCKED，通知用户"技能X丢失，需要重新安装"
5. 更新注册表状态
```

---

_Last updated: 2026-03-22_
