#!/usr/bin/env python3
"""
config-guardian.py
在 QClaw 每次启动时自动检查 openclaw.json 完整性
若发现 channels 或 plugins 丢失，自动从备份恢复
"""
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

CONFIG_PATH = Path.home() / ".qclaw" / "openclaw.json"
BACKUP_DIR = Path.home() / ".qclaw" / "backups"

# 必须保留的通道
REQUIRED_CHANNELS = [
    "telegram",
    "wechat-access",
    "qqbot",
    "wecom",
    "slack",
]

# 必须保留的插件
REQUIRED_PLUGINS = [
    "wechat-access",
    "content-plugin",
    "tool-sandbox",
    "qmemory",
    "openclaw-qqbot",
    "wecom-openclaw-plugin",
    "pcmgr-ai-security",
    "telegram",
    "slack",
]

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)

def find_latest_telegram_backup():
    """找最近一个有 telegram 的备份"""
    candidates = sorted(BACKUP_DIR.glob("openclaw.*.json"), reverse=True)
    for p in candidates:
        try:
            with open(p) as f:
                d = json.load(f)
            if "telegram" in d.get("channels", {}):
                return p
        except:
            pass
    return None

def check_and_fix():
    cfg = load_config()
    channels = cfg.get("channels", {})
    plugins_allow = cfg.get("plugins", {}).get("allow", [])
    changes = []

    # 检查缺失的通道
    for ch in REQUIRED_CHANNELS:
        if ch not in channels:
            backup = find_latest_telegram_backup()
            if backup:
                with open(backup) as f:
                    bak = json.load(f)
                if ch in bak.get("channels", {}):
                    cfg["channels"][ch] = bak["channels"][ch]
                    changes.append(f"✅ 恢复通道: {ch}")
                else:
                    changes.append(f"⚠️ 通道 {ch} 在备份中也未找到，将跳过")
            else:
                changes.append(f"❌ 通道 {ch} 无备份可恢复")

    # 检查缺失的插件
    for plugin in REQUIRED_PLUGINS:
        if plugin not in plugins_allow:
            cfg["plugins"]["allow"].append(plugin)
            changes.append(f"✅ 恢复插件: {plugin}")

    if changes:
        print(f"[config-guardian] 发现 {len(changes)} 处配置丢失，正在修复：")
        for c in changes:
            print(f"  {c}")
        save_config(cfg)
        print("[config-guardian] 配置已修复并保存")
        return True
    else:
        print("[config-guardian] ✅ 配置完整，无需修复")
        return False

if __name__ == "__main__":
    check_and_fix()
