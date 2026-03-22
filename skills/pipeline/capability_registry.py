"""
capability_registry.py — 小龙虾能力注册表 + 自我进化引擎
S+ 级别能力管理系统

维度体系：
  👁️ 感知 (perception)    — 眼睛：信息获取、读取、识别
  👂 认知 (cognition)    — 耳朵：理解、分析、推理
  🧠 大脑 (brain)        — 决策、规划、创意
  💾 记忆 (memory)        — 短期/长期/语义记忆
  🔧 工具 (tools)         — 串联、执行、自动化
  ⏰ 主动 (proactive)     — 自我驱动、主动发现
  📤 输出 (output)        — 呈现、沟通、呈现

质量等级：
  🌀 无缝等级 (0-10)     — 多工具协作流畅程度
  🛡️ 安全等级 (0-10)     — 操作安全、权限控制
  🎯 丝滑等级 (0-10)     — 用户体验、延迟、稳定性
  🧠 智商等级 (0-10)     — 推理质量、决策准确性

进化状态：
  active    — 正常运行
  upgraded  — 已升级
  evolving  — 进化中
  degraded  — 能力下降
  missing   — 缺失/未安装
  blocked   — 被阻止（需人工授权）
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

WORKSPACE = Path.home() / ".qclaw" / "workspace"
REGISTRY_FILE = WORKSPACE / "CAPABILITY_REGISTRY.json"
EVOLUTION_LOG = WORKSPACE / "memory" / "evolution_log.json"

# ─── 能力定义 ───────────────────────────────────────────────

CAPABILITIES = {
    # 👁️ 感知 (眼睛)
    "perception_web_browser": {
        "name": "网页浏览",
        "name_en": "Web Browser",
        "category": "perception",
        "emoji": "👁️",
        "description": "读取网页、截图、UI自动化",
        "weight": 0.9,
        "dimensions": {
            "无缝": 8, "安全": 9, "丝滑": 7, "智商": 8
        },
        "tools": ["browser", "web_fetch", "agent-browser"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "discover"
    },
    "perception_file_reader": {
        "name": "文件读取",
        "name_en": "File Reader",
        "category": "perception",
        "emoji": "👁️",
        "description": "PDF/Word/Excel/PPT/图片解析",
        "weight": 0.85,
        "dimensions": {
            "无缝": 8, "安全": 9, "丝滑": 8, "智商": 8
        },
        "tools": ["pdf skill", "docx skill", "xlsx skill", "pptx skill"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "manual"
    },
    "perception_search": {
        "name": "搜索",
        "name_en": "Search Engine",
        "category": "perception",
        "emoji": "👁️",
        "description": "多搜索引擎聚合、智能搜索",
        "weight": 0.8,
        "dimensions": {
            "无缝": 9, "安全": 9, "丝滑": 9, "智商": 7
        },
        "tools": ["web_search", "multi-search-engine", "x-search"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "discover"
    },
    "perception_api": {
        "name": "API数据获取",
        "name_en": "API Crawler",
        "category": "perception",
        "emoji": "👁️",
        "description": "HTTP请求、API调用、实时数据",
        "weight": 0.8,
        "dimensions": {
            "无缝": 7, "安全": 7, "丝滑": 8, "智商": 7
        },
        "tools": ["http_pool.py", "crawl_pipeline.py", "crawl4ai"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "discover"
    },

    # 👂 认知 (耳朵)
    "cognition_understanding": {
        "name": "语义理解",
        "name_en": "Semantic Understanding",
        "category": "cognition",
        "emoji": "👂",
        "description": "意图识别、上下文理解、置信度判断",
        "weight": 0.9,
        "dimensions": {
            "无缝": 8, "安全": 10, "丝滑": 8, "智商": 8
        },
        "tools": ["MiniMax-M2 (当前模型)"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "manual"
    },
    "cognition_reasoning": {
        "name": "推理分析",
        "name_en": "Reasoning",
        "category": "cognition",
        "emoji": "👂",
        "description": "CoT/ToT推理、多步分析、因果推断",
        "weight": 0.85,
        "dimensions": {
            "无缝": 7, "安全": 10, "丝滑": 7, "智商": 7
        },
        "tools": ["reasoning_log.py", "scenario_engine.py"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "discover"
    },
    "cognition_classification": {
        "name": "Cynefin分类",
        "name_en": "Cynefin Classification",
        "category": "cognition",
        "emoji": "👂",
        "description": "问题类型自动识别、复杂度判断",
        "weight": 0.7,
        "dimensions": {
            "无缝": 7, "安全": 10, "丝滑": 8, "智商": 8
        },
        "tools": ["SOUL.md 内置"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "manual"
    },

    # 🧠 大脑
    "brain_planning": {
        "name": "任务规划",
        "name_en": "Task Planning",
        "category": "brain",
        "emoji": "🧠",
        "description": "目标拆解、步骤规划、优先级排序",
        "weight": 0.85,
        "dimensions": {
            "无缝": 6, "安全": 8, "丝滑": 6, "智商": 7
        },
        "tools": ["goal_tracker.py", "goal_manager.py", "autopilot.py"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "discover"
    },
    "brain_creativity": {
        "name": "创意生成",
        "name_en": "Creative Generation",
        "category": "brain",
        "emoji": "🧠",
        "description": "文案创作、方案设计、故事编写",
        "weight": 0.75,
        "dimensions": {
            "无缝": 7, "安全": 8, "丝滑": 7, "智商": 7
        },
        "tools": ["content-factory", "canvas-design", "video-script"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "discover"
    },
    "brain_decision": {
        "name": "决策建议",
        "name_en": "Decision Making",
        "category": "brain",
        "emoji": "🧠",
        "description": "利弊分析、风险评估、最优推荐",
        "weight": 0.7,
        "dimensions": {
            "无缝": 6, "安全": 8, "丝滑": 7, "智商": 7
        },
        "tools": ["feedback.py", "evolution_engine.py"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "discover"
    },

    # 💾 记忆
    "memory_session": {
        "name": "会话记忆",
        "name_en": "Session Memory",
        "category": "memory",
        "emoji": "💾",
        "description": "当前会话上下文、短期记忆",
        "weight": 0.9,
        "dimensions": {
            "无缝": 9, "安全": 10, "丝滑": 9, "智商": 9
        },
        "tools": ["内置上下文"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "always"
    },
    "memory_longterm": {
        "name": "长期记忆",
        "name_en": "Long-term Memory",
        "category": "memory",
        "emoji": "💾",
        "description": "MEMORY.md + daily notes 持久化",
        "weight": 0.85,
        "dimensions": {
            "无缝": 7, "安全": 10, "丝滑": 7, "智商": 7
        },
        "tools": ["memory_search", "memory_get", "MEMORY.md"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "manual"
    },
    "memory_semantic": {
        "name": "语义记忆",
        "name_en": "Semantic Memory (mem0)",
        "category": "memory",
        "emoji": "💾",
        "description": "向量语义搜索、跨会话关联",
        "weight": 0.8,
        "dimensions": {
            "无缝": 7, "安全": 8, "丝滑": 7, "智商": 7
        },
        "tools": ["mem0ai", "semantic_memory.py", "mem0_bridge.py"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "discover"
    },
    "memory_task_queue": {
        "name": "任务队列",
        "name_en": "Task Queue",
        "category": "memory",
        "emoji": "💾",
        "description": "未完成任务持久化、断点续执行",
        "weight": 0.8,
        "dimensions": {
            "无缝": 8, "安全": 9, "丝滑": 8, "智商": 8
        },
        "tools": ["task_queue.py"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "always"
    },

    # 🔧 工具
    "tool_code_execution": {
        "name": "代码执行",
        "name_en": "Code Execution",
        "category": "tools",
        "emoji": "🔧",
        "description": "Python/Shell脚本执行、代码生成",
        "weight": 0.9,
        "dimensions": {
            "无缝": 8, "安全": 6, "丝滑": 8, "智商": 8
        },
        "tools": ["exec", "qwen-agent"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "manual"
    },
    "tool_browser_auto": {
        "name": "浏览器自动化",
        "name_en": "Browser Automation",
        "category": "tools",
        "emoji": "🔧",
        "description": "Playwright/agent-browser网页操作",
        "weight": 0.85,
        "dimensions": {
            "无缝": 7, "安全": 7, "丝滑": 6, "智商": 7
        },
        "tools": ["browser_control.py", "agent-browser", "human_browser.py"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "discover"
    },
    "tool_skill_creation": {
        "name": "技能创建",
        "name_en": "Skill Creator",
        "category": "tools",
        "emoji": "🔧",
        "description": "自建Pipeline脚本、新技能开发",
        "weight": 0.8,
        "dimensions": {
            "无缝": 6, "安全": 8, "丝滑": 6, "智商": 7
        },
        "tools": ["skill-creator", "自建26个pipeline脚本"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "manual"
    },
    "tool_subagent": {
        "name": "子Agent编排",
        "name_en": "SubAgent Orchestration",
        "category": "tools",
        "emoji": "🔧",
        "description": "并行任务分解、多路执行",
        "weight": 0.75,
        "dimensions": {
            "无缝": 5, "安全": 8, "丝滑": 5, "智商": 7
        },
        "tools": ["sessions_spawn", "agent_loop.py"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "discover"
    },

    # ⏰ 主动
    "proactive_heartbeat": {
        "name": "心跳检测",
        "name_en": "Heartbeat Engine",
        "category": "proactive",
        "emoji": "⏰",
        "description": "周期性主动检查、弱信号发现",
        "weight": 0.8,
        "dimensions": {
            "无缝": 7, "安全": 9, "丝滑": 7, "智商": 7
        },
        "tools": ["heartbeat_engine.py", "HEARTBEAT.md"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "always"
    },
    "proactive_cron": {
        "name": "定时调度",
        "name_en": "Cron Scheduler",
        "category": "proactive",
        "emoji": "⏰",
        "description": "精确时间任务、周期执行",
        "weight": 0.85,
        "dimensions": {
            "无缝": 8, "安全": 9, "丝滑": 8, "智商": 8
        },
        "tools": ["cron tool"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "always"
    },
    "proactive_self_heal": {
        "name": "自我修复",
        "name_en": "Self Healer",
        "category": "proactive",
        "emoji": "⏰",
        "description": "自动检测异常、自动修复能力",
        "weight": 0.75,
        "dimensions": {
            "无缝": 6, "安全": 9, "丝滑": 6, "智商": 7
        },
        "tools": ["self_healer.py"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "always"
    },
    "proactive_evolution": {
        "name": "自我进化",
        "name_en": "Evolution Engine",
        "category": "proactive",
        "emoji": "⏰",
        "description": "能力缺口发现、自动进化触发",
        "weight": 0.7,
        "dimensions": {
            "无缝": 4, "安全": 8, "丝滑": 5, "智商": 6
        },
        "tools": ["evolution_engine.py"],
        "status": "evolving",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "discover"
    },

    # 📤 输出
    "output_text": {
        "name": "文字输出",
        "name_en": "Text Output",
        "category": "output",
        "emoji": "📤",
        "description": "多渠道文字消息、格式化回复",
        "weight": 0.9,
        "dimensions": {
            "无缝": 9, "安全": 10, "丝滑": 9, "智商": 8
        },
        "tools": ["message", "webchat"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "always"
    },
    "output_voice": {
        "name": "语音合成",
        "name_en": "TTS",
        "category": "output",
        "emoji": "📤",
        "description": "文字转语音、语音播报",
        "weight": 0.7,
        "dimensions": {
            "无缝": 7, "安全": 10, "丝滑": 7, "智商": 7
        },
        "tools": ["tts tool"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "manual"
    },
    "output_canvas": {
        "name": "可视化画布",
        "name_en": "Canvas Renderer",
        "category": "output",
        "emoji": "📤",
        "description": "HTML/React图表渲染、交互展示",
        "weight": 0.65,
        "dimensions": {
            "无缝": 6, "安全": 9, "丝滑": 6, "智商": 7
        },
        "tools": ["canvas tool"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "discover"
    },

    # 🌐 平台集成
    "platform_messaging": {
        "name": "消息通道",
        "name_en": "Messaging Channels",
        "category": "platform",
        "emoji": "🌐",
        "description": "Telegram/WhatsApp/Discord/Signal",
        "weight": 0.85,
        "dimensions": {
            "无缝": 8, "安全": 8, "丝滑": 8, "智商": 8
        },
        "tools": ["message tool"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "manual"
    },
    "platform_calendar": {
        "name": "日历集成",
        "name_en": "Calendar Integration",
        "category": "platform",
        "emoji": "🌐",
        "description": "Apple日历/飞书/钉钉日程管理",
        "weight": 0.75,
        "dimensions": {
            "无缝": 7, "安全": 8, "丝滑": 7, "智商": 7
        },
        "tools": ["schedule-skill"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "manual"
    },
    "platform_cloud_docs": {
        "name": "云文档",
        "name_en": "Cloud Documents",
        "category": "platform",
        "emoji": "🌐",
        "description": "腾讯文档/Google Docs/Notion",
        "weight": 0.75,
        "dimensions": {
            "无缝": 7, "安全": 7, "丝滑": 7, "智商": 7
        },
        "tools": ["tencent-docs", "api-gateway"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "manual"
    },
    "platform_wecom": {
        "name": "企业微信",
        "name_en": "WeCom MCP",
        "category": "platform",
        "emoji": "🌐",
        "description": "企业微信MCP工具调用",
        "weight": 0.7,
        "dimensions": {
            "无缝": 6, "安全": 7, "丝滑": 6, "智商": 6
        },
        "tools": ["wecom_mcp"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "manual"
    },

    # 🔬 AI模型能力
    "model_primary": {
        "name": "主模型(MiniMax-M2)",
        "name_en": "Primary Model",
        "category": "model",
        "emoji": "🤖",
        "description": "主推理模型，通用对话理解",
        "weight": 0.95,
        "dimensions": {
            "无缝": 8, "安全": 9, "丝滑": 8, "智商": 8
        },
        "tools": ["MiniMax-M2"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "manual"
    },
    "model_groq": {
        "name": "Groq加速模型",
        "name_en": "Groq Fast Model",
        "category": "model",
        "emoji": "🤖",
        "description": "Groq路由Llama3.3/3.1，pipeline专用",
        "weight": 0.85,
        "dimensions": {
            "无缝": 8, "安全": 8, "丝滑": 9, "智商": 8
        },
        "tools": ["litellm + Groq API"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "discover"
    },
    "model_qwen": {
        "name": "Qwen Agent",
        "name_en": "Qwen Agent Framework",
        "category": "model",
        "emoji": "🤖",
        "description": "Qwen Agent框架，本地推理",
        "weight": 0.7,
        "dimensions": {
            "无缝": 6, "安全": 9, "丝滑": 6, "智商": 6
        },
        "tools": ["qwen-agent venv"],
        "status": "active",
        "last_upgraded": None,
        "evolution_history": [],
        "auto_upgrade_policy": "discover"
    },
}

# 待升级能力清单
PENDING_UPGRADES = {
    "brain_planning": {
        "current_score": 6.3,
        "target_score": 8.0,
        "gap": 1.7,
        "upgrade_plan": "引入OODA循环 + WAL Protocol，增强任务拆解深度",
        "priority": "high",
        "estimated_effect": "任务规划无缝度+2, 丝滑度+2"
    },
    "proactive_evolution": {
        "current_score": 5.1,
        "target_score": 8.0,
        "gap": 2.9,
        "upgrade_plan": "实现完全自主进化引擎，置信<70%时自动启动进化",
        "priority": "critical",
        "estimated_effect": "进化效率+3, 智商+2"
    },
    "tool_subagent": {
        "current_score": 6.0,
        "target_score": 8.0,
        "gap": 2.0,
        "upgrade_plan": "引入Agent Teams编排协议，多路并行任务协同",
        "priority": "high",
        "estimated_effect": "子agent协作能力+2.5"
    },
    "output_canvas": {
        "current_score": 6.4,
        "target_score": 8.5,
        "gap": 2.1,
        "upgrade_plan": "升级到React+shadcn/ui，支持复杂可视化仪表盘",
        "priority": "medium",
        "estimated_effect": "可视化能力+2.5"
    },
    "platform_wecom": {
        "current_score": 6.3,
        "target_score": 8.0,
        "gap": 1.7,
        "upgrade_plan": "扩展企业微信MCP品类，接入更多内部系统",
        "priority": "medium",
        "estimated_effect": "企业微信覆盖度+2"
    }
}

# 进化策略配置
EVOLUTION_POLICY = {
    "mode": "supervised",  # supervised | autonomous | hybrid
    "auto_upgrade_policy": {
        "always": "立即自动执行，无需确认",
        "discover": "自动发现，但需要人工确认",
        "manual": "仅人工触发"
    },
    "red_lines": [
        "不对外发送任何内容（邮件/消息/帖子）",
        "不删除任何文件（trash > rm）",
        "不修改AGENTS.md/SOUL.md等核心人格文件",
        "不安装未经skill-vetter审查的技能",
        "任何破坏性操作前必须确认"
    ],
    "checkpoints": {
        "pre_upgrade": "能力现状记录、备份",
        "post_upgrade": "验证所有能力完整、回退预案",
        "daily_review": "每日心跳时自动检查能力漂移"
    }
}


# ─── 核心函数 ───────────────────────────────────────────────

def load_registry() -> dict:
    """加载注册表"""
    if REGISTRY_FILE.exists():
        with open(REGISTRY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "version": "1.0",
        "last_updated": datetime.now().isoformat(),
        "capabilities": CAPABILITIES,
        "pending_upgrades": PENDING_UPGRADES,
        "evolution_policy": EVOLUTION_POLICY,
        "evolution_log": [],
        "health_summary": {}
    }


def save_registry(registry: dict):
    """保存注册表"""
    registry["last_updated"] = datetime.now().isoformat()
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_FILE, 'w', encoding='utf-8') as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)


def compute_category_scores(registry: dict) -> dict:
    """按类别计算加权平均分"""
    categories = {}
    for cap_id, cap in registry["capabilities"].items():
        cat = cap["category"]
        dims = cap["dimensions"]
        avg = (dims["无缝"] + dims["安全"] + dims["丝滑"] + dims["智商"]) / 4
        weight = cap["weight"]
        if cat not in categories:
            categories[cat] = {"total_score": 0, "total_weight": 0}
        categories[cat]["total_score"] += avg * weight
        categories[cat]["total_weight"] += weight
    
    result = {}
    for cat, data in categories.items():
        result[cat] = round(data["total_score"] / data["total_weight"], 2) if data["total_weight"] > 0 else 0
    return result


def compute_overall_score(registry: dict) -> float:
    """计算综合能力分数"""
    cat_scores = compute_category_scores(registry)
    weights = {
        "perception": 0.20, "cognition": 0.15, "brain": 0.15,
        "memory": 0.15, "tools": 0.15, "proactive": 0.10, "output": 0.05, "platform": 0.05
    }
    total = sum(cat_scores.get(cat, 0) * weights.get(cat, 0) for cat in weights)
    return round(total, 2)


def get_health_summary(registry: dict) -> dict:
    """生成健康报告"""
    cat_scores = compute_category_scores(registry)
    overall = compute_overall_score(registry)
    
    weakest = sorted(cat_scores.items(), key=lambda x: x[1])[:3]
    strongest = sorted(cat_scores.items(), key=lambda x: -x[1])[:3]
    
    critical = [k for k, v in registry.get("pending_upgrades", {}).items() 
                 if v.get("priority") == "critical"]
    
    return {
        "overall_score": overall,
        "category_scores": cat_scores,
        "weakest_categories": weakest,
        "strongest_categories": strongest,
        "critical_upgrades": critical,
        "total_capabilities": len(registry["capabilities"]),
        "active_capabilities": sum(1 for c in registry["capabilities"].values() if c.get("status") == "active"),
        "evolving_capabilities": sum(1 for c in registry["capabilities"].values() if c.get("status") == "evolving")
    }


def log_evolution(registry: dict, cap_id: str, action: str, details: str):
    """记录进化日志"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "capability_id": cap_id,
        "action": action,
        "details": details,
        "cap_name": registry["capabilities"].get(cap_id, {}).get("name", cap_id)
    }
    registry.setdefault("evolution_log", []).insert(0, entry)
    # 只保留最近100条
    registry["evolution_log"] = registry["evolution_log"][:100]


def upgrade_capability(cap_id: str, new_dims: dict, notes: str = "") -> dict:
    """升级某个能力的维度分数"""
    registry = load_registry()
    if cap_id not in registry["capabilities"]:
        return {"success": False, "error": f"Capability {cap_id} not found"}
    
    cap = registry["capabilities"][cap_id]
    old_dims = cap["dimensions"].copy()
    
    # 更新维度
    for k, v in new_dims.items():
        if k in cap["dimensions"]:
            cap["dimensions"][k] = max(0, min(10, v))
    
    cap["last_upgraded"] = datetime.now().isoformat()
    cap["evolution_history"].append({
        "timestamp": datetime.now().isoformat(),
        "old_dims": old_dims,
        "new_dims": new_dims,
        "notes": notes
    })
    
    log_evolution(registry, cap_id, "upgraded", f"更新维度: {old_dims} -> {new_dims}。备注: {notes}")
    
    # 更新健康报告
    registry["health_summary"] = get_health_summary(registry)
    save_registry(registry)
    
    return {
        "success": True,
        "cap_id": cap_id,
        "old_dims": old_dims,
        "new_dims": new_dims,
        "new_health": registry["health_summary"]
    }


def get_full_report() -> dict:
    """获取完整能力报告"""
    registry = load_registry()
    health = get_health_summary(registry)
    return {
        "registry": registry,
        "health": health,
        "category_scores": compute_category_scores(registry),
        "overall_score": health["overall_score"]
    }


def init_registry():
    """初始化注册表"""
    registry = load_registry()
    registry["capabilities"] = CAPABILITIES
    registry["pending_upgrades"] = PENDING_UPGRADES
    registry["evolution_policy"] = EVOLUTION_POLICY
    registry["health_summary"] = get_health_summary(registry)
    save_registry(registry)
    print(f"✅ 能力注册表初始化完成")
    print(f"   能力总数: {len(CAPABILITIES)}")
    print(f"   综合评分: {registry['health_summary']['overall_score']}/10")
    return registry


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--init":
        init_registry()
    elif len(sys.argv) > 1 and sys.argv[1] == "--report":
        report = get_full_report()
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "--health":
        registry = load_registry()
        health = get_health_summary(registry)
        print(json.dumps(health, ensure_ascii=False, indent=2))
    else:
        print("用法:")
        print("  python3 capability_registry.py --init    # 初始化注册表")
        print("  python3 capability_registry.py --report   # 完整报告")
        print("  python3 capability_registry.py --health   # 健康摘要")
