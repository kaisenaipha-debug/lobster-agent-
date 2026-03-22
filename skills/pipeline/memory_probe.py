"""
memory_probe.py — 记忆命中率检测器
每次从 mem0ai 查询，记录是否真的找到了有用的东西

用法：
  from memory_probe import query_with_probe, get_memory_stats

  # 带探针的记忆检索
  results = await query_with_probe("上次讨论的那个项目")
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

WORKSPACE = Path.home() / ".qclaw" / "workspace"
MEMORY_LOG_FILE = WORKSPACE / "memory" / "memory_probe_log.json"
MEM0_DB = Path.home() / ".qclaw" / "mem0_memory.db"

# 虚拟记忆探针记录（用于还没有真实mem0数据时）
MEMORY_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_log() -> List[dict]:
    if MEMORY_LOG_FILE.exists():
        with open(MEMORY_LOG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def _save_log(data: List[dict]):
    with open(MEMORY_LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── 带探针的记忆检索 ─────────────────────────────────────

async def query_with_probe(query: str, context: Optional[str] = None, limit: int = 5) -> List[dict]:
    """
    替代直接调用 mem0ai.search()
    自动记录检索是否命中
    """
    import json
    
    log = _load_log()
    
    try:
        # 尝试使用真实的 mem0
        sys.path.insert(0, str(Path.home() / ".qclaw" / "venvs" / "mem0ai" / "bin"))
        
        # 检查mem0是否可用
        mem0_path = Path.home() / ".qclaw" / "venvs" / "mem0ai" / "lib" / "python3.13" / "site-packages"
        if mem0_path.exists():
            sys.path.insert(0, str(mem0_path))
        
        try:
            from mem0 import Memory
            memory = Memory()
            results = memory.search(query, limit=limit)
            
            # 判断是否真的命中（不是空结果且有足够高的分数）
            hit = len(results) > 0 and any(
                r.get("score", 0) > 0.7 for r in results
            )
            
            hit_count = len(results)
            avg_score = round(sum(r.get("score", 0) for r in results) / len(results), 3) if results else 0
            
        except Exception:
            # mem0 不可用，用模拟数据
            results = []
            hit = False
            hit_count = 0
            avg_score = 0

    except ImportError:
        results = []
        hit = False
        hit_count = 0
        avg_score = 0

    # 记录探针数据
    log.append({
        "time": datetime.now().isoformat(),
        "query": query[:50],
        "query_context": context[:30] if context else None,
        "hit": hit,
        "hit_count": hit_count,
        "avg_score": avg_score,
        "results_preview": [r.get("text", r.get("content", ""))[:30] for r in results[:2]] if results else []
    })
    
    log[:] = log[-200:]  # 只保留200条
    _save_log(log)
    
    return results


def sync_query_with_probe(query: str, context: Optional[str] = None, limit: int = 5) -> List[dict]:
    """同步版本"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果已经在事件循环中，创建新任务
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, query_with_probe(query, context, limit))
                return future.result()
        else:
            return loop.run_until_complete(query_with_probe(query, context, limit))
    except RuntimeError:
        return asyncio.run(query_with_probe(query, context, limit))


# ─── 统计与分析 ─────────────────────────────────────────

def get_memory_stats() -> Dict[str, Any]:
    """获取记忆命中率统计"""
    log = _load_log()
    
    if len(log) < 3:
        return {
            "total_queries": 0,
            "has_data": False,
            "message": "数据不足（<3条查询）",
            "hit_rate": None,
            "avg_score": None
        }
    
    hits = sum(1 for r in log if r.get("hit", False))
    total = len(log)
    avg_score = round(sum(r.get("avg_score", 0) for r in log if r.get("avg_score")) / len(log), 3) if log else 0
    
    # 按天统计
    from collections import defaultdict
    by_day = defaultdict(lambda: {"total": 0, "hits": 0})
    for r in log:
        day = r["time"][:10]
        by_day[day]["total"] += 1
        if r.get("hit"):
            by_day[day]["hits"] += 1
    
    recent_days = sorted(by_day.items(), key=lambda x: x[0], reverse=True)[:7]
    
    return {
        "total_queries": total,
        "hits": hits,
        "misses": total - hits,
        "hit_rate": round(hits / total * 100, 1),
        "avg_score": avg_score,
        "has_data": True,
        "data_quality": "良好" if total >= 20 else "积累中" if total >= 3 else "数据不足",
        "recent_days": [
            {
                "date": day,
                "total": d["total"],
                "hits": d["hits"],
                "hit_rate": round(d["hits"] / d["total"] * 100) if d["total"] > 0 else 0
            }
            for day, d in recent_days
        ]
    }


def get_memory_hit_rate() -> Optional[int]:
    """获取记忆命中率（0-100），数据不足返回None"""
    stats = get_memory_stats()
    if not stats.get("has_data"):
        return None
    return stats["hit_rate"]


if __name__ == "__main__":
    import json
    stats = get_memory_stats()
    print(json.dumps(stats, ensure_ascii=False, indent=2))
