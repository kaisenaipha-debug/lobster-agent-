---
name: lm-operator
description: 大模型操作员技能。包含：ChatGPT/Gemini拟人化操作、提示词工程、对话管理、防检测策略。通过"观察→思考→行动"三步法操作任何大模型界面。
---

# 大模型操作员手册 v1.0

> 最后更新：2026-03-23 | 版本：v1.0

---

## 核心方法论：三步法则

**每次操作前必须遵守：**

| 步骤 | 问自己 | 通过 |
|------|---------|------|
| 1. 观察 | 现在界面是什么状态？ | 截图 |
| 2. 思考 | 我要做什么？会遇到什么？ | 分析 |
| 3. 行动 | 执行，不要盲目试探 | 操作 |

**失败了就停，不超过3次尝试。**

---

## 第一章：操作ChatGPT

### 1.1 打开ChatGPT
```python
page.goto('https://chatgpt.com/')
page.wait_for_load_state('load', timeout=15000)
page.wait_for_timeout(3000)
```

### 1.2 上传图片分析
**步骤：**
1. 点➕号 → "添加照片和文件"
2. 上传图片：`file_input.set_input_files(path)`
3. 输入提示词
4. 点击「发送提示」按钮（右下角，⬆️图标）

**选择器：**
| 元素 | 选择器 |
|------|--------|
| ➕按钮 | `button[aria-label="添加文件等"]` |
| 发送按钮 | `button[aria-label="发送提示"]` |
| 文本框 | `textarea[name="prompt-textarea"]` |
| 移除文件 | `button[aria-label="移除文件"]` |

### 1.3 生成图片
**步骤：**
1. 点➕号 → "创建图片"
2. 输入创意提示词
3. 等待「发送提示」按钮出现
4. 点击发送
5. 等待图片生成

### 1.4 拟人化打字（最重要！）
```python
import time, random, numpy as np

def human_delay(base_ms=120, variance=50):
    """高斯分布随机延迟"""
    return max(40, min(350, np.random.normal(base_ms, variance)))

def type_like_human(text, textarea):
    for i, char in enumerate(text):
        # 1.5%概率按错临键+退格
        if char.isalpha() and random.random() < 0.015:
            wrong = get_adjacent_key(char)
            textarea.type(wrong, delay=human_delay())
            time.sleep(0.05)
            textarea.press('Backspace')
            time.sleep(random.uniform(0.1, 0.2))
        
        textarea.type(char, delay=human_delay())
        
        # 标点后停顿
        if char in '.,!?;:':
            time.sleep(random.uniform(0.3, 0.8))
        
        # 换行后长停顿
        if char == '\n':
            time.sleep(random.uniform(1, 3))
```

**相邻键映射：**
```python
ADJACENT_KEYS = {
    'a': 'sq', 'b': 'vn', 'c': 'xv', 'd': 'sf', 'e': 'wr',
    'f': 'dg', 'g': 'fh', 'h': 'gj', 'i': 'uo', 'j': 'hk',
    'k': 'jl', 'l': 'ko', 'm': 'n', 'n': 'bm', 'o': 'ik',
    'p': 'ol', 'q': 'wa', 'r': 'et', 's': 'ad', 't': 'ry',
    'u': 'yi', 'v': 'cb', 'w': 'qe', 'x': 'zc', 'y': 'tu', 'z': 'x'
}
```

---

## 第二章：操作Gemini

### 2.1 打开Gemini
```python
page.goto('https://gemini.google.com/app')
page.wait_for_load_state('load', timeout=15000)
page.wait_for_timeout(3000)
```

### 2.2 新建对话
```python
new_chat = page.get_by_text('发起新对话')
new_chat.first.click()
page.wait_for_timeout(3000)
```

### 2.3 输入消息
```python
input_area = page.locator('[contenteditable="true"]').first
input_area.click()
page.wait_for_timeout(500)
# 拟人化打字
type_like_human(message, input_area)
page.keyboard.press('Enter')
```

### 2.4 等待回复
```python
for i in range(30):
    page.wait_for_timeout(2000)
    body = page.inner_text('body')
    if 'Gemini' in body and len(body) > 200:
        idx = body.find('Gemini')
        answer = body[idx:idx+3000]
        if len(answer) > 100:
            return answer
    print(f'等待{i+1}...')
return '未收到回复'
```

### 2.5 删除对话
**步骤：**
1. 左侧栏找到要删除的对话
2. 鼠标移到对话项上 → 出现三个竖点（•••）
3. 点击三个竖点 → 弹出菜单
4. 菜单有4个选项：分享、固定、重命名、**删除**
5. 点击"删除"

**选择器：**
| 元素 | 选择器 |
|------|--------|
| 对话列表 | `.conversation-items-container` |
| 三个竖点 | 鼠标hover后出现 |
| 删除选项 | 竖点菜单第4项 |

---

## 第三章：提示词工程

### 3.1 C-I-C-O框架

| 要素 | 说明 |
|------|------|
| Context/Role | 赋予AI具体身份 |
| Instruction | 具体动词指令 |
| Constraints | 设定边界 |
| Outputs | 给出例子 |

### 3.2 万能公式
```
[身份] + [任务背景] + [具体要求] + [禁止项] + [输出格式]
```

### 3.3 示例
```
你是一位资深品牌策划，擅长乔布斯式极简风格。
我需要写一段产品文案，介绍新款的智能手表。
要求：不超过50字，突出科技感。
禁止：出现"卓越"、"极致"等陈词滥调。
格式：直接输出文案。
```

### 3.4 拟人化技巧
- 用"任务背景"替代"命令指令"
- 设定"对话温度"
- 禁止AI陈词滥调

---

## 第四章：防检测策略

### 4.1 CDP环境检测
**核心：不要做"完美的隐身人"，完美本身就是异常。要做"混乱的普通人"。**

### 4.2 检测方式
- Error.stack序列化特征
- console API被接管
- Canvas/WebGL渲染差异
- AudioContext声卡指纹
- 鼠标默认位置(0,0)
- "冷启动"（无历史记录）

### 4.3 生存策略
1. 使用有长期登录状态的Profile
2. 操作前先"模拟正常人"刷网页
3. 保持"数字人格"
4. 不要每次都完美操作

### 4.4 拟人化操作
1. 延迟用高斯分布（80-200ms随机）
2. 常用词组加速（30-70ms）
3. 标点后停顿（300-800ms）
4. 段落间停顿（1-3秒）
5. 偶尔按错键+退格

---

## 第五章：操作节奏（强制执行！）

### 5.0 执行器（必须用！）

**每次操作前必须运行enforcer.py检查：**
```bash
python3 skills/lm-operator/enforcer.py status  # 查看状态
python3 skills/lm-operator/enforcer.py can_send  # 检查能否发送
```

**强制规则：**
- 上条回复没读完 ❌ 不能发
- 连续3次失败 ❌ 强制停止
- 距上次发送<60秒 ❌ 不能发
- 超过5条消息 ❌ 强制休息

### 5.1 正确节奏（必须遵守！）

```
发送问题 → 等完整回复 → 看完 → 停顿30秒+ → 给赞美 → 慢慢打字问下一个
```

**每一步的时间要求：**
| 步骤 | 最低等待时间 |
|------|-------------|
| 发问题后等回复 | 30秒+ |
| 看完回复 | 看完为止 |
| 停顿消化 | 30秒+ |
| 打字输入 | 慢慢打，每字符150ms+ |

### 5.2 提示词框架（必须用！）

**发送前必须符合C-I-C-O：**
- [ ] Context/Role：给了AI身份？
- [ ] Instruction：具体动词？
- [ ] Constraints：边界设定？
- [ ] Outputs：有例子？

**禁止的行为：**
- ❌ 不等回复完整就发下一个问题
- ❌ 不看完就跳过
- ❌ 连续发送超过3条
- ❌ 没赞美直接问
- ❌ 速度太快
- ❌ 不会了还硬撑

**不会了就停！规则：**
1. 遇到不会的操作 → 明确说"不会"
2. 连续3次失败 → 强制停止
3. **立马呼叫用户帮忙演示**
4. 不要盲目试探
5. 不要死缠烂打

### 5.3 自检清单（每次操作前）
- [ ] 只用一个对话窗口
- [ ] 等待上一轮回复完整
- [ ] 打字间隔随机
- [ ] 长文本有段落停顿
- [ ] 没有连续快速输入
- [ ] 有正常的历史记录

---

## 第六章：Chrome自动化与网页操作

### 6.1 Playwright CDP最佳实践

**连接已有Chrome（不是启动新的）：**
```python
browser = playwright.chromium.connect_over_cdp("http://localhost:9222")
page = browser.contexts[0].pages[0]
```

**绕过webdriver检测：**
```python
page.add_init_script("""
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    delete window.cdc_adoQpoasnfa76PfcOsL5P4;
""")
```

**拦截追踪脚本提速：**
```python
page.route("**/*.{png,jpg,jpeg,css}", lambda route: route.abort())
```

### 6.2 自动注册账号

**关键步骤：**
1. 环境隔离（指纹）
2. 填表
3. 邮箱验证（Mail.tm API）
4. 短信验证（接码平台API）
5. 验证码破解（2Captcha）

**推荐工具栈：**
| 模块 | 工具 |
|------|------|
| 浏览器引擎 | Playwright |
| 决策大脑 | GPT-4o / Claude |
| 框架层 | LangChain / Browser-use |
| 指纹管理 | AdsPower / BitBrowser |
| 验证码 | 2Captcha / YesCaptcha |

### 6.3 获取API Token

**OAuth流程：**
1. 打开授权页面
2. 点击授权按钮
3. 拦截回调URL获取token
4. 解析token

**从控制台提取API Key：**
1. 登录网站
2. 打开开发者工具→Network
3. 找到API请求
4. 提取Authorization header

### 6.4 情报收集合规

**四大红线：**
1. 手段合法
2. 目的合规
3. 频率适当
4. 不破坏系统

---

## 版本历史

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| v1.0 | 2026-03-23 | 初始版本，包含ChatGPT/Gemini操作、提示词工程、防检测策略 |

---

_Last updated: 2026-03-23_
