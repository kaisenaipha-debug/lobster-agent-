"""
mem0_bridge.py — 长期记忆闭环
支持本地模式（无需 API key）和 API 模式（需要 LLM key）

本地模式：SQLite 向量存储 + 关键词匹配搜索
API 模式：qdrant + Grok/LLM 分析（需要有效 key）
"""

import os
import sys
import argparse
import sqlite3
from pathlib import Path
from datetime import datetime

MEM0_DB = Path.home() / ".qclaw" / "mem0_memory.db"

# ─── 本地 SQLite 模式 ────────────────────────────────────────

def sql_init():
    MEM0_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(MEM0_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user ON memories(user_id)")
    conn.commit()
    return conn

def sql_add(user_id: str, text: str):
    conn = sql_init()
    conn.execute(
        "INSERT INTO memories (user_id, text, created_at) VALUES (?, ?, ?)",
        (user_id, text, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def sql_search(user_id: str, query: str, limit: int = 5) -> list:
    conn = sql_init()
    # 简单关键词匹配
    keywords = [w for w in query if len(w) > 1]
    if not keywords:
        rows = conn.execute(
            "SELECT id, text, created_at FROM memories WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
    else:
        # OR 匹配
        clause = " OR ".join(["text LIKE ?"] * len(keywords))
        params = [f"%{w}%" for w in keywords] + [user_id, limit]
        rows = conn.execute(
            f"SELECT id, text, created_at FROM memories WHERE user_id=? AND ({clause}) ORDER BY created_at DESC LIMIT ?",
            params
        ).fetchall()
    conn.close()
    return [{"id": r[0], "text": r[1], "created_at": r[2], "score": 1.0} for r in rows]

def sql_list(user_id: str, limit: int = 20) -> list:
    conn = sql_init()
    rows = conn.execute(
        "SELECT id, text, created_at FROM memories WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [{"id": r[0], "text": r[1], "created_at": r[2]} for r in rows]

# ─── API 模式（mem0ai + qdrant） ──────────────────────────────

def mem0_add(user_id: str, text: str):
    try:
        from mem0 import Memory
        config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "openclaw_memory",
                    "path": str(Path.home() / ".qclaw" / "mem0_store"),
                }
            },
            "llm": {
                "provider": "litellm",
                "config": {
                    "model": "xai/grok-3-mini",
                    "api_key": os.environ.get("XAI_API_KEY", ""),
                    "api_base": "https://api.x.ai/v1",
                }
            }
        }
        m = Memory.from_config(config)
        result = m.add(text, user_id=user_id)
        return result
    except Exception as e:
        print(f"⚠️ mem0ai 模式失败，使用本地模式: {e}", file=sys.stderr)
        sql_add(user_id, text)
        return {"mode": "local"}

# ─── 命令处理 ─────────────────────────────────────────────────

def cmd_add(args):
    print(f"💾 添加记忆: {args.text[:60]}{'...' if len(args.text) > 60 else ''}")
    result = mem0_add(args.user, args.text)
    print(f"✅ 已记忆 (mode={result.get('mode', 'mem0')})")

def cmd_search(args):
    results = sql_search(args.user, args.query, args.limit)
    if not results:
        print("未找到相关记忆")
        return
    for i, r in enumerate(results, 1):
        print(f"{i}. [{r['score']:.2f}] {r['text'][:100]}{'...' if len(r['text']) > 100 else ''}")

def cmd_list(args):
    results = sql_list(args.user, args.limit)
    if not results:
        print("暂无记忆")
        return
    for i, r in enumerate(results, 1):
        print(f"{i}. [{r['created_at'][:10]}] {r['text'][:100]}{'...' if len(r['text']) > 100 else ''}")

def cmd_sync(args):
    memory_file = Path.home() / ".qclaw" / "workspace" / "MEMORY.md"
    if not memory_file.exists():
        print("MEMORY.md 不存在，跳过")
        return
    content = memory_file.read_text()
    # 按行拆分成独立记忆
    lines = [
        l.strip() for l in content.splitlines()
        if l.strip() and not l.startswith("#") and len(l.strip()) > 5
    ]
    if not lines:
        print("MEMORY.md 为空")
        return
    conn = sql_init()
    for line in lines:
        sql_add(args.user, line)
    conn.close()
    print(f"✅ 已从 MEMORY.md 同步 {len(lines)} 条记忆到本地数据库")
    print(f"   数据库位置: {MEM0_DB}")

# ─── 主入口 ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="mem0 长期记忆桥接")
    parser.add_argument("--user", default="tz", help="用户ID")
    sub = parser.add_subparsers(dest="cmd")

    p_add = sub.add_parser("add", help="添加记忆")
    p_add.add_argument("text", help="记忆内容")

    p_search = sub.add_parser("search", help="搜索记忆")
    p_search.add_argument("query", help="搜索关键词")
    p_search.add_argument("--limit", type=int, default=5)

    p_list = sub.add_parser("list", help="列出所有记忆")
    p_list.add_argument("--limit", type=int, default=20, help="最多显示条数")

    sub.add_parser("sync", help="从 MEMORY.md 同步")

    args = parser.parse_args()

    if getattr(args, "cmd", None) is None:
        parser.print_help()
        return

    if args.cmd == "add":       cmd_add(args)
    elif args.cmd == "search":  cmd_search(args)
    elif args.cmd == "list":    cmd_list(args)
    elif args.cmd == "sync":    cmd_sync(args)


if __name__ == "__main__":
    main()
