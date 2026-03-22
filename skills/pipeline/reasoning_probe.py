"""
reasoning_probe.py — 推理质量检测器
检测大脑推理的实际质量

用法：
  from reasoning_probe import log_reasoning, get_brain_score, get_reasoning_quality

  # 每次完成推理后，判断用户是否采纳
  log_reasoning("分析这个问题", "建议用方案A", user_accepted=True)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

WORKSPACE = Path.home() / ".qclaw" / "workspace"
REASONING_LOG = WORKSPACE / "memory" / "reasoning_log.json"
STATS_FILE = WORKSPACE / "memory" / "reasoning_stats.json"

# ─── 采纳信号词 ─────────────────────────────────────────

ACCEPT_SIGNALS = [
    "好", "对", "执行", "继续", "就这样", "不错", "可以", "行",
    "是的", "没错", "有道理", "说得对", "按照你说的", "开始吧",
    "👍", "✅", "收到", "明白"
]

REJECT_SIGNALS = [
    "不对", "重来", "这不是我要的", "你理解错了", "错", "不是",
    "重新", "换个", "不对的", "不行", "不好", "不对",
    "❌", "👎", "算了", "不要"
]

PARTIAL_ACCEPT_SIGNALS = [
    "部分", "差不多", "接近", "但", "不过", "还需要", "再改改"
]


def _load_log() -> List[dict]:
    if REASONING_LOG.exists():
        with open(REASONING_LOG, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def _save_log(data: List[dict]):
    REASONING_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(REASONING_LOG, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_stats() -> Dict[str, Any]:
    if STATS_FILE.exists():
        with open(STATS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"total": 0, "accepted": 0, "rejected": 0, "partial": 0}


def _save_stats(data: Dict[str, Any]):
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── 核心函数 ─────────────────────────────────────────────

def log_reasoning(
    input_summary: str,
    output_summary: str,
    user_accepted: Optional[bool] = None,
    reasoning_type: str = "general"
):
    """
    每次完成推理后调用。
    
    user_accepted：
      True → 用户说「好」「对」「执行」「继续」
      False → 用户说「不对」「重新来」「这不是我要的」
      None → 用户没有明确反馈（不计入统计）
    
    reasoning_type: "planning" | "analysis" | "decision" | "creative" | "general"
    """
    if user_accepted is None:
        return  # 没有反馈不记录
    
    log = _load_log()
    stats = _load_stats()
    
    entry = {
        "time": datetime.now().isoformat(),
        "input": input_summary[:100],
        "output": output_summary[:100],
        "accepted": user_accepted,
        "reasoning_type": reasoning_type
    }
    
    log.append(entry)
    log[:] = log[-200:]  # 只保留200条
    
    stats["total"] += 1
    if user_accepted is True:
        stats["accepted"] += 1
    elif user_accepted is False:
        stats["rejected"] += 1
    else:
        stats["partial"] += 1
    
    _save_log(log)
    _save_stats(stats)


def detect_signal(text: str) -> Optional[bool]:
    """
    从用户回复中自动检测采纳/否定信号
    返回 True(采纳) / False(否定) / None(无法判断)
    """
    if not text:
        return None
    
    text_lower = text.lower()
    
    for sig in ACCEPT_SIGNALS:
        if sig in text:
            return True
    
    for sig in REJECT_SIGNALS:
        if sig in text:
            return False
    
    # 折中判断
    for sig in PARTIAL_ACCEPT_SIGNALS:
        if sig in text:
            return None  # 模棱两可，不计入
    
    return None


def get_brain_score() -> Optional[int]:
    """
    大脑分数：推理被采纳率（0-100）
    数据不足5条返回 None
    """
    stats = _load_stats()
    
    if stats["total"] < 5:
        return None
    
    return round(stats["accepted"] / stats["total"] * 100)


def get_reasoning_quality() -> Dict[str, Any]:
    """获取推理质量详细报告"""
    log = _load_log()
    stats = _load_stats()
    
    if stats["total"] < 5:
        return {
            "has_data": False,
            "total": stats["total"],
            "message": "数据不足（<5条）",
            "brain_score": None
        }
    
    recent = log[-20:] if len(log) >= 20 else log
    recent_accepted = sum(1 for r in recent if r.get("accepted", False))
    
    return {
        "has_data": True,
        "total": stats["total"],
        "accepted": stats["accepted"],
        "rejected": stats["rejected"],
        "partial": stats["partial"],
        "brain_score": round(stats["accepted"] / stats["total"] * 100, 1),
        "recent_score": round(recent_accepted / len(recent) * 100, 1) if recent else None,
        "data_quality": "良好" if stats["total"] >= 20 else "积累中" if stats["total"] >= 5 else "数据不足",
        "by_type": _get_score_by_type(log)
    }


def _get_score_by_type(log: List[dict]) -> Dict[str, Dict[str, Any]]:
    """按推理类型分析"""
    from collections import defaultdict
    
    by_type = defaultdict(lambda: {"total": 0, "accepted": 0})
    
    for r in log:
        t = r.get("reasoning_type", "general")
        by_type[t]["total"] += 1
        if r.get("accepted"):
            by_type[t]["accepted"] += 1
    
    result = {}
    for t, data in by_type.items():
        if data["total"] >= 2:  # 至少2条才显示
            result[t] = {
                "total": data["total"],
                "accepted": data["accepted"],
                "score": round(data["accepted"] / data["total"] * 100, 1)
            }
    
    return result


if __name__ == "__main__":
    import sys
    quality = get_reasoning_quality()
    print(json.dumps(quality, ensure_ascii=False, indent=2))
