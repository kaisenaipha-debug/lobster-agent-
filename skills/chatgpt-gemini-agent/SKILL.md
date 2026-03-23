---
name: chatgpt-gemini-agent
description: ChatGPT/Gemini 浏览器操控代理。熟练操作Chrome已登录的ChatGPT和Gemini，实现截图分析、图像生成、深度研究等。同时具备完美的"拟人化"打字能力，不被检测为机器人。
---

# ChatGPT & Gemini 操控代理

## Chrome 启动方式

```bash
nohup /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --profile-directory="Profile 34" \
  --no-first-run --no-default-browser-check > /tmp/chrome_pha.log 2>&1 &
```

**⚠️ 重要警告（来自Gemini）：CDP本身就是可被检测的痕迹！**

## CDP环境检测防御策略

**核心逻辑：不要做"完美的隐身人"，完美本身就是异常。要做"混乱的普通人"。**

### 1. 浏览器特征检测
- Canvas/WebGL渲染差异（GPU驱动指纹）
- AudioContext声卡指纹
- 鼠标默认位置(0,0)=红旗
- 滚动加速度太均匀会被检测

### 2. 生存策略
1. 使用有长期登录状态的Profile（不要用全新Profile）
2. 在操作AI之前，先让浏览器"模拟正常人"刷网页，产生正常缓存
3. 避免webdriver相关特征暴露
4. 保持"数字人格"——不要每次都完美

---

## 拟人化打字规则（最重要！）

根据Gemini的建议，打字必须模拟真实人类行为：

### 1. 动态延迟（高斯分布）
```python
import random
import numpy as np

def human_delay(base_ms=120, variance=50):
    # 高斯分布，均值base_ms，标准差variance
    delay = np.random.normal(base_ms, variance)
    return max(40, min(350, delay))  # 限制范围40-350ms
```

### 2. 随机停顿
```python
# 标点后停顿（300-800ms）
if char in '.,!?;:':
    time.sleep(random.uniform(0.3, 0.8))

# 段落间停顿（1-3秒）
if char == '\n':
    time.sleep(random.uniform(1, 3))
```

### 3. 偶尔"按错键"（最关键！1.5%概率）
```python
ADJACENT_KEYS = {
    'a': 'sq', 'b': 'vn', 'c': 'xv', 'd': 'sf', 'e': 'wr',
    'f': 'dg', 'g': 'fh', 'h': 'gj', 'i': 'uo', 'j': 'hk',
    'k': 'jl', 'l': 'ko', 'm': 'n', 'n': 'bm', 'o': 'ik',
    'p': 'ol', 'q': 'wa', 'r': 'et', 's': 'ad', 't': 'ry',
    'u': 'yi', 'v': 'cb', 'w': 'qe', 'x': 'zc', 'y': 'tu', 'z': 'x',
}

def get_adjacent_key(char):
    return random.choice(ADJACENT_KEYS.get(char.lower(), char))

def type_with_human_errors(text, textarea):
    for i, char in enumerate(text):
        # 1.5%概率按错临键
        if char.isalpha() and random.random() < 0.015:
            wrong = get_adjacent_key(char)
            textarea.type(wrong, delay=human_delay())
            time.sleep(0.05)
            textarea.press('Backspace')
            time.sleep(random.uniform(0.1, 0.2))
        
        textarea.type(char, delay=human_delay())
        
        # 标点后额外停顿
        if char in '.,!?;:':
            time.sleep(random.uniform(0.3, 0.8))
        
        # 换行后停顿
        if char == '\n':
            time.sleep(random.uniform(1, 3))
```

### 4. 常用词组加速
```python
COMMON_BIGRAMS = ['th', 'he', 'in', 'er', 'an', 're', 'on', 'ti', 'te', 'es', 'the', 'and', 'you', 'for', 'ing', 'ion']
if text[max(0, i-1):i+1].lower() in COMMON_BIGRAMS:
    delay = random.uniform(30, 70)  # 常用词更快
```

---

## 发送按钮

- ChatGPT：`button[aria-label="发送提示"]`
- 发送后要**等回复完整**，不要一直发新消息

---

## 操作前自检

- [ ] 只用一个对话窗口
- [ ] 等待上一轮回复完整
- [ ] 打字间隔随机（不是固定值）
- [ ] 长文本有段落停顿
- [ ] 没有连续快速输入
- [ ] 有正常的历史记录和缓存

## 操作节奏

1. 看完整回答再打字
2. 给点评再问下一个
3. 不要重复发送
4. 不要开太多窗口
5. 失败就停止
