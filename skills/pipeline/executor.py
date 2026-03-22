"""
executor.py — 后台任务执行器 v2.0

升级：
  - 结果写入可读日志（results_log）
  - 每条结果附置信度，自动记录校准
  - UUID 唯一任务ID
  - 执行结果摘要自动汇报

运行：
  python3 executor.py run        # 后台执行
  python3 executor.py status     # 查看状态
  python3 executor.py results    # 查看最近结果
"""

import os
import sys
import json
import time
import signal
import subprocess
import httpx
import uuid
from pathlib import Path
from datetime import datetime

WORKSPACE = Path.home() / ".qclaw" / "workspace"
SKILLS = WORKSPACE / "skills" / "pipeline"
QUEUE_FILE = WORKSPACE / "memory" / "task_queue.json"
GOALS_FILE = WORKSPACE / "memory" / "goals" / "goals.json"
RESULTS_FILE = WORKSPACE / "memory" / "task_results.json"
CALIBRATION_FILE = WORKSPACE / "memory" / "confidence_calibration.json"
from _secrets import GROQ_KEY
LOG_FILE = WORKSPACE / "memory" / "executor.log"

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def groq(prompt: str, max_tokens: int = 200) -> str:
    try:
        r = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens},
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            timeout=20,
        )
        data = r.json()
        if "error" not in data:
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log(f"Groq 失败: {e}")
    return ""

def read_queue() -> dict:
    if QUEUE_FILE.exists():
        return json.loads(QUEUE_FILE.read_text())
    return {"tasks": [], "last_updated": None}

def write_queue(data: dict):
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def log_result(task_id: str, description: str, result: str, confidence: int, goal_id: str = None):
    """记录结果到可读日志 + 置信校准"""
    ts = datetime.now().isoformat()
    
    # 1. 写入结果日志
    results = []
    if RESULTS_FILE.exists():
        results = json.loads(RESULTS_FILE.read_text())
    
    results.insert(0, {
        "task_id": task_id,
        "description": description,
        "result": result[:500],
        "confidence": confidence,
        "goal_id": goal_id,
        "completed_at": ts,
    })
    results = results[:50]  # 保留最近50条
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    
    # 2. 写入置信校准日志（供未来分析）
    cal = []
    if CALIBRATION_FILE.exists():
        cal = json.loads(CALIBRATION_FILE.read_text())
    cal.append({
        "task_id": task_id,
        "description": description[:100],
        "declared_confidence": confidence,
        "result_quality": None,  # 待用户反馈后更新
        "completed_at": ts,
    })
    cal = cal[-100:]
    CALIBRATION_FILE.write_text(json.dumps(cal, ensure_ascii=False, indent=2))

def dequeue() -> dict:
    data = read_queue()
    pending = [t for t in data["tasks"] if t["status"] == "pending"]
    if not pending:
        return None
    priority_order = {"P1": 0, "P2": 1, "P3": 2}
    pending.sort(key=lambda t: (priority_order.get(t["priority"], 3), t["created_at"]))
    chosen = pending[0]
    chosen["status"] = "running"
    chosen["started_at"] = datetime.now().isoformat()
    chosen["attempts"] = chosen.get("attempts", 0) + 1
    write_queue(data)
    return chosen

def mark_done(task_id: str, result: str, confidence: int = 70):
    data = read_queue()
    for t in data["tasks"]:
        if t["id"] == task_id:
            t["status"] = "done"
            t["completed_at"] = datetime.now().isoformat()
            t["result"] = result[:500]
            t["confidence"] = confidence
            break
    write_queue(data)
    # 记录结果
    desc = next((t["description"] for t in data["tasks"] if t["id"] == task_id), "")
    goal_id = next((t.get("goal_id") for t in data["tasks"] if t["id"] == task_id), None)
    log_result(task_id, desc, result, confidence, goal_id)

def mark_failed(task_id: str, error: str):
    data = read_queue()
    for t in data["tasks"]:
        if t["id"] == task_id:
            t["status"] = "failed"
            t["completed_at"] = datetime.now().isoformat()
            t["error"] = error
            break
    write_queue(data)

def execute_task(task: dict, dry: bool = False) -> tuple[bool, str, int]:
    """
    返回: (是否成功, 结果文本, 置信度)
    置信度说明：
      70% = 简化版本，可能有边界条件未覆盖
      85% = 完整实现，通过基本验证
      95% = 高置信，经多次验证
    """
    desc = task["description"]
    confidence = 70  # 默认降级置信度
    
    log(f"执行 [{task['id']}]: {desc[:50]}")
    
    if dry:
        return True, "[DRY] 模拟完成", 50
    
    if '搜索' in desc or 'search' in desc.lower():
        # 真实搜索：用 crawl4ai 爬取 DuckDuckGo
        keywords = desc.replace('搜索','').replace('search','').replace('并分析','').strip()
        search_url = 'https://duckduckgo.com/?q=' + keywords.replace(' ', '+') + '&ia=web'
        import subprocess
        venv_py = str(Path.home() / '.qclaw/venvs/crawl4ai/bin/python')
        crawl_script = str(SKILLS / 'crawl_pipeline.py')
        r = subprocess.run(
            [venv_py, crawl_script, search_url, '--task', f'找出与{keywords}相关的最新信息'],
            capture_output=True, text=True, timeout=60
        )
        if r.returncode == 0:
            result = r.stdout[:400]
            confidence = 78
        else:
            result = groq(f'简洁回答：{keywords}', 200)
            confidence = 60
        return True, result, confidence

        return True, result, confidence
    
    elif "分析" in desc or "研究" in desc:
        result = groq(f"用3-5句话分析：{desc}", 300)
        confidence = 70
        return True, result, confidence
    
    elif "总结" in desc:
        result = groq(f"一句话总结：{desc}", 100)
        confidence = 75
        return True, result, confidence
    
    else:
        # 默认：Groq 直接执行
        result = groq(desc, 200)
        confidence = 65
        return True, result, confidence

def run_executor(dry: bool = False, interval: int = 30):
    log(f"Executor 启动 (dry={dry})")
    running = True
    
    def shutdown(signum, frame):
        nonlocal running
        log("退出信号，停止...")
        running = False
    
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    
    idle = 0
    while running:
        task = dequeue()
        if task is None:
            idle += 1
            if idle >= 5:
                log(f"队列空，休眠 {interval}s")
                idle = 0
            time.sleep(interval)
            continue
        
        idle = 0
        ok, result, confidence = execute_task(task, dry)
        
        if ok:
            mark_done(task["id"], result, confidence)
            log(f"✅ [{task['id']}] 置信度 {confidence}%")
        else:
            mark_failed(task["id"], result)
            log(f"❌ [{task['id']}] {result[:50]}")
        
        time.sleep(2)
    
    log("Executor 已停止")

def show_results(limit: int = 10):
    if not RESULTS_FILE.exists():
        print("暂无执行结果")
        return
    results = json.loads(RESULTS_FILE.read_text())
    print(f"📋 最近执行结果 (共 {len(results)} 条)\n")
    for r in results[:limit]:
        conf_bar = "▓" * (r["confidence"] // 10) + "░" * (10 - r["confidence"] // 10)
        print(f"[{r['task_id']}] {conf_bar} {r['confidence']}% | {r['description'][:40]}")
        print(f"  结果: {r['result'][:100]}")
        print(f"  时间: {r['completed_at'][11:19]}")
        print()

def show_status():
    data = read_queue()
    pending = [t for t in data["tasks"] if t["status"] == "pending"]
    running = [t for t in data["tasks"] if t["status"] == "running"]
    done = [t for t in data["tasks"] if t["status"] == "done"]
    failed = [t for t in data["tasks"] if t["status"] == "failed"]
    
    print(f"📋 Executor 状态")
    print(f"   ⏳ pending: {len(pending)}  🔄 running: {len(running)}  ✅ done: {len(done)}  ❌ failed: {len(failed)}")
    
    if results_exists():
        results = json.loads(RESULTS_FILE.read_text())
        avg_conf = sum(r.get("confidence", 0) for r in results[:10]) / min(len(results), 10)
        print(f"   最近10条平均置信度: {avg_conf:.0f}%")
    
    if pending:
        print(f"\n   队列前3:")
        for t in pending[:3]:
            print(f"     [{t['id']}] {t['priority']} | {t['description'][:45]}")

def results_exists():
    return RESULTS_FILE.exists() and RESULTS_FILE.stat().st_size > 0

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Executor v2.0 - 结果感知执行器")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("run", help="启动后台执行")
    sub.add_parser("dry", help="模拟执行")
    sub.add_parser("status", help="查看状态")
    sub.add_parser("results", help="查看最近结果")
    
    args = parser.parse_args()
    if args.cmd == "run":
        run_executor(dry=False)
    elif args.cmd == "dry":
        run_executor(dry=True)
    elif args.cmd == "results":
        show_results()
    elif args.cmd == "status":
        show_status()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
