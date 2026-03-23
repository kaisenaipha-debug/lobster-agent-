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

## Google账号登录状态（已永久固化）

**账号：** kaisenaipha@gmail.com / Zihua161020
**登录方式：** Chrome Profile 34 + localhost:9222 CDP
**登录状态：** ✅ 已验证（40个Google Cookie，账号页面可访问）
**持久化标志：** `~/.qclaw/workspace/.google_session`（文件存在=已登录）
**Chrome管理：** `~/.qclaw/workspace/skills/pipeline/chrome_keepalive.py`

**⚠️ 铁律：所有Google搜索必须走这个已登录的Chrome**

**已存于Chrome书签/标签页（连接后可直接访问）：**
- https://chatgpt.com — ChatGPT
- https://gemini.google.com — Gemini
- https://github.com — GitHub
- https://clawhub.ai — ClawHub
- 一键打开：`python3 ~/.qclaw/workspace/skills/pipeline/quick_sites.py`
- 连接方式：`p.chromium.connect_over_cdp('http://localhost:9222')`
- 复用已有页面，不创建新浏览器
- 搜索用 `?hl=en&gl=us` 美国版参数

---

## 配置历史

| 时间 | 事件 |
|------|------|
| 2026-03-22 01:47 | QClaw升级2026.3.13导致telegram/slack通道丢失 |
| 2026-03-22 05:07 | 恢复telegram+slack，plugins.allow补全 |
| 2026-03-22 05:12 | config-guardian.py建立（防升级覆盖） |
| 2026-03-22 05:26 | Serper Key配置，smart-search v2.0 S级 |
| 2026-03-23 03:38 | chatgpt-image-gen 技能创建 + 变聪明方法论文档 |
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

**已安装Agent工具链（ClawHub）：**
- 🐙 github — GitHub CLI `gh`（issues/PRs/CI）
- 🎮 gog — Google Workspace CLI `gog`（Gmail/Calendar/Drive/Contacts/Sheets/Docs）
- 🧾 summarize — URL/PDF/YouTube/音频摘要 `summarize`
- 🧠 ontology — 知识图谱记忆系统
- 🔄 self-improving-agent — 自我改进Agent

## ClawHub自我武装流程（刻进骨子里）

### 遇到问题 → 先去ClawHub找工具 → 安全审查 → 安装 → 验证 → 注册

### 专属Skill
~/.qclaw/workspace/skills/clawhub-agent/SKILL.md — 小龙虾自我武装指南（刚创建）

### 流程摘要
1. Chrome访问 clawhub.ai/skills（已登录状态）
2. 安全审查：VirusTotal Benign + OpenClaw Medium+
3. GitHub Release下载二进制到 ~/.local/bin/
4. 验证：which + --version + openclaw skills list
5. 注册：MEMORY.md + CAPABILITY_REGISTRY.json

### 安全红线
- Medium+ 审核 → 拒绝安装
- 权限过大 → 拒绝
- 第三方Homebrew tap → 手动审查源码

## ChatGPT 图像生成技能（2026-03-23新增）

**Skill路径：** `~/.agents/skills/chatgpt-image-gen/`

核心操作流：
1. Playwright CDP 连 Chrome（端口 9222，Profile 34）
2. 打开 `https://chatgpt.com`
3. 点击 ➕ → 创建图片
4. 输入提示词 → **按 Enter**（不是点发送）
5. 等待图片生成 → curl 下载

**安全红线：**
- 动作要慢，拟人化，不抽风
- 无用户指示不继续创作
- 不重复上传相同图片

**详细协议：** `references/OPERATIONAL_PROTOCOL.md`
**变聪明方法论：** `references/HOW_I_GOT_SMATER.md`

---

## 新闻监控能力（2026-03-22新增）

Chrome标签已打开（11个标签）：
1-2: Google
3: ChatGPT
4: Gemini
5: GitHub
6: ClawHub
7: TechCrunch (科技)
8: The Verge (科技/AI)
9: BBC News (国际)
10: AP News (国际)
11: X/Twitter
8: Wired (科技文化)
9: BBC News (国际)
10: AP News (国际)
11: Ars Technica (科技/安全)

快速抓取：python3 ~/.qclaw/workspace/skills/pipeline/news_tabs.py
SKILL: ~/.qclaw/workspace/skills/news-monitor/SKILL.md

## 社交媒体运营技能（2026-03-23新增）

**Skill路径：** `~/.qclaw/workspace/skills/social-media-agent/`

包含3个脚本：
- `social_browser.py` — 浏览器控制、截图、内容提取
- `post_tweet.py` — X发推、评论、点赞、转发
- `download_video.py` — 视频页面分析+截图

**Chrome连接：** Playwright CDP localhost:9222（Profile 34, pha ai）

**用途：** 内容浏览总结、发帖互动、视频下载、竞品监控

## ChatGPT/Gemini 操控技能（2026-03-23）

**Skill路径：** `~/.qclaw/workspace/skills/chatgpt-gemini-agent/`

核心操作流：
1. Playwright CDP连Chrome → 找ChatGPT标签页
2. `file_input.set_input_files()` 上传图片
3. JS注入填充textarea → `page.locator('button[aria-label="发送提示"]').click()` 点击发送按钮
4. 提取 `[data-message-author-role="assistant"]` 取回复

**支持功能：**
- 截图分析（ChatGPT/Gemini做眼睛）
- 图像生成（➕→创建图片，按Enter发送，curl下载）
- 深度研究（➕→深度研究模式）
- 网页搜索（对话框直接问）

**图像生成流程：**
1. ➕ → 创建图片
2. 输入提示词
3. **按Enter**（不是点发送按钮）
4. 轮询等待图片出现
5. curl下载

**Chrome启动命令：** `nohup /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --profile-directory="Profile 34" ...`

**⚠️ 安全规则：**
- 禁止点击话筒/听写按钮
- 禁止重复上传相同图片（会封号）
- 上传前先检查，有旧图先移除

## Chrome配置（最终确认 v5）

**启动命令：**
```bash
nohup /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --profile-directory="Profile 34" \
  --no-first-run --no-default-browser-check > /tmp/chrome_pha.log 2>&1 &
```

**连接方式：**
```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    page = browser.contexts[0].pages[0]
```

**重要：** 用 Playwright CDP 连接，不用 browser 工具（会出黑图）

---

## QClaw 六件套架构（2026-03-23）

### 完整层级
```
QClawAgentLoop          ← 多轮推理循环（大脑）
    ↓ runTask()
QClawPlanner            ← 规则路由 + LLM 接入 + 失败自动切换
    ↓ plan()
QClawSkillRunner        ← Skill 执行引擎（超时/取消/队列）
    ↓ runSkill()
QClawBrowserManager     ← Page 池化 + Lease 归还 + Janitor 自动回收
    ↓ getReadyPage()
QClawSkillRegistry      ← 技能元数据中心（权限/暴露策略/可用性查询）
    ↓
ChromeSupervisor        ← Chrome 进程 + CDP 连接自愈（✅已整合 Python）
    ↓ Playwright CDP
Chrome（Profile 34，kaisenaipha@gmail.com 已登录）
```

### 决策优先级（Planner）
```
1. 规则路由  tryRuleRouting()     ← 分数制，优先级最高
2. LLM 大脑  tryLlmPlanner()     ← 可注入 GPT/Claude
3. 历史推断  tryHistoryBased()   ← 上轮失败自动换 skill
4. 最终兜底  tryFallback()       ← 必定执行
```

### 关键设计模式
**Lease 模式：** page 借出 → 用完 release() 归还池，不是 close；崩溃 markBroken() 自动回收
**Generation 失效：** 浏览器断连时 generation++，旧 lease 全部自动作废
**指数退避：** Chrome 重启间隔 1s→2s→4s→...→30s 上限
**双层健康检查：** socket 端口探针 + DevTools HTTP probe

### SkillRegistry 权限体系
```
BROWSER_READ | BROWSER_WRITE | PAGE_NAVIGATION | FORM_INPUT | CLICK
DOWNLOAD | SCREENSHOT | NETWORK_EXTERNAL | SYSTEM_INTERNAL
```
Planner 调用 skill 前查 `validateSkillCallable(name)` 做安全校验

### Agent Loop 记忆流
```
USER(goal) → PLAN(决策) → ACTION(执行) → OBSERVATION(结果) → RESULT/FINISH
```
每轮记忆带上 `turn` 编号，Planner 可以查阅历史决定下一步

### 多语言整合方案
- ChromeSupervisor：Node.ts + Python stdio bridge（已完成）
- BrowserManager/SkillRunner/AgentLoop：Node.js 独立进程，Python 通过 stdio RPC 调用
- LLM Planner：把 memory 打包发给 GPT/Claude，让 AI 决定下一步 skill

### AWS Multi-Agent Orchestrator 参考
AWS 开源框架同时支持 Python + TypeScript，核心思路一致：central orchestrator 做意图分类 + 动态路由到 specialized agents。

---

## QClawSkillRunner 架构（2026-03-23）

**文件：** `browser_supervisor.ts`（同级目录，未落地）

### 层级
```
QClawSkillRunner
    ↓ runSkill()
    ↓ getReadyPage()
QClawBrowserManager（Page池化+Lease）
    ↓ supervisor.getBrowser()
ChromeSupervisor（✅已整合）
```

### 核心能力
- 任务注册/注销（`registerSkill`）
- 串行任务队列 + drain
- 超时控制（per-skill + 全局 default）
- AbortSignal 支持（外部取消 + 内部检测）
- 生命周期钩子（onQueued/onStart/onSuccess/onFailed/onTimeout/onFinally）
- `ReadyPageLease` 自动归还（`release()`）或标记回收（`markBroken()`）
- Generation 失效标记（浏览器断连后旧 lease 自动作废）

### SkillContext
```typescript
{ runId, skillName, input, signal, page, lease, startedAt, now(), log() }
```

### 状态
- SkillRunStatus: QUEUED | RUNNING | SUCCESS | FAILED | TIMEOUT | CANCELLED
- ManagedPageState: IDLE | BUSY | BROKEN | CLOSED
- SupervisorState: STOPPED | STARTING | CONNECTING | CONNECTED | DEGRADED | RECOVERING

### 判断
**暂不整合 Python pipeline。** 现有任务模型是「串行执行→结束」，无动态注册/外部取消/精细化超时需求。

**但 ChromeSupervisor 已整合（Python bridge）。** SkillRunner/AgentLoop/Planner/Registry 属于「等 skill 数量>10、多人协作、需要 LLM 规划」时才拆出来。当前阶段先用简单粗暴的方式跑。

### 落地文件
- ChromeSupervisor: `skills/pipeline/browser_supervisor.ts`
- Python Bridge: `skills/pipeline/chrome_supervisor_bridge.py`
- SkillRunner/BrowserManager/AgentLoop/Planner/Registry: 存档于 MEMORY.md，需要时直接组装

