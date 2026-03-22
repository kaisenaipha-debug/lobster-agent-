"""
goal_tracker.py — 长线目标追踪系统

每个目标一个 JSON 文件，自动记录：
- 目标创建时间
- 分解的子步骤
- 每个步骤的状态（pending/in_progress/done/blocked）
- 最新更新时间
- 关键决策记录

用法:
  python3 goal_tracker.py new "研究竞品A的动态" --tags 研究,竞品
  python3 goal_tracker.py list
  python3 goal_tracker.py update <id> <step_id> --status done
  python3 goal_tracker.py show <id>
  python3 goal_tracker.py next     # 展示当前最需要推进的下一个动作
"""

import os, sys, json, uuid, argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

GOALS_DIR = Path.home() / ".qclaw" / "workspace" / "memory" / "goals"
GOALS_DIR.mkdir(parents=True, exist_ok=True)

# ─── 存储 ─────────────────────────────────────────────────

def load_goal(goal_id: str) -> Optional[dict]:
    path = GOALS_DIR / f"{goal_id}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None

def save_goal(goal: dict):
    path = GOALS_DIR / f"{goal['id']}.json"
    path.write_text(json.dumps(goal, ensure_ascii=False, indent=2), encoding="utf-8")

def list_goals() -> list[dict]:
    goals = []
    for f in GOALS_DIR.glob("*.json"):
        g = json.loads(f.read_text())
        g["_file"] = f.name
        goals.append(g)
    goals.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return goals

# ─── 步骤解析 ─────────────────────────────────────────────

def parse_steps(text: str) -> list[dict]:
    """从自然语言描述自动分解子步骤"""
    import httpx
    prompt = f"""把以下目标分解成具体的执行步骤。

要求：
- 每个步骤是独立可执行的动作
- 步骤数量 3-8 个
- 输出 JSON 格式：{{"steps": [{{"id": "1", "description": "...", "status": "pending"}}, ...]}}

目标：{text}

直接输出 JSON，不要解释。"""
    
    try:
        r = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}], "max_tokens": 500},
            headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
            timeout=15
        )
        data = r.json()
        if "error" not in data:
            import re
            match = re.search(r'\{.*?"steps".*?\}', data["choices"][0]["message"]["content"], re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                return parsed.get("steps", [])
    except Exception:
        pass
    
    # 降级：简单按行分解
    steps = [{"id": str(i+1), "description": line.strip(), "status": "pending"}
             for i, line in enumerate(text.split("→")) if line.strip()]
    if not steps:
        steps = [{"id": "1", "description": text[:100], "status": "pending"}]
    return steps

# ─── 命令 ──────────────────────────────────────────────────

def cmd_new(args):
    goal_id = str(uuid.uuid4())[:8]
    steps = []
    
    if args.steps:
        steps = [{"id": str(i+1), "description": s.strip(), "status": "pending"}
                 for i, s in enumerate(args.steps.split("|")) if s.strip()]
    elif args.auto:
        print("🤖 正在用 Groq 自动分解目标...", file=sys.stderr)
        steps = parse_steps(args.text)
        print(f"✅ 分解为 {len(steps)} 个步骤", file=sys.stderr)
    
    goal = {
        "id": goal_id,
        "title": args.text,
        "tags": args.tags.split(",") if args.tags else [],
        "steps": steps,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "status": "active",  # active | completed | blocked
        "decisions": [],
        "notes": [],
    }
    save_goal(goal)
    print(f"✅ 目标已创建: [{goal_id}]")
    print(f"   {args.text}")
    if steps:
        print(f"   子步骤: {len(steps)} 个")
    else:
        print("   (无子步骤，用 --auto 让 Groq 自动分解)")

def cmd_list(args):
    goals = list_goals()
    if not goals:
        print("暂无目标，创建第一个：goal_tracker.py new \"目标描述\" --auto")
        return
    
    active = [g for g in goals if g.get("status") == "active"]
    done = [g for g in goals if g.get("status") == "completed"]
    
    print(f"📋 目标列表（共 {len(goals)} 个，{len(active)} 进行中）\n")
    for g in goals:
        steps = g.get("steps", [])
        done_count = len([s for s in steps if s.get("status") == "done"])
        bar = f"[{'✅' * done_count}{'⬜' * (len(steps) - done_count)}]" if steps else ""
        updated = g.get("updated_at", "")[:10]
        print(f"[{g['id']}] {bar} {g['title'][:40]}")
        print(f"        更新: {updated} | 状态: {g['status']} | 标签: {','.join(g.get('tags',[])) or '无'}")
        print()

def cmd_show(args):
    goal = load_goal(args.goal_id)
    if not goal:
        print(f"❌ 未找到目标: {args.goal_id}")
        return
    
    print(f"# 🎯 {goal['title']}")
    print(f"**ID**: {goal['id']}")
    print(f"**状态**: {goal['status']}")
    print(f"**标签**: {', '.join(goal.get('tags', [])) or '无'}")
    print(f"**创建**: {goal['created_at'][:19]}")
    print(f"**更新**: {goal['updated_at'][:19]}")
    
    if goal.get("steps"):
        print(f"\n## 📌 子步骤")
        for s in goal["steps"]:
            icon = {"done": "✅", "in_progress": "🔄", "blocked": "🚫", "pending": "⬜"}.get(s.get("status"), "⬜")
            print(f"  {icon} [{s['id']}] {s['description']}")
    
    if goal.get("decisions"):
        print(f"\n## 💡 关键决策")
        for d in goal["decisions"][-3:]:
            print(f"  - {d}")
    
    if goal.get("notes"):
        print(f"\n## 📝 备注")
        for n in goal["notes"][-3:]:
            print(f"  - {n}")

def cmd_update(args):
    goal = load_goal(args.goal_id)
    if not goal:
        print(f"❌ 未找到目标: {args.goal_id}")
        return
    
    if args.step_id:
        for s in goal["steps"]:
            if s["id"] == args.step_id:
                old = s["status"]
                s["status"] = args.status
                print(f"✅ 步骤 [{args.step_id}] {old} → {args.status}")
                break
        else:
            print(f"❌ 未找到步骤: {args.step_id}")
            return
    elif args.status:
        goal["status"] = args.status
        print(f"✅ 目标状态 → {args.status}")
    
    if args.note:
        goal["notes"].append(f"[{datetime.now().strftime('%m/%d %H:%M')}] {args.note}")
    
    if args.decision:
        goal["decisions"].append(f"[{datetime.now().strftime('%m/%d %H:%M')}] {args.decision}")
    
    goal["updated_at"] = datetime.now().isoformat()
    save_goal(goal)
    
    # 检查是否全部完成
    if all(s.get("status") == "done" for s in goal.get("steps", [])):
        print("🎉 所有子步骤完成！目标自动标记为 completed")
        goal["status"] = "completed"
        save_goal(goal)

def cmd_next(args):
    """展示当前最需要推进的目标和下一步"""
    goals = [g for g in list_goals() if g.get("status") == "active"]
    if not goals:
        print("🎯 没有进行中的目标，创建第一个吧！")
        return
    
    goal = goals[0]  # 取最新的
    next_step = next((s for s in goal.get("steps", []) if s.get("status") in ("pending", "in_progress")), None)
    
    print(f"🎯 **{goal['title']}** [{goal['id']}]")
    if next_step:
        print(f"\n➡️  **下一步**: {next_step['description']}")
        print(f"   步骤 {next_step['id']}/{len(goal.get('steps', []))}")
    else:
        print("\n所有步骤已完成！")
    
    others = len(goals) - 1
    if others:
        print(f"\n还有 {others} 个进行中的目标")

def cmd_done(args):
    goal = load_goal(args.goal_id)
    if not goal:
        print(f"❌ 未找到目标: {args.goal_id}")
        return
    goal["status"] = "completed"
    goal["completed_at"] = datetime.now().isoformat()
    goal["updated_at"] = datetime.now().isoformat()
    for s in goal.get("steps", []):
        s["status"] = "done"
    save_goal(goal)
    print(f"✅ 目标 [{args.goal_id}] 已完成！")

# ─── 主入口 ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="目标追踪系统")
    sub = parser.add_subparsers(dest="cmd")
    
    p_new = sub.add_parser("new", help="创建新目标")
    p_new.add_argument("text", help="目标描述")
    p_new.add_argument("--auto", action="store_true", help="用 Groq 自动分解子步骤")
    p_new.add_argument("--steps", help="手动指定步骤，用 | 分隔")
    p_new.add_argument("--tags", help="标签，逗号分隔")
    
    sub.add_parser("list", help="列出所有目标")
    
    p_show = sub.add_parser("show", help="查看目标详情")
    p_show.add_argument("goal_id")
    
    p_up = sub.add_parser("update", help="更新目标或步骤")
    p_up.add_argument("goal_id")
    p_up.add_argument("step_id", nargs="?", help="步骤ID")
    p_up.add_argument("--status", choices=["pending","in_progress","done","blocked"])
    p_up.add_argument("--note", help="添加备注")
    p_up.add_argument("--decision", help="记录决策")
    
    sub.add_parser("next", help="查看下一个要推进的目标")
    
    p_done = sub.add_parser("done", help="标记目标完成")
    p_done.add_argument("goal_id")
    
    args = parser.parse_args()
    
    if args.cmd == "new":       cmd_new(args)
    elif args.cmd == "list":    cmd_list(args)
    elif args.cmd == "show":    cmd_show(args)
    elif args.cmd == "update":  cmd_update(args)
    elif args.cmd == "next":    cmd_next(args)
    elif args.cmd == "done":    cmd_done(args)
    else:                       parser.print_help()

if __name__ == "__main__":
    main()
