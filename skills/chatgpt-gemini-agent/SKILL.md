---
name: chatgpt-gemini-agent
description: ChatGPT/Gemini 浏览器操控代理。熟练操作Chrome已登录的ChatGPT和Gemini，实现截图分析、图像生成、深度研究、网页搜索等任务。是小龙虾的"眼睛"和"智囊"。
---

# ChatGPT & Gemini 操控代理

## Chrome 启动方式

**命令（必须用这个，不要用其他方式）：**
```bash
nohup /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --profile-directory="Profile 34" \
  --no-first-run --no-default-browser-check > /tmp/chrome_pha.log 2>&1 &
```

**检查端口：**
```python
import socket
sock = socket.socket()
result = sock.connect_ex(('localhost', 9222))
print('已连接' if result == 0 else '未连接')
sock.close()
```

## Playwright 连接方式

```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    page = browser.contexts[0].pages[0]  # 复用已有标签页
    # 或者新建标签页
    new_page = browser.contexts[0].new_page()
```

---

## 核心操作流程

### 🔍 截图 + 分析（最常用）

**完整流程：**

```python
# 1. 截图
page.screenshot(path='/tmp/screenshot.png', full_page=False)

# 2. 上传图片
file_inputs = page.locator('input[type="file"]')
# ChatGPT有3个file input，其中第2或第3个接受图片
for i in range(file_inputs.count()):
    accept = file_inputs.nth(i).get_attribute('accept') or ''
    if 'image' in accept:
        file_inputs.nth(i).set_input_files('/tmp/screenshot.png')
        break
page.wait_for_timeout(1000)

# 3. 输入提示词
script = """
() => {
    const ta = document.querySelector('textarea[name="prompt-textarea"]');
    if (ta) {
        ta.value = '请描述这张图片的内容，用中文回复';
        ta.dispatchEvent(new Event('input', {bubbles: true}));
    }
}
"""
page.evaluate(script)
page.wait_for_timeout(500)

# 4. 按回车发送（不是点击按钮）
page.keyboard.press('Enter')
page.wait_for_timeout(8000)  # 等待ChatGPT回复

# 5. 提取回复
response = page.evaluate("""
() => {
    const msgs = document.querySelectorAll('[data-message-author-role="assistant"]');
    const last = msgs[msgs.length - 1];
    return last ? last.innerText : '未找到回复';
}
""")
print(response)
```

### 🖼️ 图像生成

**操作步骤：**
1. 点➕号 → 选择"创建图片"
2. 在对话框输入创意提示词
3. **按Enter发送**（不需要点发送按钮）
4. 等待生成完成（轮询检测有图）
5. 下载图片

**创建图片模式特征：**
- 没有「发送提示」按钮
- 输入提示词后按Enter自动触发生成
- 生成后会有图片出现

**提示词技巧：**
- 英文效果更好
- 包含风格、细节、情绪
- 例如：`A futuristic cyberpunk city at night, neon lights, rain-soaked streets, cinematic, 8k`

**⚠️ 打字速度：**
- 模拟人打字，每个字符 80-120ms 间隔
- 不要太快，会被识别为机器人导致生成失败

**下载生成的图片：**
```python
# 从页面提取图片URL
img_url = page.evaluate("""
() => {
    const imgs = Array.from(document.querySelectorAll('img'));
    const found = imgs.find(img => img.src && img.src.startsWith('http') && !img.src.includes('data:'));
    return found ? found.src : null;
}
""")
# curl下载
subprocess.run(['curl', '-L', '-o', save_path, img_url])
```

### 🔬 深度研究

**操作步骤：**
1. 点➕号 → 找到深度研究选项（或在对话框输入相应命令）
2. 输入研究主题
3. 等待ChatGPT进行多轮搜索和分析
4. 获取完整报告

### 🌐 网页搜索

**操作步骤：**
1. 在ChatGPT对话框直接输入搜索内容
2. ChatGPT会自动进行网页搜索
3. 获取搜索结果和分析

---

## 提示词模板库

### 截图分析
```
请描述这张图片的内容，用中文回复
```
```
分析这张图片的关键信息，用bullet points总结
```
```
这张图片里有什么需要注意的细节？
```

### 图像生成
```
创建一个[风格]的[主题]图片
```
```
画一张[描述具体场景]，包含[关键元素]，风格[风格名称]
```

### 深度研究
```
请对[主题]进行深度研究，包括：
1. 背景和现状
2. 主要参与者和立场
3. 最新进展
4. 未来趋势
```
```
帮我研究[公司/人物/事件]，给出详细信息汇总
```

### 内容创作
```
帮我写一段关于[主题]的推广文案，目标人群是[人群]
```
```
用[风格]的语气写一条[平台]帖子，主题是[内容]
```

---

## 输出方式

**文字输出：** 直接print到控制台，发送给用户

**语音输出：** 使用tts工具生成语音
```python
import subprocess
result = subprocess.run(['tts', response_text], capture_output=True)
```

---

## 常用选择器

### ChatGPT 选择器
| 元素 | 选择器 |
|------|--------|
| 文本输入框 | `textarea[name="prompt-textarea"]` |
| 文件上传按钮 | `input[type="file"]` |
| 发送按钮 | `button[aria-label="发送提示"]`（右下角，⬆️图标） |
| 助手回复 | `[data-message-author-role="assistant"]` |
| 加号按钮 | 查找包含+图标的按钮 |

### Gemini 选择器
（待补充，需要实际测试）

---

## 快速命令

```bash
# 打开ChatGPT新标签页
open https://chatgpt.com

# 打开Gemini新标签页
open https://gemini.google.com
```

---

## ⚠️ 安全规则（必须遵守）

1. **❌ 禁止点击话筒/听写按钮** — 会触发语音输入，误操作
2. **❌ 禁止重复上传相同图片** — 会导致账号被封禁
3. **同一图片每次操作前先检查** — 如果图片已上传过，先移除再上传新图片
4. **避免短时间内大量上传** — 间隔至少10秒以上

## 发送按钮定位

- **ChatGPT发送按钮**：`button[aria-label="发送提示"]`（右下角，⬆️图标）
- **不要用** `button[aria-label="听写按钮"]`（话筒图标，左边）
- **备选发送方式**：回车键 `page.keyboard.press('Enter')`

## 注意事项

1. **上传图片用set_input_files**，不是拖拽
2. **发送用点击「发送提示」按钮**，不是回车（回车可能失败）
3. **等待时间要给够**，ChatGPT生成回复需要5-10秒
4. **提示词要明确**，告诉AI你具体想要什么
5. **有疑问就多问**，ChatGPT是智囊，不确定的就问它
