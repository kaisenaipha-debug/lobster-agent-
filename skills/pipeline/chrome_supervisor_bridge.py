#!/usr/bin/env python3
"""
chrome_supervisor_bridge.py
============================
Python → browser_supervisor.ts 的 stdio JSON-RPC 桥接层。

替代 browser_control.py 中原始的 _ensure_chrome()，
把 Chrome 生命周期管理交给有自愈能力的 Node.js 守护进程。

使用方式：
  from chrome_supervisor_bridge import ChromeBridge
  bridge = ChromeBridge()
  bridge.start()           # 启动守护进程 + Chrome
  state = bridge.status()  # { "state": "CONNECTED", "connected": true, "endpoint": "..." }
  bridge.stop()             # 停止

CDP URL: http://127.0.0.1:9222
"""

import os
import sys
import json
import subprocess
import time
import select
import threading
from pathlib import Path
from typing import Optional

SUPERVISOR_SCRIPT = str(Path(__file__).parent / "browser_supervisor.ts")


class ChromeBridge:
    """
    Chrome Supervisor 桥接器。

    在后台启动 tsx browser_supervisor.ts rpc，
    通过 stdio JSON-RPC 与其通信。

    核心改进（相比 browser_control.py 的 _ensure_chrome）：
      ✅ 进程死亡自动重启 Chrome
      ✅ 指数退避重连（最多 30s 间隔）
      ✅ 双层健康检查（端口探针 + DevTools HTTP probe）
      ✅ 三种恢复路径：重连 → 杀进程+重连 → 完整重启
      ✅ connectGeneration 防 stale 连接
      ✅ Graceful shutdown（SIGTERM → SIGKILL）
    """

    def __init__(
        self,
        debug_port: int = 9222,
        chrome_path: str = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        user_data_dir: str = None,
        log_prefix: str = "PY_BRIDGE",
    ):
        self.debug_port = debug_port
        self.chrome_path = chrome_path
        self.user_data_dir = (
            user_data_dir
            or str(Path.home() / ".qclaw" / "browser" / "pha-debug")
        )
        self.log_prefix = log_prefix

        self._proc: Optional[subprocess.Popen] = None
        self._started = False
        self._rpc_id = 0
        self._lock = threading.Lock()

    # ─── Public API ─────────────────────────────────────────

    def start(self, timeout: float = 30) -> dict:
        """启动守护进程 + Chrome 自愈管理"""
        if self._started:
            return self._call_rpc("status")

        self._ensure_node_deps()
        self._proc = self._spawn_daemon()
        self._started = True

        # 发送 start，触发 supervisor.launchChrome() + connectBrowser()
        # _spawn_daemon 已确保进程就绪，这里发 start 请求
        start_resp = self._call_rpc("start", timeout=min(timeout, 25))
        # start_resp 可能返回 CONNECTED（快）或 timeout（Chrome 还在启动）
        # 继续轮询直到 CONNECTED
        deadline = time.time() + timeout
        while time.time() < deadline:
            resp = self._call_rpc("status", timeout=5)
            state = resp.get("result", {}).get("state", "")
            if state == "CONNECTED" or resp.get("result", {}).get("connected"):
                return resp
            if resp.get("error"):
                # 有错误，稍等再试
                time.sleep(1)
                continue
            # 未 CONNECTED 但也无错误，说明还在启动中
            time.sleep(1)

        # 返回最后一次状态
        return self._call_rpc("status", timeout=5)

    def stop(self) -> dict:
        """停止守护进程 + Chrome"""
        if not self._proc:
            return {"ok": True}
        try:
            result = self._call_rpc("stop")
        except Exception as e:
            result = {"ok": False, "error": str(e)}
        self._proc.terminate()
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        self._proc = None
        self._started = False
        return result

    def status(self) -> dict:
        """查询当前状态"""
        if not self._started:
            return {"result": {"state": "STOPPED", "connected": False}}
        return self._call_rpc("status")

    def is_healthy(self) -> bool:
        """Chrome 是否处于 CONNECTED 状态"""
        if not self._started:
            return False
        try:
            s = self.status()
            r = s.get("result", {})
            return r.get("connected") is True or r.get("state") == "CONNECTED"
        except Exception:
            return False

    def get_cdp_url(self) -> str:
        """CDP 端点"""
        return f"http://127.0.0.1:{self.debug_port}"

    def get_debug_endpoint(self) -> str:
        return self.get_cdp_url()

    def get_playwright_browser(self, timeout: float = 10):
        """
        返回 playwright.Browser 对象。
        Python 侧可以直接：
          from playwright.sync_api import sync_playwright
          browser = bridge.get_playwright_browser()
          page = browser.contexts()[0].new_page()
        """
        from playwright.sync_api import sync_playwright

        if not self.is_healthy():
            self.start()
        return sync_playwright().start().chromium.connect_over_cdp(
            self.get_cdp_url()
        )

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

    # ─── Internals ─────────────────────────────────────────

    def _ensure_node_deps(self):
        """确保 tsx 和依赖已安装"""
        pipeline_dir = Path(__file__).parent
        pkg_json = pipeline_dir / "package.json"
        if not pkg_json.exists():
            raise RuntimeError(
                f"package.json not found in {pipeline_dir}. "
                "Run: cd {pipeline_dir} && npm init -y && npm install tsx playwright @types/node"
            )
        tsx = pipeline_dir / "node_modules" / ".bin" / "tsx"
        if not tsx.exists():
            raise RuntimeError(
                f"tsx not found. Run: cd {pipeline_dir} && npm install tsx"
            )

    def _spawn_daemon(self) -> subprocess.Popen:
        """启动 tsx rpc 守护进程"""
        tsx = Path(__file__).parent / "node_modules" / ".bin" / "tsx"
        proc = subprocess.Popen(
            [str(tsx), SUPERVISOR_SCRIPT, "rpc"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(Path(__file__).parent),
            text=True,
            bufsize=1,
        )
        return proc

    def _next_id(self) -> int:
        with self._lock:
            self._rpc_id += 1
            return self._rpc_id

    def _call_rpc(self, method: str, params: dict = None, timeout: float = 10) -> dict:
        """
        使用 select + readline 实现可靠的 stdio RPC。
        每次请求写入 stdin，读取 stdout 一行 JSON 响应。
        """
        if not self._proc or self._proc.poll() is not None:
            raise RuntimeError("Supervisor daemon not running")

        req_id = self._next_id()
        req = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
        req_str = json.dumps(req) + "\n"

        # 发送请求
        self._proc.stdin.write(req_str)
        self._proc.stdin.flush()

        # 用 select 轮询，直到读到一行完整 JSON
        deadline = time.time() + timeout
        fd = self._proc.stdout.fileno()

        while time.time() < deadline:
            ready, _, _ = select.select([fd], [], [], 0.2)
            if ready:
                # 读取一整行（直到 \n）
                line = self._proc.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line or line == "RESP:":
                    continue
                try:
                    resp = json.loads(line)
                    if isinstance(resp, dict) and resp.get("id") == req_id:
                        return resp
                    # id 不匹配，说明是过期的响应，忽略继续等
                except json.JSONDecodeError:
                    pass
            # else: select 超时，继续轮询

        return {"error": "timeout waiting for supervisor response"}

    # ─── Logging ────────────────────────────────────────────

    def _log(self, level: str, msg: str):
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"[{ts}] [{self.log_prefix}] [{level}] {msg}", flush=True)


# ─── CLI ──────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Chrome Supervisor Bridge")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("start", help="启动 Chrome 守护进程")
    sub.add_parser("status", help="查询状态")
    sub.add_parser("stop", help="停止")
    sub.add_parser("test", help="启动 + 检查健康")

    args = parser.parse_args(sys.argv[1:] or ["test"])

    bridge = ChromeBridge()

    if args.cmd == "start":
        r = bridge.start()
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif args.cmd == "status":
        print(json.dumps(bridge.status(), ensure_ascii=False, indent=2))
    elif args.cmd == "stop":
        print(json.dumps(bridge.stop(), ensure_ascii=False, indent=2))
    else:
        print("🚀 启动 Chrome Supervisor...")
        r = bridge.start()
        print("📊 状态:", json.dumps(r, ensure_ascii=False, indent=2))
        print("🔗 CDP:", bridge.get_cdp_url())
        print("✅ 健康:", bridge.is_healthy())
