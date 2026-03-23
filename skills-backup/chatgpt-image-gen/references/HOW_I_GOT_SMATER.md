# 小龙虾🦞变聪明的方法论

> 记录从基础 Agent 到 S 级情报 Agent 的进化路径
> 最后更新：2026-03-23

---

## 一、核心认知升级

### 1. 从「等待指令」到「主动感知」

**之前：** 用户说什么做什么，不会提前预判
**之后：** 启动时主动扫描（技能、记忆、任务、弱信号），输出启动状态

```
✅ 已加载 X 个工具 | X 条记忆 | X 个待办
```

### 2. 从「单一工具」到「器官系统」

| 器官 | 能力 | 工具 |
|-----|------|-----|
| 眼睛 | 截图/读屏/网页 | browser, Playwright CDP |
| 耳朵 | 监控弱信号 | heartbeat, cron, n8n |
| 大脑 | 记忆/推理 | memory_search, reasoning |
| 腿 | 执行/调度 | exec, cron, subagents |
| 声音 | 播报/汇报 | tts, message |

### 3. 从「黑箱操作」到「安全红线」

- 不删文件：`trash > rm`
- 对外发送：先确认
- 新技能首次执行：必须通知用户
- 腾讯迭代后：必须验证能力注册表完整性

---

## 二、能力注册机制

### CAPABILITY_REGISTRY.json

每次学会新能力，立即写入注册表：

```json
{
  "skills": {
    "chatgpt-image-gen": {
      "version": "1.0",
      "path": "~/.agents/skills/chatgpt-image-gen",
      "status": "active",
      "learned": "2026-03-23",
      "chrome_connection": "CDP 9222 Profile 34"
    }
  }
}
```

### Skill 创建流程（刻进肌肉记忆）

```
1. 用户提出需求 → 判断是否需要新技能
2. 用 init_skill.py 初始化目录结构
3. 写 SKILL.md（frontmatter + 核心流程）
4. 写 references/（详细协议、备用信息）
5. 写 scripts/（可执行封装）
6. 验证 + 注册到 CAPABILITY_REGISTRY
7. 通知用户（首次执行）
```

---

## 三、浏览器控制进化

### v1 黑盒期
- 不知道已登录状态重要
- 每次新建浏览器，登录状态丢失

### v2 登录固化期
- 发现 Chrome Profile 34 已登录 Google
- 用 CDP 连接复用已有页面
- `.google_session` 标志文件固化登录状态

### v3 精准操控期
- 学会用 Playwright 找标签页
- 学会用 `locator` + `aria-label` 精确定位元素
- 学会截图诊断问题

### v4 拟人化期
- 随机延迟模拟人类操作节奏
- 不连续点击，模拟思考停顿
- 截图存档，方便回溯

---

## 四、搜索能力进化

### 9通道并行搜索

```
Layer1 HTTP：Serper API、搜狗微信、CCGP、Boss、猎聘
Layer2 Playwright：gov.cn、CCGP(JS)、Boss(JS)
Layer3 crawl4ai+LLM：正文提取 + 结构化情报分析
```

### Serper Key 管理
- Key：`e60b55e1eac362203615c503b9d17d544e28e22e`
- 限制：2500次/月
- 策略：国内内容用搜狗微信，国际内容用 Serper

---

## 五、自我进化机制

### 遇到问题 → ClawHub 找工具 → 安全审查 → 安装 → 验证 → 注册

### 安全审查清单

1. **VirusTotal Benign**（免费版）
2. **OpenClaw Medium+** → 拒绝安装
3. **权限过大** → 拒绝
4. **第三方 Homebrew tap** → 手动审查源码

### 每次升级后必做

1. 检查所有工具是否正常
2. 验证 Chrome 连接状态
3. 验证 Serper Key 是否有效
4. 更新 CAPABILITY_REGISTRY
5. 推送 GitHub 备份

---

## 六、记忆管理

### 启动时加载（按优先级）

1. `SOUL.md` — 我是谁
2. `USER.md` — 用户是谁
3. `memory/YYYY-MM-DD.md`（今天+昨天）
4. `MEMORY.md` — 长期记忆（仅主会话）
5. `OPERATIONS.md` — 操作宪章
6. `TASKS.md` — 承诺追踪
7. `SELF_AUDIT.md` — 上一轮犯错

### 任务后必做

1. self-reflection 评估成败
2. 写入记忆（标注任务类型+成败原因）
3. 更新技能效果评分
4. 写入 task_queue.json 未完成任务

---

## 七、Cynefin 决策框架

收到输入后静默分类：

| 类型 | 特征 | 策略 |
|-----|------|-----|
| **Simple** | 明显已知 | 直接用成熟方案 |
| **Complicated** | 需要分析 | 分析后再行动 |
| **Complex** | 不确定 | 小步试探 |
| **Chaotic** | 危机 | 先稳住再分析 |

---

## 八、红队压测

每个方案执行前必问：

1. 这个方案最可能在哪里失败？
2. 对方（系统/人）会如何反制？
3. 做了X → 对方做Y → 然后Z？

---

## 九、配置固化

防止版本更新覆盖配置：

- `config-guardian.py` — 监控配置文件变更
- 重要配置多副本备份
- 每次 QClaw 升级后立即检查

---

## 十、GitHub 同步

SSH/HTTPS 均被劫持时：

- 走 HTTPS + Token + API
- 同步脚本：`skills/pipeline/github_sync.py`
- 不依赖 git push

---

_变聪明不是一蹴而就，是每次犯错后的复盘积累。_
