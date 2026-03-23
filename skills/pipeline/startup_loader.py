"""
startup_loader.py — 会话启动上下文加载器

每次新会话开始时，自动加载：
1. 当前活跃目标（goal_tracker）
2. 今日重要进展（memory/YYYY-MM-DD.md）
3. 未解决的待办
4. 最近记忆（mem0）

输出格式：结构化上下文摘要，直接拼接入主会话

用法:
  python3 startup_loader.py [--compact]  # 紧凑模式输出
  python3 startup_loader.py [--verbose]  # 详细模式
"""

import json, sys, sqlite3
from pathlib import Path
from datetime import datetime

# ── 能力扫描（每次启动必须）────────────────────────────────
try:
    _scanner_path = __file__.parent / "capability_scanner.py"
    if _scanner_path.exists():
        import subprocess
        # 运行扫描，更新注册表（静默，只更新文件）
        subprocess.run([sys.executable, str(_scanner_path)], capture_output=True, timeout=30)
except Exception:
    pass

# ── BRAIN 大脑启动 ──────────────────────────────────────────
try:
    _brain_path = Path.home() / ".qclaw" / "BRAIN.py"
    if _brain_path.exists():
        sys.path.insert(0, str(Path.home() / ".qclaw"))
        from BRAIN import boot as _brain_boot, get_brain, get_search
        _brain = _brain_boot()   # 启动时扫描所有能力
        _brain_client_count = len(_brain.clients)
except Exception as e:
    _brain = None
    _brain_client_count = 0
# ───────────────────────────────────────────────────────────

WORKSPACE = Path.home() / ".qclaw" / "workspace"
MEM0_DB = Path.home() / ".qclaw" / "mem0_memory.db"
GOALS_DIR = WORKSPACE / "memory" / "goals"

def load_active_goals():
    if not GOALS_DIR.exists():
        return []
    goals = []
    for f in GOALS_DIR.glob("*.json"):
        g = json.loads(f.read_text())
        if g.get("status") == "active":
            goals.append(g)
    return goals

def load_today_log():
    today = datetime.now().strftime("%Y-%m-%d")
    f = WORKSPACE / "memory" / f"{today}.md"
    if f.exists():
        content = f.read_text(encoding="utf-8")
        # 取最后 2000 字（最新内容）
        return content[-2000:]
    return ""

def load_memories(limit: int = 5):
    if not MEM0_DB.exists():
        return []
    conn = sqlite3.connect(MEM0_DB)
    rows = conn.execute(
        "SELECT text, created_at FROM memories ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return rows

def load_heartbeat_state():
    state_file = WORKSPACE / "memory" / "heartbeat_state.json"
    if state_file.exists():
        return json.loads(state_file.read_text())
    return {}

def main():
    compact = "--compact" in sys.argv
    verbose = "--verbose" in sys.argv

    goals = load_active_goals()
    today_log = load_today_log()
    memories = load_memories(limit=5)
    hb_state = load_heartbeat_state()
    now = datetime.now()

    sections = []

    # ── 头部 ──
    sections.append(f"## 🏠 会话启动上下文 | {now.strftime('%Y-%m-%d %H:%M')}")

    # ── 活跃目标 ──
    if goals:
        sections.append(f"\n### 🎯 进行中的目标 ({len(goals)} 个)")
        for g in goals[:3]:
            steps = g.get("steps", [])
            done = sum(1 for s in steps if s.get("status") == "done")
            bar = f"[{'✅' * done}{'⬜' * (len(steps) - done)}]" if steps else ""
            next_step = next((s["description"] for s in steps
                              if s.get("status") in ("pending", "in_progress")), None)
            sections.append(f"  • **{g['title'][:50]}** {bar}")
            if next_step and verbose:
                sections.append(f"    → 下一步: {next_step[:60]}")
    else:
        sections.append("\n### 🎯 进行中的目标：无")

    # ── 今日进展 ──
    if today_log:
        lines = [l.strip() for l in today_log.splitlines() if l.strip() and not l.startswith("#")]
        # 取最新的10行
        recent = lines[-10:] if len(lines) > 10 else lines
        sections.append("\n### 📅 今日进展")
        for l in recent:
            if len(l) > 100:
                l = l[:100] + "..."
            sections.append(f"  • {l}")

    # ── 长期记忆 ──
    if memories:
        sections.append(f"\n### 🧠 相关记忆 ({len(memories)} 条)")
        for text, created in memories[:5]:
            date = created[:10]
            text = text[:80] + ("..." if len(text) > 80 else "")
            sections.append(f"  • [{date}] {text}")

    # ── 心跳状态 ──
    if hb_state:
        last = hb_state.get("last_run", "从未")
        last_task = hb_state.get("last_task", "无")
        if not compact:
            sections.append(f"\n### 💓 心跳状态: 最近 {last[:16]} 执行了「{last_task}」")

    # ── 紧凑输出（只有目标） ──
    if compact:
        output_lines = [f"**{now.strftime('%H:%M')} 会话 | {len(goals)} 个活跃目标**"]
        if goals:
            for g in goals[:3]:
                output_lines.append(f"  🎯 {g['title'][:50]}")
        print("\n".join(output_lines))
    else:
        print("\n".join(sections))

if __name__ == "__main__":
    main()
