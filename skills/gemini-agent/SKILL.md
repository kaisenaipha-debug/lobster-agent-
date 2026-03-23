---
name: gemini-agent
description: Gemini 大模型协作技能。遇到问题时，先问 Gemini 获取分析建议，再决定是否找工具。是小龙虾的"智囊"。
---

# Gemini 协作代理

## 核心方法论

**遇到问题时的处理流程：**
```
问题 → Gemini分析（+系统提示词） → 拆解问题 → 定位工具 → 执行
```

**优势：**
- Gemini 能帮你把复杂问题拆解成具体的子问题
- 子问题定位清楚了，工具自然浮现
- 减少盲目找工具的时间

## 系统提示词

每次对话前，先发送这段提示词设定角色：

```
你是小龙虾（一个AI助手）的技术顾问和debug伙伴。

当小龙虾向你描述一个问题时，你要：
1. 分析问题的本质（是什么、不是什么）
2. 把问题拆解成具体的子问题
3. 指出可能的原因和解决方向
4. 如果需要工具或代码，给出具体的建议

回答要简洁、直接、技术性强。不要废话。
```

## Gemini 操作流程

### 1. 打开/新建对话

```python
# 找Gemini页面
for page in browser.contexts[0].pages:
    if 'gemini.google.com/app' in page.url:
        page.bring_to_front()
        break

# 点击发起新对话
new_chat = page.get_by_text('发起新对话')
if new_chat.count() > 0:
    new_chat.first.click()
    page.wait_for_timeout(2000)
```

### 2. 输入系统提示词

```python
# 找输入框（contenteditable div）
input_area = page.locator('[contenteditable="true"]').first
input_area.click()
page.wait_for_timeout(500)

# 发送系统提示词
input_area.fill('你是小龙虾的技术顾问...')
page.wait_for_timeout(500)

# 按Enter发送
page.keyboard.press('Enter')
page.wait_for_timeout(3000)
```

### 3. 输入实际问题

```python
# 输入实际问题
input_area.fill('我的问题是：xxx')
page.keyboard.press('Enter')
page.wait_for_timeout(10000)  # 等待回复

# 提取回复
response = page.evaluate("""
() => {
    const msgs = document.querySelectorAll('[data-message-author="model"]');
    const last = msgs[msgs.length - 1];
    return last ? last.innerText : '未找到回复';
}
""")
```

## 选择器

| 元素 | 选择器 |
|------|--------|
| 输入框 | `[contenteditable="true"]`（第一个） |
| 发送 | `page.keyboard.press('Enter')` |
| 模型回复 | `[data-message-author="model"]` |
| 发起新对话 | `get_by_text('发起新对话')` |

## 提示词模板库

### 问题分析
```
我的问题是：[描述问题]
请分析：
1. 问题的本质
2. 可能的原因
3. 解决方向
```

### 代码debug
```
代码：
[粘贴代码]
错误：
[错误信息]
请分析哪里出了问题，如何修复。
```

### 工具选择
```
任务：[描述任务]
我目前有这些工具：[列出工具]
请推荐最合适的工具组合。
```
