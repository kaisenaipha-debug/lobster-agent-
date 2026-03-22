"""
consequence_tracker.py — 后果闭环系统

核心原则：
  反馈 bad → 降低同类问题置信度基准 → 下次更谨慎
  反馈 good → 可适当提升基准 → 但有上限
  无反馈 → 置信度不调整，但记录"未验证"

三层系统：
  1. consequence_log   — 每条反馈的因果链
  2. domain_baselines — 各领域置信度基准（自动调整）
  3. autonomy_trigger — 置信度触发自主行动边界

用法：
  python3 consequence_tracker.py record <task_id> good|bad  # 记录反馈
  python3 consequence_tracker.py baselines               # 查看各领域基准
  python3 consequence_tracker.py should_act <domain> <confidence>  # 判断是否自动执行
  python3 consequence_tracker.py report                # 完整报告
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

WORKSPACE = Path.home() / ".qclaw" / "workspace"
CONSEQ_FILE = WORKSPACE / "memory" / "consequence_log.json"
CALIB_FILE = WORKSPACE / "memory" / "confidence_calibration.json"

# ─── 初始领域基准 ──────────────────────────────────────

INITIAL_BASELINES = {
    "search":       {"baseline": 70, "weight": 1.0,  "sample": 0},
    "analysis":      {"baseline": 68, "weight": 1.0,  "sample": 0},
    "crawl":        {"baseline": 75, "weight": 1.0,  "sample": 0},
    "coding":       {"baseline": 72, "weight": 1.0,  "sample": 0},
    "general":      {"baseline": 65, "weight": 1.0,  "sample": 0},
    "judgment":     {"baseline": 60, "weight": 1.0,  "sample": 0},  # 复杂判断最难
}

# ─── 置信度授权阈值 ─────────────────────────────────

AUTONOMY_THRESHOLDS = {  # 0=auto, 1=propose, 2=confirm
    "auto_execute": 80,   # ≥80% 自动执行
    "propose":      65,   # 65-79% 提议后执行
    "confirm":       0,   # <65% 必须确认
}

# ─── 核心函数 ───────────────────────────────────────

def load_conseq() -> list:
    if CONSEQ_FILE.exists():
        return json.loads(CONSEQ_FILE.read_text())
    return []

def save_conseq(data: list):
    CONSEQ_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONSEQ_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def load_baselines() -> dict:
    if CALIB_FILE.exists():
        raw = json.loads(CALIB_FILE.read_text())
        return raw.get("domain_baselines", INITIAL_BASELINES)
    return INITIAL_BASELINES

def save_baselines(data: dict):
    raw = {}
    if CALIB_FILE.exists():
        raw = json.loads(CALIB_FILE.read_text())
    raw["domain_baselines"] = data
    CALIB_FILE.parent.mkdir(parents=True, exist_ok=True)
    CALIB_FILE.write_text(json.dumps(raw, ensure_ascii=False, indent=2))

def categorize(description: str) -> str:
    """分类任务到领域"""
    desc = description.lower()
    if "搜索" in description or "search" in desc:
        return "search"
    elif "分析" in description or "研究" in desc:
        return "analysis"
    elif "爬取" in description or "crawl" in desc:
        return "crawl"
    elif "代码" in description or "python" in desc or "写代码" in desc:
        return "coding"
    elif any(kw in desc for kw in ["判断", "决策", "应该", "哪个"]):
        return "judgment"
    return "general"

def record_feedback(task_id: str, quality: str, description: str = "", declared_confidence: int = None) -> dict:
    """
    记录反馈，并更新领域基准
    
    quality: 'good' | 'bad' | 'neutral'
    """
    conseq = load_conseq()
    baselines = load_baselines()
    domain = categorize(description)
    entry = {
        "task_id": task_id,
        "domain": domain,
        "quality": quality,
        "description": description[:100],
        "declared_confidence": declared_confidence,
        "recorded_at": datetime.now().isoformat(),
    }
    conseq.append(entry)
    conseq = conseq[-200:]  # 保留最近200条
    save_conseq(conseq)
    
    # 更新领域基准
    if quality in ("good", "bad"):
        recent = [c for c in conseq if c.get("domain") == domain][-10:]
        if len(recent) >= 3:
            bad_rate = sum(1 for c in recent if c.get("quality") == "bad") / len(recent)
            current = baselines.get(domain, {}).get("baseline", 65)
            adjustment = 0
            
            if quality == "bad":
                # 错了：基准下调
                adjustment = -5 if bad_rate > 0.4 else -3
            else:
                # 对了：基准上调（有上限）
                if bad_rate < 0.2:
                    adjustment = +3
            
            new_baseline = max(40, min(92, current + adjustment))
            baselines[domain] = {
                "baseline": new_baseline,
                "weight": 1.0,
                "sample": len(recent),
                "last_updated": datetime.now().isoformat(),
            }
            save_baselines(baselines)
            
            return {
                "recorded": True,
                "domain": domain,
                "old_baseline": current,
                "new_baseline": new_baseline,
                "adjustment": adjustment,
                "recent_accuracy": f"{int((1-bad_rate)*100)}%",
            }
    
    return {"recorded": True, "domain": domain, "baseline": baselines.get(domain, {}).get("baseline", 65), "adjustment": 0}

def should_auto_execute(domain: str, confidence: int = None) -> dict:
    """
    判断是否应该自动执行
    
    返回：
      level: "auto" | "propose" | "confirm"
      threshold_used: int
      domain_baseline: int
    """
    baselines = load_baselines()
    base = baselines.get(domain, {}).get("baseline", 65)
    effective_conf = confidence or base
    
    auto_thresh = int(AUTONOMY_THRESHOLDS[0])
    propose_thresh = int(AUTONOMY_THRESHOLDS[1])
    
    if effective_conf >= auto_thresh:
        level = "auto"
    elif effective_conf >= propose_thresh:
        level = "propose"
    else:
        level = "confirm"
    
    return {
        "level": level,
        "effective_confidence": effective_conf,
        "domain_baseline": base,
        "auto_threshold": auto_thresh,
        "propose_threshold": propose_thresh,
        "reason": f"置信度{effective_conf}% {'≥' if level == 'auto' else '<'}{auto_thresh}%",
    }

def judgment_review() -> dict:
    """
    定期回顾：对比同类问题的历史判断
    返回：哪些领域的判断在变准，哪些在变差
    """
    conseq = load_conseq()
    baselines = load_baselines()
    
    if len(conseq) < 5:
        return {"status": "insufficient_data", "total": len(conseq), "need": 5 - len(conseq)}
    
    report = {"total_records": len(conseq), "domains": {}}
    
    for domain in set(c.get("domain", "general") for c in conseq[-50:]):
        recent = [c for c in conseq[-20:] if c.get("domain") == domain]
        if len(recent) < 3:
            continue
        
        good = sum(1 for c in recent if c.get("quality") == "good")
        bad = sum(1 for c in recent if c.get("quality") == "bad")
        accuracy = good / (good + bad) if (good + bad) > 0 else 0.5
        
        old = [c for c in conseq[:-20] if c.get("domain") == domain]
        old_accuracy = 0.5
        if len(old) >= 3:
            old_good = sum(1 for c in old if c.get("quality") == "good")
            old_bad = sum(1 for c in old if c.get("quality") == "bad")
            old_accuracy = old_good / (old_good + old_bad) if (old_good + old_bad) > 0 else 0.5
        
        trend = "📈 变准" if accuracy > old_accuracy + 0.1 else "📉 变差" if accuracy < old_accuracy - 0.1 else "➡️ 稳定"
        
        report["domains"][domain] = {
            "recent_accuracy": f"{int(accuracy*100)}%",
            "older_accuracy": f"{int(old_accuracy*100)}%",
            "trend": trend,
            "baseline": baselines.get(domain, {}).get("baseline", "?"),
            "samples": len(recent),
        }
    
    return report

def print_baselines():
    baselines = load_baselines()
    print("📊 领域置信度基准\n")
    for domain, info in baselines.items():
        b = info.get("baseline", 65)
        bar = "▓" * (b // 10) + "░" * (10 - b // 10)
        s = info.get("sample", 0)
        updated = info.get("last_updated", "?")[:10]
        print(f"  {domain:10} {bar} {b}%  (样本:{s})")

def main():
    args = sys.argv[1:]
    
    if not args or args[0] == "baselines":
        print_baselines()
    
    elif args[0] == "record" and len(args) >= 3:
        task_id = args[1]
        quality = args[2]
        desc = args[3] if len(args) > 3 else ""
        conf = int(args[4]) if len(args) > 4 else None
        result = record_feedback(task_id, quality, desc, conf)
        if result.get("adjustment", 0) != 0:
            d = result["adjustment"]
            print(f"✅ 记录 | 领域:{result['domain']} | 基准:{result['old_baseline']}%→{result['new_baseline']}% ({d:+d}%) | 近5次准确率:{result['recent_accuracy']}")
        else:
            print(f"✅ 记录 | 基准未调整(样本不足3条)")
    
    elif args[0] == "should_act" and len(args) >= 2:
        domain = args[1]
        conf = int(args[2]) if len(args) > 2 else None
        r = should_auto_execute(domain, conf)
        icon = {"auto": "⚡", "propose": "💡", "confirm": "❓"}.get(r["level"], "?")
        print(f"{icon} {r['reason']} → {r['level'].upper()}")
        print(f"   领域基准:{r['domain_baseline']}%  有效置信:{r['effective_confidence']}%")
    
    elif args[0] == "report":
        print("📋 判断回顾报告\n")
        r = judgment_review()
        if r.get("status") == "insufficient_data":
            print(f"数据不足（{r['total']}/{r['need']}条），继续积累")
        else:
            for domain, info in r.get("domains", {}).items():
                print(f"  {domain}: {info['trend']}  {info['older_accuracy']}→{info['recent_accuracy']}  基准:{info['baseline']}%")
    
    else:
        print("用法：")
        print("  python3 consequence_tracker.py baselines               # 查看基准")
        print("  python3 consequence_tracker.py record <id> good|bad [描述] [置信度]")
        print("  python3 consequence_tracker.py should_act <领域> [置信度]")
        print("  python3 consequence_tracker.py report                # 定期回顾")

if __name__ == "__main__":
    main()
