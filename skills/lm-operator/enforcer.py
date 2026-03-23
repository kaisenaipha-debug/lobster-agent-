#!/usr/bin/env python3
"""
大模型操作执行器 - 强制节奏控制
每次操作前必须通过这个执行器，不允许跳过
"""

import time
import json
import os

STATE_FILE = "/tmp/lm_operator_state.json"


def load_state():
    """加载状态"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {
        "last_send_time": 0,
        "last_message": "",
        "last_response_read": True,
        "consecutive_failures": 0,
        "message_count": 0,
        "window_count": 0,
        "open_windows": []
    }


def save_state(state):
    """保存状态"""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def check_window_limit():
    """
    检查浏览器窗口数量
    最多6个窗口，超过必须删除重复的
    """
    state = load_state()
    
    # 通过CDP获取实际窗口数
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp('http://localhost:9222')
            pages = browser.contexts[0].pages
            actual_count = len(pages)
            
            # 更新状态
            state['window_count'] = actual_count
            state['open_windows'] = [p.url for p in pages]
            save_state(state)
            
            if actual_count > 6:
                return False, f"❌ 窗口数{actual_count}超过6个！必须先删除。"
            
            return True, f"✅ 窗口数{actual_count}，正常"
    except Exception as e:
        return True, f"⚠️ 无法检查窗口数: {e}"


def record_window_open(url, name):
    """记录打开的窗口"""
    state = load_state()
    
    if state['window_count'] >= 6:
        return False, "❌ 已达6个窗口上限，不能再开"
    
    state['open_windows'].append({"url": url, "name": name})
    state['window_count'] = len(state['open_windows'])
    save_state(state)
    return True, f"✅ 已记录窗口: {name}"


def record_window_close(name):
    """记录关闭的窗口"""
    state = load_state()
    state['open_windows'] = [w for w in state['open_windows'] if w.get('name') != name]
    state['window_count'] = len(state['open_windows'])
    save_state(state)
    return True, f"✅ 已关闭窗口: {name}"


def cleanup_duplicates():
    """清理重复窗口"""
    state = load_state()
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp('http://localhost:9222')
            pages = browser.contexts[0].pages
            
            # 找重复URL
            urls = [p.url for p in pages]
            seen = set()
            duplicates = []
            for i, url in enumerate(urls):
                if url in seen:
                    duplicates.append(pages[i])
                seen.add(url)
            
            # 关闭重复的
            for page in duplicates:
                page.close()
            
            if duplicates:
                return len(duplicates), f"✅ 已关闭{len(duplicates)}个重复窗口"
            return 0, "✅ 没有重复窗口"
    except Exception as e:
        return 0, f"⚠️ 清理失败: {e}"


def check_can_send(message_type="question"):
    """
    检查是否可以发送消息
    返回 (can_send: bool, reason: str)
    """
    state = load_state()
    now = time.time()
    elapsed = now - state["last_send_time"]
    
    # 检查1：上条消息的回复是否已读完
    if not state["last_response_read"]:
        return False, f"❌ 还有回复没读完！先看完再说。（{int(elapsed)}秒前发的消息）"
    
    # 检查2：连续失败超过3次
    if state["consecutive_failures"] >= 3:
        return False, "❌ 连续3次失败，已强制停止。休息一下，等用户演示。"
    
    # 检查3：消息间隔（至少60秒）
    if elapsed < 60 and state["message_count"] > 0:
        remaining = 60 - elapsed
        return False, f"❌ 太快了！还有{int(remaining)}秒才能发下一条。"
    
    # 检查4：连续消息检查
    if state["message_count"] >= 5:
        # 每5条消息强制休息
        if elapsed < 120:
            return False, f"❌ 发了太多消息了，休息一下。已经发了{state['message_count']}条。"
    
    # 检查5：窗口数量
    can_check, window_msg = check_window_limit()
    if not can_check:
        return False, window_msg
    
    return True, "✅ 可以发送"


def record_sent(message, message_type="question"):
    """记录已发送消息"""
    state = load_state()
    state["last_send_time"] = time.time()
    state["last_message"] = message[:50]
    state["last_response_read"] = False
    state["message_count"] += 1
    save_state(state)
    print(f"📤 已发送消息 #{state['message_count']}")


def record_response_received(response_preview=""):
    """记录已收到回复"""
    state = load_state()
    state["last_response_read"] = False  # 等待确认
    state["consecutive_failures"] = 0
    state["last_response_preview"] = response_preview[:100]
    save_state(state)
    print(f"📥 已收到回复，等待确认...")


def confirm_read():
    """确认已读完回复"""
    state = load_state()
    state["last_response_read"] = True
    save_state(state)
    print("✅ 已确认读完回复")


def record_failure():
    """记录失败"""
    state = load_state()
    state["consecutive_failures"] += 1
    save_state(state)
    print(f"⚠️ 失败+1，当前连续失败：{state['consecutive_failures']}/3")


def reset():
    """重置状态"""
    save_state({
        "last_send_time": 0,
        "last_message": "",
        "last_response_read": True,
        "consecutive_failures": 0,
        "message_count": 0,
        "window_count": 0,
        "open_windows": []
    })
    print("🔄 状态已重置")


def print_status():
    """打印当前状态"""
    state = load_state()
    now = time.time()
    elapsed = now - state["last_send_time"]
    
    # 检查窗口数
    can_open, window_msg = check_window_limit()
    
    print(f"""
╔══════════════════════════════════════════╗
║         大模型操作执行器状态             ║
╠══════════════════════════════════════════╣
║  消息数: {state['message_count']}                               ║
║  距上次发送: {int(elapsed)}秒                       ║
║  回复已读: {"✅ 是" if state['last_response_read'] else "❌ 否"}                            ║
║  连续失败: {state['consecutive_failures']}/3                           ║
║  窗口数: {state['window_count']}/6                          ║
╚══════════════════════════════════════════╝
{window_msg}
    """)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("""
大模型操作执行器

用法:
  python3 enforcer.py status          # 查看状态
  python3 enforcer.py can_send        # 检查是否可以发送
  python3 enforcer.py sent <消息>    # 记录已发送
  python3 enforcer.py received        # 记录已收到回复
  python3 enforcer.py confirm         # 确认已读完回复
  python3 enforcer.py failed          # 记录失败
  python3 enforcer.py reset           # 重置状态
  
执行流程:
  1. check_can_send() → 问可以吗
  2. 发送消息 → sent()
  3. 等待回复
  4. 收到回复 → received()
  5. 看完回复 → confirm()
  6. 下一条 → can_send()
        """)
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "status":
        print_status()
    elif cmd == "can_send":
        can, reason = check_can_send()
        print(reason)
        sys.exit(0 if can else 1)
    elif cmd == "sent":
        msg = sys.argv[2] if len(sys.argv) > 2 else ""
        record_sent(msg)
    elif cmd == "received":
        preview = sys.argv[2] if len(sys.argv) > 2 else ""
        record_response_received(preview)
    elif cmd == "confirm":
        confirm_read()
    elif cmd == "failed":
        record_failure()
    elif cmd == "reset":
        reset()
    elif cmd == "help":
        print("""
╔══════════════════════════════════════════╗
║         大模型操作执行器 - 帮助          ║
╠══════════════════════════════════════════╣
║                                          ║
║  核心规则：                                ║
║  1. 不会了 → 立马停止，呼叫用户           ║
║  2. 连续3次失败 → 强制停止               ║
║  3. 没读完回复 → 不能发新消息            ║
║  4. 操作太快 → 被限制                    ║
║                                          ║
║  正确节奏：                                ║
║  发送 → 等30秒+ → 看完 → 停顿 → 赞美    ║
║  → 慢慢打字问下一个                        ║
║                                          ║
╚══════════════════════════════════════════╝
        """)
