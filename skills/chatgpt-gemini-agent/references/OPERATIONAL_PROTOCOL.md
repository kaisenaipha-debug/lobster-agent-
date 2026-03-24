# ChatGPT / Gemini 操作规范 v2.0

> 每次操作 ChatGPT/Gemini 前必须通读本文件并执行。
> 违反任何一条视为铁律违规。

---

## 一、操作前检查（强制）

```
1. enforcer.py can_send → 必须返回 0 才能操作
2. 检查当前 Chrome CDP 连接是否稳定
3. 确认登录状态（头像/用户名可见）
4. 明确本次任务目标，写出结构化提示词
```

---

## 二、连接检查

```python
# 连接稳定性验证
browser = p.chromium.connect_over_cdp('http://localhost:9222')
pages = browser.contexts[0].pages
assert len(pages) > 0, "CDP连接失败"

# 检查目标网站登录状态
page.goto('https://chatgpt.com OR gemini.google.com')
page.wait_for_timeout(3000)  # 等待3秒网络idle
assert '登录' not in page.locator('body').inner_text(), "未登录，需先完成登录"
```

---

## 三、打开目标网站

```python
page.goto(url, wait_until='networkidle', timeout=30000)
page.wait_for_timeout(2000)  # 必须等2秒页面完全加载
```

**时间规则：**
- 页面跳转后至少等 2 秒
- 弹出对话框等 1.5 秒
- 下拉菜单加载等 1 秒

---

## 四、提示词撰写规范

### 必须包含的5个部分

```
1. 角色设定（你是什么）
2. 任务描述（要做什么，1-2句话）
3. 约束条件（限制/边界/禁止什么）
4. 输出格式（JSON/markdown/列表/字数限制）
5. 示例（few-shot，2-3个例子）
```

### 禁止事项

- ❌ 不写角色直接问问题
- ❌ 不写输出格式（"随便写"类）
- ❌ 不分段落的长文本
- ❌ 一次问多个不相关问题

### 模板

```
你是[角色名称]，有[X]年[领域]经验。

任务：[具体描述]

要求：
- [格式要求]
- [字数限制]
- [其他约束]

示例：
输入：[例子1]
输出：[期望输出1]

输入：[例子2]
输出：[期望输出2]
```

---

## 五、输入操作（严格时间控制）

### 5.1 找到输入框

```python
# 查找优先级
selectors = [
    'div[contenteditable="true"]',     # ChatGPT/Gemini主输入框
    'textarea[name="prompt"]',          # 备选
    'textarea',                          # 兜底
]

editor = page.locator(selector).first
assert editor.is_visible(), f"找不到输入框: {selector}"
```

### 5.2 点击并准备输入

```python
editor.click()
time.sleep(random.uniform(1.0, 2.0))  # 必须等1-2秒，光标出现
```

### 5.3 拟人化打字（核心规则）

```python
import random, time

HUMAN_TYPE_CONFIG = {
    'alpha_delay': (0.06, 0.15),      # 字母延迟：60-150ms
    'punct_delay': (0.3, 0.8),         # 标点延迟：300-800ms
    'space_delay': (0.02, 0.08),       # 空格延迟：20-80ms
    'caps_chance': 0.02,               # 大写概率：2%
    'backspace_chance': 0.015,         # 退格概率：1.5%（模拟打错）
    'backspace_duration': (0.05, 0.1),  # 退格后等待：50-100ms
}

def human_type(page, selector, text):
    """
    拟人化打字核心函数
    """
    editor = page.locator(selector).first
    editor.click()
    time.sleep(random.uniform(1.0, 2.0))

    ADJACENT_KEYS = {
        'a':'sq', 'b':'vn', 'c':'xv', 'd':'sf', 'e':'wr',
        'f':'dg', 'g':'fh', 'h':'gj', 'i':'uo', 'j':'hk',
        'k':'jl', 'l':'ko', 'm':'nm', 'n':'bm', 'o':'ip',
        'p':'ol', 'q':'wa', 'r':'et', 's':'ad', 't':'ry',
        'u':'yi', 'v':'cb', 'w':'eq', 'x':'zc', 'y':'tu',
        'z':'x'
    }

    for char in text:
        cfg = HUMAN_TYPE_CONFIG

        # 模拟打错字（1.5%概率）
        if char.isalpha() and random.random() < cfg['backspace_chance']:
            adj = ADJACENT_KEYS.get(char.lower(), char)
            page.keyboard.type(adj, delay=random.uniform(30, 80))
            time.sleep(random.uniform(*cfg['backspace_duration']))
            page.keyboard.press('Backspace')
            time.sleep(random.uniform(0.1, 0.2))

        # 普通字符
        if char.isalpha():
            delay = random.uniform(*cfg['alpha_delay'])
        elif char in '.,!?;:':
            delay = random.uniform(*cfg['punct_delay'])
        elif char == ' ':
            delay = random.uniform(*cfg['space_delay'])
        else:
            delay = random.uniform(0.05, 0.15)

        # 大写概率（2%）
        if char.isalpha() and random.random() < cfg['caps_chance']:
            page.keyboard.type(char.upper(), delay=delay * 1.5)
        else:
            page.keyboard.type(char, delay=delay)

        # 标点后额外停顿
        if char in '.,!?;:':
            time.sleep(random.uniform(0.2, 0.5))

        # 换行后长停顿
        if char == '\n':
            time.sleep(random.uniform(1.0, 2.0))
```

### 5.4 发送

```python
# 必须按 Enter，不点按钮
time.sleep(0.5)
page.keyboard.press('Enter')
```

### 5.5 等待回复（核心规则）

```python
# 最低等待时间
MIN_WAIT_AFTER_SEND = 5  # 秒

# 检查回复出现
def wait_for_response(page, timeout=120, poll_interval=3):
    """
    轮询等待回复出现
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            messages = page.locator('[data-message-author-role="assistant"]').all()
            if messages:
                last_msg = messages[-1]
                text = last_msg.inner_text()
                if len(text) > 10:  # 回复至少10个字符
                    return text
        except:
            pass
        time.sleep(poll_interval)

    raise TimeoutError(f"等待回复超时（{timeout}秒）")
```

### 5.6 读取完整回复（强制）

```python
# 必须读取完整回复，不能截断
def get_full_response(page):
    """
    读取完整回复，不截断
    """
    messages = page.locator('[data-message-author-role="assistant"]').all()
    if not messages:
        return None

    full_text = messages[-1].inner_text()

    # 检查是否被截断（"继续"按钮）
    try:
        continue_btn = page.locator('button:has-text("继续"), [data-testid="continue-generation"]')
        if continue_btn.is_visible():
            continue_btn.click()
            time.sleep(3)
            full_text += "\n" + messages[-1].inner_text()
    except:
        pass

    return full_text
```

---

## 六、回复后操作（强制）

### 6.1 必须赞美（如果是好答案）

```python
# 识别答案质量
QUALITY_PATTERNS = [
    '✅', '正确', '完整', '专业', '代码', '方案',
    '架构', '推荐', '最佳', '解决方案'
]

if any(p in response for p in QUALITY_PATTERNS):
    # 给予正面反馈（拟人化）
    page.locator('textarea').first.click()
    time.sleep(0.5)
    page.keyboard.type("👍 这个方案很专业，代码示例很有参考价值。", delay=0.1)
    page.keyboard.press('Enter')
    time.sleep(3)
```

### 6.2 操作后确认

```python
enforcer.confirm()  # 必须调用
```

---

## 七、时间总览

```
打开网页          → 等待 2-5 秒
点击输入框        → 等待 1-2 秒
拟人化打字        → 平均 100ms/字符
发送              → 等待 0.5 秒
等待回复          → 至少 5 秒（上不封顶）
读取完整回复      → 手动滚动，不截断
赞美（如有必要）  → 等待 3-5 秒
确认 enforcer    → 最后一步
```

---

## 八、禁止事项（铁律）

| 禁止 | 原因 |
|------|------|
| ❌ 跳过 enforcer 检查 | 安全第一 |
| ❌ 一次性 fill() 贴入长文本 | 可被检测为机器人 |
| ❌ 不等页面加载就操作 | 元素未渲染完成 |
| ❌ 回复没读完就截断 | 信息不完整 |
| ❌ 不写输出格式要求 | GPT会随意发挥 |
| ❌ 点发送按钮 | 不如 Enter 拟人 |
| ❌ 操作完不调用 confirm | 铁律要求 |
| ❌ 不做错误处理 | 任何步骤都可能失败 |

---

## 九、错误处理

```python
RETRY_CONFIG = {
    'max_retries': 3,
    'backoff_base': 2,  # 指数退避：2, 4, 8秒
    'cdp_error_codes': [1000, 1001, 1002],  # CDP断连错误码
}

def handle_error(error, step_name):
    """标准化错误处理"""
    print(f"❌ 步骤 [{step_name}] 失败: {error}")

    if "CDP" in str(error) or "Target closed" in str(error):
        # CDP断连，尝试重连
        reconnect_with_backoff()
    elif "Timeout" in str(error):
        # 超时，等待后重试
        time.sleep(RETRY_CONFIG['backoff_base'])
    else:
        # 未知错误，停止并上报
        raise
```

---

## 十、完整操作流程（逐字执行）

```
Step 1: enforcer.can_send()                         → 返回0才能继续
Step 2: CDP连接检查                                  → assert连接正常
Step 3: 页面goto(url)                                → wait 2秒
Step 4: 检查登录状态                                 → assert已登录
Step 5: 撰写结构化提示词                              → 角色+任务+约束+格式+示例
Step 6: 找输入框并click                              → wait 1-2秒
Step 7: human_type()拟人化输入                      → 按键延迟60-150ms
Step 8: page.keyboard.press('Enter')                → wait 0.5秒
Step 9: wait_for_response()                         → 至少5秒
Step 10: get_full_response()                        → 不截断，检查"继续"按钮
Step 11: 如是好答案 → 发送赞美                      → wait 3-5秒
Step 12: enforcer.confirm()                          → 必须调用
```

---

_Last updated: 2026-03-23_
