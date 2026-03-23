---
name: news-monitor
description: |
  国际新闻和科技资讯监控能力。定时抓取Reuters/BBC/AP/TechCrunch/Verge/Wired/Ars Technica等新闻源。
  当用户需要"最新新闻"、"国际动态"、"科技资讯"、"今天发生了什么"时触发。
---

# 📰 News Monitor — 新闻监控能力

## 当前监控标签（Chrome已打开）

| 标签 | 站点 | 内容 |
|------|------|------|
| 6 | TechCrunch | 科技创业新闻 |
| 7 | The Verge | 科技产品/AI新闻 |
| 8 | Wired | 科技文化深度报道 |
| 9 | BBC News | 国际重大新闻 |
| 10 | AP News | Associated Press国际新闻 |
| 11 | Ars Technica | 科技/安全深度分析 |

## 快速抓取（Playwright）

```python
from browser_control import BrowserSession
b = BrowserSession()
b.connect()
for i, page in enumerate(b.context.pages):
    print(f"标签{i+1}: {page.title()}")
```

## 深度抓取（curl）

```bash
curl -s --max-time 10 "https://techcrunch.com" | grep -oP '(?<=<h2 class="loop-title">).*?(?=</h2>)' | head -5
curl -s --max-time 10 "https://www.bbc.com/news" | grep -oP '(?<=<h3>).*?(?=</h3>)' | head -10
```

## 关键词监控

```bash
~/.qclaw/venvs/crawl4ai/bin/python ~/.agents/skills/smart-search/scripts/search.py "关键词" all
```

## Chrome标签操作

```bash
python3 ~/.qclaw/workspace/skills/pipeline/chrome_keepalive.py start  # 启动Chrome
python3 ~/.qclaw/workspace/skills/pipeline/news_tabs.py               # 打开新闻标签
```
