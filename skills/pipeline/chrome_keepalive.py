#!/usr/bin/env python3
"""
chrome_keepalive.py — 保持Chrome在后台运行，不重复启动

用法：
  python3 chrome_keepalive.py start   # 启动或确认Chrome运行
  python3 chrome_keepalive.py status # 检查状态
  python3 chrome_keepalive.py stop  # 停止
"""

import os, subprocess, time, sys
import httpx
from pathlib import Path

HOME = Path.home()
PROFILE_DIR = HOME / ".qclaw" / "browser" / "pha-debug"
CDP = "http://localhost:9222"
PID_FILE = HOME / ".qclaw" / ".chrome_keepalive.pid"
LOG_FILE = "/tmp/chrome_keepalive.log"

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CHROME_ARGS = [
    "--remote-debugging-port=9222",
    f"--user-data-dir={PROFILE_DIR}",
    "--profile-directory=Profile 34",
    "--no-first-run", "--no-default-browser-check",
    "--disable-sync", "--disable-background-networking",
    "--no-default-browser-check",
]

def is_alive():
    try:
        r = httpx.get(f"{CDP}/json/version", timeout=3)
        return r.status_code == 200
    except:
        return False

def get_pid():
    try:
        return int(PID_FILE.read_text().strip())
    except:
        return None

def start():
    if is_alive():
        pid = get_pid()
        print(f"✅ Chrome已在运行 (PID {pid})")
        return

    print("🚀 启动 Chrome...")
    with open(LOG_FILE, "w") as f:
        proc = subprocess.Popen(
            [CHROME_BIN] + CHROME_ARGS,
            stdout=f, stderr=subprocess.STDOUT
        )
    PID_FILE.write_text(str(proc.pid))
    time.sleep(4)

    if is_alive():
        print(f"✅ Chrome已启动 (PID {proc.pid})")
    else:
        print("❌ Chrome启动失败，查看日志：")
        print(open(LOG_FILE).read()[-500:])

def stop():
    pid = get_pid()
    if pid:
        try:
            os.kill(pid, 15)
            print(f"已终止 PID {pid}")
        except:
            pass
    PID_FILE.unlink(missing_ok=True)

def status():
    alive = is_alive()
    pid = get_pid()
    if alive:
        print(f"🟢 Chrome运行中 (PID {pid})")
    else:
        print(f"🔴 Chrome未运行")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"start": start, "stop": stop, "status": status, "restart": lambda: (stop(), start()) or True}.get(cmd, status)()
