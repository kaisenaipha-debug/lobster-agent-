# ChatGPT 图像生成 — 详细操作协议

## Chrome 连接配置

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    page = browser.contexts[0].pages[0]  # 复用已有页面，不创建新浏览器
```

**重要：**
- 用 Playwright CDP 连接，不用 browser 工具（会出黑图）
- Chrome 启动命令已在 TOOLS.md 中定义
- 登录状态由 `~/.qclaw/workspace/.google_session` 标志文件固化

## 完整操作步骤

### Step 1：检查 Chrome 状态

确保 Chrome 已在端口 9222 运行：

```bash
# 检查端口
lsof -i :9222 | grep Chrome
```

### Step 2：连接并定位标签页

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    # 找到 ChatGPT 标签页
    for page in browser.contexts[0].pages:
        if 'chatgpt' in page.url.lower():
            break
```

### Step 3：点击创建图片

1. 点击 `➕` 按钮（通常在输入框左侧）
2. 在下拉菜单中选择「创建图片」（"Create image"）
3. 输入框会切换为图片生成模式

### Step 4：输入提示词

- 在出现的输入框中填写英文提示词（效果更好）
- **按 Enter 键提交**（不是点击发送按钮）

### Step 5：等待图片生成

- 页面会出现加载状态（skeleton/loading）
- 轮询检查，直到 `<img>` 元素出现或加载状态消失
- 通常需要 5-15 秒

### Step 6：下载图片

```python
import urllib.request
import os

# 方法1：通过 <img> src 下载
img_element = page.locator('img[src*="dalle"]').first
img_url = img_element.get_attribute('src')

# 方法2：截图后通过 curl 下载（如果 src 无法获取）
# 截图找到图片区域，交给用户选择
```

### Step 7：保存文件

```python
output_path = '/Users/tz/.qclaw/workspace/downloads/'
os.makedirs(output_path, exist_ok=True)
filename = f'dalle_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
urllib.request.urlretrieve(img_url, os.path.join(output_path, filename))
```

## 拟人化操作要点

- 每步操作之间加 1-3 秒随机延迟
- 不要连续快速点击
- 可适当模拟"思考"停顿
- 用 `page.wait_for_timeout(2000)` 实现延迟

## 错误处理

| 错误 | 处理方式 |
|------|---------|
| 找不到➕按钮 | 截图诊断，可能是页面未加载 |
| 图片生成失败 | 重试1次，仍失败则告知用户 |
| 网络超时 | 延长等待时间 |
| 被封号 | 立即停止，通知用户 |
