"""
goal_manager.py — 目标追踪管理器

功能：
  - 创建目标（带ID、优先级、里程碑）
  - 更新进度（追加里程碑记录）
  - 查看目标详情
  - 列出所有目标
  - 关闭/归档目标

用法：
  python3 goal_manager.py add "目标名称" --priority P1 --desc "描述"
  python3 goal_manager.py update G001 "完成XX功能"
  python3 goal_manager.py list
  python3 goal_manager.py view G001
  python3 goal_manager.py close G001
  python3 goal_manager.py reopen G001
  python3 goal_manager.py next   # 显示下一个最优先的目标
"""

import json
import os
import sys
import re
import argparse
from pathlib import Path
from datetime import datetime, date
from typing import Optional

# ─── 路径配置 ───────────────────────────────────────────────

WORKSPACE = Path.home() / ".qclaw" / "workspace"
GOALS_DIR = WORKSPACE / "memory" / "goals"
GOALS_FILE = GOALS_DIR / "goals.json"
INDEX_FILE = WORKSPACE / "memory" / "goals" / "GOAL_TRACKER.md"

# ─── 数据结构 ───────────────────────────────────────────────

DEFAULT_GOAL = {
    "id": None,
    "name": "",
    "description": "",
    "status": "active",        # active | completed | waiting | abandoned
    "priority": "P2",
    "created_at": None,
    "updated_at": None,
    "completed_at": None,
    "milestones": [],          # [{"date": "YYYY-MM-DD", "text": "...", "type": "created|update|completed"}]
    "next_step": "",
    "blockers": [],
    "tags": [],
}

# ─── 核心读写 ───────────────────────────────────────────────

def load_goals() -> dict:
    if GOALS_FILE.exists():
        return json.loads(GOALS_FILE.read_text())
    return {"goals": {}, "next_id": 1}

def save_goals(data: dict):
    GOALS_DIR.mkdir(parents=True, exist_ok=True)
    GOALS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    rebuild_index(data)

def rebuild_index(data: dict):
    """从 JSON 生成可读的 Markdown 索引"""
    goals = data["goals"]
    status_emoji = {"active": "🔄", "completed": "✅", "waiting": "⏳", "abandoned": "❌"}
    
    lines = [
        "# 🎯 目标追踪总表",
        f"> _最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
        "## 活跃目标",
        "",
        "| ID | 名称 | 状态 | 优先级 | 创建日期 | 下一步 |",
        "|----|------|------|--------|---------|--------|",
    ]
    
    active = {k: v for k, v in goals.items() if v["status"] in ("active", "waiting")}
    waiting = {k: v for k, v in goals.items() if v["status"] == "waiting"}
    completed = {k: v for k, v in goals.items() if v["status"] == "completed"}
    
    for g in sorted(active.values(), key=lambda x: (x["priority"], x["created_at"])):
        sid = g["id"]
        name = g["name"][:20]
        status = status_emoji.get(g["status"], "❓")
        pri = g["priority"]
        created = g["created_at"][:10] if g["created_at"] else "?"
        next_step = (g.get("next_step") or "")[:25]
        lines.append(f"| {sid} | {name} | {status} | {pri} | {created} | {next_step} |")
    
    if waiting:
        lines.append("")
        lines.append("## ⏳ 等待中的目标（缺外部资源）")
        lines.append("")
        for g in sorted(waiting.values(), key=lambda x: x["created_at"]):
            blockers = ", ".join(g.get("blockers", [])[:2]) or "—"
            lines.append(f"- **{g['id']}** {g['name']} — 阻塞: {blockers}")
    
    if completed:
        lines.append("")
        lines.append("## ✅ 已完成目标")
        lines.append("")
        for g in sorted(completed.values(), key=lambda x: x.get("completed_at", ""), reverse=True)[:10]:
            completed_date = g.get("completed_at", "?")[:10]
            lines.append(f"- **{g['id']}** {g['name']} (完成于 {completed_date})")
    
    lines.append("")
    lines.append("---")
    lines.append(f"_共 {len(goals)} 个目标，{len(active)} 活跃，{len(completed)} 已完成_")
    
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text("\n".join(lines))

# ─── 目标操作 ───────────────────────────────────────────────

def cmd_add(args):
    data = load_goals()
    gid = f"G{len(data['goals']) + 1:03d}"
    
    goal = DEFAULT_GOAL.copy()
    goal.update({
        "id": gid,
        "name": args.name,
        "description": args.desc or "",
        "priority": args.priority or "P2",
        "status": "waiting" if args.waiting else "active",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "next_step": args.next_step or "确定执行计划",
        "milestones": [{
            "date": date.today().isoformat(),
            "text": f"目标创建：{args.name}",
            "type": "created"
        }],
    })
    
    if args.blockers:
        goal["blockers"] = [b.strip() for b in args.blockers.split(",")]
    
    data["goals"][gid] = goal
    save_goals(data)
    print(f"✅ 创建目标 [{gid}]: {args.name}")

def cmd_update(args):
    data = load_goals()
    if args.goal_id not in data["goals"]:
        print(f"❌ 目标 {args.goal_id} 不存在")
        return
    
    goal = data["goals"][args.goal_id]
    
    if args.status:
        goal["status"] = args.status
        if args.status == "completed":
            goal["completed_at"] = datetime.now().isoformat()
        elif goal.get("completed_at"):
            del goal["completed_at"]
    
    if args.text:
        goal["milestones"].append({
            "date": date.today().isoformat(),
            "text": args.text,
            "type": "update"
        })
    
    if args.next_step:
        goal["next_step"] = args.next_step
    
    if args.blockers:
        goal["blockers"] = [b.strip() for b in args.blockers.split(",")]
    
    goal["updated_at"] = datetime.now().isoformat()
    save_goals(data)
    print(f"✅ 更新目标 [{args.goal_id}]: {args.text or args.status or '进度更新'}")

def cmd_view(args):
    data = load_goals()
    if args.goal_id not in data["goals"]:
        print(f"❌ 目标 {args.goal_id} 不存在")
        return
    
    g = data["goals"][args.goal_id]
    status_emoji = {"active": "🔄", "completed": "✅", "waiting": "⏳", "abandoned": "❌"}
    
    print(f"""
╔══════════════════════════════════════════════╗
║  🎯 {g['id']}: {g['name']}
╠══════════════════════════════════════════════╣
║  状态:    {status_emoji.get(g['status'], '❓')} {g['status']}
║  优先级:  {g['priority']}
║  创建于:  {g.get('created_at', '?')[:10]}
║  更新于:  {g.get('updated_at', '?')[:10]}
║  下一步:  {g.get('next_step', '—')}
║  阻塞:    {', '.join(g.get('blockers', [])[:3]) or '—'}
╚══════════════════════════════════════════════╝""")
    
    if g.get("description"):
        print(f"\n📋 描述: {g['description']}\n")
    
    print("📜 里程碑:")
    for m in reversed(g.get("milestones", [])):
        type_icon = {"created": "🆕", "update": "📝", "completed": "✅"}.get(m["type"], "•")
        print(f"  {m['date']} {type_icon} {m['text']}")

def cmd_list(args):
    data = load_goals()
    if not data["goals"]:
        print("暂无目标，使用 `add` 创建第一个目标")
        return
    
    status_emoji = {"active": "🔄", "completed": "✅", "waiting": "⏳", "abandoned": "❌"}
    priority_color = {"P1": "🔴", "P2": "🟡", "P3": "🟢"}
    
    goals = data["goals"]
    if args.filter:
        goals = {k: v for k, v in goals.items() if v["status"] == args.filter}
    
    if args.waiting:
        goals = {k: v for k, v in goals.items() if v["status"] == "waiting"}
    
    if not goals:
        print("无匹配目标")
        return
    
    print(f"🎯 目标列表 (共 {len(goals)} 个)\n")
    for g in sorted(goals.values(), key=lambda x: (x["status"] == "completed", x["priority"], x.get("created_at", ""))):
        sid = g["id"]
        status = status_emoji.get(g["status"], "❓")
        pri = priority_color.get(g["priority"], "⚪")
        next_step = (g.get("next_step") or "—")[:30]
        updated = g.get("updated_at", "?")[:10]
        print(f"  {pri}{g['priority']} {status} **{sid}** {g['name']}")
        print(f"         → {next_step} (更新: {updated})")
        blockers = g.get("blockers", [])
        if blockers:
            print(f"         ⚠️  阻塞: {', '.join(blockers[:2])}")
        print()

def cmd_next(args):
    """显示最优先的待处理目标"""
    data = load_goals()
    active = {k: v for k, v in data["goals"].items() if v["status"] == "active"}
    
    if not active:
        print("✅ 没有进行中的目标")
        return
    
    # 按优先级排序
    top = sorted(active.values(), key=lambda x: (x["priority"], x.get("updated_at", "")))[0]
    print(f"🎯 当前最优先目标 [{top['id']}]: {top['name']}")
    print(f"   优先级: {top['priority']}")
    print(f"   下一步: {top.get('next_step', '—')}")
    
    blockers = top.get("blockers", [])
    if blockers:
        print(f"   阻塞: {', '.join(blockers)}")

def cmd_close(args):
    cmd_update(argparse.Namespace(
        goal_id=args.goal_id, text="目标关闭", status="completed",
        next_step=None, blockers=None
    ))

def cmd_reopen(args):
    cmd_update(argparse.Namespace(
        goal_id=args.goal_id, text="重新激活", status="active",
        next_step=args.next_step or "重新规划", blockers=None
    ))

# ─── 主入口 ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="🎯 目标追踪管理器")
    sub = parser.add_subparsers(dest="cmd")

    p_add = sub.add_parser("add", help="创建新目标")
    p_add.add_argument("name", help="目标名称")
    p_add.add_argument("--desc", help="目标描述")
    p_add.add_argument("--priority", "-p", choices=["P1", "P2", "P3"], default="P2")
    p_add.add_argument("--next", dest="next_step", help="下一步行动")
    p_add.add_argument("--blockers", help="阻塞因素，逗号分隔")
    p_add.add_argument("--waiting", action="store_true", help="标记为等待状态")

    p_update = sub.add_parser("update", help="更新目标进度")
    p_update.add_argument("goal_id", help="目标ID，如 G001")
    p_update.add_argument("text", nargs="?", help="新里程碑描述")
    p_update.add_argument("--status", "-s", choices=["active", "completed", "waiting", "abandoned"])
    p_update.add_argument("--next", dest="next_step", help="更新下一步行动")
    p_update.add_argument("--blockers", help="阻塞因素，逗号分隔")

    p_list = sub.add_parser("list", help="列出所有目标")
    p_list.add_argument("--filter", choices=["active", "completed", "waiting", "abandoned"])
    p_list.add_argument("--waiting", action="store_true")

    p_view = sub.add_parser("view", help="查看目标详情")
    p_view.add_argument("goal_id", help="目标ID")

    sub.add_parser("next", help="显示最优先目标")
    sub.add_parser("close", help="关闭目标").add_argument("goal_id")

    p_reopen = sub.add_parser("reopen", help="重新激活目标")
    p_reopen.add_argument("goal_id")
    p_reopen.add_argument("--next", dest="next_step", help="下一步行动")

    args = parser.parse_args()

    if args.cmd == "add":      cmd_add(args)
    elif args.cmd == "update": cmd_update(args)
    elif args.cmd == "list":   cmd_list(args)
    elif args.cmd == "view":   cmd_view(args)
    elif args.cmd == "next":   cmd_next(args)
    elif args.cmd == "close":  cmd_close(args)
    elif args.cmd == "reopen": cmd_reopen(args)
    else:
        parser.print_help()
        print("\n💡 快速开始:")
        print("  python3 goal_manager.py add '学习Python' -p P3")
        print("  python3 goal_manager.py list")
        print("  python3 goal_manager.py next")

if __name__ == "__main__":
    main()
