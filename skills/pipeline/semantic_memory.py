"""
semantic_memory.py — 语义记忆层 v1.0

原理：用 Groq LLM 替代 embedding 模型，实现语义搜索
- 每次存记忆时，用 Groq 生成语义标签和摘要
- 搜索时，把查询和所有记忆一起给 Groq，让它做语义匹配
- 不需要 sentence-transformers，不依赖外部 embedding 服务

用法：
  python3 semantic_memory.py add "用户喜欢简洁的回复"
  python3 semantic_memory.py search "用户偏好什么沟通方式"
  python3 semantic_memory.py list
  python3 semantic_memory.py stats
"""

import os
import sys
import json
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# ─── 配置 ─────────────────────────────────────────────────

WORKSPACE = Path.home() / ".qclaw" / "workspace"
MEMORY_DB = WORKSPACE / "memory" / "semantic_memory.db"
from _secrets import GROQ_KEY
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# ─── 语义标签生成 ───────────────────────────────────────

def generate_semantic_tags(text: str) -> str:
    """用 Groq 生成记忆的语义标签"""
    prompt = f"""分析以下记忆文本，生成3-5个关键词标签（中文，单词或短语）。

记忆：{text}

输出格式：直接输出标签，用逗号分隔，不要其他文字。
示例输出：用户偏好,沟通风格,工作效率
"""
    
    try:
        import httpx
        r = httpx.post(GROQ_URL, json={
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 50
        }, headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json"
        }, timeout=15)
        data = r.json()
        if "error" not in data:
            return data["choices"][0]["message"]["content"].strip()
    except Exception:
        pass
    
    # 降级：提取关键词
    import re
    words = re.findall(r'[\u4e00-\u9fff]{2,}', text)
    from collections import Counter
    common = Counter(words).most_common(5)
    return ", ".join(w for w, _ in common)

def summarize_memory(text: str) -> str:
    """用 Groq 生成一句话摘要"""
    prompt = f"""用一句话概括以下记忆，10个字以内（中文）：

记忆：{text}

直接输出摘要，不要其他文字。"""
    
    try:
        import httpx
        r = httpx.post(GROQ_URL, json={
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 30
        }, headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json"
        }, timeout=15)
        data = r.json()
        if "error" not in data:
            return data["choices"][0]["message"]["content"].strip()[:30]
    except Exception:
        pass
    
    return text[:30]

# ─── 数据库 ────────────────────────────────────────────────

def init_db():
    MEMORY_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(MEMORY_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            summary TEXT,
            tags TEXT,
            user_id TEXT DEFAULT 'tz',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user ON memories(user_id)")
    conn.commit()
    conn.close()

def add_memory(text: str, user_id: str = "tz") -> dict:
    """添加记忆，自动生成语义标签和摘要"""
    init_db()
    
    print(f"   🏷️ 生成语义标签...")
    tags = generate_semantic_tags(text)
    print(f"   📝 生成摘要...")
    summary = summarize_memory(text)
    
    conn = sqlite3.connect(MEMORY_DB)
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "INSERT INTO memories (text, summary, tags, user_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (text, summary, tags, user_id, now, now)
    )
    mem_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return {"id": mem_id, "tags": tags, "summary": summary}

def semantic_search(query: str, user_id: str = "tz", limit: int = 5) -> List[dict]:
    """语义搜索：用 Groq 判断每条记忆的相关性"""
    init_db()
    conn = sqlite3.connect(MEMORY_DB)
    rows = conn.execute(
        "SELECT id, text, summary, tags FROM memories WHERE user_id=? ORDER BY created_at DESC LIMIT 30",
        (user_id,)
    ).fetchall()
    conn.close()
    
    if not rows:
        return []
    
    # 准备上下文
    memories_text = "\n".join([
        f"[ID {r[0]}] 标签:{r[3]} | 摘要:{r[2]} | 内容:{r[1][:100]}"
        for r in rows
    ])
    
    prompt = f"""你是语义搜索助手。用户查询："{query}"

以下是所有记忆（格式：[ID] 标签 | 摘要 | 内容）：
{memories_text}

任务：从记忆中找出与用户查询最相关的几条，返回格式：
[相关ID] | 相关原因

只返回相关的记忆，格式严格遵守。每条一行。
如果没有相关记忆，返回"无相关记忆"。"""
    
    try:
        import httpx
        r = httpx.post(GROQ_URL, json={
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300
        }, headers={
            "Authorization": f"Bearer {GROQ_KEY}",
            "Content-Type": "application/json"
        }, timeout=20)
        data = r.json()
        if "error" not in data:
            response = data["choices"][0]["message"]["content"]
            # 解析 ID
            import re
            ids = re.findall(r'\[?(\d+)\]?', response)
            id_scores = {}
            for mid in ids:
                id_scores[int(mid)] = 1.0
            # 合并结果
            results = []
            for row in rows:
                if row[0] in id_scores:
                    results.append({
                        "id": row[0],
                        "text": row[1],
                        "summary": row[2],
                        "tags": row[3],
                        "relevance": "high"
                    })
            return results[:limit]
    except Exception as e:
        pass
    
    # 降级：关键词匹配
    keywords = query.split()
    results = []
    for row in rows:
        score = sum(1 for kw in keywords if kw in row[1] or kw in (row[2] or "") or kw in (row[3] or ""))
        if score > 0:
            results.append({
                "id": row[0], "text": row[1], "summary": row[2], "tags": row[3], "relevance": "keyword"
            })
    return results[:limit]

def list_memories(user_id: str = "tz", limit: int = 20) -> List[dict]:
    """列出记忆"""
    init_db()
    conn = sqlite3.connect(MEMORY_DB)
    rows = conn.execute(
        "SELECT id, text, summary, tags, created_at FROM memories WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    return [{"id": r[0], "text": r[1], "summary": r[2], "tags": r[3], "created": r[4][:10]} for r in rows]

def stats() -> dict:
    """统计"""
    init_db()
    conn = sqlite3.connect(MEMORY_DB)
    total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    conn.close()
    return {"total": total, "db_path": str(MEMORY_DB)}

# ─── 主入口 ───────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="🧠 语义记忆层")
    sub = parser.add_subparsers(dest="cmd")

    p_add = sub.add_parser("add", help="添加记忆")
    p_add.add_argument("text", help="记忆内容")

    p_search = sub.add_parser("search", help="语义搜索")
    p_search.add_argument("query", help="搜索查询")
    p_search.add_argument("--limit", type=int, default=5)

    p_list = sub.add_parser("list", help="列出记忆")
    p_list.add_argument("--limit", type=int, default=20)

    sub.add_parser("stats", help="统计")
    sub.add_parser("gc", help="垃圾回收")

    args = parser.parse_args()

    if args.cmd == "add":
        print(f"🧠 添加记忆: {args.text[:50]}...")
        result = add_memory(args.text)
        print(f"✅ 添加成功 [ID {result['id']}]")
        print(f"   标签: {result['tags']}")
        print(f"   摘要: {result['summary']}")

    elif args.cmd == "search":
        print(f"🔍 语义搜索: {args.query}")
        results = semantic_search(args.query, limit=args.limit)
        if not results:
            print("   无相关记忆")
        for r in results:
            print(f"\n  [{r['id']}] {r.get('summary', r['text'][:50])}")
            print(f"      标签: {r.get('tags','')}")
            print(f"      内容: {r['text'][:80]}...")
            print(f"      相关性: {r.get('relevance','')}")

    elif args.cmd == "list":
        memories = list_memories(limit=args.limit)
        print(f"📚 记忆列表 (共 {len(memories)} 条)")
        for m in memories:
            print(f"  [{m['id']}] {m['created']} | {m.get('summary', m['text'][:30])}")

    elif args.cmd == "stats":
        s = stats()
        print(f"📊 记忆统计:")
        print(f"   总数: {s['total']}")
        print(f"   存储: {s['db_path']}")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
