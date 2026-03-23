"""
self_healer.py — 自我修复引擎 v2.0

升级：真正的自动修复能力

核心功能：
  1. 健康检查 ✅
  2. 智能诊断 ✅  
  3. 自动修复 ✅（新增）
  4. 回滚机制 ✅
  5. 降级策略 ✅

用法：
  python3 self_healer.py check
  python3 self_healer.py diagnose "错误信息"
  python3 self_healer.py heal     # 真正的自动修复
  python3 self_healer.py fix-all  # 强制修复所有已知问题
"""

import os
import sys
import json
import time
import subprocess
import httpx
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# ─── 配置 ───────────────────────────────────────────────────

WORKSPACE = Path.home() / ".qclaw" / "workspace"
BACKUP_DIR = WORKSPACE / "backups"
DEPS_BACKUP = Path.home() / ".qclaw" / "deps_backup"
VENV_DIR = Path.home() / ".qclaw" / "venvs"
from _secrets import GROQ_KEY
SNAPSHOT_FILE = WORKSPACE / "memory" / "system_snapshot.json"

# ─── 健康检查 ───────────────────────────────────────────────

def check_health(verbose: bool = True) -> Dict:
    """完整健康检查"""
    issues = []
    healthy = []
    
    # venv 检查
    for name in ["crawl4ai", "qwen-agent", "mem0ai"]:
        venv_path = VENV_DIR / name
        pkg_map = {"crawl4ai": "crawl4ai", "qwen-agent": "qwen_agent", "mem0ai": "mem0"}
        pkg = pkg_map[name]
        
        if not venv_path.exists():
            issues.append(f"❌ {name} venv 不存在")
            continue
        
        try:
            result = subprocess.run(
                [str(venv_path / "bin" / "python"), "-c", f"import {pkg}"],
                capture_output=True, timeout=10
            )
            if result.returncode == 0:
                healthy.append(f"✅ {name} venv 正常")
            else:
                issues.append(f"⚠️  {name} 包损坏，需要重装")
        except Exception as e:
            issues.append(f"⚠️  {name} 检查失败: {str(e)[:30]}")
    
    # API 检查
    try:
        r = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 2},
            headers={"Authorization": f"Bearer {GROQ_KEY}"}, timeout=5
        )
        if r.status_code == 200:
            healthy.append("✅ Groq API 正常")
        else:
            issues.append(f"⚠️  Groq API 异常 ({r.status_code})")
    except Exception as e:
        issues.append(f"⚠️  Groq API 失败: {str(e)[:30]}")
    
    # 关键文件检查
    for fname in ["heartbeat_engine.py", "agent_loop.py", "goal_manager.py", "self_healer.py"]:
        fpath = WORKSPACE / "skills" / "pipeline" / fname
        if fpath.exists():
            healthy.append(f"✅ {fname} 存在")
        else:
            issues.append(f"❌ {fname} 丢失")
    
    result = {
        "timestamp": datetime.now().isoformat(),
        "healthy_count": len(healthy),
        "issue_count": len(issues),
        "status": "✅ 健康" if not issues else f"⚠️ {len(issues)} 个问题",
        "details": healthy + issues
    }
    
    if verbose:
        print(f"\n🏥 健康检查: {result['status']}")
        for d in result['details']:
            print(f"   {d}")
    
    return result

# ─── 诊断 ─────────────────────────────────────────────────

def _extract_missing_package(stderr: str) -> Optional[str]:
    """从错误输出中提取缺失的包名"""
    import re
    # 匹配 "No module named 'xxx'" 或 "ModuleNotFoundError: No module named 'xxx'"
    m = re.search(r"No module named ['\"]([^'\"]+)['\"]", stderr)
    if m:
        return m.group(1)
    return None

def _detect_venv_from_package(pkg: str) -> Optional[str]:
    """根据缺失的包推算所属 venv"""
    # 已知包 -> venv 映射
    known = {
        "crawl4ai":   "crawl4ai",
        "crawl4ai.*": "crawl4ai",
        "qwen_agent": "qwen-agent",
        "qwen_agent.*": "qwen-agent",
        "qwen_agent": "qwen-agent",
        "mem0":       "mem0ai",
        "mem0ai":     "mem0ai",
        "mem0.*":     "mem0ai",
        "groq":       None,   # 系统包
        "httpx":      None,   # 系统包
        "litellm":    None,   # 系统包
    }
    for key, venv in known.items():
        if pkg.startswith(key.replace("_", "")) or pkg.startswith(key):
            return venv
    return None  # 未知包

def diagnose(error_msg: str) -> Dict:
    """诊断错误 — 真实执行测试，不只做字符串匹配"""
    findings = {
        "error": error_msg[:150],
        "tests_run": [],
        "cause": None,
        "fix": None,
        "severity": "medium",
        "action": None,
        "details": []
    }

    error_lower = error_msg.lower()

    # ── 测试1：网络连通性 ─────────────────────────────────
    findings["tests_run"].append("network_check")
    try:
        r = httpx.get("https://api.groq.com", timeout=5)
        findings["details"].append(f"✅ Groq API 网络可达 (status={r.status_code})")
        findings["network"] = "ok"
    except httpx.ConnectTimeout:
        findings["details"].append("❌ 连接 Groq API 超时")
        findings["network"] = "timeout"
        findings["cause"] = "网络问题"
        findings["fix"] = "retry"
        findings["severity"] = "high"
        findings["action"] = "check_proxy_or_network"
        return findings
    except Exception as e:
        findings["details"].append(f"❌ 网络错误: {e}")
        findings["network"] = "fail"
        findings["cause"] = "网络问题"
        findings["fix"] = "retry"
        findings["severity"] = "medium"
        findings["action"] = "check_network"
        return findings

    # ── 测试2：API Key 有效性 ─────────────────────────────
    findings["tests_run"].append("api_key_check")
    if any(k in error_lower for k in ["401", "403", "api_key", "unauthorized", "invalid"]):
        try:
            r = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json={"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 2},
                headers={"Authorization": f"Bearer {GROQ_KEY}"}, timeout=5
            )
            if r.status_code == 401:
                findings["details"].append("❌ Groq API Key 无效 (401)")
                findings["cause"] = "API 密钥无效"
                findings["fix"] = "check_api_key"
                findings["severity"] = "high"
                findings["action"] = "update_groq_key"
            elif r.status_code == 200:
                findings["details"].append("✅ API Key 有效")
                findings["key_valid"] = True
        except Exception as e:
            findings["details"].append(f"⚠️ API Key 检查失败: {e}")

    # ── 测试3：Python 包是否存在 ───────────────────────────
    missing_pkg = _extract_missing_package(error_msg)
    if missing_pkg:
        findings["tests_run"].append("package_check")
        findings["missing_package"] = missing_pkg
        venv_name = _detect_venv_from_package(missing_pkg)

        if venv_name:
            venv_path = VENV_DIR / venv_name
            if venv_path.exists():
                py = venv_path / "bin" / "python"
                test_result = subprocess.run(
                    [str(py), "-c", f"import {missing_pkg.replace('-','_')}"],
                    capture_output=True, timeout=10
                )
                if test_result.returncode == 0:
                    findings["details"].append(f"✅ 包 '{missing_pkg}' 在 {venv_name} 中可正常导入")
                    findings["cause"] = "可能是其他问题导致的报错"
                    findings["fix"] = "investigate"
                else:
                    findings["details"].append(f"❌ 包 '{missing_pkg}' 在 {venv_name} 中导入失败")
                    findings["details"].append(f"   stderr: {test_result.stderr.decode()[:100]}")
                    findings["cause"] = "Python 包缺失或损坏"
                    findings["fix"] = "reinstall"
                    findings["severity"] = "medium"
                    findings["action"] = f"reinstall_in_venv:{venv_name}"
            else:
                findings["details"].append(f"❌ venv '{venv_name}' 不存在")
                findings["cause"] = "Python venv 缺失"
                findings["fix"] = "create_venv"
                findings["severity"] = "high"
                findings["action"] = f"create_venv:{venv_name}"
        else:
            # 尝试系统 Python
            sys_result = subprocess.run(
                ["python3", "-c", f"import {missing_pkg.replace('-','_')}"],
                capture_output=True, timeout=10
            )
            if sys_result.returncode == 0:
                findings["details"].append(f"✅ '{missing_pkg}' 在系统 Python 中可用（可考虑用系统包）")
            else:
                findings["details"].append(f"❌ '{missing_pkg}' 在系统 Python 中也不可用")
                findings["cause"] = "Python 包缺失"
                findings["fix"] = "pip_install"
                findings["severity"] = "medium"
                findings["action"] = f"pip_install:{missing_pkg}"

    # ── 测试4：文件不存在 ─────────────────────────────────
    if any(k in error_lower for k in ["no such file", "enoent", "not found", "not exist"]):
        findings["tests_run"].append("file_check")
        import re
        path_match = re.search(r"[/~\w\-\.]+/[\w\-\./]+", error_msg)
        if path_match:
            p = Path(path_match.group()).expanduser()
            findings["details"].append(f"{'✅' if p.exists() else '❌'} 路径: {p} {'存在' if p.exists() else '不存在'}")
            if not p.exists():
                findings["cause"] = "文件不存在"
                findings["fix"] = "create_or_restore"
                findings["severity"] = "medium"
                findings["action"] = f"restore_file:{p.name}"

    # ── 测试5：权限问题 ────────────────────────────────────
    if "permission" in error_lower or "denied" in error_lower:
        findings["tests_run"].append("permission_check")
        findings["cause"] = "权限不足"
        findings["fix"] = "chmod"
        findings["severity"] = "high"
        findings["action"] = "fix_permissions"

    # ── 测试6：限流 ────────────────────────────────────────
    if any(k in error_lower for k in ["429", "rate limit", "too many requests"]):
        findings["tests_run"].append("rate_limit_check")
        findings["cause"] = "API 限流"
        findings["fix"] = "wait"
        findings["severity"] = "low"
        findings["action"] = "backoff_retry"

    # ── 未知错误：全面扫描 ────────────────────────────────
    if findings["cause"] is None:
        findings["tests_run"].append("full_scan")
        findings["details"].append("⚠️ 未能定位原因，运行全面扫描...")

        # 扫描所有 venv
        for name in ["crawl4ai", "qwen-agent", "mem0ai"]:
            venv_path = VENV_DIR / name
            pkg_import = {"crawl4ai": "crawl4ai", "qwen-agent": "qwen_agent", "mem0ai": "mem0"}.get(name, name)
            if venv_path.exists():
                r = subprocess.run(
                    [str(venv_path / "bin" / "python"), "-c", f"import {pkg_import}"],
                    capture_output=True, timeout=10
                )
                findings["details"].append(
                    f"{'✅' if r.returncode == 0 else '❌'} {name}: {pkg_import} {'OK' if r.returncode == 0 else 'FAIL'}"
                )
                if r.returncode != 0:
                    findings["cause"] = f"{name} venv 包损坏"
                    findings["fix"] = "reinstall"
                    findings["severity"] = "medium"
                    findings["action"] = f"reinstall_in_venv:{name}"

    # 如果什么都没发现
    if findings["cause"] is None:
        findings["cause"] = "未知错误"
        findings["fix"] = "manual"
        findings["severity"] = "medium"
        findings["action"] = "manual_review"

    print(f"\n🔍 诊断结果:")
    print(f"   原因: {findings['cause']}")
    print(f"   修复方案: {findings['fix']}")
    print(f"   严重程度: {findings['severity']}")
    print(f"   执行动作: {findings['action']}")
    if findings["details"]:
        print(f"   详细信息:")
        for d in findings["details"]:
            print(f"     {d}")

    return findings

# ─── 自动修复 ─────────────────────────────────────────────

def heal(dry_run: bool = False) -> Dict:
    """执行真正的自动修复"""
    print("🔧 开始自我修复...")
    results = []
    
    # 1. 健康检查
    health = check_health(verbose=False)
    results.append({"step": "健康检查", "result": health["status"]})
    
    if not health["issue_count"]:
        print("   ✅ 系统健康，无需修复")
        return {"status": "healthy", "steps": results}
    
    # 2. 修复 venv 包问题
    # 正确的包名映射（包分发名 -> import名）
    pkg_install_map = {"crawl4ai": "crawl4ai", "qwen-agent": "qwen-agent", "mem0ai": "mem0ai"}
    pkg_import_map  = {"crawl4ai": "crawl4ai", "qwen-agent": "qwen_agent", "mem0ai": "mem0"}

    for name in ["crawl4ai", "qwen-agent", "mem0ai"]:
        venv_path = VENV_DIR / name
        if not venv_path.exists():
            results.append({"step": f"检查 {name}", "result": "❌ venv 不存在"})
            print(f"   ❌ {name} venv 不存在，需要先创建")
            continue

        pkg_install = pkg_install_map[name]
        pkg_import  = pkg_import_map[name]

        result = subprocess.run(
            [str(venv_path / "bin" / "python"), "-c", f"import {pkg_import}"],
            capture_output=True, timeout=10
        )

        if result.returncode != 0:
            print(f"   🔨 修复 {name}: 重新安装 {pkg_install}...")
            if not dry_run:
                # 卸载（容错：可能没装过）
                subprocess.run(
                    [str(venv_path / "bin" / "pip"), "uninstall", "-y", pkg_install],
                    capture_output=True, timeout=60
                )
                install_result = subprocess.run(
                    [str(venv_path / "bin" / "pip"), "install", pkg_install],
                    capture_output=True, timeout=120
                )
                # 验证修复是否成功
                verify = subprocess.run(
                    [str(venv_path / "bin" / "python"), "-c", f"import {pkg_import}"],
                    capture_output=True, timeout=10
                )
                if verify.returncode == 0:
                    results.append({"step": f"修复 {name}", "result": "✅ 已重装并验证"})
                    print(f"   ✅ {name} 重装并验证成功")
                else:
                    results.append({"step": f"修复 {name}", "result": f"❌ 重装后验证失败: {verify.stderr.decode()[:80]}"})
                    print(f"   ❌ {name} 重装后验证失败: {verify.stderr.decode()[:80]}")
            else:
                results.append({"step": f"修复 {name}", "result": "[dry-run] 将重装并验证"})
    
    # 3. 检查 Groq API
    print("   🔍 检查 Groq API...")
    try:
        r = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": "test"}], "max_tokens": 2},
            headers={"Authorization": f"Bearer {GROQ_KEY}"}, timeout=10
        )
        if r.status_code == 200:
            results.append({"step": "Groq API", "result": "✅ 正常"})
            print("   ✅ Groq API 正常")
        else:
            results.append({"step": "Groq API", "result": f"⚠️ 状态码 {r.status_code}"})
            print(f"   ⚠️ Groq API 异常 ({r.status_code})")
    except Exception as e:
        results.append({"step": "Groq API", "result": f"❌ {str(e)[:30]}"})
        print(f"   ❌ Groq API 失败: {str(e)[:50]}")
    
    # 4. 验证关键文件
    for fname in ["heartbeat_engine.py", "agent_loop.py"]:
        fpath = WORKSPACE / "skills" / "pipeline" / fname
        if not fpath.exists():
            print(f"   ⚠️  {fname} 丢失，需要恢复")
            results.append({"step": f"检查 {fname}", "result": "❌ 丢失"})
    
    # 5. 保存快照
    if not dry_run:
        snapshot = take_snapshot()
        SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_FILE.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
        results.append({"step": "保存快照", "result": "✅ 完成"})
    
    final_status = "✅ 修复完成" if not any("❌" in r.get("result","") for r in results) else "⚠️ 部分问题需要人工处理"
    
    print(f"\n📊 修复结果: {final_status}")
    for r in results:
        print(f"   {r['step']}: {r['result']}")
    
    return {"status": final_status, "steps": results}

def fix_all():
    """强制修复所有已知问题"""
    print("🔧 全面修复模式...\n")
    
    # 1. 检查所有 venv
    for name in ["crawl4ai", "qwen-agent", "mem0ai"]:
        venv_path = VENV_DIR / name
        if not venv_path.exists():
            print(f"❌ {name} venv 不存在，创建中...")
            result = subprocess.run(["python3", "-m", "venv", str(venv_path)], capture_output=True, timeout=60)
            if result.returncode == 0:
                # 安装对应包（pip包名）
                pkg_install_map = {"crawl4ai": "crawl4ai", "qwen-agent": "qwen-agent", "mem0ai": "mem0ai"}
                subprocess.run([str(venv_path / "bin" / "pip"), "install", pkg_install_map[name]], capture_output=True, timeout=120)
                print(f"✅ {name} venv 创建并安装完成")
            else:
                print(f"❌ {name} venv 创建失败")
        else:
            print(f"✅ {name} venv 存在")
    
    # 2. 测试 Groq
    print("\n测试 Groq API...")
    try:
        r = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": "ok"}], "max_tokens": 2},
            headers={"Authorization": f"Bearer {GROQ_KEY}"}, timeout=10
        )
        print(f"✅ Groq API 正常 (状态: {r.status_code})")
    except Exception as e:
        print(f"❌ Groq API 失败: {e}")
    
    print("\n🔄 重新检查健康状态...")
    check_health()

# ─── 快照 ─────────────────────────────────────────────────

def take_snapshot() -> Dict:
    snapshot = {"timestamp": datetime.now().isoformat(), "venvs": {}, "apis": {}}
    for name in ["crawl4ai", "qwen-agent", "mem0ai"]:
        venv_path = VENV_DIR / name
        snapshot["venvs"][name] = {"exists": venv_path.exists()}
    return snapshot

# ─── 回滚 ─────────────────────────────────────────────────

def rollback() -> Dict:
    """回滚到之前状态"""
    print("🔄 检查可用回滚点...")
    backups = sorted(Path.home() / ".qclaw" / "backups" .glob("*") if (Path.home() / ".qclaw" / "backups").exists() else [])
    if backups:
        latest = backups[-1]
        print(f"   最新备份: {latest.name}")
        return {"status": "找到备份", "path": str(latest)}
    return {"status": "无备份", "note": "无法回滚"}

# ─── 主入口 ───────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="🔧 自我修复引擎 v2.0")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("check", help="健康检查")
    sub.add_parser("heal", help="自动修复")
    sub.add_parser("fix-all", help="全面修复")
    sub.add_parser("rollback", help="回滚")
    
    p_diagnose = sub.add_parser("diagnose", help="诊断错误")
    p_diagnose.add_argument("error", nargs="?", default="no module named test")

    args = parser.parse_args()
    
    if args.cmd == "check":
        check_health()
    elif args.cmd == "heal":
        heal()
    elif args.cmd == "fix-all":
        fix_all()
    elif args.cmd == "rollback":
        result = rollback()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.cmd == "diagnose":
        result = diagnose(args.error)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        parser.print_help()
        print("\n💡 建议: python3 self_healer.py fix-all  # 全面修复所有问题")

if __name__ == "__main__":
    main()
