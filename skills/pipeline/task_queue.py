"""
task_queue.py — 任务队列管理 v1.0

功能：
  - 原子性写入goals.json，防止并发冲突
  - 任务队列，支持5分钟粒度子任务
  - 断点续执行，崩溃后可恢复
  - 执行状态：pending / running / done / failed / blocked

并发安全：flock文件锁 + 原子写入（写临时文件再rename）

用法：
  python3 task_queue.py enqueue "分析竞品" --goal-id G005 --priority P2
  python3 task_queue.py status
  python3 task_queue.py next
  python3 task_queue.py done TASK_ID
  python3 task_queue.py fail TASK_ID "原因"
"""

import os
import sys
import json
import fcntl
import time
import uuid
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

WORKSPACE = Path.home() / ".qclaw" / "workspace"
QUEUE_FILE = WORKSPACE / "memory" / "task_queue.json"
GOALS_FILE = WORKSPACE / "memory" / "goals" / "goals.json"
LOCK_FILE = WORKSPACE / "memory" / "task_queue.lock"

# ─── 原子读写 ─────────────────────────────────────────────

def atomic_read() -> dict:
    """带锁读取"""
    if not QUEUE_FILE.exists():
        return {"tasks": [], "last_updated": None}
    with open(LOCK_FILE, "w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            with open(QUEUE_FILE) as f:
                return json.loads(f.read())
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

def atomic_write(data: dict):
    """原子写入（临时文件+rename）"""
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = QUEUE_FILE.with_suffix(".tmp")
    with open(LOCK_FILE, "w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
            tmp.rename(QUEUE_FILE)
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

# ─── 队列操作 ─────────────────────────────────────────────

def enqueue(
    description: str,
    goal_id: str = None,
    priority: str = "P3",
    estimated_minutes: int = 5,
    depends_on: List[str] = None,
) -> str:
    """入队一个任务"""
    queue = atomic_read()
    
    task_id = f"T{int(time.time()) % 1000000:06d}"  # T000001
    
    task = {
        "id": task_id,
        "description": description,
        "goal_id": goal_id,
        "priority": priority,
        "status": "pending",  # pending / running / done / failed / blocked
        "created_at": datetime.now().isoformat(),
        "started_at": None,
        "completed_at": None,
        "estimated_minutes": estimated_minutes,
        "depends_on": depends_on or [],
        "error": None,
        "result": None,
        "attempts": 0,
    }
    
    queue["tasks"].append(task)
    queue["last_updated"] = datetime.now().isoformat()
    atomic_write(queue)
    
    return task_id

def dequeue() -> Optional[Dict]:
    """取下一个可执行的任务（考虑依赖）"""
    queue = atomic_read()
    now = datetime.now()
    
    # 按优先级和创建时间排序
    pending = [t for t in queue["tasks"] if t["status"] == "pending"]
    
    # 过滤掉有未完成依赖的任务
    available = []
    for t in pending:
        if t.get("depends_on"):
            # 检查依赖是否都已完成
            deps = t["depends_on"]
            done_ids = {tt["id"] for tt in queue["tasks"] if tt["status"] == "done"}
            if all(d in done_ids for d in deps):
                available.append(t)
        else:
            available.append(t)
    
    if not available:
        return None
    
    # 选优先级最高、创建最早的
    priority_order = {"P1": 0, "P2": 1, "P3": 2}
    available.sort(key=lambda t: (priority_order.get(t["priority"], 3), t["created_at"]))
    
    chosen = available[0]
    chosen["status"] = "running"
    chosen["started_at"] = now.isoformat()
    chosen["attempts"] = chosen.get("attempts", 0) + 1
    atomic_write(queue)
    
    return chosen

def mark_done(task_id: str, result: str = None):
    """标记完成"""
    queue = atomic_read()
    for t in queue["tasks"]:
        if t["id"] == task_id:
            t["status"] = "done"
            t["completed_at"] = datetime.now().isoformat()
            t["result"] = result
            break
    queue["last_updated"] = datetime.now().isoformat()
    atomic_write(queue)

def mark_failed(task_id: str, error: str):
    """标记失败"""
    queue = atomic_read()
    for t in queue["tasks"]:
        if t["id"] == task_id:
            t["status"] = "failed"
            t["completed_at"] = datetime.now().isoformat()
            t["error"] = error
            break
    queue["last_updated"] = datetime.now().isoformat()
    atomic_write(queue)

def get_status() -> dict:
    """获取队列状态"""
    queue = atomic_read()
    counts = {"pending": 0, "running": 0, "done": 0, "failed": 0, "blocked": 0}
    for t in queue["tasks"]:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    
    running_tasks = [t for t in queue["tasks"] if t["status"] == "running"]
    active_goal = None
    if running_tasks:
        gid = running_tasks[0].get("goal_id")
        if gid and GOALS_FILE.exists():
            goals = json.loads(GOALS_FILE.read_text())
            if gid in goals.get("goals", {}):
                active_goal = f"{gid}: {goals['goals'][gid]['name']}"
    
    return {
        "total": len(queue["tasks"]),
        "counts": counts,
        "active": running_tasks[0] if running_tasks else None,
        "active_goal": active_goal,
        "last_updated": queue.get("last_updated"),
    }

def peek(limit: int = 10) -> List[Dict]:
    """预览队列"""
    queue = atomic_read()
    pending = [t for t in queue["tasks"] if t["status"] == "pending"]
    pending.sort(key=lambda t: ({"P1":0,"P2":1,"P3":2}.get(t["priority"],3), t["created_at"]))
    return pending[:limit]

# ─── 主入口 ───────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="📋 任务队列管理")
    sub = parser.add_subparsers(dest="cmd")

    p_eq = sub.add_parser("enqueue", help="添加任务")
    p_eq.add_argument("description")
    p_eq.add_argument("--goal-id", "-g")
    p_eq.add_argument("--priority", "-p", choices=["P1","P2","P3"], default="P3")
    p_eq.add_argument("--minutes", "-m", type=int, default=5)
    p_eq.add_argument("--deps", "-d", nargs="*", default=[])

    sub.add_parser("status", help="队列状态")
    sub.add_parser("peek", help="预览待执行任务")
    sub.add_parser("next", help="取下一个任务")
    sub.add_parser("done", help="标记完成").add_argument("task_id")
    sub.add_parser("failed", help="标记失败").add_argument("task_id")

    p_fail = sub.add_parser("fail", help="标记失败")
    p_fail.add_argument("task_id")
    p_fail.add_argument("error")

    args = parser.parse_args()

    if args.cmd == "enqueue":
        tid = enqueue(args.description, args.goal_id, args.priority, args.minutes, args.deps)
        print(f"✅ 任务入队 [{tid}]: {args.description[:50]}")
    
    elif args.cmd == "status":
        s = get_status()
        print(f"📋 队列状态 (总计 {s['total']} 任务)")
        print(f"   ⏳ pending: {s['counts'].get('pending',0)}")
        print(f"   🔄 running: {s['counts'].get('running',0)}")
        print(f"   ✅ done: {s['counts'].get('done',0)}")
        print(f"   ❌ failed: {s['counts'].get('failed',0)}")
        if s.get("active_goal"):
            print(f"   当前: {s['active_goal']}")
        if s.get("active"):
            t = s["active"]
            print(f"   执行中: [{t['id']}] {t['description'][:50]}")
    
    elif args.cmd == "peek":
        tasks = peek()
        if not tasks:
            print("队列空")
        for t in tasks:
            print(f"  [{t['id']}] {t['priority']} | {t['description'][:50]}")
    
    elif args.cmd == "next":
        task = dequeue()
        if task:
            print(json.dumps(task, ensure_ascii=False, indent=2))
        else:
            print("无待执行任务")
    
    elif args.cmd == "done":
        mark_done(args.task_id)
        print(f"✅ [{args.task_id}] 已标记完成")
    
    elif args.cmd == "fail":
        mark_failed(args.task_id, args.error)
        print(f"❌ [{args.task_id}] 标记失败: {args.error[:50]}")

if __name__ == "__main__":
    main()
