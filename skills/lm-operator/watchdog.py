#!/usr/bin/env python3
"""
看门狗 v2.0 - 精准版
规则：
1. 只杀"托管进程"（小龙虾自己拉起的）
2. CDP附着的Chrome → 不断连，不断连
3. 用户自己的Chrome → 永不kill
4. kill前必须经过quarantine + graceful shutdown
"""

import os
import time
import json
import subprocess

STATE_FILE = "/tmp/lm_watchdog_state.json"

# 规则配置
SCAN_INTERVAL = 2  # 秒
UNHEALTHY_THRESHOLD = 4  # 连续4次异常才进入回收
QUARANTINE_DURATION = 15  # 秒
GRACEFUL_WAIT = 15  # 优雅关闭等待

# 白名单关键词（永不kill）
ALLOW_KEYWORDS = [
    "--remote-debugging-port",
    "--remote-debugging-pipe",
    "--profile-directory=",
    "--user-data-dir=",
]

# 进程分类
CLASSIFY_CMD = """
ps aux | grep -E 'python3|node|chrome' | grep -v grep | awk '{print $2, $11, $12, $13, $14, $15, $16}'
"""

STATE = {
    "quarantined": [],  # 隔离中的进程
    "registered": [],    # 已登记的托管进程
    "logs": []           # 日志
}


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return STATE


def save_state(s):
    with open(STATE_FILE, 'w') as f:
        json.dump(s, f, indent=2)


def get_process_list():
    """获取进程列表"""
    try:
        result = subprocess.run(
            ['ps', '-ax', '-o', 'pid,ppid,command'],
            capture_output=True, text=True, timeout=3
        )
        processes = []
        for line in result.stdout.split('\n')[1:]:
            parts = line.strip().split(None, 2)
            if len(parts) >= 3:
                processes.append({
                    'pid': parts[0],
                    'ppid': parts[1] if len(parts) > 1 else '',
                    'cmdline': parts[2]
                })
        return processes
    except:
        return []


def is_whitelisted(cmdline):
    """检查是否在白名单（永不kill）"""
    if not cmdline:
        return False
    for kw in ALLOW_KEYWORDS:
        if kw in cmdline:
            return True
    return False


def is_registeredManaged(pid, state):
    """检查是否是已登记的托管进程"""
    return any(p['pid'] == pid for p in state.get('registered', []))


def register_managed(pid, cmdline):
    """登记托管进程"""
    s = load_state()
    s['registered'].append({
        'pid': pid,
        'cmdline': cmdline[:100],
        'registered_at': time.time()
    })
    save_state(s)


def log(msg):
    """写日志"""
    print(f"[看门狗 {time.strftime('%H:%M:%S')}] {msg}")
    s = load_state()
    s.setdefault('logs', []).append({
        'time': time.time(),
        'msg': msg
    })
    # 只保留最近20条
    s['logs'] = s['logs'][-20:]
    save_state(s)


def try_graceful_shutdown(pid):
    """优雅关闭进程"""
    try:
        # 先尝试TERM信号（优雅）
        os.kill(int(pid), 15)  # SIGTERM
        log(f"发送SIGTERM到 {pid}")
        return True
    except:
        return False


def quarantine_process(pid, reason):
    """隔离进程"""
    s = load_state()
    s['quarantined'].append({
        'pid': pid,
        'reason': reason,
        'quarantined_at': time.time()
    })
    save_state(s)
    log(f"隔离进程 {pid}: {reason}")


def should_kill(pid, state):
    """
    判断是否应该kill
    规则：
    1. 白名单进程 → 不kill
    2. CDP附着的Chrome → 不kill
    3. 用户Chrome → 不kill
    4. 未托管进程 → 不kill
    5. 托管进程连续异常 → quarantine → graceful → kill
    """
    # 找进程cmdline
    cmdline = ""
    for p in get_process_list():
        if p['pid'] == pid:
            cmdline = p['cmdline']
            break
    
    # 规则1：白名单
    if is_whitelisted(cmdline):
        return False, "白名单进程"
    
    # 规则2：检查是否在隔离区
    in_quarantine = any(q['pid'] == pid for q in state.get('quarantined', []))
    if in_quarantine:
        # 检查隔离时间
        for q in state['quarantined']:
            if q['pid'] == pid:
                elapsed = time.time() - q['quarantined_at']
                if elapsed < QUARANTINE_DURATION:
                    return False, f"隔离中({int(elapsed)}s)"
                # 隔离超时，进入graceful shutdown
                if try_graceful_shutdown(pid):
                    return False, f"优雅关闭中({GRACEFUL_WAIT}s)"
                # 还没退出，kill
                return True, "graceful timeout"
    
    # 规则3：不是托管进程 → 不kill
    if not is_registeredManaged(pid, state):
        return False, "非托管进程"
    
    return False, "未知"


def scan():
    """扫描进程"""
    state = load_state()
    
    # 清理已退出的隔离进程
    active_pids = {p['pid'] for p in get_process_list()}
    state['quarantined'] = [
        q for q in state['quarantined'] if q['pid'] in active_pids
    ]
    save_state(state)
    
    log(f"扫描中... 托管:{len(state.get('registered',[]))} 隔离:{len(state.get('quarantined',[]))}")


def main():
    log("看门狗v2.0启动")
    while True:
        try:
            scan()
        except Exception as e:
            log(f"扫描错误: {e}")
        time.sleep(SCAN_INTERVAL)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "scan":
        scan()
    elif len(sys.argv) > 1 and sys.argv[1] == "register":
        if len(sys.argv) > 2:
            register_managed(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    else:
        main()
