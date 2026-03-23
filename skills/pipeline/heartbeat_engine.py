"""
heartbeat_engine.py — 主动心跳引擎

目标：从"被动检查"升级为"主动发现"
每次心跳随机挑选一个任务执行，不重复，直到清单清空或时间到。

用法（可被 cron 或 heartbeat 调用）：
  python3 heartbeat_engine.py [--dry-run] [--verbose]

依赖：
  - Groq API (from _secrets)
  - mem0_bridge.sh
  - crawl_pipeline.py
"""

import os
import sys
import json
import random
import sqlite3
import subprocess
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

# ─── 配置 ───────────────────────────────────────────────────

WORKSPACE = Path.home() / ".qclaw" / "workspace"
HEARTBEAT_FILE = WORKSPACE / "HEARTBEAT.md"
MEM0_DB = Path.home() / ".qclaw" / "mem0_memory.db"
STATE_FILE = WORKSPACE / "memory" / "heartbeat_state.json"

from _secrets import GROQ_KEY
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# ─── 状态管理 ───────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_task": None, "task_index": 0, "last_run": None, "completed_tasks": []}

def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))

# ─── Groq 调用 ─────────────────────────────────────────────

def groq(prompt: str, max_tokens: int = 300) -> str:
    from http_pool import groq_fast
    try:
        return groq_fast(prompt, max_tokens)
    except Exception as e:
        print(f'[GroqPool降级: {e}]')
        pass
    # 降级直接调用
    import httpx
    try:
        r = httpx.post(GROQ_URL, json={
            'model': 'llama-3.1-8b-instant',
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': max_tokens
        }, headers={'Authorization': f'Bearer {GROQ_KEY}', 'Content-Type': 'application/json'}, timeout=15)
        data = r.json()
        if 'error' not in data:
            return data['choices'][0]['message']['content']
    except Exception:
        pass
    return ''


def task_discover_insight(state: dict) -> tuple[str, bool]:
    """任务1：主动发现一个有价值的洞察"""
    topics = [
        "AI agent 领域最新进展",
        "中国AI产品最近动态",
        "开源大模型新发布",
        "电商/出海领域技术趋势",
    ]
    topic = random.choice(topics)
    prompt = f"""你是我的商业情报助手。请用中文简洁回答：

你今天的发现任务：{topic}

要求：
1. 说出1个你认为最重要的动态或趋势
2. 为什么这个重要
3. 对我的潜在价值

保持简洁，3-5句话，不要搜索，直接给洞察。"""
    
    insight = groq(prompt)
    return (
        f"💡 **[主动发现] {topic}**\n\n{insight}\n\n"
        f"⏱ {datetime.now().strftime('%H:%M')}",
        True
    )

def task_memory_review(state: dict) -> tuple[str, bool]:
    """任务2：检查记忆库，随机激活一条旧记忆"""
    if not MEM0_DB.exists():
        return "记忆库为空，跳过", False
    
    conn = sqlite3.connect(MEM0_DB)
    rows = conn.execute(
        "SELECT text, created_at FROM memories ORDER BY RANDOM() LIMIT 3"
    ).fetchall()
    conn.close()
    
    if not rows:
        return "无历史记忆，跳过", False
    
    lines = [f"- **{r[1][:10]}**: {r[0][:80]}{'...' if len(r[0]) > 80 else ''}" for r in rows]
    return (
        f"🧠 **[记忆激活]** 从记忆库随机调取：\n\n" + "\n".join(lines),
        True
    )

def task_system_health(state: dict) -> tuple[str, bool]:
    """任务3：检查系统健康"""
    checks = []

    # 正确的包名映射（venv名 -> import名）
    venv_import_map = {"crawl4ai": "crawl4ai", "qwen-agent": "qwen_agent", "mem0ai": "mem0"}

    # 检查 venv
    venvs = ["crawl4ai", "qwen-agent", "mem0ai"]
    for v in venvs:
        venv_path = Path.home() / ".qclaw" / "venvs" / v
        pkg_import = venv_import_map[v]
        if not venv_path.exists():
            checks.append(f"❌ {v} venv 不存在")
            continue
        # 真实 import 测试
        result = subprocess.run(
            [str(venv_path / "bin" / "python"), "-c", f"import {pkg_import}"],
            capture_output=True, timeout=10
        )
        if result.returncode == 0:
            checks.append(f"✅ {v} venv 正常")
        else:
            checks.append(f"❌ {v} venv 损坏（import失败）")
    
    # 检查 API
    try:
        import httpx
        r = httpx.post(GROQ_URL, json={
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 2
        }, headers={"Authorization": f"Bearer {GROQ_KEY}"}, timeout=5)
        if r.status_code == 200:
            checks.append("✅ Groq API 正常")
        else:
            checks.append(f"⚠️ Groq API 异常 ({r.status_code})")
    except Exception as e:
        checks.append(f"❌ Groq API 失败: {e}")
    
    return (
        "🏥 **[系统健康]**\n" + "\n".join(checks),
        True
    )

def task_todo_check(state: dict) -> tuple[str, bool]:
    """任务4：检查待办状态"""
    # 读取今日待办
    today = datetime.now().strftime("%Y-%m-%d")
    note = WORKSPACE / "memory" / f"{today}.md"
    
    if not note.exists():
        return f"📋 今日日志为空，跳过待办检查", False
    
    content = note.read_text()
    
    # 找待解决问题
    if "待解决" in content or "TODO" in content.upper():
        lines = [l for l in content.splitlines() if "待" in l or "TODO" in l.upper()]
        if lines:
            return (
                f"📋 **[待办提醒]** 发现未解决问题：\n\n" + "\n".join(f"  {l.strip()}" for l in lines[:3]),
                True
            )
    
    return "📋 无待处理事项", False

def task_client_check(state: dict) -> tuple[str, bool]:
    """任务6：检查客户档案，推送待办事项"""
    import json
    from datetime import datetime
    clients_dir = WORKSPACE / "memory" / "clients"
    if not clients_dir.exists():
        return "🏢 无客户档案，跳过", False

    alerts = []
    insights = []
    now = datetime.now()

    for f in clients_dir.glob("*.json"):
        try:
            c = json.loads(f.read_text())
            stage = c.get("stage", "S1_INTEL")
            log = c.get("log", [])
            if not log:
                continue

            client_name = c.get("name", f.stem)
            last_time = log[-1].get("time", "")
            last_input = log[-1].get("input", "")

            if not last_time:
                continue

            try:
                last_dt = datetime.fromisoformat(last_time)
                days_ago = (now - last_dt).days

                if stage in ("S4_PROPOSAL", "S5_CLOSING") and days_ago >= 3:
                    alerts.append(f"⚠️ **{client_name}**（{stage}）已{days_ago}天无进展，需跟进")
                elif stage == "S2_CONTACT" and days_ago >= 7:
                    alerts.append(f"📌 **{client_name}**（S2初次接触）已{days_ago}天未推进")
                else:
                    # 无预警 → 主动给洞察
                    if last_input and days_ago <= 2:
                        ins = _gen_insight(client_name, stage, last_input)
                        if ins:
                            insights.append(ins)
            except Exception:
                pass
        except Exception:
            pass

    outputs = []
    if alerts:
        outputs.append("🏢 **[客户预警]**\n" + "\n".join(alerts[:5]))
    if insights:
        outputs.append("🏢 **[客户动态]** " + " | ".join(insights[:3]))

    if outputs:
        return "\n\n".join(outputs), True
    return "🏢 客户档案正常", True


def _gen_insight(name: str, stage: str, inp: str) -> str:
    if stage == "S4_PROPOSAL" and ("方案" in inp or "预算" in inp):
        return f"{name}刚推进到{stage}，3天内主动跟进"
    if stage == "S3_NEED" and "需求" in inp:
        return f"{name}正在挖掘需求，是介入时机"
    if stage == "S2_CONTACT" and ("见" in inp or "聊" in inp):
        return f"{name}刚完成初次接触，是建立信任关键期"
    return ""

def task_goal_review(state: dict) -> tuple[str, bool]:
    """任务7：检查目标追踪系统"""
    import json
    goals_file = WORKSPACE / "memory" / "goals" / "goals.json"
    if not goals_file.exists():
        return "🎯 无目标文件，跳过", False
    
    data = json.loads(goals_file.read_text())
    goals = data.get("goals", {})
    
    waiting = {k: v for k, v in goals.items() if v["status"] == "waiting"}
    active = {k: v for k, v in goals.items() if v["status"] == "active"}
    
    lines = []
    if waiting:
        blockers = []
        for g in waiting.values():
            bl = g.get("blockers", [])
            if bl:
                blockers.append(f"**{g['id']}** {g['name']}: {', '.join(bl)}")
        if blockers:
            lines.append("⚠️ **等待中的目标有进展机会**：")
            for b in blockers[:3]:
                lines.append(f"  {b}")
    
    if active:
        top = sorted(active.values(), key=lambda x: x["priority"])[0]
        lines.append(f"🔴 **{top['id']}** {top['name']} — 下一步: {top.get('next_step', '—')}")
    
    if not lines:
        return "🎯 目标系统一切正常，无待处理项", True
    
    return "🎯 **[目标追踪]**\n" + "\n".join(lines), True

def task_daily_briefing(state: dict) -> tuple[str, bool]:
    """任务5：生成今日简报"""
    prompt = f"""用中文简洁地写一段今日科技/AI领域的晨间简报。

格式：
📰 今日简报 ({datetime.now().strftime('%m/%d')})

【头条】xxx
【趋势】xxx
【值得关注】xxx

不需要搜索，基于你对2026年初科技界的了解来写。"""
    
    briefing = groq(prompt, max_tokens=200)
    return (
        f"📰 **[今日简报]**\n\n{briefing}",
        True
    )

# ─── 任务调度器 ────────────────────────────────────────────

TASKS = [
    ("发现洞察",   task_discover_insight),
    ("记忆激活",   task_memory_review),
    ("系统健康",   task_system_health),
    ("待办检查",   task_todo_check),
    ("客户追踪",   task_client_check),
    ("晨间简报",   task_daily_briefing),
    ("目标追踪",   task_goal_review),
]

def run_heartbeat(dry_run: bool = False, verbose: bool = False) -> Optional[str]:
    state = load_state()
    now = datetime.now()

    # 时间保护
    hour = now.hour
    if hour < 7 or hour >= 23:
        if verbose:
            print("[静默时段，不打扰]")
        return None

    outputs = []

    # ── 核心检查：每次必跑（system_health + goal_review）────────
    if verbose:
        print(f"[Heartbeat] 执行核心检查...")

    health_result, health_ok = task_system_health(state)
    if health_ok:
        outputs.append(health_result)

    goal_result, goal_ok = task_goal_review(state)
    if goal_ok and goal_result != "🎯 目标系统一切正常，无待处理项":
        outputs.append(goal_result)

    # ── 随机任务：避免重复 ───────────────────────────────────
    last = state.get("last_task")
    available = [t for t in TASKS if t[0] != last]
    if not available:
        available = TASKS

    task_name, task_fn = random.choice(available)

    if dry_run:
        return f"[Dry Run] 将执行: {task_name}"

    if verbose:
        print(f"[Heartbeat] 执行随机任务: {task_name}")

    result, should_report = task_fn(state)

    if should_report:
        state["last_task"] = task_name
        state["last_run"] = now.isoformat()
        save_state(state)
        outputs.append(result)

    if not outputs:
        return None

    return "\n\n".join(outputs)

# ─── 主入口 ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="主动心跳引擎")
    parser.add_argument("--dry-run", action="store_true", help="只显示将执行什么")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    
    result = run_heartbeat(dry_run=args.dry_run, verbose=args.verbose)
    
    if result:
        print(result)
    elif not args.dry_run:
        print("HEARTBEAT_OK")

if __name__ == "__main__":
    main()
