"""
task_recorder.py — 任务执行记录器 v2
新增：无缝衔接追踪（跨器官连续任务）
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

WORKSPACE = Path.home() / ".qclaw" / "workspace"
RECORD_FILE = WORKSPACE / "memory" / "task_records.json"
STAT_FILE = WORKSPACE / "memory" / "organ_stats.json"
TRANSITION_FILE = WORKSPACE / "memory" / "transition_stats.json"

def _load_records() -> List[dict]:
    if RECORD_FILE.exists():
        with open(RECORD_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def _save_records(data: List[dict]):
    RECORD_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(RECORD_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _load_stats() -> Dict[str, dict]:
    if STAT_FILE.exists():
        with open(STAT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def _save_stats(data: Dict[str, dict]):
    STAT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STAT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _load_transitions() -> Dict[str, Any]:
    if TRANSITION_FILE.exists():
        with open(TRANSITION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"transitions": {}, "chains": []}

def _save_transitions(data: Dict):
    TRANSITION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TRANSITION_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def record_task(
    task_type: str,
    organ: str,
    success: bool,
    error: Optional[str] = None,
    interrupted: bool = False,
    task_id: Optional[str] = None,
    duration_ms: Optional[int] = None,
    is_continuation: bool = False,
    prev_organ: Optional[str] = None
):
    """
    每次任务完成或失败，调用这个函数记录。
    
    is_continuation: 这次任务是否是上一个任务的延续（跨器官协作）
    prev_organ: 如果是延续，上一个器官是什么
    """
    records = _load_records()
    stats = _load_stats()
    trans = _load_transitions()
    
    # 无缝衔接记录：跨器官连续任务
    if is_continuation and prev_organ and prev_organ != organ:
        key = f"{prev_organ}→{organ}"
        if key not in trans["transitions"]:
            trans["transitions"][key] = {"total": 0, "success": 0, "failed": 0}
        trans["transitions"][key]["total"] += 1
        if success:
            trans["transitions"][key]["success"] += 1
        else:
            trans["transitions"][key]["failed"] += 1
        
        # 追踪连续链条
        if records:
            records[-1]["next_organ"] = organ
            records[-1]["chain_continued"] = True
    
    entry = {
        "time": datetime.now().isoformat(),
        "task_type": task_type,
        "organ": organ,
        "success": success,
        "interrupted": interrupted,
        "duration_ms": duration_ms,
        "is_continuation": is_continuation,
    }
    if error:
        entry["error"] = error
    if task_id:
        entry["task_id"] = task_id
    
    records.append(entry)
    records[:] = records[-500:]
    _save_records(records)
    
    # 更新器官统计
    if organ not in stats:
        stats[organ] = {"total": 0, "success": 0, "interrupted": 0}
    stats[organ]["total"] += 1
    if success:
        stats[organ]["success"] += 1
    if interrupted:
        stats[organ]["interrupted"] += 1
    _save_stats(stats)
    _save_transitions(trans)


def get_organ_score(organ_name: str) -> Optional[int]:
    """根据真实记录计算器官等级（成功率 0-100）"""
    stats = _load_stats()
    if organ_name not in stats:
        return None
    s = stats[organ_name]
    if s["total"] < 5:
        return None
    return round(s["success"] / s["total"] * 100)


def get_smooth_score() -> Optional[int]:
    """丝滑等级：任务完成未打断用户的比率"""
    records = _load_records()
    if len(records) < 5:
        return None
    not_interrupted = sum(1 for r in records if not r.get("interrupted", False))
    return round(not_interrupted / len(records) * 100)


def get_seamless_score() -> Optional[int]:
    """
    无缝衔接程度：跨器官连续任务的完成率
    只有出现≥3次的器官切换路径才统计
    """
    trans = _load_transitions()
    all_trans = trans.get("transitions", {})
    if not all_trans:
        return None
    
    total = sum(t["total"] for t in all_trans.values())
    success = sum(t["success"] for t in all_trans.values())
    
    if total < 3:
        return None
    return round(success / total * 100)


def get_seamless_detail() -> Dict[str, Any]:
    """无缝衔接详细数据"""
    trans = _load_transitions()
    all_trans = trans.get("transitions", {})
    
    if not all_trans:
        return {"has_data": False, "transitions": [], "overall": None, "message": "暂无跨器官协作记录"}
    
    entries = []
    for key, data in all_trans.items():
        rate = round(data["success"] / data["total"] * 100) if data["total"] > 0 else 0
        entries.append({
            "transition": key,
            "total": data["total"],
            "success": data["success"],
            "failed": data["failed"],
            "rate": rate
        })
    
    entries.sort(key=lambda x: -x["total"])
    total_all = sum(e["total"] for e in entries)
    success_all = sum(e["success"] for e in entries)
    
    return {
        "has_data": True,
        "transitions": entries,
        "overall": round(success_all / total_all * 100) if total_all > 0 else 0,
        "total_cross_organ_tasks": total_all
    }


def get_organ_stats() -> Dict[str, dict]:
    return _load_stats()


def get_task_summary() -> Dict[str, Any]:
    records = _load_records()
    stats = _load_stats()
    trans = _load_transitions()
    
    if not records:
        return {"total_tasks": 0, "has_data": False, "message": "暂无任务记录"}
    
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    recent = [r for r in records if datetime.fromisoformat(r["time"]) > today]
    
    return {
        "total_tasks": len(records),
        "today_tasks": len(recent),
        "total_organs": len(stats),
        "has_data": True,
        "data_quality": "良好" if len(records) >= 50 else "积累中" if len(records) >= 5 else "数据不足",
        "organs": stats,
        "cross_organ_tasks": sum(1 for r in records if r.get("is_continuation", False)),
        "seamless_detail": get_seamless_detail()
    }


def get_stability_score() -> Optional[int]:
    """
    稳定丝滑程度：连续N次执行都不被打断的概率
    通过分析连续无打断任务序列计算
    """
    records = _load_records()
    if len(records) < 10:
        return None
    
    # 找到最长的连续无打断序列
    max_streak = 0
    current_streak = 0
    interrupted_count = 0
    
    for r in records:
        if r.get("interrupted", False):
            current_streak = 0
            interrupted_count += 1
        else:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
    
    total = len(records)
    if total < 10:
        return None
    
    # 稳定性 = 最长连续无打断序列 / 总任务数 * 加权
    # 同时考虑打断频率
    interruption_rate = interrupted_count / total
    stability = round((1 - interruption_rate) * min(max_streak / 10, 1.0) * 100)
    return max(0, min(100, stability))


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "--stats":
            print("=== 器官统计 ===")
            stats = get_organ_stats()
            for o, s in stats.items():
                rate = round(s["success"]/s["total"]*100) if s["total"] > 0 else 0
                print(f"  {o}: {s['success']}/{s['total']}={rate}% | 打断{s['interrupted']}次")
        elif sys.argv[1] == "--seamless":
            print("=== 无缝衔接 ===")
            d = get_seamless_detail()
            print(f"  总体: {d['overall']}%")
            for t in d.get('transitions', []):
                print(f"  {t['transition']}: {t['success']}/{t['total']}={t['rate']}%")
        elif sys.argv[1] == "--stability":
            s = get_stability_score()
            print(f"  稳定丝滑: {s}%")
        elif sys.argv[1] == "--all":
            stats = get_organ_stats()
            for o, s in stats.items():
                print(f"  {o}: {s['success']}/{s['total']}")
            print(f"  丝滑: {get_smooth_score()}%")
            print(f"  无缝: {get_seamless_score()}%")
            print(f"  稳定: {get_stability_score()}%")
    else:
        print("用法: task_recorder --stats | --seamless | --stability | --all")
