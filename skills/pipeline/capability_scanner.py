#!/usr/bin/env python3
"""
capability_scanner.py — 启动时自动扫描所有 pipeline 文件，生成能力清单
每次新会话启动时运行，更新 CAPABILITY_REGISTRY.json

用法（每次启动自动调用）:
  python3 capability_scanner.py
"""

import ast, json, re
from pathlib import Path
from datetime import datetime

WORKSPACE = Path.home() / ".qclaw" / "workspace"
PIPELINE = WORKSPACE / "skills" / "pipeline"
SKILLS_DIR = WORKSPACE / "skills"
REGISTRY_FILE = WORKSPACE / "CAPABILITY_REGISTRY.json"

# ─── 已知的管道能力（从文件头推断）─────────────────────────

PIPELINE_CAPABILITIES = {
    "http_pool": {
        "name": "多路径HTTP搜索",
        "category": "perception",
        "description": "搜狗微信/搜狗网页/百度，自动切换路径",
        "tools": ["http_pool.py"],
        "status": "active",
        "key_funcs": ["search", "MultiSearch.search", "MultiSearch.search_all"],
    },
    "scenario_engine": {
        "name": "S++政府客户七模型分析",
        "category": "cognition",
        "description": "Cynefin分类+OODA弱信号+红队+二阶推演+叙事+心智模拟+五阶段",
        "tools": ["scenario_engine.py"],
        "status": "active",
        "key_funcs": ["process_plus", "classify_cynefin", "detect_weak", "red_team"],
    },
    "agent_loop": {
        "name": "政府客户智能路由",
        "category": "tools",
        "description": "government/search/client/general 四路自动分流",
        "tools": ["agent_loop.py"],
        "status": "active",
        "key_funcs": ["Router.route", "handle_government", "handle_search", "run"],
    },
    "heartbeat_engine": {
        "name": "主动心跳引擎",
        "category": "proactive",
        "description": "系统健康+客户追踪+记忆激活+洞察发现，有预警时推送",
        "tools": ["heartbeat_engine.py"],
        "status": "active",
        "key_funcs": ["task_client_check", "task_system_health", "run_heartbeat"],
    },
    "evolution_engine": {
        "name": "实时进化引擎",
        "category": "proactive",
        "description": "意图理解+障碍检测+技能获取+进化记忆写入",
        "tools": ["evolution_engine.py"],
        "status": "active",
        "key_funcs": ["understand_intent", "plan_execution", "detect_obstacle", "evolve"],
    },
    "self_healer": {
        "name": "自动修复引擎",
        "category": "proactive",
        "description": "venv检查+API健康+依赖修复+配置恢复",
        "tools": ["self_healer.py"],
        "status": "active",
        "key_funcs": ["fix_all", "diagnose", "check"],
    },
    "crawl_pipeline": {
        "name": "爬取分析Pipeline",
        "category": "perception",
        "description": "Groq+LLM正文提取+结构化分析",
        "tools": ["crawl_pipeline.py"],
        "status": "active",
        "key_funcs": ["extract", "analyze", "crawl"],
    },
    "browser_control": {
        "name": "浏览器自动化",
        "category": "tools",
        "description": "Playwright+LLM问答+可视化截图",
        "tools": ["browser_control.py", "human_browser.py"],
        "status": "active",
        "key_funcs": ["browser_act", "browser_screenshot", "browser_snapshot"],
    },
    "mem0_bridge": {
        "name": "语义记忆桥接",
        "category": "memory",
        "description": "mem0ai向量存储+查询+与探针协同",
        "tools": ["mem0_bridge.py"],
        "status": "active",
        "key_funcs": ["add_memory", "query_memories"],
    },
    "capability_registry": {
        "name": "能力注册表管理",
        "category": "brain",
        "description": "32项能力量化评分+进化追踪+健康报告",
        "tools": ["capability_registry.py"],
        "status": "active",
        "key_funcs": ["get_full_report", "upgrade_capability", "get_health_summary"],
    },
    "auto_upgrade_engine": {
        "name": "自动升级引擎",
        "category": "proactive",
        "description": "能力差距检测+升级计划生成+注册表更新",
        "tools": ["auto_upgrade_engine.py"],
        "status": "active",
        "key_funcs": ["check_gaps", "generate_upgrade_plan"],
    },
    "skill_guardian": {
        "name": "技能守护",
        "category": "tools",
        "description": "技能目录监控+冲突检测+安装验证",
        "tools": ["skill_guardian.py"],
        "status": "active",
        "key_funcs": ["scan_skills", "api"],
    },
    "gap_recorder": {
        "name": "能力缺口记录",
        "category": "memory",
        "description": "缺口记录+升级队列+统计分析",
        "tools": ["gap_recorder.py"],
        "status": "active",
        "key_funcs": ["record_gap", "get_pending_upgrades"],
    },
    "reasoning_probe": {
        "name": "推理探针",
        "category": "cognition",
        "description": "推理路径记录+弱信号检测+逻辑链路分析",
        "tools": ["reasoning_probe.py"],
        "status": "active",
        "key_funcs": ["log_reasoning", "detect_signal"],
    },
    "memory_probe": {
        "name": "记忆命中率探针",
        "category": "memory",
        "description": "查询命中率统计+记忆同步",
        "tools": ["memory_probe.py"],
        "status": "active",
        "key_funcs": ["sync_query_with_probe", "get_memory_hit_rate"],
    },
    "github_sync": {
        "name": "GitHub同步",
        "category": "tools",
        "description": "通过GitHub API推送pipeline文件（绕过代理封锁）",
        "tools": ["github_sync.py"],
        "status": "active",
        "key_funcs": ["push_file", "sync_all"],
    },
    "goal_tracker": {
        "name": "目标追踪",
        "category": "brain",
        "description": "目标分解+状态管理+下一步推荐",
        "tools": ["goal_tracker.py"],
        "status": "active",
        "key_funcs": ["track_goal", "get_next_action"],
    },
    "executor": {
        "name": "任务执行器",
        "category": "tools",
        "description": "原子步骤执行+结果验证+失败重试",
        "tools": ["executor.py"],
        "status": "active",
        "key_funcs": ["execute_step", "retry"],
    },
    "startup_loader": {
        "name": "启动加载器",
        "category": "proactive",
        "description": "会话启动时加载能力注册表+健康检查+预警",
        "tools": ["startup_loader.py"],
        "status": "active",
        "key_funcs": ["load", "check"],
    },
    "delivery-list-generator": {
        "name": "发货清单生成",
        "category": "output",
        "description": "博敏电子模板像素级还原，Excel格式",
        "tools": ["delivery-list-generator/generator.py"],
        "status": "active",
        "key_funcs": ["generate", "render"],
    },
}

# ─── 扫描器 ──────────────────────────────────────────────

def scan_pipeline_files():
    """检查 pipeline 目录下哪些文件实际存在"""
    existing = {}
    for name, info in PIPELINE_CAPABILITIES.items():
        for tool in info["tools"]:
            path = PIPELINE / tool
            if tool.startswith("delivery"):
                path = SKILLS_DIR / tool
            if path.exists():
                existing[name] = info.copy()
                existing[name]["file_exists"] = True
                existing[name]["last_modified"] = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
                break
        else:
            existing[name] = {**info, "file_exists": False}
    return existing


def scan_untracked_files():
    """扫描目录中发现但不在注册表中的新文件"""
    tracked = set()
    for tools in PIPELINE_CAPABILITIES.values():
        tracked.update(tools.get("tools", []))

    untracked = []
    for py_file in PIPELINE.glob("*.py"):
        if py_file.name.startswith("_") or py_file.name.startswith("test_"):
            continue
        if py_file.name not in tracked:
            # 读取文件获取函数列表
            try:
                tree = ast.parse(py_file.read_text())
                funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.col_offset == 0]
                if funcs:
                    untracked.append({
                        "file": py_file.name,
                        "funcs": funcs[:8],
                        "size": py_file.stat().st_size,
                    })
            except:
                pass
    return untracked


def build_registry_update(scanned: dict, untracked: list) -> dict:
    """根据扫描结果构建注册表更新"""
    # 读取现有注册表
    if REGISTRY_FILE.exists():
        registry = json.loads(REGISTRY_FILE.read_text())
    else:
        registry = {"capabilities": {}, "evolution_log": []}

    updates = []
    for name, info in scanned.items():
        cap_id = f"pipeline_{name}"
        if cap_id not in registry.get("capabilities", {}):
            registry["capabilities"][cap_id] = {
                "name": info["name"],
                "category": info["category"],
                "description": info["description"],
                "tools": info["tools"],
                "status": "active" if info.get("file_exists") else "missing",
                "last_verified": datetime.now().isoformat(),
                "evolution_history": [],
                "dimensions": {
                    "无缝": 7, "安全": 8, "丝滑": 7, "智商": 7
                }
            }
            updates.append(cap_id)
        else:
            # 更新最后验证时间
            registry["capabilities"][cap_id]["last_verified"] = datetime.now().isoformat()
            if not info.get("file_exists"):
                registry["capabilities"][cap_id]["status"] = "missing"

    return registry, updates, untracked


def run_scan():
    """主扫描函数"""
    print("🔍 扫描 pipeline 能力...\n")

    scanned = scan_pipeline_files()
    untracked = scan_untracked_files()

    active = [n for n, i in scanned.items() if i.get("file_exists")]
    missing = [n for n, i in scanned.items() if not i.get("file_exists")]

    print(f"✅ 活跃能力: {len(active)}")
    for n in active:
        print(f"   • {n}: {scanned[n]['name']}")

    if missing:
        print(f"\n❌ 缺失能力: {len(missing)}")
        for n in missing:
            print(f"   • {n}")

    if untracked:
        print(f"\n🆕 未注册新文件: {len(untracked)}")
        for u in untracked:
            print(f"   • {u['file']} ({u['size']} bytes) — funcs: {', '.join(u['funcs'][:4])}")

    # 更新注册表
    registry, new_caps, new_files = build_registry_update(scanned, untracked)

    if new_caps or new_files:
        REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY_FILE.write_text(json.dumps(registry, ensure_ascii=False, indent=2))
        print(f"\n📝 注册表已更新: {len(new_caps)} 新增能力, {len(new_files)} 未注册文件")

    # 打印摘要
    total = len(registry.get("capabilities", {}))
    active_count = sum(1 for c in registry["capabilities"].values() if c["status"] == "active")
    print(f"\n📊 能力总数: {total} | 活跃: {active_count} | 缺失: {total - active_count}")

    return {
        "active": active,
        "missing": missing,
        "untracked": untracked,
        "registry_updated": bool(new_caps or new_files),
        "total_caps": total,
    }


if __name__ == "__main__":
    result = run_scan()
    if not result["registry_updated"]:
        print("\n✅ 扫描完成，注册表无需更新")
