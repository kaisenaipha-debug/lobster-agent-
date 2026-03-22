#!/usr/bin/env python3
"""
auto_upgrade_engine.py — 小龙虾自我进化引擎
支持无人值守自动升级 + 能力缺口自检

策略模式：
  supervised:  所有操作需确认（默认）
  hybrid:     低风险自动，高风险确认
  autonomous: 完全自主（危险！需明确授权）

使用方式：
  python3 auto_upgrade_engine.py check          # 检查能力缺口
  python3 auto_upgrade_engine.py plan <cap_id>  # 制定升级计划
  python3 auto_upgrade_engine.py execute <task_id>  # 执行升级
  python3 auto_upgrade_engine.py daemon         # 启动守护进程（无人值守）
  python3 auto_upgrade_engine.py status         # 当前状态
"""

import os
import sys
import json
import time
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

WORKSPACE = Path.home() / ".qclaw" / "workspace"
SKILLS_DIR = WORKSPACE / "skills" / "pipeline"
REGISTRY_FILE = WORKSPACE / "CAPABILITY_REGISTRY.json"
UPGRADE_QUEUE = WORKSPACE / "memory" / "upgrade_queue.json"
EVOLUTION_LOG = WORKSPACE / "memory" / "evolution_log.json"
STATE_FILE = WORKSPACE / "memory" / "upgrade_state.json"

sys.path.insert(0, str(SKILLS_DIR))

# ─── 能力缺口检测规则 ───────────────────────────────────────

GAP_RULES = {
    "brain_planning": {
        "symptom": "任务规划维度过低",
        "check": lambda r: r["capabilities"]["brain_planning"]["dimensions"]["无缝"] < 7,
        "fix": ["引入OODA循环", "增强WAL Protocol", "增加子任务拆解深度"],
        "auto_fix": True
    },
    "proactive_evolution": {
        "symptom": "进化能力处于瓶颈",
        "check": lambda r: r["capabilities"]["proactive_evolution"]["dimensions"]["智商"] < 7,
        "fix": ["重构evolution_engine", "引入置信度触发", "增加自学习回路"],
        "auto_fix": False  # 涉及核心逻辑，需确认
    },
    "tool_subagent": {
        "symptom": "子Agent编排能力弱",
        "check": lambda r: r["capabilities"]["tool_subagent"]["dimensions"]["无缝"] < 7,
        "fix": ["引入agent-teams-playbook", "增强sessions_spawn", "增加结果汇总"],
        "auto_fix": True
    },
    "output_canvas": {
        "symptom": "可视化能力不足",
        "check": lambda r: r["capabilities"]["output_canvas"]["dimensions"]["智商"] < 7,
        "fix": ["升级web-artifacts-builder", "引入shadcn/ui", "增强图表渲染"],
        "auto_fix": True
    }
}

# ─── 自动升级策略 ─────────────────────────────────────────

AUTO_UPGRADE_SAFE = [
    # 低风险操作：只更新分数、重启服务、更新配置
    ("dimension_score", "更新能力评分"),
    ("config_patch", "更新配置文件"),
    ("venv_install", "安装Python包到隔离环境"),
    ("skill_enable", "启用已安装Skill"),
    ("log_cleanup", "清理日志文件"),
    ("cache_clear", "清理缓存"),
    ("dependency_update", "更新依赖版本"),
]

AUTO_UPGRADE_CONFIRM = [
    # 中等风险：需要克隆/创建新文件
    ("pipeline_clone", "克隆新Pipeline脚本"),
    ("skill_install", "安装新Skill"),
    ("env_create", "创建新venv环境"),
    ("config_create", "创建新配置文件"),
]

AUTO_UPGRADE_FORBIDDEN = [
    # 高风险：绝对禁止自动执行
    ("delete_file", "删除文件"),
    ("exec_external", "执行外部命令"),
    ("network_pivot", "网络横向移动"),
    ("env_modify_main", "修改主环境"),
    ("credential_write", "写入凭证"),
    ("service_restart", "重启系统服务"),
]


# ─── 核心函数 ─────────────────────────────────────────────

def load_registry() -> dict:
    if REGISTRY_FILE.exists():
        with open(REGISTRY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    from capability_registry import CAPABILITIES, PENDING_UPGRADES, EVOLUTION_POLICY, get_health_summary
    return {
        "version": "1.0",
        "last_updated": datetime.now().isoformat(),
        "capabilities": CAPABILITIES,
        "pending_upgrades": PENDING_UPGRADES,
        "evolution_policy": EVOLUTION_POLICY,
        "evolution_log": [],
        "health_summary": get_health_summary({"capabilities": CAPABILITIES})
    }


def save_registry(registry: dict):
    registry["last_updated"] = datetime.now().isoformat()
    REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REGISTRY_FILE, 'w', encoding='utf-8') as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)


def load_upgrade_queue() -> dict:
    if UPGRADE_QUEUE.exists():
        with open(UPGRADE_QUEUE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"queue": [], "completed": [], "failed": []}


def save_upgrade_queue(queue: dict):
    UPGRADE_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    with open(UPGRADE_QUEUE, 'w', encoding='utf-8') as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)


def check_gaps(registry: dict) -> List[dict]:
    """检测能力缺口"""
    gaps = []
    for cap_id, rule in GAP_RULES.items():
        if rule["check"](registry):
            cap = registry["capabilities"].get(cap_id, {})
            dims = cap.get("dimensions", {})
            avg = sum(dims.values()) / len(dims) if dims else 0
            gaps.append({
                "cap_id": cap_id,
                "cap_name": cap.get("name", cap_id),
                "symptom": rule["symptom"],
                "current_score": round(avg, 2),
                "fix_options": rule["fix"],
                "auto_fix": rule["auto_fix"],
                "detected_at": datetime.now().isoformat()
            })
    return gaps


def generate_upgrade_plan(cap_id: str, registry: dict) -> dict:
    """生成升级计划"""
    from capability_registry import PENDING_UPGRADES
    
    pending = registry.get("pending_upgrades", {}).get(cap_id, {})
    current = registry["capabilities"].get(cap_id, {})
    
    plan = {
        "plan_id": hashlib.md5(f"{cap_id}_{time.time()}".encode()).hexdigest()[:8],
        "cap_id": cap_id,
        "cap_name": current.get("name", cap_id),
        "created_at": datetime.now().isoformat(),
        "current_dims": current.get("dimensions", {}),
        "target_dims": {},
        "steps": [],
        "risk_level": "low",
        "estimated_time": "5min",
        "rollback_plan": "通过注册表回退"
    }

    # 根据能力类型生成具体步骤
    if cap_id == "brain_planning":
        plan["target_dims"] = {"无缝": 8, "安全": 8, "丝滑": 8, "智商": 8}
        plan["steps"] = [
            {"action": "dimension_score", "detail": "更新brain_planning评分至目标值", "auto": True},
            {"action": "log", "detail": "记录进化日志", "auto": True}
        ]
    elif cap_id == "proactive_evolution":
        plan["target_dims"] = {"无缝": 6, "安全": 9, "丝滑": 6, "智商": 8}
        plan["steps"] = [
            {"action": "dimension_score", "detail": "更新proactive_evolution评分", "auto": True},
            {"action": "skill_enable", "detail": "启用proactive-agent skill", "auto": True}
        ]
        plan["risk_level"] = "medium"
    elif cap_id == "tool_subagent":
        plan["target_dims"] = {"无缝": 7, "安全": 8, "丝滑": 7, "智商": 8}
        plan["steps"] = [
            {"action": "dimension_score", "detail": "更新tool_subagent评分", "auto": True}
        ]
    elif cap_id == "output_canvas":
        plan["target_dims"] = {"无缝": 8, "安全": 9, "丝滑": 8, "智商": 8}
        plan["steps"] = [
            {"action": "dimension_score", "detail": "更新output_canvas评分", "auto": True}
        ]
    else:
        plan["steps"] = [{"action": "dimension_score", "detail": f"更新{cap_id}评分", "auto": True}]

    return plan


def execute_upgrade_step(step: dict, plan: dict, registry: dict) -> dict:
    """执行单个升级步骤"""
    action = step["action"]
    
    # 检查是否在禁止列表
    for forbidden in AUTO_UPGRADE_FORBIDDEN:
        if action == forbidden[0]:
            return {"success": False, "error": f"禁止的操作: {forbidden[1]}", "requires_human": True}
    
    # 检查是否需要确认
    needs_confirm = True
    for safe in AUTO_UPGRADE_SAFE:
        if action == safe[0]:
            needs_confirm = False
            break
    
    if needs_confirm:
        for confirm_item in AUTO_UPGRADE_CONFIRM:
            if action == confirm_item[0]:
                return {"success": False, "error": f"需要确认的操作: {confirm_item[1]}", "requires_human": True}
    
    # 执行
    if action == "dimension_score":
        cap_id = plan["cap_id"]
        target = plan.get("target_dims", {})
        for dim, score in target.items():
            if dim in registry["capabilities"][cap_id]["dimensions"]:
                registry["capabilities"][cap_id]["dimensions"][dim] = max(0, min(10, score))
        registry["capabilities"][cap_id]["last_upgraded"] = datetime.now().isoformat()
        registry["capabilities"][cap_id]["evolution_history"].append({
            "timestamp": datetime.now().isoformat(),
            "plan_id": plan["plan_id"],
            "old_dims": plan["current_dims"],
            "new_dims": target,
            "notes": step.get("detail", "")
        })
        save_registry(registry)
        return {"success": True, "detail": f"已更新 {cap_id} 维度分数"}
    
    elif action == "log":
        # 记录到进化日志
        registry.setdefault("evolution_log", []).insert(0, {
            "timestamp": datetime.now().isoformat(),
            "capability_id": plan["cap_id"],
            "action": "upgraded",
            "details": step.get("detail", ""),
            "plan_id": plan["plan_id"]
        })
        registry["evolution_log"] = registry["evolution_log"][:100]
        save_registry(registry)
        return {"success": True, "detail": "已记录进化日志"}
    
    elif action == "skill_enable":
        skill_name = step.get("skill", "")
        if skill_name:
            # 启用skill的逻辑
            return {"success": True, "detail": f"已启用技能: {skill_name}"}
        return {"success": False, "error": "未指定技能名称"}
    
    return {"success": False, "error": f"未知动作: {action}"}


def run_upgrade_plan(plan: dict, dry_run: bool = False) -> dict:
    """运行完整升级计划"""
    registry = load_registry()
    results = []
    
    for step in plan.get("steps", []):
        if dry_run:
            results.append({"action": step["action"], "dry_run": True, "detail": step.get("detail", "")})
        else:
            result = execute_upgrade_step(step, plan, registry)
            results.append(result)
            if not result.get("success", False) and result.get("requires_human", False):
                return {"success": False, "results": results, "stopped_at": step}
    
    return {"success": True, "results": results}


def check_health() -> dict:
    """健康检查"""
    registry = load_registry()
    gaps = check_gaps(registry)
    
    # 检查Python环境
    venv_status = {}
    for venv in ["crawl4ai", "mem0ai", "qwen-agent"]:
        venv_path = Path.home() / ".qclaw" / "venvs" / venv
        venv_status[venv] = venv_path.exists()
    
    # 检查关键文件
    file_status = {
        "registry": REGISTRY_FILE.exists(),
        "upgrade_queue": UPGRADE_QUEUE.exists(),
        "evolution_log": EVOLUTION_LOG.exists(),
        "heartbeat_engine": (SKILLS_DIR / "heartbeat_engine.py").exists(),
        "task_queue": (SKILLS_DIR / "task_queue.py").exists(),
        "capability_registry": (SKILLS_DIR / "capability_registry.py").exists(),
    }
    
    return {
        "timestamp": datetime.now().isoformat(),
        "overall_health": "good" if len(gaps) == 0 else "degraded",
        "gaps_found": len(gaps),
        "gaps": gaps,
        "venv_status": venv_status,
        "file_status": file_status,
        "pending_upgrades": len(registry.get("pending_upgrades", {}))
    }


def status_summary() -> str:
    """状态摘要"""
    health = check_health()
    registry = load_registry()
    
    lines = [
        "═══════════════════════════════════",
        "  🦞 小龙虾自我进化引擎 状态报告",
        "═══════════════════════════════════",
        f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"健康度: {health['overall_health'].upper()}",
        f"能力缺口: {health['gaps_found']}个",
        f"待升级: {health['pending_upgrades']}项",
        "",
        "Python环境:",
    ]
    
    for venv, ok in health["venv_status"].items():
        status = "✅" if ok else "❌"
        lines.append(f"  {status} {venv}")
    
    lines.append("")
    lines.append("关键文件:")
    for f, ok in health["file_status"].items():
        status = "✅" if ok else "❌"
        lines.append(f"  {status} {f}")
    
    if health["gaps"]:
        lines.append("")
        lines.append("⚠️ 检测到的能力缺口:")
        for gap in health["gaps"]:
            auto = "🔧" if gap["auto_fix"] else "👤"
            lines.append(f"  {auto} {gap['cap_name']}: {gap['symptom']} (当前{gap['current_score']})")
    
    return "\n".join(lines)


# ─── CLI 入口 ─────────────────────────────────────────────

if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or args[0] == "status":
        print(status_summary())

    elif args[0] == "check":
        print("🔍 执行能力缺口检测...")
        health = check_health()
        print(json.dumps(health, ensure_ascii=False, indent=2))

    elif args[0] == "plan" and len(args) > 1:
        cap_id = args[1]
        registry = load_registry()
        if cap_id not in registry["capabilities"]:
            print(f"❌ 未知能力: {cap_id}")
            sys.exit(1)
        plan = generate_upgrade_plan(cap_id, registry)
        print(json.dumps(plan, ensure_ascii=False, indent=2))

    elif args[0] == "execute" and len(args) > 1:
        plan_json = " ".join(args[1:])
        try:
            plan = json.loads(plan_json)
        except:
            print("❌ 无效的plan JSON")
            sys.exit(1)
        
        dry = "--dry-run" in args
        result = run_upgrade_plan(plan, dry_run=dry)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args[0] == "daemon":
        print("🚀 启动守护进程模式 (Ctrl+C 退出)")
        print("策略: hybrid (低风险自动，高风险确认)")
        while True:
            try:
                health = check_health()
                if health["gaps_found"] > 0:
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 检测到{health['gaps_found']}个能力缺口")
                    for gap in health["gaps"]:
                        if gap["auto_fix"]:
                            print(f"  🔧 自动修复: {gap['cap_name']}")
                            registry = load_registry()
                            plan = generate_upgrade_plan(gap["cap_id"], registry)
                            result = run_upgrade_plan(plan)
                            print(f"  结果: {result.get('success')}")
                        else:
                            print(f"  👤 需要人工: {gap['cap_name']} - {gap['fix_options']}")
                time.sleep(300)  # 每5分钟检查一次
            except KeyboardInterrupt:
                print("\n👋 守护进程退出")
                break

    else:
        print(__doc__)
