---
name: clawhub-agent
description: |
  小龙虾专属ClawHub技能生态。负责从ClawHub发现、安装、管理AI Agent能力扩展。
  当需要新能力时触发：用户说"装个xxx"、"找个能xxx的技能"、"扩展能力"等。
  
  核心职责：
  1. ClawHub浏览和搜索（已登录Google的Chrome）
  2. 安全审查（VirusTotal + OpenClaw审核标签）
  3. 技能安装（Homebrew/GitHub Release/npm等）
  4. 验证和管理（openclaw skills list）
  5. 能力注册（写入CAPABILITY_REGISTRY.json）
---

# 🦞 ClawHub Agent — 小龙虾自我武装指南

## 何时用

当你需要新能力时 → 用户说"装个xxx"、"找个能xxx的"、"扩展能力"等。

## 标准流程（5步）

### Step 1 — ClawHub浏览
用已登录Chrome访问：https://clawhub.ai/skills
找目标技能 → 点技能卡看详情

### Step 2 — 安全审查（必做）
在技能页面检查：
- VirusTotal: 显示 Benign ✅ 才继续
- OpenClaw审核: Medium+ → 仔细读README风险部分
- 权限范围: 只申请必要权限
- 安装来源: 优先选纯指令型（无外部下载）

### Step 3 — 安装
根据技能页面提供的安装命令：

Homebrew安装（推荐）：
brew install steipete/tap/gogcli
brew install steipete/tap/summarize

GitHub Release直接下载：
curl -s "https://api.github.com/repos/用户名/仓库/releases/latest" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['tag_name']); [print(a['name'], a['browser_download_url']) for a in d.get('assets',[])]"

### Step 4 — 验证
which tool && tool --version
bash /Applications/QClaw.app/Contents/Resources/openclaw/config/skills/qclaw-openclaw/scripts/openclaw-mac.sh skills list

### Step 5 — 注册
安装成功后更新 MEMORY.md 和 CAPABILITY_REGISTRY.json

---

## 安全审查清单

| 检查项 | 标准 | 处理 |
| VirusTotal | Benign ✅ | Medium+ → 拒绝 |
| OpenClaw标签 | Medium+ | 仔细读README |
| 权限申请 | 最小必要 | 过度申请 → 拒绝 |
| 安装来源 | 官方/ClawHub审核 | 第三方 → 手动审查 |

---

## 常用已安装工具

| 工具 | 命令 | 用途 |
| github | gh | GitHub issues/PRs/CI |
| gog | gog | Gmail/Calendar/Drive/Sheets/Docs |
| summarize | summarize | URL/PDF/YouTube/音频摘要 |
| Chrome | localhost:9222 | 已登录Google账号 |

---

## 当前技能状态

所有技能已验证 ready：
- ✅ github (gh CLI)
- ✅ gog (Google Workspace)
- ✅ summarize (URL/PDF摘要)
- ✅ ontology (知识图谱)
- ✅ self-improving-agent (自我改进)
- ✅ agent-browser (浏览器自动化)
- ✅ smart-search (9通道搜索)
