---
name: chatgpt-image-gen
description: 使用 ChatGPT 的 DALL-E 生成图片。触发场景：(1) 用户要求用 ChatGPT 创建/生成图片；(2) 用户要求 AI 作画；(3) 需要调用 ChatGPT 的图像生成功能。技能包含通过 Playwright CDP 连接已登录的 Chrome，完成「创建图片」操作全流程。禁止在无用户指示时连续创作，动作要慢、拟人化，避免触发封号机制。
---

# ChatGPT 图像生成技能

## 核心操作流程

1. **连接 Chrome**（通过 Playwright CDP，端口 9222，Profile 34）
2. **打开 ChatGPT**：`https://chatgpt.com`（已登录 kaisenaipha@gmail.com）
3. **点击创作**：点击 `➕` → 「创建图片」
4. **输入提示词**：在输入框填写，**按 Enter**（不是点发送按钮）
5. **等待生成**：轮询等待图片出现
6. **下载图片**：curl 下载到本地
7. **立即停止**：无用户指示不继续

## 安全红线

- ❌ 不点话筒/听写按钮
- ❌ 不重复上传相同图片（会封号）
- ❌ 不抽风式连续操作，动作要慢
- ❌ 无用户明确指示不继续创作

## 详细协议

完整操作细节、Chrome 连接方式、下载逻辑 → 见 `references/OPERATIONAL_PROTOCOL.md`

## 脚本工具

- `scripts/chatgpt_image_gen.py` — 可独立调用的 Python 封装（自动处理连接、截图、下载）
