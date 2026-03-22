# Pipeline Suite — 能力链路集成技能 (v2.0)

> 🛡️ 安全状态: 所有包均运行于独立 venv 隔离环境  
> 🏆 升级日期: 2026-03-21

---

## 架构总览

```
用户输入
    ↓
Agent Loop（目标分解 → 执行 → 验证 → 记录）
    ↓
├── crawl4ai venv    → 网页爬取
├── browser_control → 浏览器控制（点击/填表/截图）
├── Groq             → 语义分析 / 任务分解 / 记忆标签
├── semantic_memory  → 向量级语义记忆
├── self_healer      → 健康检查 / 自动修复
└── goal_manager     → 目标追踪
```

---

## 工具清单

| 工具 | 路径 | 功能 | 状态 |
|------|------|------|------|
| agent_loop.py | skills/pipeline/ | 自主执行闭环 | ✅ |
| heartbeat_engine.py | skills/pipeline/ | 主动心跳引擎 | ✅ |
| goal_manager.py | skills/pipeline/ | 目标追踪管理 | ✅ |
| self_healer.py | skills/pipeline/ | 自动修复引擎 | ✅ |
| browser_control.py | skills/pipeline/ | 浏览器自动化 | ✅ |
| semantic_memory.py | skills/pipeline/ | 语义记忆层 | ✅ |
| crawl_pipeline.py | skills/pipeline/ | 爬取分析Pipeline | ✅ |
| mem0_bridge.sh | skills/pipeline/ | 记忆桥接 | ✅ |

---

## venv 隔离状态

| venv | 路径 | 包 | 状态 |
|------|------|-----|------|
| crawl4ai | ~/.qclaw/venvs/crawl4ai/ | crawl4ai + playwright | ✅ |
| qwen-agent | ~/.qclaw/venvs/qwen-agent/ | qwen-agent + numpy + scipy | ✅ |
| mem0ai | ~/.qclaw/venvs/mem0ai/ | mem0ai + qdrant-client | ✅ |

---

## 快速测试

```bash
# 健康检查
python3 ~/.qclaw/workspace/skills/pipeline/self_healer.py check

# 自主执行（示例）
python3 ~/.qclaw/workspace/skills/pipeline/agent_loop.py "搜索 Python 3.13 新特性" --auto-approve

# 浏览器控制
python3 ~/.qclaw/workspace/skills/pipeline/browser_control.py screenshot "https://example.com" --out /tmp/test.png

# 语义记忆
python3 ~/.qclaw/workspace/skills/pipeline/semantic_memory.py add "测试记忆"
python3 ~/.qclaw/workspace/skills/pipeline/semantic_memory.py search "测试"

# 目标追踪
python3 ~/.qclaw/workspace/skills/pipeline/goal_manager.py list
python3 ~/.qclaw/workspace/skills/pipeline/goal_manager.py next

# 爬取分析
~/.qclaw/venvs/crawl4ai/bin/python ~/.qclaw/workspace/skills/pipeline/crawl_pipeline.py "https://example.com"
```

---

## 自我评分（vs 顶级龙虾 = 100分）

| 维度 | 得分 | 说明 |
|------|------|------|
| 工具能力 | 95 | 齐全，真实执行 |
| 主动性 | 55 | 心跳+随机任务调度 |
| 记忆语义 | 60 | Groq语义标签+搜索，超越关键词 |
| 执行闭环 | 80 | 分解→browser/crawl/python/search→验证 |
| 自我修复 | 75 | 真修复+诊断+回滚 |
| 浏览器操作 | 60 | 点击/填表/截图/交互序列 |
| 多模态 | 5 | 纯文本，截图→文件 |
| 长期规划 | 35 | 单轮分解，无持续状态机 |

**总分: ~62分**（从 43 升至 62）

---

## 剩余差距

1. 多模态（看图/听语音）— 需要 vision 模型
2. 持续状态机（跨会话追踪）— 需要后台进程
3. 真正向量记忆 — sentence-transformers 太大暂缓

---

*最后更新: 2026-03-21*
