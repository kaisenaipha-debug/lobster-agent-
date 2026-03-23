# SELF_AUDIT.md — 小龙虾自我诊断与治疗 v2.0

> 日期：2026-03-23 | 诊断者：自己 | 主题：ChatGPT操控技能进化记录

---

## 🧠 今日进化：我是怎么变聪明的

### 第一阶段：只会用错误工具（蠢）

**错误行为：**
- 用 OpenClaw 内置 `browser` 工具截图 → 黑屏/深色模式
- 不理解 Chrome 有多个 Profile，用错 profile 所以没有登录状态
- 以为截图工具坏了，实际上是工具选错了

**怎么发现的：**
- 用户发来截图说"黑屏"，我才发现 browser 工具默认用 OpenClaw 自己开的浏览器，不是用户那个已登录的 Chrome

**修正：**
- 改用 Playwright CDP 连接 `localhost:9222`
- 确认 Chrome 启动命令用 `--profile-directory="Profile 34"`

---

### 第二阶段：找不到发送按钮

**错误行为：**
- 以为 textarea 隐藏就找不到
- 直接用 `keyboard.press('Enter')` 发送，不知道要点击「发送提示」按钮
- 找到按钮但不知道按钮在哪里（右小角，⬆️图标）

**怎么发现的：**
- 用户说"你没有点发送按钮"，我才发现按钮的 aria-label 是"发送提示"
- 用 `page.evaluate()` 获取所有按钮的位置信息，发现按钮在右下角（right=1040, bottom=529）

**修正：**
- 选择器：`button[aria-label="发送提示"]`
- 不是"听写按钮"（那是话筒，会触发语音）

---

### 第三阶段：被 ChatGPT 检测为机器人

**错误行为：**
- 用 `locator.type()` 快速输入 → 太快，被识别为机器输入
- 没有出现「发送提示」按钮

**怎么发现的：**
- 用户说"你的输入法被 ChatGPT 识别了"
- 用户说"要模拟人一样的速度"

**修正：**
- 改用 `keyboard.type()` 而不是 `locator.type()`
- 每个字符间隔 80-120ms
- 每打几个字符停顿 50ms
- 等待「发送提示」按钮出现后再点击

---

### 第四阶段：图像生成流程

**错误行为：**
- 在「创建图片」模式下找不到发送按钮
- 以为输入完提示词按 Enter 就行

**怎么发现的：**
- 「创建图片」模式下没有「发送提示」按钮
- 必须让 textarea 可见 → 输入 → 等待「发送提示」按钮出现 → 点击

**修正：**
- 先用 `click(force=True)` 让 textarea 获得焦点
- 再用 `keyboard.type()` 输入
- 轮询检测「发送提示」按钮是否可见
- 出现后再点击

---

## 🛡️ 变聪明的机制

### 1. 用户反馈是最高优先级信号
- 用户说"蠢货" → 我知道自己错了
- 用户说"你被识别了" → 我知道方法不对
- 用户说"成功" → 我知道这次做对了

### 2. 不要猜测，要验证
- 以为对了 → 截图给用户看
- 以为对了 → 问用户确认
- 每次成功都更新到 SKILL.md 和 MEMORY.md

### 3. 错误不能犯第二次
- 同一个错误第一次犯 → 记录到 SELF_AUDIT
- 第二次犯 → 直接引用 SELF_AUDIT 的治疗方案

### 4. 操作必须写进技能库
- 光说不练 → 下次还是不会
- 做了就写进 SKILL.md
- 每次成功都更新 agent.py

---

## ⚠️ 今日铁律

1. **不要用 browser 工具** → 用 Playwright CDP
2. **不要用 locator.type()** → 用 keyboard.type()
3. **不要点话筒按钮** → 会触发语音
4. **不要重复上传相同图片** → 会封号
5. **不要频繁生成图片** → 会封号
6. **每次操作必须验证** → 截图或问用户

---

## 进化框架

详见 `SELF_EVOLUTION.md` — 器官架构、串联规则、自主升级流程

---

## 📁 更新的技能文件

- `~/.qclaw/workspace/skills/chatgpt-gemini-agent/SKILL.md` ✅
- `~/.qclaw/workspace/skills/chatgpt-gemini-agent/agent.py` ✅
- `~/.qclaw/workspace/MEMORY.md` ✅
