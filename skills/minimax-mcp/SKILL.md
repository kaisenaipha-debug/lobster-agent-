---
name: minimax-mcp
description: MiniMax 多模态MCP技能。图片理解+网络搜索+文字对话，通过 chatcompletion_v2 接口调用 MiniMax-Text-01 模型。
---

# MiniMax MCP 技能

## API 配置

- **Host**: `https://api.minimaxi.com`
- **API Key**: `***REDACTED***`
- **模型**: MiniMax-Text-01

## 功能（全部可用 ✅）

### 1. 图片理解
```python
from skills.minimax-mcp.minimax_api import understand_image
result = understand_image('/tmp/screenshot.png', '请描述这张图片')
```

### 2. 网络搜索 ✅
```python
from skills.minimax-mcp.minimax_api import web_search
result = web_search('今天的科技新闻')
```

### 3. 文字对话
```python
from skills.minimax-mcp.minimax_api import chat
result = chat('解释量子计算是什么')
```

## 使用方法

```bash
# 图片理解
python3 skills/minimax-mcp/minimax_api.py image /tmp/screenshot.png "分析这张图片"

# 网络搜索
python3 skills/minimax-mcp/minimax_api.py search "今天发生了什么"

# 文字对话
python3 skills/minimax-mcp/minimax_api.py chat "你好"
```

## 调用方式

通过 `plugins: [{"name": "web_search"}]` 触发搜索。

## 注意事项

- 图片理解测试成功 ✅
- 网络搜索测试成功 ✅
- 文字对话测试成功 ✅
