"""
reasoning_log.py — 推理过程外化系统

目的：
  边界2「推理时不观察自己」的解法
  把推理过程写下来，之后可以回看

用法：
  python3 reasoning_log.py log "问题" "推理链" [结论]
  python3 reasoning_log.py compare "问题"
  python3 reasoning_log.py recent
  python3 reasoning_log.py search "问题"
"""

import json
import sys
from pathlib import Path
from datetime import datetime

WORKSPACE = Path.home() / ".qclaw" / "workspace"
REASONING_FILE = WORKSPACE / "memory" / "reasoning_log.json"
JUDGMENT_FILE = WORKSPACE / "memory" / "judgment_comparison.json"

def load_reasoning() -> list:
    if REASONING_FILE.exists():
        return json.loads(REASONING_FILE.read_text())
    return []

def save_reasoning(data: list):
    REASONING_FILE.parent.mkdir(parents=True, exist_ok=True)
    REASONING_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def load_judgments() -> list:
    if JUDGMENT_FILE.exists():
        return json.loads(JUDGMENT_FILE.read_text())
    return []

def save_judgments(data: list):
    JUDGMENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    JUDGMENT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def find_similar(question: str, data: list, threshold: float = 0.5) -> list:
    q_words = set(question.lower().split())
    similar = []
    for d in data[-30:]:
        d_words = set(d.get("question", "").lower().split())
        if not q_words or not d_words:
            continue
        intersection = len(q_words & d_words)
        union = len(q_words | d_words)
        score = intersection / union if union > 0 else 0
        if score >= threshold:
            similar.append(d)
    return similar

def log_reasoning(question: str, reasoning: str, conclusion: str = "", domain: str = "general") -> str:
    data = load_reasoning()
    similar = find_similar(question, data)
    updated = [s["id"] for s in similar] if similar else []
    if similar:
        for s in similar:
            for d in data:
                if d["id"] == s["id"]:
                    d["superseded_by"] = f"R{len(data)+1:04d}"

    entry = {
        "id": f"R{len(data)+1:04d}",
        "question": question,
        "reasoning": reasoning,
        "conclusion": conclusion,
        "domain": domain,
        "confidence": None,
        "recorded_at": datetime.now().isoformat(),
        "updated_judgments": updated,
    }
    data.insert(0, entry)
    data = data[:100]
    save_reasoning(data)
    return entry["id"]

def log_judgment(question: str, judgment: str, confidence: int, domain: str = "general"):
    data = load_judgments()
    for d in data[:5]:
        if d.get("question", "").lower() == question.lower():
            return {"status": "duplicate", "id": d.get("id")}
    entry = {
        "id": f"J{len(data)+1:04d}",
        "question": question,
        "judgment": judgment,
        "confidence": confidence,
        "domain": domain,
        "recorded_at": datetime.now().isoformat(),
    }
    data.insert(0, entry)
    data = data[:100]
    save_judgments(data)
    return {"status": "recorded", "id": entry["id"]}

def compare_judgments(question: str) -> dict:
    data = load_reasoning()
    similar = find_similar(question, data)
    if not similar:
        return {"status": "no_history"}
    conclusions = [s.get("conclusion", "") for s in similar if s.get("conclusion")]
    change = len(set(c for c in conclusions if c)) > 1 if conclusions else False
    return {
        "status": "found",
        "count": len(similar),
        "change": change,
        "entries": [{"id": s["id"], "conclusion": s.get("conclusion",""), "at": s.get("recorded_at","")[:10]} for s in similar],
    }

def recent(n: int = 10) -> list:
    return load_reasoning()[:n]

def main():
    args = sys.argv[1:]
    if not args:
        print("用法：log|compare|recent|search")
        for r in recent(5):
            print(f"  [{r['id']}] {r['question'][:60]}")
        return
    cmd = args[0]
    if cmd == "log" and len(args) >= 3:
        rid = log_reasoning(args[1], args[2], args[3] if len(args) > 3 else "", args[4] if len(args) > 4 else "general")
        print(f"推理已记录 [{rid}]")
    elif cmd == "compare" and len(args) >= 2:
        r = compare_judgments(args[1])
        print(f"历史判断: {'无' if r['status']=='no_history' else str(r['count'])+'条, 变化:'+str(r['change'])}")
        for e in r.get("entries", []):
            print(f"  [{e['id']}] {e.get('conclusion','')[:60] or '(无结论)'} | {e['at']}")
    elif cmd == "recent":
        n = int(args[1]) if len(args) > 1 else 10
        for r in recent(n):
            print(f"[{r['id']}] {r['question'][:60]}")
            print(f"  置信:{r.get('confidence','?')} | {r.get('recorded_at','?')[:10]}")
    else:
        print("未知命令")

if __name__ == "__main__":
    main()
