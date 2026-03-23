#!/usr/bin/env python3
"""
看门狗 v3.0 - 基于小龙虾项目Kotlin代码重写
精准进程管理，不误杀CDP目标浏览器
"""

import os
import time
import json
import re
import signal
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any

# ==================== 枚举 ====================

class ProcessSource:
    USER = "USER"
    ATTACHED_CDP = "ATTACHED_CDP"
    MANAGED_LAUNCH = "MANAGED_LAUNCH"
    RECOVERED = "RECOVERED"


class ProcessRole:
    USER_BROWSER = "USER_BROWSER"
    CDP_TARGET_BROWSER = "CDP_TARGET_BROWSER"
    BROWSER_LAUNCHER = "BROWSER_LAUNCHER"
    PLAYWRIGHT_WORKER = "PLAYWRIGHT_WORKER"
    NODE_HELPER = "NODE_HELPER"
    DEVTOOLS_PROXY = "DEVTOOLS_PROXY"
    APP_HELPER = "APP_HELPER"
    UNKNOWN = "UNKNOWN"


class ProcessLifecycle:
    NEW = "NEW"
    RUNNING = "RUNNING"
    QUARANTINED = "QUARANTINED"
    GRACEFUL_STOPPING = "GRACEFUL_STOPPING"
    ORPHAN_CANDIDATE = "ORPHAN_CANDIDATE"
    TERMINATED = "TERMINATED"


class ProtectionLevel:
    PROTECTED = "PROTECTED"
    SOFT_GUARDED = "SOFT_GUARDED"
    MANAGED = "MANAGED"
    DISPOSABLE = "DISPOSABLE"


class KillReason:
    OWNER_DEAD_ORPHAN_TIMEOUT = "OWNER_DEAD_ORPHAN_TIMEOUT"
    HEARTBEAT_TIMEOUT_CONSECUTIVE = "HEARTBEAT_TIMEOUT_CONSECUTIVE"
    IPC_BROKEN_AND_NO_RECOVERY = "IPC_BROKEN_AND_NO_RECOVERY"
    PLAYWRIGHT_WORKER_HUNG = "PLAYWRIGHT_WORKER_HUNG"
    LAUNCHER_EXITED_CHILD_LEAKED = "LAUNCHER_EXITED_CHILD_LEAKED"
    MANAGED_BROWSER_NOT_RESPONDING = "MANAGED_BROWSER_NOT_RESPONDING"
    MANUAL_FORCE_CLEANUP = "MANUAL_FORCE_CLEANUP"


class WatchdogDecisionType:
    ALLOW = "ALLOW"
    OBSERVE_PROTECTED = "OBSERVE_PROTECTED"
    QUARANTINE = "QUARANTINE"
    REQUEST_GRACEFUL_SHUTDOWN = "REQUEST_GRACEFUL_SHUTDOWN"
    HARD_KILL = "HARD_KILL"


# ==================== 数据类 ====================

class ProcessRecord:
    def __init__(self, pid, ppid=0, name="", cmdline="",
                 session_id="", owner_pid=0, launch_token="",
                 source=ProcessSource.USER, role=ProcessRole.UNKNOWN,
                 lifecycle=ProcessLifecycle.NEW, protection=ProtectionLevel.PROTECTED,
                 start_at=None, last_heartbeat_at=0, last_healthy_at=0,
                 unhealthy_count=0, quarantine_since=0, graceful_since=0,
                 attached_debug_port=None, is_owner_alive=True,
                 marked_by_user=False, allow_graceful_shutdown=True, notes=""):
        self.pid = pid
        self.ppid = ppid
        self.name = name
        self.cmdline = cmdline
        self.session_id = session_id
        self.owner_pid = owner_pid
        self.launch_token = launch_token
        self.source = source
        self.role = role
        self.lifecycle = lifecycle
        self.protection = protection
        self.start_at = start_at or time.time()
        self.last_heartbeat_at = last_heartbeat_at
        self.last_healthy_at = last_healthy_at
        self.unhealthy_count = unhealthy_count
        self.quarantine_since = quarantine_since
        self.graceful_since = graceful_since
        self.attached_debug_port = attached_debug_port
        self.is_owner_alive = is_owner_alive
        self.marked_by_user = marked_by_user
        self.allow_graceful_shutdown = allow_graceful_shutdown
        self.notes = notes

    def to_dict(self):
        return {
            'pid': self.pid, 'ppid': self.ppid, 'name': self.name,
            'cmdline': self.cmdline, 'session_id': self.session_id,
            'owner_pid': self.owner_pid, 'launch_token': self.launch_token,
            'source': self.source, 'role': self.role,
            'lifecycle': self.lifecycle, 'protection': self.protection,
            'start_at': self.start_at,
            'last_heartbeat_at': self.last_heartbeat_at,
            'last_healthy_at': self.last_healthy_at,
            'unhealthy_count': self.unhealthy_count,
            'quarantine_since': self.quarantine_since,
            'graceful_since': self.graceful_since,
            'attached_debug_port': self.attached_debug_port,
            'is_owner_alive': self.is_owner_alive,
            'marked_by_user': self.marked_by_user,
            'allow_graceful_shutdown': self.allow_graceful_shutdown,
            'notes': self.notes,
        }


class HealthSnapshot:
    def __init__(self, process_alive=False, owner_alive=True,
                 heartbeat_fresh=True, ws_connected=None,
                 devtools_reachable=None, cpu_busy=None,
                 recent_io=None, last_error=None):
        self.process_alive = process_alive
        self.owner_alive = owner_alive
        self.heartbeat_fresh = heartbeat_fresh
        self.ws_connected = ws_connected
        self.devtools_reachable = devtools_reachable
        self.cpu_busy = cpu_busy
        self.recent_io = recent_io
        self.last_error = last_error


class WatchdogDecision:
    def __init__(self, type, reason=None, message=""):
        self.type = type
        self.reason = reason
        self.message = message


# ==================== 配置 ====================

@dataclass
class WatchdogConfig:
    scan_interval_ms: int = 2000
    heartbeat_timeout_ms: int = 8000
    unhealthy_threshold: int = 4
    quarantine_ms: int = 15000
    graceful_shutdown_wait_ms: int = 15000
    orphan_grace_ms: int = 20000


# ==================== 进程注册表 ====================

class ProcessRegistry:
    _records = {}
    _session_port_map = {}

    @classmethod
    def upsert(cls, record):
        cls._records[record.pid] = record

    @classmethod
    def get(cls, pid):
        return cls._records.get(pid)

    @classmethod
    def all(cls):
        return list(cls._records.values())

    @classmethod
    def remove(cls, pid):
        if pid in cls._records:
            del cls._records[pid]

    @classmethod
    def mark_terminated(cls, pid):
        if pid in cls._records:
            cls._records[pid].lifecycle = ProcessLifecycle.TERMINATED

    @classmethod
    def update_heartbeat(cls, pid, now=None):
        if now is None:
            now = time.time()
        if pid in cls._records:
            r = cls._records[pid]
            r.last_heartbeat_at = now
            r.last_healthy_at = now
            if r.lifecycle == ProcessLifecycle.NEW:
                r.lifecycle = ProcessLifecycle.RUNNING

    @classmethod
    def bind_session_debug_port(cls, session_id, port):
        if session_id:
            cls._session_port_map[session_id] = port

    @classmethod
    def get_session_debug_port(cls, session_id):
        if not session_id:
            return None
        return cls._session_port_map.get(session_id)

    @classmethod
    def unregister_session(cls, session_id):
        if session_id in cls._session_port_map:
            del cls._session_port_map[session_id]

    @classmethod
    def exists(cls, pid):
        return pid in cls._records

    @classmethod
    def is_managed_pid(cls, pid):
        r = cls._records.get(pid)
        if not r:
            return False
        return r.source == ProcessSource.MANAGED_LAUNCH


# ==================== 分类器 ====================

class ProcessClassifier:

    @staticmethod
    def classify(record):
        cmd = record.cmdline.lower()
        name = record.name.lower()

        # 1. 用户标记
        if record.marked_by_user:
            return ProcessClassifier._as_user(record, name, cmd)

        # 2. CDP附着
        cdp_port = ProcessClassifier._parse_debug_port(cmd)
        is_remote_debug = cdp_port is not None or "--remote-debugging-pipe" in cmd
        bound_port = ProcessRegistry.get_session_debug_port(record.session_id)
        session_port_matched = (cdp_port is not None and bound_port is not None and cdp_port == bound_port)

        if record.source == ProcessSource.ATTACHED_CDP or is_remote_debug or session_port_matched:
            return ProcessClassifier._as_attached_cdp(record, cdp_port or bound_port)

        # 3. 托管启动
        if ProcessClassifier._is_managed_launch(record):
            return ProcessClassifier._as_managed_launch(record, name, cmd)

        # 4. 恢复为已知helper
        if ProcessClassifier._should_recover_as_known_helper(name, cmd):
            record.source = ProcessSource.RECOVERED
            record.role = ProcessClassifier._infer_managed_role(name, cmd)
            record.protection = ProtectionLevel.SOFT_GUARDED
            record.lifecycle = ProcessClassifier._normalize_lifecycle(record.lifecycle)
            return record

        # 5. 默认用户拥有
        return ProcessClassifier._as_user(record, name, cmd)

    @staticmethod
    def is_cdp_protected(record):
        """检查是否受CDP保护（永不kill）"""
        cmd = record.cmdline.lower()
        return (
            record.source == ProcessSource.ATTACHED_CDP or
            record.role == ProcessRole.CDP_TARGET_BROWSER or
            record.protection == ProtectionLevel.PROTECTED or
            "--remote-debugging-port=" in cmd or
            "--remote-debugging-pipe" in cmd
        )

    @staticmethod
    def can_hard_kill(record):
        """检查是否可以hard kill"""
        if record.protection == ProtectionLevel.PROTECTED:
            return False
        if record.source == ProcessSource.USER:
            return False
        if record.source == ProcessSource.ATTACHED_CDP:
            return False
        if record.role == ProcessRole.CDP_TARGET_BROWSER:
            return False
        return True

    @staticmethod
    def _as_user(record, name, cmd):
        record.source = ProcessSource.USER
        record.role = ProcessClassifier._infer_user_role(name, cmd)
        record.protection = ProtectionLevel.PROTECTED
        record.lifecycle = ProcessClassifier._normalize_lifecycle(record.lifecycle)
        return record

    @staticmethod
    def _as_attached_cdp(record, port):
        record.source = ProcessSource.ATTACHED_CDP
        record.role = ProcessRole.CDP_TARGET_BROWSER
        record.protection = ProtectionLevel.PROTECTED
        record.attached_debug_port = port or record.attached_debug_port
        record.lifecycle = ProcessClassifier._normalize_lifecycle(record.lifecycle)
        return record

    @staticmethod
    def _as_managed_launch(record, name, cmd):
        record.source = ProcessSource.MANAGED_LAUNCH
        record.role = ProcessClassifier._infer_managed_role(name, cmd)
        record.protection = ProcessClassifier._infer_managed_protection(name, cmd)
        record.lifecycle = ProcessClassifier._normalize_lifecycle(record.lifecycle)
        return record

    @staticmethod
    def _is_managed_launch(record):
        if record.source == ProcessSource.MANAGED_LAUNCH:
            return True
        if not record.launch_token:
            return False
        if record.owner_pid <= 0:
            return False
        if not record.session_id:
            return False
        return True

    @staticmethod
    def _should_recover_as_known_helper(name, cmd):
        looks_like_worker = (
            "node" in name or
            "playwright" in name or
            "playwright" in cmd or
            "devtools" in cmd or
            "helper" in cmd
        )
        return looks_like_worker

    @staticmethod
    def _infer_user_role(name, cmd):
        if ProcessClassifier._is_browser(name, cmd):
            return ProcessRole.USER_BROWSER
        return ProcessRole.UNKNOWN

    @staticmethod
    def _infer_managed_role(name, cmd):
        if ProcessClassifier._is_browser(name, cmd) and ("launcher" in cmd or "user-data-dir" in cmd):
            return ProcessRole.BROWSER_LAUNCHER
        if "node" in name and "playwright" in cmd:
            return ProcessRole.PLAYWRIGHT_WORKER
        if "node" in name:
            return ProcessRole.NODE_HELPER
        if "devtools" in cmd or "cdp-proxy" in cmd:
            return ProcessRole.DEVTOOLS_PROXY
        if "helper" in cmd or "helper" in name:
            return ProcessRole.APP_HELPER
        if ProcessClassifier._is_browser(name, cmd):
            return ProcessRole.BROWSER_LAUNCHER
        return ProcessRole.UNKNOWN

    @staticmethod
    def _infer_managed_protection(name, cmd):
        role = ProcessClassifier._infer_managed_role(name, cmd)
        if role in [ProcessRole.PLAYWRIGHT_WORKER, ProcessRole.NODE_HELPER,
                    ProcessRole.DEVTOOLS_PROXY, ProcessRole.APP_HELPER,
                    ProcessRole.BROWSER_LAUNCHER]:
            return ProtectionLevel.MANAGED
        return ProtectionLevel.SOFT_GUARDED

    @staticmethod
    def _is_browser(name, cmd):
        return (
            "chrome" in name or
            "chromium" in name or
            "msedge" in name or
            "chrome.exe" in cmd or
            "chromium" in cmd or
            "msedge" in cmd
        )

    @staticmethod
    def _normalize_lifecycle(lifecycle):
        if lifecycle == ProcessLifecycle.NEW:
            return ProcessLifecycle.RUNNING
        return lifecycle

    @staticmethod
    def _parse_debug_port(cmd):
        match = re.search(r'--remote-debugging-port=(\d+)', cmd)
        if match:
            return int(match.group(1))
        return None


# ==================== 看门狗策略 ====================

class WatchdogPolicy:

    @staticmethod
    def evaluate(record, health, now, config):
        # 0. 已终止
        if record.lifecycle == ProcessLifecycle.TERMINATED:
            return WatchdogDecision(WatchdogDecisionType.ALLOW, message="already terminated")

        # 1. 保护资源只观察
        if record.protection == ProtectionLevel.PROTECTED or ProcessClassifier.is_cdp_protected(record):
            return WatchdogDecision(WatchdogDecisionType.OBSERVE_PROTECTED,
                                    message="protected or cdp-attached resource")

        # 2. owner死亡转orphan
        if not health.owner_alive and record.source == ProcessSource.MANAGED_LAUNCH:
            if record.lifecycle not in [ProcessLifecycle.ORPHAN_CANDIDATE, ProcessLifecycle.TERMINATED]:
                record.lifecycle = ProcessLifecycle.ORPHAN_CANDIDATE
                if record.quarantine_since == 0:
                    record.quarantine_since = now

        # 3. 健康就恢复
        if WatchdogPolicy._is_healthy(record, health, now, config):
            record.unhealthy_count = 0
            record.quarantine_since = 0
            record.graceful_since = 0
            record.last_healthy_at = now
            if record.lifecycle != ProcessLifecycle.TERMINATED:
                record.lifecycle = ProcessLifecycle.RUNNING
            return WatchdogDecision(WatchdogDecisionType.ALLOW, message="healthy")

        # 4. 不健康累计
        record.unhealthy_count += 1

        # orphan特判
        if record.lifecycle == ProcessLifecycle.ORPHAN_CANDIDATE:
            orphan_wait = now - (record.quarantine_since or now)
            if orphan_wait >= config.orphan_grace_ms:
                return WatchdogPolicy._move_to_graceful_or_kill(
                    record, now, config, KillReason.OWNER_DEAD_ORPHAN_TIMEOUT)
            return WatchdogDecision(WatchdogDecisionType.QUARANTINE,
                                    reason=KillReason.OWNER_DEAD_ORPHAN_TIMEOUT,
                                    message="orphan candidate waiting grace window")

        # 5. 未达阈值
        if record.unhealthy_count < config.unhealthy_threshold:
            if record.lifecycle in [ProcessLifecycle.RUNNING, ProcessLifecycle.NEW]:
                record.lifecycle = ProcessLifecycle.QUARANTINED
            if record.quarantine_since == 0:
                record.quarantine_since = now
            return WatchdogDecision(WatchdogDecisionType.QUARANTINE,
                                    reason=WatchdogPolicy._decide_reason(record, health),
                                    message=f"unhealthy but below threshold ({record.unhealthy_count}/{config.unhealthy_threshold})")

        # 6. 达到阈值
        return WatchdogPolicy._move_to_graceful_or_kill(
            record, now, config, WatchdogPolicy._decide_reason(record, health))

    @staticmethod
    def _is_healthy(record, health, now, config):
        if not health.process_alive:
            return False

        # CDP保护的资源只要进程活着就视为健康
        if record.source == ProcessSource.ATTACHED_CDP:
            return True

        score = 0
        if health.process_alive:
            score += 3
        if health.owner_alive:
            score += 2
        if health.heartbeat_fresh or WatchdogPolicy._is_heartbeat_fresh(record, now, config):
            score += 2
        if health.ws_connected:
            score += 1
        if health.devtools_reachable:
            score += 1
        if health.recent_io:
            score += 1

        return score >= 5

    @staticmethod
    def _is_heartbeat_fresh(record, now, config):
        if record.last_heartbeat_at <= 0:
            return False
        return (now - record.last_heartbeat_at) <= (config.heartbeat_timeout_ms / 1000)

    @staticmethod
    def _move_to_graceful_or_kill(record, now, config, reason):
        # 先优雅关闭
        if record.allow_graceful_shutdown and record.lifecycle != ProcessLifecycle.GRACEFUL_STOPPING:
            record.lifecycle = ProcessLifecycle.GRACEFUL_STOPPING
            record.graceful_since = now
            if record.quarantine_since == 0:
                record.quarantine_since = now
            return WatchdogDecision(WatchdogDecisionType.REQUEST_GRACEFUL_SHUTDOWN,
                                    reason=reason,
                                    message="request graceful shutdown first")

        # 已经进入优雅关闭，等待窗口
        if record.lifecycle == ProcessLifecycle.GRACEFUL_STOPPING:
            graceful_since = record.graceful_since or now
            waited = now - graceful_since
            if waited < config.graceful_shutdown_wait_ms:
                return WatchdogDecision(WatchdogDecisionType.ALLOW,
                                        reason=reason,
                                        message=f"waiting graceful shutdown ({int(waited)}ms)")

        # 最后才hard kill
        if ProcessClassifier.can_hard_kill(record):
            return WatchdogDecision(WatchdogDecisionType.HARD_KILL,
                                    reason=reason,
                                    message="graceful failed, can hard kill")

        return WatchdogDecision(WatchdogDecisionType.OBSERVE_PROTECTED,
                                reason=reason,
                                message="cannot hard kill due to protection/source/role")

    @staticmethod
    def _decide_reason(record, health):
        if not health.owner_alive and record.source == ProcessSource.MANAGED_LAUNCH:
            return KillReason.OWNER_DEAD_ORPHAN_TIMEOUT
        if record.role == ProcessRole.PLAYWRIGHT_WORKER:
            return KillReason.PLAYWRIGHT_WORKER_HUNG
        if record.role == ProcessRole.BROWSER_LAUNCHER:
            return KillReason.MANAGED_BROWSER_NOT_RESPONDING
        if health.ws_connected is False and health.devtools_reachable is False:
            return KillReason.IPC_BROKEN_AND_NO_RECOVERY
        return KillReason.HEARTBEAT_TIMEOUT_CONSECUTIVE


# ==================== 日志 ====================

class WatchdogLogger:
    LOG_FILE = "/tmp/watchdog_v3.log"

    @classmethod
    def log_decision(cls, stage, record, decision, health=None):
        msg = f"""
[WATCHDOG][{stage}]
pid={record.pid}
ppid={record.ppid}
name={record.name}
role={record.role}
source={record.source}
lifecycle={record.lifecycle}
protection={record.protection}
session_id={record.session_id}
owner_pid={record.owner_pid}
launch_token={record.launch_token}
attached_debug_port={record.attached_debug_port}
unhealthy_count={record.unhealthy_count}
last_heartbeat_at={record.last_heartbeat_at}
last_healthy_at={record.last_healthy_at}
quarantine_since={record.quarantine_since}
graceful_since={record.graceful_since}
allow_graceful_shutdown={record.allow_graceful_shutdown}
cmdline={record.cmdline[:100]}
decision={decision.type}
reason={decision.reason}
message={decision.message}
health=process_alive={health.process_alive if health else None}
""".strip()

        print(msg)
        with open(cls.LOG_FILE, 'a') as f:
            f.write(msg + "\n")


# ==================== 看门狗主循环 ====================

class Watchdog:
    def __init__(self, config=None):
        self.config = config or WatchdogConfig()
        self.running = True

    def start(self):
        print("🐕 看门狗 v3.0 启动")
        print(f"配置: scan={self.config.scan_interval_ms}ms, threshold={self.config.unhealthy_threshold}, quarantine={self.config.quarantine_ms}ms")

        while self.running:
            try:
                self._tick(time.time())
            except Exception as e:
                print(f"扫描错误: {e}")
            time.sleep(self.config.scan_interval_ms / 1000)

    def stop(self):
        self.running = False

    def _tick(self, now):
        records = ProcessRegistry.all()

        for record in records:
            if record.lifecycle == ProcessLifecycle.TERMINATED:
                continue

            health = self._probe_health(record)
            decision = WatchdogPolicy.evaluate(record, health, now, self.config)
            WatchdogLogger.log_decision("TICK", record, decision, health)
            self._execute_decision(record, decision, health, now)

    def _probe_health(self, record):
        process_alive = self._is_process_alive(record.pid)
        owner_alive = True
        if record.owner_pid > 0:
            owner_alive = self._is_process_alive(record.owner_pid)
        heartbeat_fresh = False
        if record.last_heartbeat_at > 0:
            heartbeat_fresh = (time.time() - record.last_heartbeat_at) <= (self.config.heartbeat_timeout_ms / 1000)

        return HealthSnapshot(
            process_alive=process_alive,
            owner_alive=owner_alive,
            heartbeat_fresh=heartbeat_fresh,
            ws_connected=None,
            devtools_reachable=None,
            recent_io=None
        )

    def _is_process_alive(self, pid):
        if pid <= 0:
            return True
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _execute_decision(self, record, decision, health, now):
        if decision.type == WatchdogDecisionType.HARD_KILL:
            self._hard_kill(record)

    def _hard_kill(self, record):
        try:
            os.kill(record.pid, signal.SIGKILL)
            record.lifecycle = ProcessLifecycle.TERMINATED
            print(f"🔪 HARD KILL pid={record.pid}")
        except OSError as e:
            print(f"kill失败 pid={record.pid}: {e}")


# ==================== CLI ====================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("""
🐕 看门狗 v3.0

用法:
  python3 watchdog2.py start           # 启动看门狗
  python3 watchdog2.py register <pid>  # 登记托管进程
  python3 watchdog2.py status        # 查看状态
  python3 watchdog2.py stop         # 停止
        """)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "start":
        w = Watchdog()
        w.start()
    elif cmd == "register":
        if len(sys.argv) > 2:
            pid = int(sys.argv[2])
            ProcessRegistry.upsert(ProcessRecord(pid=pid, name="managed"))
            print(f"已登记 pid={pid}")
    elif cmd == "status":
        records = ProcessRegistry.all()
        print(f"托管进程数: {len(records)}")
        for r in records:
            print(f"  {r.pid}: {r.role} / {r.lifecycle}")
    elif cmd == "stop":
        print("停止...")
        sys.exit(0)
