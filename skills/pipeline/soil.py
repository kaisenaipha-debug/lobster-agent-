#!/usr/bin/env python3
import os, sys, json, time, signal, httpx
from pathlib import Path
from datetime import datetime

WORKSPACE = Path.home() / ".qclaw" / "workspace"
SKILLS = WORKSPACE / "skills" / "pipeline"
TG_TOKEN = "8329844607:AAFYLczSkqcQ4FUj_fQuyUa8mkwQ24wh15I"
TG_CHAT_ID = "-1003590654654"

def send_tg(text):
    try:
        r = httpx.post(
            "https://api.telegram.org/bot" + TG_TOKEN + "/sendMessage",
            json={"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=15
        )
        return r.status_code == 200
    except Exception as e:
        print("[TG] " + str(e))
        return False

def notify(text):
    ok = send_tg(text)
    if not ok:
        print(text)

def is_bad_result(r):
    res = r.get("result") or ""
    err = r.get("error") or ""
    if "错误" in res:
        return True
    if err and "error" in err.lower():
        return True
    return False

def check_baseline():
    try:
        sys.path.insert(0, str(SKILLS))
        import consequence_tracker
        baselines = consequence_tracker.load_baselines()
        conseq = consequence_tracker.load_conseq()
        if not conseq:
            return []
        drifting = []
        for domain, info in baselines.items():
            recent = [c for c in conseq if c.get("domain") == domain][-5:]
            if len(recent) < 3:
                continue
            bad = sum(1 for c in recent if c.get("quality") == "bad")
            rate = bad / len(recent)
            if rate >= 0.4:
                drifting.append({"domain": domain, "bad_rate": rate, "baseline": info.get("baseline", 65)})
        return drifting
    except Exception as e:
        print("[step1] " + str(e))
        return []

def check_reasoning():
    try:
        sys.path.insert(0, str(SKILLS))
        import reasoning_log
        data = reasoning_log.load_reasoning()
        if not data:
            return []
        issues = []
        inc = [d for d in data if not d.get("conclusion")]
        sup = [d for d in data if d.get("superseded_by")]
        if inc:
            issues.append(str(len(inc)) + "条推理未出结论")
        if sup:
            issues.append(str(len(sup)) + "条判断被更新")
        return issues
    except Exception as e:
        print("[step2] " + str(e))
        return []

def check_queue():
    try:
        sys.path.insert(0, str(SKILLS))
        import task_queue
        data = task_queue.atomic_read()
        tasks = data.get("tasks", [])
        stalled = []
        now = datetime.now()
        for t in tasks:
            if t.get("status") == "running" and t.get("started_at"):
                try:
                    t_start = datetime.fromisoformat(t["started_at"])
                    age = (now - t_start).total_seconds() / 60
                    if age > 10:
                        stalled.append({
                            "id": t.get("id"),
                            "age": round(age, 1),
                            "desc": t.get("description", "")[:50]
                        })
                except Exception:
                    pass
        return stalled
    except Exception as e:
        print("[step3] " + str(e))
        return []

def check_feedback():
    try:
        sys.path.insert(0, str(SKILLS))
        import feedback
        results = feedback.load_results()
        if not results:
            return 0, 0
        recent = results[:10]
        bad = sum(1 for r in recent if is_bad_result(r))
        rate = bad / len(recent)
        return rate, len(recent)
    except Exception as e:
        print("[step4] " + str(e))
        return 0, 0

def run_once():
    drifting = check_baseline()
    reasoning_issues = check_reasoning()
    stalled = check_queue()
    fb_rate, fb_count = check_feedback()

    count = 0
    if drifting:
        count += 1
    if reasoning_issues:
        count += 1
    if stalled:
        count += 1
    if fb_rate > 0.3 and fb_count > 0:
        count += 1

    conf = min(count * 30, 88)

    ts = datetime.now().strftime("%H:%M")
    lines = ["【SOIL 巡检】" + ts]

    if count == 0:
        lines.append("系统健康，无异常")
        return "\n".join(lines), count, conf

    lines.append("发现：" + str(count) + "个系统信号\n")

    if drifting:
        lines.append("  - 基准下沉：" + ", ".join(d["domain"] for d in drifting))
    if reasoning_issues:
        lines.append("  - 推理异常：" + " ".join(reasoning_issues))
    if stalled:
        lines.append("  - 任务卡顿：" + ", ".join(s["id"] for s in stalled))
    if fb_rate > 0.3:
        lines.append("  - 反馈质量：bad率" + str(int(fb_rate * 100)) + "%")

    if drifting and fb_rate > 0.3:
        ptype = "基准+反馈双重"
        cause = "双重信号，工具链可靠性可能已变化"
        fix = "锁定该领域置信度基准，观察一轮"
    elif drifting:
        ptype = "基准下沉"
        cause = "连续bad累积，基准可能已偏离真实水平"
        fix = "禁止该领域置信度上调"
    elif fb_rate > 0.3:
        ptype = "反馈质量"
        cause = "近期结果系统性偏低，工具可能退化"
        fix = "降低该领域任务频率"
    elif stalled:
        ptype = "任务卡顿"
        cause = "任务执行超时，工具或网络可能阻塞"
        fix = "检查工具健康，清理卡住的任务"
    else:
        ptype = "推理异常"
        cause = "推理路径存在系统性偏差"
        fix = "补充推理结论，减少未完成条目"

    lines.append("\n最高优先级：" + ptype)
    lines.append("根因：" + cause)
    lines.append("\n置信度：" + str(conf) + "%")

    if conf >= 80:
        lines.append("\n置信度>=80%，自动执行")
        lines.append("-> " + fix)
    else:
        lines.append("\n置信度" + str(conf) + "%，等待确认")
        lines.append("回复「执行」=确认   回复「跳过」=跳过")

    return "\n".join(lines), count, conf

def run_loop(interval=1800):
    print("[SOIL] 启动，30分钟循环")
    running = True

    def stop(sig, frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    healthy = 0
    while running:
        try:
            report, count, conf = run_once()
            print("\n" + report + "\n")
            if count == 0:
                healthy += 1
                if healthy >= 3:
                    notify("[SOIL] 健康三轮，无异常")
                    healthy = 0
            else:
                healthy = 0
                notify(report)
                if conf >= 80:
                    print("[SOIL] 自动执行，置信度" + str(conf) + "%")
            for _ in range(interval):
                if not running:
                    break
                time.sleep(1)
        except Exception as e:
            print("[SOIL] 异常：" + str(e))
            time.sleep(60)
    print("[SOIL] 已停止")

def main():
    args = sys.argv[1:]
    if not args or args[0] == "once":
        report, count, conf = run_once()
        print(report)
        print("\n信号:" + str(count) + " 置信度:" + str(conf) + "%")
    elif args[0] == "start":
        run_loop()
    elif args[0] == "test":
        ok = send_tg("SOIL推送测试\n收到即正常")
        print("成功" if ok else "失败")
    else:
        print("用法: soil.py once|start|test")

if __name__ == "__main__":
    main()
