"""
feedback.py — 置信校准反馈收集器

用户对执行结果点👍或👎，自动更新置信校准数据。

用法：
  python3 feedback.py good TASK_ID   # 结果正确，上调置信度
  python3 feedback.py bad TASK_ID    # 结果错误，下调置信度
  python3 feedback.py report        # 查看校准报告
"""

import json
import sys
from pathlib import Path
from datetime import datetime

WORKSPACE = Path.home() / ".qclaw" / "workspace"
RESULTS_FILE = WORKSPACE / "memory" / "task_results.json"
CALIBRATION_FILE = WORKSPACE / "memory" / "confidence_calibration.json"

def load_cal():
    if CALIBRATION_FILE.exists():
        return json.loads(CALIBRATION_FILE.read_text())
    return {"calibration_log": [], "domain_baselines": {}, "tracking_started": "2026-03-21"}

def save_cal(data):
    CALIBRATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    CALIBRATION_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def load_results():
    if RESULTS_FILE.exists():
        return json.loads(RESULTS_FILE.read_text())
    return []

def update_calibration(task_id: str, quality: str):
    """
    quality: 'good' | 'bad'
    """
    results = load_results()
    data = load_cal()
    
    # 找到任务
    task = None
    for r in results:
        if r.get("task_id") == task_id:
            task = r
            break
    
    if not task:
        return f"未找到任务 {task_id}"
    
    # 更新校准记录
    log_entry = {
        "task_id": task_id,
        "description": task.get("description", "")[:100],
        "declared_confidence": task.get("confidence", 70),
        "result_quality": quality,
        "updated_at": datetime.now().isoformat(),
    }
    
    data["calibration_log"].append(log_entry)
    data["calibration_log"] = data["calibration_log"][-100:]  # 保留最近100条
    
    # 更新基准
    domain = categorize_task(task.get("description", ""))
    recent = [e for e in data["calibration_log"] 
              if categorize_task(e.get("description", "")) == domain][-10:]
    
    if len(recent) >= 3:
        errors = sum(1 for e in recent if e.get("result_quality") == "bad")
        error_rate = errors / len(recent)
        
        if domain not in data["domain_baselines"]:
            data["domain_baselines"][domain] = {"baseline": 70, "sample_size": 0}
        
        baseline = data["domain_baselines"][domain]["baseline"]
        # 误差率 > 30% → 基准 -5%
        # 误差率 < 20% → 基准 +5%
        if error_rate > 0.3:
            baseline = max(40, baseline - 5)
        elif error_rate < 0.2:
            baseline = min(90, baseline + 5)
        
        data["domain_baselines"][domain] = {
            "baseline": baseline,
            "sample_size": len(recent),
            "error_rate": round(error_rate, 2),
        }
    
    save_cal(data)
    
    # 生成反馈
    if quality == "good":
        delta = data["domain_baselines"].get(domain, {}).get("baseline", 70) - task.get("confidence", 70)
        return f"✅ 已记录：结果正确，基准调整 {delta:+d}%"
    else:
        delta = task.get("confidence", 70) - data["domain_baselines"].get(domain, {}).get("baseline", 70)
        return f"❌ 已记录：结果错误，基准调整 {-delta:+d}%"

def categorize_task(description: str) -> str:
    """分类任务类型"""
    desc = description.lower()
    if "搜索" in description or "search" in desc:
        return "search"
    elif "分析" in description or "研究" in desc:
        return "analysis"
    elif "爬取" in description or "crawl" in desc:
        return "crawl"
    elif "总结" in description:
        return "summary"
    else:
        return "general"

def show_report():
    data = load_cal()
    log = data.get("calibration_log", [])
    baselines = data.get("domain_baselines", {})
    
    print("📊 置信校准报告\n")
    print(f"总反馈记录: {len(log)} 条")
    if not log:
        print("暂无反馈数据。")
        print("\n👉 收到执行结果后，运行以下命令反馈：")
        print("  python3 feedback.py good <task_id>   # 结果正确")
        print("  python3 feedback.py bad <task_id>    # 结果错误")
        return
    
    # 最近的反馈
    recent = log[-5:]
    print("\n最近反馈:")
    for e in reversed(recent):
        icon = "✅" if e.get("result_quality") == "good" else "❌"
        print(f"  {icon} [{e['task_id']}] {e.get('description','')[:40]}")
        print(f"      声明置信:{e.get('declared_confidence',0)}% | 质量:{e.get('result_quality')}")
    
    # 领域基准
    if baselines:
        print("\n各领域基准:")
        for domain, info in baselines.items():
            bar = "▓" * (info["baseline"] // 10) + "░" * (10 - info["baseline"] // 10)
            print(f"  {domain}: {bar} {info['baseline']}% (样本:{info['sample_size']}, 误差率:{info.get('error_rate',0):.0%})")
    
    # 系统性偏差检测
    if len(log) >= 5:
        good = sum(1 for e in log if e.get("result_quality") == "good")
        rate = good / len(log)
        if rate > 0.8:
            print(f"\n⚠️ 系统性高估：声明置信度比实际偏高 {int((rate - 0.5)*200)}%，建议主动下调基准")
        elif rate < 0.5:
            print(f"\n⚠️ 系统性低估：声明置信度比实际偏低，建议适度上调基准")

def show_results_with_ids():
    """显示结果供选择"""
    results = load_results()
    if not results:
        print("无执行结果")
        return
    print("📋 最近执行结果（复制 task_id 反馈）：\n")
    for r in results[:10]:
        bar = "▓" * (r.get("confidence", 70) // 10) + "░" * (10 - r.get("confidence", 70) // 10)
        print(f"[{r['task_id']}] {bar} {r.get('confidence',70)}%")
        print(f"  {r.get('description','')[:50]}")
        print(f"  结果: {r.get('result','')[:60]}")
        print()

if __name__ == "__main__":
    args = sys.argv[1:]
    
    if not args:
        print("用法：")
        print("  python3 feedback.py good <task_id>   # 结果正确")
        print("  python3 feedback.py bad <task_id>    # 结果错误")
        print("  python3 feedback.py report            # 校准报告")
        print("  python3 feedback.py results          # 查看结果")
        print()
        show_results_with_ids()
        sys.exit(0)
    
    cmd = args[0]
    
    if cmd == "good" and len(args) > 1:
        print(update_calibration(args[1], "good"))
    elif cmd == "bad" and len(args) > 1:
        print(update_calibration(args[1], "bad"))
    elif cmd == "report":
        show_report()
    elif cmd == "results":
        show_results_with_ids()
    else:
        print("未知命令")
