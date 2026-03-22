"""
session_summary.py — 对话总结与记忆归档

在长对话结束时（或定时），提取关键信息并：
1. 追加到今日 memory/YYYY-MM-DD.md
2. 存入 mem0 SQLite（长期记忆）
3. 评估是否有未完成的目标，需要创建 goal

用法:
  python3 session_summary.py "今天我们讨论了X，做了Y，结论是Z"
  python3 session_summary.py --from-file session_transcript.txt
  python3 session_summary.py --goal-suggest "竞品研究需要继续跟进"
"""

import sys, json, os, re
from datetime import datetime
from pathlib import Path

from _secrets import GROQ_KEY
WORKSPACE = Path.home() / ".qclaw" / "workspace"
MEM0_DB = Path.home() / ".qclaw" / "mem0_memory.db"
GOAL_TRACKER = Path.home() / ".qclaw" / "workspace" / "skills" / "pipeline" / "goal_tracker.py"

# ─── Groq 提取关键信息 ─────────────────────────────────

def extract_summary(text: str) -> dict:
    """用 Groq 提取关键信息并结构化"""
    import httpx
    prompt = f"""分析以下对话记录，提取关键信息，输出 JSON：

{{
  "what_happened": "发生了什么（3句以内）",
  "decisions": ["关键决策1", "关键决策2"],
  "decisions": ["结论1", "结论2"],
  "unfinished": "未完成的事情（如果没有则写'无'）",
  "action_items": ["待办1", "待办2"],
  "insights": ["学到的有价值信息1", "有价值信息2"],
  "goal_candidates": ["可以创建为长线目标的事项，如果没有则为空数组"]
}}

对话记录：
{text}

直接输出 JSON，不要有其他内容。"""
    
    r = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        json={"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}], "max_tokens": 600},
        headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
        timeout=20
    )
    data = r.json()
    if "error" in data:
        return {"error": data["error"]["message"]}
    
    try:
        match = re.search(r'\{.*?"what_happened".*?\}', data["choices"][0]["message"]["content"], re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    
    return {"what_happened": text[:200], "decisions": [], "action_items": [], "unfinished": "无"}

# ─── 写入记忆 ─────────────────────────────────────────────

def save_to_memory(data: dict, raw_text: str):
    today = datetime.now().strftime("%Y-%m-%d")
    mem_file = WORKSPACE / "memory" / f"{today}.md"
    mem_file.parent.mkdir(parents=True, exist_ok=True)
    
    now = datetime.now().strftime("%H:%M")
    lines = [f"\n## [{now}] 会话总结", f"- **事件**: {data.get('what_happened', '')}"]
    
    if data.get("decisions"):
        lines.append(f"- **决策**: {', '.join(data['decisions'])}")
    if data.get("action_items"):
        lines.append(f"- **待办**: {', '.join(data['action_items'])}")
    if data.get("unfinished") and data["unfinished"] != "无":
        lines.append(f"- **未完成**: {data['unfinished']}")
    if data.get("insights"):
        lines.append(f"- **洞察**: {data['insights'][0]}")
    
    existing = mem_file.read_text() if mem_file.exists() else ""
    mem_file.write_text(existing + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"✅ 写入今日日志: {mem_file.name}")

def save_to_mem0(data: dict, raw_text: str):
    if not MEM0_DB.exists():
        return
    
    import sqlite3
    conn = sqlite3.connect(MEM0_DB)
    
    # 关键决策
    for d in data.get("decisions", []):
        conn.execute(
            "INSERT INTO memories (user_id, text, created_at) VALUES (?, ?, ?)",
            ("tz", f"决策: {d}", datetime.now().isoformat())
        )
    
    # 待办
    for a in data.get("action_items", []):
        conn.execute(
            "INSERT INTO memories (user_id, text, created_at) VALUES (?, ?, ?)",
            ("tz", f"待办: {a}", datetime.now().isoformat())
        )
    
    # 有价值的洞察
    for i in data.get("insights", []):
        conn.execute(
            "INSERT INTO memories (user_id, text, created_at) VALUES (?, ?, ?)",
            ("tz", f"洞察: {i}", datetime.now().isoformat())
        )
    
    conn.commit()
    conn.close()
    print("✅ 写入长期记忆库")

# ─── 目标建议 ─────────────────────────────────────────────

def suggest_goals(data: dict):
    """如果有值得追踪的目标，建议创建"""
    candidates = data.get("goal_candidates", [])
    if not candidates:
        return
    
    print(f"\n🎯 建议创建以下长线目标：")
    for i, c in enumerate(candidates, 1):
        print(f"  {i}. {c}")
    
    print(f"\n创建命令：")
    for c in candidates:
        safe_id = re.sub(r'[^\w]', '_', c[:30])
        print(f"  python3 {GOAL_TRACKER} new \"{c}\" --auto")

# ─── 主入口 ───────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="对话总结与记忆归档")
    parser.add_argument("text", nargs="?", help="对话记录文本")
    parser.add_argument("--from-file", help="从文件读取对话记录")
    args = parser.parse_args()
    
    if args.from_file:
        text = Path(args.from_file).read_text(encoding="utf-8", errors="ignore")
    elif args.text:
        text = args.text
    else:
        print("请提供对话内容，或用 --from-file 指定文件")
        sys.exit(1)
    
    print(f"📝 分析中（{len(text)} 字）...")
    data = extract_summary(text)
    
    if "error" in data:
        print(f"❌ 提取失败: {data['error']}")
        sys.exit(1)
    
    print(f"\n{'='*40}")
    print(f"💡 发生了什么: {data.get('what_happened','')}")
    if data.get("decisions"):
        print(f"📌 决策: {', '.join(data['decisions'])}")
    if data.get("action_items"):
        print(f"📋 待办: {', '.join(data['action_items'])}")
    if data.get("unfinished") and data["unfinished"] != "无":
        print(f"⏳ 未完成: {data['unfinished']}")
    
    # 归档
    save_to_memory(data, text)
    save_to_mem0(data, text)
    suggest_goals(data)

if __name__ == "__main__":
    main()
