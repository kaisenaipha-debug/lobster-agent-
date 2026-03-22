#!/usr/bin/env python3
import sys, os
sys.path.insert(0, '/Users/tz/.qclaw/workspace/skills/pipeline')
from evolution_engine import evolve, format_output

cases = [
    ("明天有个重要的事", "NEEDS_HUMAN"),
    ("帮我研究政府客户情报", "COMPLETED"),
    ("查一下这个局", "NEEDS_HUMAN"),
    ("发封邮件给客户", "NEEDS_HUMAN"),
    ("诊断一下系统", "COMPLETED"),
]
print("=== evolution_engine 测试 ===\n")
all_pass = True
for raw, expected in cases:
    r = evolve(raw)
    ok = "PASS" if r["type"] == expected else "FAIL"
    if ok == "FAIL":
        all_pass = False
    print(f"[{ok}] {raw}")
    print(f"  类型: {r['type']} (期望: {expected})")
    print(f"  格式化: {format_output(r)[:80]}")
    print()
print("全部通过" if all_pass else "有失败项")
