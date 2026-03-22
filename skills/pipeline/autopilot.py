#!/usr/bin/env python3
"""
autopilot.py — 永不死的能力引擎 v1.0

核心理念：
  即使 OpenClaw gateway 崩溃，这个进程继续运行
  所有工具独立于主 session 工作
  有状态记录，断后可续

运行：
  python3 autopilot.py once   # 单次测试
  python3 autopilot.py start   # 后台常驻
"""

import os
import sys
import json
import time
import signal
import subprocess
from http_pool import groq_fast
import httpx
from pathlib import Path
from datetime import datetime
from typing import Optional

WORKSPACE = Path.home() / ".qclaw" / "workspace"
SKILLS_DIR = WORKSPACE / "skills" / "pipeline"
STATE_FILE = WORKSPACE / "memory" / "autopilot_state.json"
LOG_FILE = WORKSPACE / "memory" / "autopilot.log"
from _secrets import GROQ_KEY

def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"running": False, "last_run": {}, "uptime": 0, "errors": []}

def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))

def groq(prompt: str, max_tokens: int = 200) -> str:
    from http_pool import groq_fast
    try:
        return groq_fast(prompt, max_tokens)
    except Exception as e:
        log(f"GroqPool 失败，回退: {e}", "ERROR")
        # 回退到直接调用
        pass
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
        log(f"Groq 回退也失败: {e}", "ERROR")
    return ""

def health_check() -> str:
    results = []
    for name in ["crawl4ai", "qwen-agent", "mem0ai"]:
        v = Path.home() / ".qclaw" / "venvs" / name
        results.append(f"{name}={'ok' if v.exists() else 'MISSING'}")
    try:
        r = httpx.post("https://api.groq.com/openai/v1/chat/completions",
            json={"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": "ok"}], "max_tokens": 2},
            headers={"Authorization": f"Bearer {GROQ_KEY}"}, timeout=5)
        results.append(f"groq={'ok' if r.status_code == 200 else 'ERROR'}")
    except Exception:
        results.append("groq=ERROR")
    return "🏥 " + ", ".join(results)

def task_insight() -> str:
    topics = [
        "AI agent 领域最新进展",
        "中国AI产品最近动态",
        "开源大模型新发布",
        "电商/出海领域技术趋势",
    ]
    topic = topics[int(time.time()) % len(topics)]
    answer = groq(f"用3句话简洁回答：{topic}", 150)
    return f"💡 **{topic}**\n{answer}"

def task_memory() -> str:
    sem_db = WORKSPACE / "memory" / "semantic_memory.db"
    mem_count = 0
    if sem_db.exists():
        import sqlite3
        conn = sqlite3.connect(sem_db)
        mem_count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        conn.close()
    goals_file = WORKSPACE / "memory" / "goals" / "goals.json"
    active = []
    if goals_file.exists():
        data = json.loads(goals_file.read_text())
        for k, v in data.get("goals", {}).items():
            if v.get("status") == "active":
                active.append(f"{k}:{v.get('name','')}")
    return (f"🧠 记忆: {mem_count}条 | 活跃目标: {', '.join(active) or '无'}")

TASKS = [
    ("insight", task_insight, 3600),
    ("memory", task_memory, 1800),
    ("health", health_check, 7200),
]

def run_autopilot():
    state = load_state()
    state["running"] = True
    state["start"] = datetime.now().isoformat()
    save_state(state)
    log("AutoPilot 启动")
    last_run = {}
    while state["running"]:
        try:
            now = time.time()
            for name, func, interval in TASKS:
                if now - last_run.get(name, 0) >= interval:
                    log(f"执行: {name}")
                    result = func()
                    log(f"完成: {name}")
                    last_run[name] = now
            state["last_run"] = {k: datetime.fromtimestamp(v).isoformat() for k, v in last_run.items()}
            state["uptime"] = state.get("uptime", 0) + 1
            save_state(state)
        except Exception as e:
            log(f"循环异常: {e}", "ERROR")
        time.sleep(1)
    log("AutoPilot 停止")

def run_once():
    log("单次运行...")
    for name, func, interval in TASKS:
        log(f"执行: {name}")
        result = func()
        print(f"\n=== {name} ===\n{result}")
    return "完成"

def main():
    import argparse
    parser = argparse.ArgumentParser(description="AutoPilot 永不死引擎")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("once", help="单次执行")
    sub.add_parser("start", help="后台常驻")
    sub.add_parser("status", help="查看状态")
    args = parser.parse_args()
    if args.cmd == "once":
        run_once()
    elif args.cmd == "start":
        signal.signal(signal.SIGINT, lambda s, f: (save_state(load_state()), sys.exit(0)))
        signal.signal(signal.SIGTERM, lambda s, f: (save_state(load_state()), sys.exit(0)))
        run_autopilot()
    elif args.cmd == "status":
        print(json.dumps(load_state(), ensure_ascii=False, indent=2))
    else:
        run_once()

if __name__ == "__main__":
    main()
