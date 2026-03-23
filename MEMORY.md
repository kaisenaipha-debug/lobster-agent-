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
