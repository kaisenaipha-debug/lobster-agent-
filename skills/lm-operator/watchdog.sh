#!/bin/bash
# 看门狗 - 监控违规操作
# 如果检测到违规操作，立即kill

LOG_FILE="/tmp/lm_watchdog.log"
VIOLATION_COUNT=0
MAX_VIOLATIONS=3

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

check_and_kill() {
    # 检查enforcer状态
    STATUS=$(~/.qclaw/venvs/crawl4ai/bin/python3 ~/.qclaw/workspace/skills/lm-operator/enforcer.py status 2>/dev/null)
    
    # 如果消息数超过5，违规
    if echo "$STATUS" | grep -q "消息数: [6-9]"; then
        log "⚠️ 违规：消息数超过5"
        VIOLATION_COUNT=$((VIOLATION_COUNT + 1))
        
        # kill违规的playwright进程
        pkill -f "python3.*playwright" 2>/dev/null
        pkill -f "python3.*gemini" 2>/dev/null
        pkill -f "python3.*chatgpt" 2>/dev/null
        
        log "🔪 已kill违规进程"
        
        # 重置状态
        ~/.qclaw/venvs/crawl4ai/bin/python3 ~/.qclaw/workspace/skills/lm-operator/enforcer.py reset 2>/dev/null
        
        if [ $VIOLATION_COUNT -ge $MAX_VIOLATIONS ]; then
            log "🚫 达到违规上限，锁定系统"
            echo "已达到违规上限，系统锁定。请用户确认后重置。"
            exit 1
        fi
    fi
}

# 持续监控
log "🐕 看门狗启动"
while true; do
    check_and_kill
    sleep 5  # 每5秒检查一次
done
