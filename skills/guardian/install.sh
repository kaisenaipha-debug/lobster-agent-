#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════
# 小龙虾 Guardian — 一键安装 / 迁移脚本
# 适配版：~/.qclaw 路径
#
# 用法:
# 首次安装: bash install.sh install
# 导出备份: bash install.sh export
# 新机恢复: bash install.sh restore /path/to/backup.tar.gz
# ═══════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$HOME/.qclaw"
WORKSPACE_DIR="$BASE_DIR/workspace"
CORE_DIR="$BASE_DIR/core"
LOG_DIR="$BASE_DIR/logs"
EXPORT_DIR="$BASE_DIR/exports"
PYTHON="${PYTHON:-python3}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

step() { echo -e "${CYAN} ▶ $*${RESET}"; }
ok()   { echo -e "${GREEN} ✅ $*${RESET}"; }
warn() { echo -e "${YELLOW} ⚠️ $*${RESET}"; }
err()  { echo -e "${RED} ❌ $*${RESET}"; exit 1; }
header(){ echo -e "\n${BOLD}${CYAN}═══ $* ═══${RESET}\n"; }

# ─── 安装 ───────────────────────────────────────────
do_install() {
 header "安装 小龙虾 Guardian"

 step "检查 Python 环境..."
 PY_BIN=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo "")
 [ -z "$PY_BIN" ] && err "未找到 Python，请先安装 Python 3.9+"
 ok "Python: $("$PY_BIN" --version)  路径: $PY_BIN"

 step "创建目录结构..."
 mkdir -p "$BASE_DIR"/{core,logs,exports,workspace}
 ok "目录创建完成: $BASE_DIR"

 step "检查核心文件..."
 [ ! -f "$SCRIPT_DIR/guardian.py" ] && err "guardian.py 未找到"
 cp "$SCRIPT_DIR/guardian.py" "$CORE_DIR/guardian.py"
 chmod 444 "$CORE_DIR/guardian.py"
 ok "核心文件已部署: $CORE_DIR/guardian.py (只读)"

 step "建立完整性基准..."
 "$PYTHON" - <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.expanduser("~/.qclaw/core"))
from pathlib import Path
from guardian import IntegrityWatchdog

BASE = Path.home() / ".qclaw"
w = IntegrityWatchdog([
    str(BASE / "core" / "guardian.py"),
    str(BASE / "workspace" / "CAPABILITY_REGISTRY.json"),
    str(BASE / "workspace" / "baseline.sha256"),
])
w.snapshot()
print(" 基准快照已建立")
PYEOF
 ok "完整性基准建立完成"

 step "写入 shell 快捷命令..."
 ALIAS_BLOCK="
# 小龙虾 Guardian
alias xlstatus='python3 -c \"import sys; sys.path.insert(0, \\\"$HOME/.qclaw/core\\\"); from guardian import Guardian; Guardian().status()\"'
alias xlexport='bash \"$SCRIPT_DIR/install.sh\" export'
alias xlrestore='bash \"$SCRIPT_DIR/install.sh\" restore'
"
 for RC in "$HOME/.bashrc" "$HOME/.zshrc"; do
     [ -f "$RC" ] && ! grep -q "小龙虾 Guardian" "$RC" 2>/dev/null && \
         echo "$ALIAS_BLOCK" >> "$RC" && ok "别名已写入: $RC"
 done

 # macOS launchd
 if [[ "$(uname)" == "Darwin" ]]; then
     step "配置 macOS 开机自启（看门狗）..."
     PLIST="$HOME/Library/LaunchAgents/com.xiaolongxia.guardian.plist"
     mkdir -p "$(dirname "$PLIST")"
     cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
 <key>Label</key> <string>com.xiaolongxia.guardian</string>
 <key>ProgramArguments</key>
 <array>
  <string>${PYTHON}</string>
  <string>-c</string>
  <string>
import sys, time
sys.path.insert(0, "${HOME}/.qclaw/core")
from guardian import IntegrityWatchdog
from pathlib import Path
BASE = Path.home() / ".qclaw"
w = IntegrityWatchdog([
    str(BASE / "core" / "guardian.py"),
    str(BASE / "workspace" / "CAPABILITY_REGISTRY.json"),
])
w.load_baseline()
w.start_monitoring(60)
while True: time.sleep(3600)
  </string>
 </array>
 <key>RunAtLoad</key> <true/>
 <key>KeepAlive</key> <true/>
 <key>StandardErrorPath</key> <string>${HOME}/.qclaw/logs/watchdog.err</string>
 <key>StandardOutPath</key> <string>${HOME}/.qclaw/logs/watchdog.out</string>
</dict>
</plist>
PLIST_EOF
     launchctl load "$PLIST" 2>/dev/null || warn "launchd 加载失败"
     ok "看门狗开机自启已配置"
 fi

 header "安装完成 🦞"
 echo -e " ${BOLD}下一步：${RESET}"
 echo -e " source ~/.zshrc"
 echo -e " xlstatus           查看系统状态"
 echo -e " xlexport           导出能力备份"
 echo ""
}

# ─── 导出备份 ─────────────────────────────────────────
do_export() {
 header "导出能力备份"
 TIMESTAMP=$(date +%Y%m%d_%H%M%S)
 OUTPUT="$HOME/Desktop/xiaolongxia_backup_${TIMESTAMP}.tar.gz"
 mkdir -p "$(dirname "$OUTPUT")"

 step "开始打包..."
 "$PYTHON" - "$OUTPUT" <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.expanduser("~/.qclaw/core"))
from guardian import Migrator
m = Migrator()
print(m.export(sys.argv[1]))
PYEOF
 ok "备份已保存: $OUTPUT"
 echo ""
 echo -e " ${BOLD}迁移到新电脑：${RESET}"
 echo -e " bash install.sh restore /path/to/backup.tar.gz"
 echo ""
}

# ─── 恢复备份 ─────────────────────────────────────────
do_restore() {
 ARCHIVE="${1:-}"
 [ -z "$ARCHIVE" ] && err "请指定备份文件"
 [ ! -f "$ARCHIVE" ] && err "备份文件不存在: $ARCHIVE"

 header "从备份恢复能力"
 "$PYTHON" - "$ARCHIVE" <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.expanduser("~/.qclaw/core"))
from guardian import Migrator
ok = Migrator().restore(sys.argv[1])
if not ok: sys.exit(1)
print("恢复成功")
PYEOF

 step "重建完整性基准..."
 "$PYTHON" - <<'PYEOF'
import sys, os
sys.path.insert(0, os.path.expanduser("~/.qclaw/core"))
from guardian import IntegrityWatchdog
from pathlib import Path
BASE = Path.home() / ".qclaw"
IntegrityWatchdog([
    str(BASE / "core" / "guardian.py"),
    str(BASE / "workspace" / "CAPABILITY_REGISTRY.json"),
]).snapshot()
print("基准快照已重建")
PYEOF
 ok "恢复完成，所有能力已还原"
}

# ─── 主入口 ───────────────────────────────────────────
CMD="${1:-help}"
case "$CMD" in
 install) do_install ;;
 export)  do_export ;;
 restore) do_restore "${2:-}" ;;
 *)
 echo ""
 echo -e "${BOLD}小龙虾 Guardian 管理脚本${RESET}"
 echo -e " ${CYAN}bash install.sh install${RESET}                        首次安装"
 echo -e " ${CYAN}bash install.sh export${RESET}                         导出能力备份"
 echo -e " ${CYAN}bash install.sh restore backup.tar.gz${RESET}         从备份恢复"
 echo ""
 ;;
esac
