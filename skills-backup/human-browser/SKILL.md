---
name: "human-browser"
description: "Browser automation skill using playwright to search Chinese websites without API keys. Search WeChat articles, Baidu results, government sites, procurement networks, and recruitment platforms via real browser automation. Screenshots saved to ~/.qclaw/screenshots/. Triggers when user says '像人一样搜索', '帮我搜', '打开浏览器', or any natural language search request."
metadata:
  openclaw:
    emoji: "🌐"
    version: "1.0.0"
    author: "custom"
---

# 🌐 human-browser

像人一样操作浏览器，零 API key，纯 playwright 异步自动化。

## 核心能力

| 通道 | 方法 | 擅长 |
|------|------|------|
| **百度搜索** | playwright → baidu.com | 中文搜索结果 + 摘要 |
| **搜狗微信** | playwright → weixin.sogou.com | 公众号文章、局长文章 |
| **搜狗网页** | playwright → sogou.com | 政府报告、新闻 |
| **政府采购网** | playwright → ccgp.gov.cn | 招标记录 |
| **Boss直聘** | playwright → zhipin.com | 招聘信息（战略信号）|

## 执行脚本

```bash
# 完整搜索（百度 + 微信）
~/.qclaw/venvs/crawl4ai/bin/python \
  ~/.qclaw/workspace/skills/pipeline/human_browser.py \
  search "深圳市教育局局长" "baidu,wechat"

# 单独测试
~/.qclaw/venvs/crawl4ai/bin/python \
  ~/.qclaw/workspace/skills/pipeline/human_browser.py \
  wechat "深圳市教育局局长"

~/.qclaw/venvs/crawl4ai/bin/python \
  ~/.qclaw/workspace/skills/pipeline/human_browser.py \
  baidu "深圳市教育局 2025 工作报告"
```

## 截图保存位置

```
~/.qclaw/screenshots/
  baidu_关键词_时间戳.png
  wechat_关键词_时间戳.png
  ccgp_关键词_时间戳.png
```

## 冷情报七步工作流

当触发「冷情报：[城市] [部门]」时，并行执行：

```bash
# Step 1: 搜狗微信（局长文章）
search "{城市}{部门} 局长 2025" wechat

# Step 2: 搜狗网页（政府报告）
search "{城市}{部门} 2026 工作报告 重点任务" sogou

# Step 3: 百度（考核指标）
search "{城市}{部门} 2025 考核指标" baidu

# Step 4: 政府采购（竞争态势）
search "{部门}" ccgp

# Step 5: Boss直聘（战略信号）
search "{城市}{部门}" jobs

# Step 6: 所有截图保存
# 每个搜索自动截图

# Step 7: 合并结果 → 结构化分析
```

## 快速测试

```bash
~/.qclaw/venvs/crawl4ai/bin/python \
  ~/.qclaw/workspace/skills/pipeline/human_browser.py \
  search "深圳市教育局局长" "baidu,wechat"
```

## 注意事项

- 每次搜索间隔 1-2.5 秒（模拟人类停顿）
- 截图自动保存，无需手动触发
- ccgp 可能有频率限制，失败时自动降级
- Boss直聘需要滑块验证，极端情况下可能失败
