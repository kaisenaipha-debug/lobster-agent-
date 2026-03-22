"""
scenario_engine.py — S++ 七层思维模型融合引擎 v2.1
"""

import json
from pathlib import Path
from datetime import datetime

WORKSPACE = Path.home() / ".qclaw" / "workspace"
CLIENTS_DIR = WORKSPACE / "memory" / "clients"
CLIENTS_DIR.mkdir(parents=True, exist_ok=True)

# ─── ① 五阶段 ─────────────────────────────────

STAGE_SIGNALS = {
    "S1_INTEL":    ["调研","情报","了解一下","背景"],
    "S2_CONTACT":  ["见面","拜访","第一次","开场","破冰"],
    "S3_NEED":      ["需求","诉求","真实需求","深层需求"],
    "S4_PROPOSAL": ["方案","立项","预算","流程"],
    "S5_CLOSING":  ["合同","签约","付款","还没签"],
    "S0_DISCOVERY":["了解","打听","还没见过"],
}

# ─── ② Cynefin ────────────────────────────────

CYNEFIN = {
    "Simple":      ["标准流程","采购标准","文件准备","归档"],
    "Complicated": ["分析","调研","竞争格局","决策链"],
    "Complex":     ["信任","关系","推进进度","评估"],
    "Chaotic":     ["突然","紧急","危机","换人"],
}

def classify_cynefin(text):
    scores = {}
    for domain, kws in CYNEFIN.items():
        scores[domain] = sum(1 for kw in kws if kw in text) / len(kws)
    if not scores or max(scores.values()) == 0:
        return "Complex"
    return max(scores, key=scores.get)

# ─── ③ OODA 弱信号 ───────────────────────────

WEAK_SIGNALS = [
    ("回复变慢",      "内部阻力，谨慎应对"),
    ("开始问细节",    "认真评估，机会窗口"),
    ("突然问竞品",    "对比阶段，需差异化"),
    ("领导层出现",    "决策层介入，需换策略"),
    ("开始压价",      "意向强但有顾虑"),
    ("要求案例",      "准备内部汇报材料"),
    ("提到上级压力",  "时间窗口收紧"),
    ("提到人手不足",  "执行能力有限"),
]

def detect_weak(text):
    return [{"signal": s, "meaning": m} for s, m in WEAK_SIGNALS if s in text]

# ─── ④ 红队预死亡分析 ────────────────────────

RED_TEAM = [
    ("经办人被架空", "绕过经办找领导，经办成隐形否决者"),
    ("领导层意见不合", "方向分歧，项目停滞"),
    ("预算不足",     "规模被压缩，效果打折"),
    ("时间窗口关闭", "错过政策或人事变动窗口"),
    ("竞争对手介入", "对比方案进入，需差异化"),
    ("执行能力不足", "方案无法落地，变成烂尾"),
]

def red_team(stage):
    if stage in ("S0_DISCOVERY","S1_INTEL","S2_CONTACT"):
        return RED_TEAM[:2]
    elif stage in ("S3_NEED","S4_PROPOSAL","S5_CLOSING"):
        return RED_TEAM[2:]
    return RED_TEAM[:2]

# ─── ⑤ 二阶推演 ─────────────────────────────

SECOND_ORDER = {
    "催促对方":       "关系变紧张，窗口期缩短",
    "绕过经办找高层": "经办感到被架空，变成隐形否决者",
    "提供折扣":       "信任受损，质疑整体方案",
    "强调政策合规":   "强化时间窗口，倒推决策链",
}

def second_order(text):
    return {a: c for a, c in SECOND_ORDER.items() if a in text}

# ─── ⑥ 叙事引擎 ─────────────────────────────

def build_narrative(client, stage, input_text):
    stage_zh = {
        "S0_DISCOVERY": "初次发现决策者",
        "S1_INTEL":     "情报收集阶段",
        "S2_CONTACT":   "初次接触",
        "S3_NEED":      "需求挖掘",
        "S4_PROPOSAL":  "方案推进",
        "S5_CLOSING":   "成交障碍排除",
    }
    return {
        "hero": client,
        "situation": f"{client}面临一个决策窗口",
        "challenge": stage_zh.get(stage, stage),
        "action": input_text[:50],
        "urgency": "时间窗口内的行动时机",
        "risk": "错过窗口的风险"
    }

# ─── ⑦ 心智模拟 ─────────────────────────────

def mental_simulate(steps):
    anomalies = []
    for step in steps:
        if "绕过" in step or "直接找" in step:
            anomalies.append({"step": step, "issue": "经办人被架空风险"})
    return {
        "verdict": "有隐患需预处理" if anomalies else "通过",
        "anomalies": anomalies
    }

# ─── 客户持久化 ─────────────────────────────

def load_client(name):
    p = CLIENTS_DIR / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else {"name": name, "stage": "S1_INTEL", "log": []}

def save_client(c):
    (CLIENTS_DIR / f"{c['name']}.json").write_text(json.dumps(c, ensure_ascii=False, indent=2))

# ─── 统一入口 ─────────────────────────────────

def process_plus(user_input, client_name="default"):
    c = load_client(client_name)
    old = c.get("stage", "S1_INTEL")

    # 阶段推进
    new_stage = old
    for s, kws in STAGE_SIGNALS.items():
        if any(kw in user_input for kw in kws):
            new_stage = s
            break

    if new_stage != old:
        c["stage"] = new_stage

    # 七模型分析
    cynefin   = classify_cynefin(user_input)
    weak      = detect_weak(user_input)
    red       = red_team(new_stage)
    so        = second_order(user_input)
    sim       = mental_simulate([user_input])
    narrative = build_narrative(client_name, new_stage, user_input)

    # 写入历史
    c.setdefault("log", []).append({
        "time": datetime.now().isoformat(),
        "stage": new_stage,
        "input": user_input,
        "cynefin": cynefin,
        "weak": [w["signal"] for w in weak],
    })
    save_client(c)

    return {
        "client": client_name,
        "stage": new_stage,
        "cynefin": cynefin,
        "weak_signals": weak,
        "red_attacks": [r[0] for r in red],
        "second_order": so,
        "simulation": sim["verdict"],
        "narrative": narrative,
        "stage_advanced": new_stage != old,
    }

def format_plus(r):
    lines = [
        f"📋 客户：{r['client']} | 阶段：{r['stage']}",
        f"🌀 场景性质：{r['cynefin']}",
    ]
    ws = r.get("weak_signals", [])
    if ws:
        lines.append(f"⚠️  弱信号：{' / '.join(w['signal'] for w in ws[:2])}")
    ra = r.get("red_attacks", [])
    if ra:
        lines.append(f"🔴 红队预警：{' / '.join(ra[:2])}")
    lines.append(f"🧠 心智模拟：{r['simulation']}")
    n = r.get("narrative", {})
    lines.append(f"📖 叙事：{n.get('challenge','—')} → {n.get('urgency','—')}")
    return "\n".join(lines)
