---
name: social-media-agent
description: 社交媒体运营助手技能。支持登录Chrome后操控X/Twitter、Instagram、微信等平台，完成内容浏览总结、内容发布、评论互动、视频下载等操作。适用场景：账号运营、内容监控、竞品分析、社交媒体管理。
---

# 社交媒体运营助手

## 核心能力

### 1. 浏览器自动化控制
- 使用 Playwright CDP 连接本地 Chrome（Profile 34，pha ai 账号）
- 打开任意网页、截图、滚动、点击交互
- 保持登录状态（谷歌账号体系网站自动登录）

### 2. 内容总结
- 读取任意网页/X帖子/文章内容
- 用 LLM 提取关键信息，生成摘要
- 结构化输出：标题、要点、观点

### 3. 内容发布
- X/Twitter 发推文（带图/带视频）
- 评论、点赞、转发
- 自动生成符合平台风格的文案

### 4. 视频下载
- 支持 X/Twitter 视频下载
- 支持 YouTube/Instagram reels 下载
- 保存到本地指定目录

### 5. 账号监控
- 定期抓取特定话题/关键词最新内容
- 竞品账号内容追踪
- 数据报告生成

## 使用方式

用户说「帮我看X上XXX的内容并总结」→ 执行 social_browser.py
用户说「帮我发一条X」→ 执行 post_tweet.py
用户说「帮我下载这个视频」→ 执行 download_video.py

## 图片分析能力（已升级）

通过 Playwright + ChatGPT 实现截图自动分析：

```python
# 截图 → 上传ChatGPT → 获取描述
1. page.screenshot(path='/tmp/screenshot.png')
2. file_input.set_input_files('/tmp/screenshot.png')  # 上传到ChatGPT
3. textarea.fill('请描述这张图片内容')
4. page.keyboard.press('Enter')
5. 提取 assistant 回复
```

**Chrome 连接方式**

```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    page = browser.contexts[0].pages[0]  # 复用已有标签页
    # 或者新建标签页
    new_page = browser.contexts[0].new_page()
```

## Chrome 启动命令（首次使用）

如果端口 9222 未开启：
```bash
nohup /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --profile-directory="Profile 34" \
  --no-first-run --no-default-browser-check > /tmp/chrome_pha.log 2>&1 &
```

## 安全规则

- 发内容前必须用户确认
- 不主动发帖、不参与政治/敏感话题
- 下载仅限自有账号内容或公开内容
