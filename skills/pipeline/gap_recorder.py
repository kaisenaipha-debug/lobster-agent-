"""
gap_recorder.py — 能力缺口记录器
每次发现能力不足，记录缺的是什么

用法：
  from gap_recorder import record_gap, get_pending_upgrades, get_gap_stats

  # 发现能力缺口
  record_gap("用户要翻译视频", "视频音频提取", "adapted", True)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from collections import Counter

WORKSPACE = Path.home() / ".qclaw" / "workspace"
GAP_FILE = WORKSPACE / "memory" / "capability_gaps.json"
STATS_FILE = WORKSPACE / "memory" / "gap_stats.json"

# ─── Resolution 类型 ─────────────────────────────────────

RESOLUTION_LABELS = {
    "clawhub": "从 ClawHub 安装",
    "adapted": "改造现有工具",
    "created": "自己创建",
    "failed": "未解决",
    "skipped": "跳过/绕过",
    "manual": "人工处理"
}

PRIORITY_MAP = {
    "high": "高",
    "medium": "中",
    "low": "低"
}


def _load_gaps() -> List[dict]:
    if GAP_FILE.exists():
        with open(GAP_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def _save_gaps(data: List[dict]):
    GAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(GAP_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_stats() -> Dict[str, Any]:
    if STATS_FILE.exists():
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"total_gaps": 0, "resolved": 0, "unresolved": 0}


def _save_stats(data: Dict[str, Any]):
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── 核心函数 ─────────────────────────────────────────────

def record_gap(
    task: str,
    missing_capability: str,
    resolution: str,
    resolved: bool,
    priority: str = "medium",
    notes: str = ""
):
    """
    发现能力缺口时调用。
    
    resolution:
      "clawhub" → 从 ClawHub 安装了
      "adapted" → 改造了现有工具
      "created" → 自己创建了新工具
      "failed" → 没能解决
      "skipped" → 跳过/绕过了
      "manual" → 让用户自己处理
    
    priority: "high" | "medium" | "low"
    """
    gaps = _load_gaps()
    stats = _load_stats()
    
    entry = {
        "time": datetime.now().isoformat(),
        "task": task[:100],
        "missing": missing_capability,
        "resolution": resolution,
        "resolved": resolved,
        "priority": priority,
        "notes": notes
    }
    
    gaps.append(entry)
    gaps[:] = gaps[-100:]  # 只保留100条
    
    stats["total_gaps"] += 1
    if resolved:
        stats["resolved"] += 1
    else:
        stats["unresolved"] += 1
    
    _save_gaps(gaps)
    _save_stats(stats)


def get_pending_upgrades() -> List[Dict[str, Any]]:
    """
    返回尚未解决的能力缺口列表（按出现次数排序）
    这就是仪表盘「待升级能力」的真实数据来源
    """
    gaps = _load_gaps()
    unresolved = [g for g in gaps if not g["resolved"]]
    
    # 去重，按出现次数排序
    counts = Counter(g["missing"] for g in unresolved)
    
    result = []
    for name, count in counts.most_common(10):
        # 找出最高优先级
        priorities = [g["priority"] for g in unresolved if g["missing"] == name]
        top_priority = "high" if "high" in priorities else "medium" if "medium" in priorities else "low"
        
        # 找出最新一条
        latest = max(
            (g for g in unresolved if g["missing"] == name),
            key=lambda g: g["time"],
            default={}
        )
        
        result.append({
            "name": name,
            "count": count,
            "priority": PRIORITY_MAP.get(top_priority, top_priority),
            "priority_raw": top_priority,
            "last_seen": latest.get("time", ""),
            "latest_task": latest.get("task", "")
        })
    
    return result


def get_gap_stats() -> Dict[str, Any]:
    """获取能力缺口统计"""
    gaps = _load_gaps()
    stats = _load_stats()
    
    if stats["total_gaps"] == 0:
        return {
            "has_data": False,
            "message": "暂无缺口记录",
            "total": 0
        }
    
    # Resolution 分布
    resolution_dist = Counter(g["resolution"] for g in gaps)
    
    # 每日趋势
    from collections import defaultdict
    by_day = defaultdict(lambda: {"total": 0, "resolved": 0})
    for g in gaps:
        day = g["time"][:10]
        by_day[day]["total"] += 1
        if g["resolved"]:
            by_day[day]["resolved"] += 1
    
    recent_days = sorted(by_day.items(), key=lambda x: x[0], reverse=True)[:7]
    
    return {
        "has_data": True,
        "total_gaps": stats["total_gaps"],
        "resolved": stats["resolved"],
        "unresolved": stats["unresolved"],
        "resolution_rate": round(stats["resolved"] / stats["total_gaps"] * 100, 1) if stats["total_gaps"] > 0 else 0,
        "data_quality": "良好" if stats["total_gaps"] >= 10 else "积累中" if stats["total_gaps"] >= 3 else "数据不足",
        "resolution_distribution": {
            RESOLUTION_LABELS.get(k, k): v for k, v in resolution_dist.most_common()
        },
        "pending": get_pending_upgrades(),
        "recent_days": [
            {
                "date": day,
                "total": d["total"],
                "resolved": d["resolved"]
            }
            for day, d in recent_days
        ]
    }


def get_unresolved_gaps_by_priority() -> Dict[str, List[Dict]]:
    """按优先级分组未解决缺口"""
    gaps = _load_gaps()
    unresolved = [g for g in gaps if not g["resolved"]]
    
    by_priority = {"high": [], "medium": [], "low": []}
    for g in unresolved:
        p = g.get("priority", "medium")
        if p in by_priority:
            by_priority[p].append(g)
    
    return by_priority


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        stats = get_gap_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "--pending":
        pending = get_pending_upgrades()
        print(json.dumps(pending, ensure_ascii=False, indent=2))
    else:
        print("用法: gap_recorder.py --stats | --pending")
