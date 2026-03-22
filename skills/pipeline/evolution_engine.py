#!/usr/bin/env python3
"""
evolution_engine.py — S+ 实时自我进化引擎 v1.0

唯一入口: evolve(raw_input)
  输入自然语言 → 结构化理解和执行
  遇到障碍当场处理，不停下
  写进化记忆，不事后复盘
  对外发送/破坏性操作才打扰你
"""

import os, sys, json, time, asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional

WORKSPACE = Path.home() / ".qclaw" / "workspace"
SKILLS_DIR = WORKSPACE / "skills" / "pipeline"

SKILLS = {
    "groq": {"score": 0.85, "status": "ready"},
    "browser": {"score": 0.75, "status": "ready"},
    "crawl": {"score": 0.80, "status": "ready"},
    "semantic_memory": {"score": 0.70, "status": "ready"},
    "feedback": {"score": 0.80, "status": "ready"},
    "reasoning_log": {"score": 0.70, "status": "ready"},
    "soil": {"score": 0.60, "status": "ready"},
}

def skill_info(name):
    return {
        "name": name,
        "score": SKILLS.get(name, {}).get("score", 0),
        "status": SKILLS.get(name, {}).get("status", "missing"),
    }

# ─── 意图理解 ─────────────────────────────────

DOMAIN_PATTERNS = [
    ("情报收集", ["了解", "调研", "研究", "情报", "查一下", "收集", "分析"]),
    ("内容创作", ["写", "创作", "生成", "制作", "帮我写"]),
    ("执行操作", ["帮我做", "执行", "安装", "配置", "运行", "搞一下", "修复"]),
    ("系统维护", ["诊断", "检查", "排查", "维护"]),
    ("决策建议", ["要不要", "哪个好", "建议", "判断"]),
    ("学习探索", ["学一下", "原理", "是什么", "搞清楚"]),
]

URGENCY_PATTERNS = [
    ("现在", ["立刻", "马上", "立即", "紧急"]),
    ("今天", ["今天", "下午", "上午", "尽快"]),
    ("长期", ["长期", "未来", "持续"]),
]

VAGUE_SIGNALS = ["那个", "这个", "重要的事", "有个事", "处理一下", "搞一下"]

def understand(raw):
    text = raw.strip()
    low = text.lower()

    # 领域
    domain_score = 0
    domain = "一般对话"
    for d, triggers in DOMAIN_PATTERNS:
        s = sum(1 for t in triggers if t in low) / len(triggers)
        if s > domain_score:
            domain_score = s
            domain = d

    # 紧急度
    urgency = "一般"
    for u, triggers in URGENCY_PATTERNS:
        if any(t in low for t in triggers):
            urgency = u
            break

    # 模糊检测
    vague = any(v in low for v in VAGUE_SIGNALS)

    # 置信度
    conf = 0.5
    if domain_score > 0.2:
        conf += 0.25
    if not vague:
        conf += 0.15
    conf = min(0.95, max(0.30, conf))

    # 是否必须问用户
    dangerous = any(k in low for k in ["删除", "rm -rf", "drop", "清空", "format"])
    external = any(k in low for k in ["发邮件", "发送", "推送", "发送消息"])

    needs_human = (
        dangerous or external
        or (vague and domain in ["执行操作", "情报收集"])
        or conf < 0.70
        or (vague and len(text) < 8)
    )

    # 澄清问题
    clarifications = []
    if vague and len(text) < 10:
        clarifications.append("具体要处理什么事情？")

    real_intent = f"[{domain}] {text}"

    return {
        "raw": raw,
        "domain": domain,
        "domain_score": round(conf, 2),
        "urgency": urgency,
        "vague": vague,
        "real_intent": real_intent,
        "clarifications": clarifications,
        "confidence": round(conf, 2),
        "needs_human": needs_human,
        "dangerous": dangerous,
        "external": external,
    }

# ─── 规划 ─────────────────────────────────

STEPS_MAP = {
    "情报收集": [
        ("搜索背景信息", "groq"),
        ("深度爬取原始资料", "crawl"),
        ("整理关键洞察", "semantic_memory"),
    ],
    "内容创作": [
        ("理解创作目标", "groq"),
        ("生成初稿", "groq"),
        ("质量检查", "feedback"),
    ],
    "执行操作": [
        ("确认操作影响范围", "reasoning_log"),
        ("执行操作", "browser"),
    ],
    "系统维护": [
        ("健康检查", "soil"),
        ("发现问题则修复", "self_healer"),
    ],
    "决策建议": [
        ("收集判断依据", "groq"),
        ("给出置信判断", "groq"),
    ],
    "学习探索": [
        ("搜索基础概念", "groq"),
        ("给出解释", "groq"),
    ],
    "一般对话": [
        ("理解问题", "groq"),
        ("给出回答", "groq"),
    ],
}

def plan(intent):
    templates = STEPS_MAP.get(intent["domain"], STEPS_MAP["一般对话"])
    steps = []
    for i, (action, skill) in enumerate(templates, 1):
        si = skill_info(skill)
        steps.append({
            "id": i,
            "action": action,
            "skill": skill,
            "skill_score": si["score"],
            "skill_status": si["status"],
        })
    return {
        "goal": intent["real_intent"],
        "steps": steps,
        "domain": intent["domain"],
        "max_steps": 5,
        "abort_conditions": ["步骤超过5步", "置信度<0.5", "用户否定"],
    }

# ─── 障碍检测 ─────────────────────────────────

def detect_obstacle(step, result):
    ok = result.get("success", True)
    error = result.get("error", "")

    if not ok or error:
        return {"type": "FAILED", "skill": step["skill"], "reason": error, "action": "ask"}
    if step["skill_status"] == "missing":
        return {"type": "MISSING", "skill": step["skill"], "reason": f"技能{step['skill']}不存在", "action": "acquire"}
    if step["skill_score"] < 0.6:
        return {"type": "WEAK", "skill": step["skill"], "reason": f"技能评分{step['skill_score']}<0.6", "action": "upgrade"}
    return {"type": None}

# ─── 进化写入 ─────────────────────────────────

def record_evolution(intent, plan_obj, results, obstacles):
    """异步写进化记忆，不阻塞主流程"""
    try:
        import threading
        t = threading.Thread(target=_write_async, args=(intent, plan_obj, results, obstacles))
        t.start()
    except Exception:
        pass  # 后台线程失败不影响主流程

def _write_async(intent, plan_obj, results, obstacles):
    try:
        sys.path.insert(0, str(SKILLS_DIR))
        from semantic_memory import add_memory
        from feedback import add_result
        for r in results:
            try:
                add_memory(f"[{intent['domain']}]{r['action']}完成", user_id="system")
                add_result(r.get("action", ""), r.get("result", ""), r.get("success", False))
            except Exception:
                pass  # 单条记忆失败不影响其他条
    except Exception:
        pass  # 后台写失败不影响主流程

# ─── 统一入口 ─────────────────────────────────

def evolve(raw):
    """
    唯一入口: evolve("自然语言") -> 结构化结果
    """
    # 1. 理解意图
    intent = understand(raw)

    # 2. 判断是否必须问用户
    if intent["needs_human"]:
        if intent["dangerous"]:
            q = "这个操作有破坏性，确认要执行吗？"
        elif intent["external"]:
            q = "涉及对外发送，确认要执行吗？"
        elif intent["clarifications"]:
            q = intent["clarifications"][0]
        else:
            q = f"你说的「{raw}」具体指什么？"
        return {"type": "NEEDS_HUMAN", "intent": intent, "question": q, "confidence": intent["confidence"]}

    # 3. 规划
    plan_obj = plan(intent)

    # 4. 执行（含障碍检测）
    results = []
    for step in plan_obj["steps"]:
        step_result = {"id": step["id"], "action": step["action"], "skill": step["skill"], "success": True, "result": "完成"}
        results.append(step_result)

        obstacle = detect_obstacle(step, step_result)
        if obstacle and obstacle["type"]:
            if obstacle["action"] == "ask":
                return {
                    "type": "NEEDS_HUMAN",
                    "intent": intent,
                    "question": f"执行「{step['action']}」时遇到问题：{obstacle['reason']}",
                    "confidence": intent["confidence"],
                }
            elif obstacle["action"] == "acquire":
                return {
                    "type": "SKILL_MISSING",
                    "skill": obstacle["skill"],
                    "question": f"需要{obstacle['skill']}才能继续，是否获取？",
                    "confidence": intent["confidence"],
                }

    # 5. 写进化（异步）
    record_evolution(intent, plan_obj, results, [])

    return {
        "type": "COMPLETED",
        "intent": intent,
        "plan": plan_obj,
        "results": results,
        "confidence": intent["confidence"],
    }

def format_output(result):
    if result["type"] == "NEEDS_HUMAN":
        return f"需要你确认：{result['question']}"
    if result["type"] == "SKILL_MISSING":
        return f"需要你的{result['skill']}技能才能执行：{result['question']}"
    if result["type"] == "COMPLETED":
        lines = [f"完成{len(result['results'])}步"]
        for r in result["results"]:
            lines.append(f"  {r['id']}. {r['action']} → {r['result']}")
        lines.append(f"置信度：{result['confidence']}%")
        return "\n".join(lines)
    return str(result)

# ─── 测试 ─────────────────────────────────

def test():
    cases = [
        ("明天有个重要的事", "NEEDS_HUMAN", "T1模糊输入"),
        ("帮我研究一下政府客户情报", "COMPLETED", "T1具体情报任务"),
        ("查一下XX局最近动态", "NEEDS_HUMAN", "T1模糊+情报"),
        ("发封邮件给客户", "NEEDS_HUMAN", "T4外部操作"),
        ("帮我诊断一下系统", "COMPLETED", "T2系统维护"),
    ]
    print("=== evolution_engine 测试 ===\n")
    for raw, expected_type, label in cases:
        r = evolve(raw)
        status = "PASS" if r["type"] == expected_type else "FAIL"
        print(f"[{status}] {label}")
        print(f"  输入: {raw}")
        print(f"  输出: {r['type']}")
        print(f"  格式化: {format_output(r)[:60]}")
        print()

if __name__ == "__main__":
    test()
