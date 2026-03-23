"""
小龙虾 Guardian 系统 v1.0
集成版 — 路径常量已适配 ~/.qclaw

模块：
 SecurityGuard       - S级安全防护（路径/输出/意图）
 CapabilityRegistry  - 能力只进不退版本管理
 StepTracer          - 步骤追踪 + 错误精确定位
 SmartCaller         - 智能LLM调用（防滥用/指数退避）
 IntegrityWatchdog   - 完整性看门狗（SHA-256基线）
 Migrator            - 一键打包/恢复全部能力
"""

import os, re, json, time, math, shutil, hashlib, logging, tarfile, tempfile, threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Callable, Any
from dataclasses import dataclass, field, asdict
from functools import wraps
from collections import deque

# ─────────────────────────────────────────────
# 路径常量（适配 ~/.qclaw）
# ─────────────────────────────────────────────
BASE_DIR      = Path.home() / ".qclaw"
CORE_DIR      = BASE_DIR / "core"
LOG_DIR       = BASE_DIR / "logs"
EXPORT_DIR    = BASE_DIR / "exports"
WORKSPACE_DIR = BASE_DIR / "workspace"

# 能力注册表（兼容现有路径）
CAPABILITY_FILE = BASE_DIR / "workspace" / "CAPABILITY_REGISTRY.json"
BASELINE_FILE   = BASE_DIR / "workspace" / "baseline.sha256"

for _d in [BASE_DIR, CORE_DIR, LOG_DIR, EXPORT_DIR, WORKSPACE_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────
# 日志（append-only）
# ─────────────────────────────────────────────
def _make_logger(name: str, file: str) -> logging.Logger:
    lg = logging.getLogger(name)
    lg.setLevel(logging.DEBUG)
    if not lg.handlers:
        fh = logging.FileHandler(LOG_DIR / file, mode="a", encoding="utf-8")
        fh.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S"
        ))
        lg.addHandler(fh)
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))
        lg.addHandler(ch)
    return lg

audit_log = _make_logger("audit",  "audit.log")
error_log = _make_logger("errors", "errors.log")
step_log  = _make_logger("steps",  "steps.log")


# ══════════════════════════════════════════════
# 1. SecurityGuard — S级安全防护
# ══════════════════════════════════════════════
class SecurityGuard:
    """
    三道防线：
    A. 路径ACL   — 控制哪些路径可读/写/不可访问
    B. 意图扫描  — 阻断泄露/破坏型指令
    C. 输出脱敏  — 自动遮盖密钥/路径/高熵串
    """

    # ── A. 路径 ACL ──────────────────────────
    DENY_READ_PATTERNS = [
        r"\.ssh[/\\]",
        r"\.aws[/\\]credentials",
        r"\.gnupg[/\\]",
        r"\.env$",
        r"\.env\.",
        r"id_rsa", r"id_ed25519", r"id_ecdsa",
        r".*\.pem$", r".*\.p12$", r".*\.pfx$",
        r".*\.key$",
        r"keychain", r"Keychain",
        r"/etc/shadow", r"/etc/passwd",
        r"\.netrc$",
        r"\.pgpass$",
    ]

    CORE_READONLY_DIRS = [
        str(BASE_DIR / "workspace" / "CAPABILITY_REGISTRY.json"),
        str(BASE_DIR / "workspace" / "baseline.sha256"),
    ]

    # ── B. 危险意图关键词 ────────────────────
    DANGEROUS_INTENTS = [
        # 泄露类
        r"send.*password", r"upload.*secret", r"post.*token",
        r"exfiltrat", r"leak.*credential",
        # 破坏类
        r"rm\s+-rf", r"shutil\.rmtree.*core",
        r"os\.remove.*guardian", r"truncate.*capability",
        r"delete.*baseline", r"wipe.*log",
        # 绕过类
        r"disable.*security", r"bypass.*guard",
        r"ignore.*acl", r"skip.*audit",
    ]

    # ── C. 输出脱敏正则 ──────────────────────
    REDACT_PATTERNS = [
        (re.compile(r"sk-[A-Za-z0-9]{20,}"),             "[OPENAI_KEY_REDACTED]"),
        (re.compile(r"ghp_[A-Za-z0-9]{36}"),            "[GITHUB_TOKEN_REDACTED]"),
        (re.compile(r"AKIA[0-9A-Z]{16}"),               "[AWS_KEY_REDACTED]"),
        (re.compile(r"glpat-[A-Za-z0-9\-]{20}"),        "[GITLAB_TOKEN_REDACTED]"),
        (re.compile(r"xox[bpoa]-[A-Za-z0-9\-]{10,60}"), "[SLACK_TOKEN_REDACTED]"),
        (re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]{20,}"), "Bearer [TOKEN_REDACTED]"),
        (re.compile(r"(?i)password['\"]?\s*[:=]\s*\S+"), "password=[REDACTED]"),
        (re.compile(r"(?i)secret['\"]?\s*[:=]\s*\S+"),  "secret=[REDACTED]"),
        (re.compile(r"/Users/[^/\s]+"),                  "~"),
        (re.compile(r"/home/[^/\s]+"),                  "~"),
        (re.compile(r"C:\\\\Users\\\\[^\\\\]+"),        "~"),
    ]

    @staticmethod
    def _entropy(s: str) -> float:
        if not s:
            return 0.0
        freq = {}
        for c in s:
            freq[c] = freq.get(c, 0) + 1
        return -sum((f/len(s)) * math.log2(f/len(s)) for f in freq.values())

    def check_path_access(self, path: str, mode: str = "read") -> tuple[bool, str]:
        p = str(Path(path).expanduser().resolve())
        for pattern in self.DENY_READ_PATTERNS:
            if re.search(pattern, p, re.IGNORECASE):
                reason = f"路径命中敏感规则: {pattern}"
                audit_log.warning(f"PATH_DENIED [{mode}] {p} — {reason}")
                return False, reason
        for core in self.CORE_READONLY_DIRS:
            if p.startswith(core) and mode in ("write", "delete"):
                reason = f"核心文件受保护，拒绝 {mode}: {p}"
                audit_log.warning(f"CORE_PROTECTED [{mode}] {p}")
                return False, reason
        audit_log.debug(f"PATH_OK [{mode}] {p}")
        return True, "ok"

    def check_intent(self, text: str) -> tuple[bool, str]:
        for pattern in self.DANGEROUS_INTENTS:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                reason = f"危险意图: 命中规则 `{pattern}`，匹配词: `{m.group()}`"
                audit_log.error(f"INTENT_BLOCKED — {reason}")
                return False, reason
        return True, "ok"

    def sanitize_output(self, text: str) -> str:
        result = text
        for pattern, replacement in self.REDACT_PATTERNS:
            result = pattern.sub(replacement, result)
        words = re.findall(r"[A-Za-z0-9+/=_\-]{20,}", result)
        for w in words:
            if self._entropy(w) > 4.5:
                result = result.replace(w, f"[HIGH_ENTROPY_REDACTED:{w[:4]}…]")
        if result != text:
            audit_log.info("OUTPUT_SANITIZED — 已脱敏敏感内容")
        return result

    def safe_file_read(self, path: str) -> tuple[bool, str]:
        ok, reason = self.check_path_access(path, "read")
        if not ok:
            return False, f"[安全拒绝] {reason}"
        try:
            content = Path(path).read_text(encoding="utf-8", errors="replace")
            return True, self.sanitize_output(content)
        except Exception as e:
            return False, f"[读取失败] {e}"


# ══════════════════════════════════════════════
# 2. CapabilityRegistry — 能力只进不退
# ══════════════════════════════════════════════
@dataclass
class CapabilityEntry:
    name:        str
    version:     str          # 语义版本 "1.2.3"
    score:       float        # 0.0 ~ 1.0
    description: str
    last_updated: str
    history:     list = field(default_factory=list)

    def version_tuple(self) -> tuple:
        return tuple(int(x) for x in self.version.split("."))


class CapabilityRegistry:
    """
    能力版本管理器：
    - 注册新能力 / 升级现有能力
    - 拒绝任何降版本或降分操作
    - 每次变更写入不可变历史
    """

    def __init__(self):
        self._lock   = threading.Lock()
        self._data: dict[str, CapabilityEntry] = {}
        self._load()

    def _load(self):
        if CAPABILITY_FILE.exists():
            try:
                raw = json.loads(CAPABILITY_FILE.read_text())
                for name, d in raw.items():
                    self._data[name] = CapabilityEntry(**d)
            except Exception as e:
                error_log.error(f"CAPABILITY_LOAD_ERROR: {e}")

    def _save(self):
        tmp = CAPABILITY_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(
            {k: asdict(v) for k, v in self._data.items()},
            ensure_ascii=False, indent=2
        ))
        tmp.replace(CAPABILITY_FILE)
        audit_log.info("CAPABILITY_SAVED")

    def register(self, name: str, version: str, score: float,
                 description: str = "") -> tuple[bool, str]:
        with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            new_ver = tuple(int(x) for x in version.split("."))

            if name in self._data:
                existing = self._data[name]
                old_ver   = existing.version_tuple()

                # ── 防退化 ──
                if new_ver < old_ver:
                    msg = f"⛔ 拒绝降版本: {name} {existing.version} → {version}"
                    audit_log.error(f"CAPABILITY_DOWNGRADE_BLOCKED: {msg}")
                    return False, msg

                if score < existing.score - 0.001:
                    msg = f"⛔ 拒绝降分: {name} {existing.score:.3f} → {score:.3f}"
                    audit_log.error(f"CAPABILITY_SCORE_DROP_BLOCKED: {msg}")
                    return False, msg

                if new_ver == old_ver and abs(score - existing.score) < 0.001:
                    return True, f"✓ 无变化: {name} {version}"

                existing.history.append({
                    "from_version": existing.version,
                    "from_score":   existing.score,
                    "to_version":   version,
                    "to_score":     score,
                    "time":         now,
                })
                existing.version     = version
                existing.score      = score
                existing.description = description or existing.description
                existing.last_updated = now
                msg = f"✅ 升级: {name} → v{version} (score={score:.3f})"
            else:
                self._data[name] = CapabilityEntry(
                    name=name, version=version, score=score,
                    description=description, last_updated=now,
                    history=[]
                )
                msg = f"✅ 新增能力: {name} v{version} (score={score:.3f})"

            self._save()
            audit_log.info(f"CAPABILITY_UPDATED: {msg}")
            return True, msg

    def get(self, name: str) -> Optional[CapabilityEntry]:
        return self._data.get(name)

    def list_all(self) -> list[CapabilityEntry]:
        return sorted(self._data.values(), key=lambda x: x.name)

    def summary(self) -> str:
        entries = self.list_all()
        if not entries:
            return "（暂无注册能力）"
        lines = [f"{'能力名':<30} {'版本':<10} {'得分':>6}  描述"]
        lines.append("─" * 70)
        for e in entries:
            lines.append(f"{e.name:<30} {e.version:<10} {e.score:>6.3f}  {e.description[:30]}")
        return "\n".join(lines)


# ══════════════════════════════════════════════
# 3. StepTracer — 步骤追踪 + 错误精确定位
# ══════════════════════════════════════════════
@dataclass
class StepResult:
    index:       int
    name:        str
    status:      str   # "ok" | "error" | "skipped" | "running"
    detail:      str   = ""
    elapsed_ms:  float = 0.0
    error_type:  str   = ""
    suggestion:  str   = ""


class StepTracer:
    def __init__(self, task_name: str):
        self.task_name   = task_name
        self.steps: list[StepResult] = []
        self._start_time = time.time()

    def run(self, steps: list[tuple[str, Callable, dict]]) -> bool:
        print(f"\n{'━'*60}")
        print(f"  任务: {self.task_name}")
        print(f"  共 {len(steps)} 步  {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'━'*60}")

        all_ok = True
        for i, (name, func, kwargs) in enumerate(steps, 1):
            result = StepResult(index=i, name=name, status="running")
            self.steps.append(result)
            print(f"\n  步骤 {i}/{len(steps)} ▶ {name}")

            t0 = time.perf_counter()
            try:
                ret = func(**kwargs)
                result.elapsed_ms = (time.perf_counter() - t0) * 1000
                result.status     = "ok"
                result.detail     = str(ret) if ret is not None else "成功"
                print(f"  ✅ OK ({result.elapsed_ms:.0f}ms)")
                step_log.info(f"[{self.task_name}] STEP {i} OK — {name}")

            except Exception as e:
                result.elapsed_ms = (time.perf_counter() - t0) * 1000
                result.status     = "error"
                result.error_type = type(e).__name__
                result.detail     = str(e)
                result.suggestion = self._suggest(e, name)
                all_ok = False

                print(f"  ❌ 失败 [{result.error_type}]")
                print(f"  错误: {result.detail}")
                print(f"  建议: {result.suggestion}")
                step_log.error(
                    f"[{self.task_name}] STEP {i} FAILED — {name} | "
                    f"{result.error_type}: {result.detail}"
                )
                error_log.error(
                    f"TASK={self.task_name} | STEP={i}/{len(steps)} | "
                    f"NAME={name} | {result.error_type}: {result.detail}"
                )
                for j in range(i, len(steps)):
                    skipped = StepResult(
                        index=j+1, name=steps[j][0],
                        status="skipped",
                        detail=f"因步骤 {i} 失败而跳过"
                    )
                    self.steps.append(skipped)
                    print(f"\n  步骤 {j+1}/{len(steps)} ⏭ {steps[j][0]} (跳过)")
                break

        self._print_summary(all_ok)
        return all_ok

    def _suggest(self, e: Exception, step_name: str) -> str:
        t   = type(e).__name__
        msg = str(e).lower()
        if t == "FileNotFoundError":
            return f"文件不存在，请检查路径是否正确: {e}"
        if t == "PermissionError":
            return "权限不足，可能是受保护的核心文件，不应修改"
        if t in ("ConnectionError", "TimeoutError"):
            return "网络超时，请检查网络连接，或稍后重试"
        if t == "JSONDecodeError":
            return "JSON格式错误，请检查配置文件是否完整，勿手动编辑"
        if "api" in msg and ("rate" in msg or "limit" in msg or "429" in msg):
            return "API限流，已触发退避策略，稍候会自动重试"
        if "import" in msg or t == "ModuleNotFoundError":
            return f"缺少依赖，请运行: pip install {str(e).split('No module named')[-1].strip()}"
        if "memory" in msg or t == "MemoryError":
            return "内存不足，请关闭其他程序或减小批次大小"
        return f"请查看 {LOG_DIR}/errors.log 获取详细堆栈信息"

    def _print_summary(self, all_ok: bool):
        total    = time.time() - self._start_time
        ok_cnt   = sum(1 for s in self.steps if s.status == "ok")
        err_cnt  = sum(1 for s in self.steps if s.status == "error")
        skip_cnt = sum(1 for s in self.steps if s.status == "skipped")

        print(f"\n{'━'*60}")
        status_icon = "✅ 全部完成" if all_ok else "❌ 任务中断"
        print(f"  {status_icon} | 耗时 {total:.1f}s")
        print(f"  成功 {ok_cnt}  失败 {err_cnt}  跳过 {skip_cnt}")

        if not all_ok:
            failed = [s for s in self.steps if s.status == "error"]
            for s in failed:
                print(f"\n  ── 出错位置 ──")
                print(f"  步骤 {s.index}: {s.name}")
                print(f"  类型: {s.error_type}")
                print(f"  详情: {s.detail}")
                print(f"  建议: {s.suggestion}")
        print(f"{'━'*60}\n")


def step(name: str):
    """装饰器：自动将函数包装成步骤"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        wrapper._step_name = name
        return wrapper
    return decorator


# ══════════════════════════════════════════════
# 4. SmartCaller — 智能LLM调用（防滥用）
# ══════════════════════════════════════════════
@dataclass
class CallRecord:
    timestamp:  float
    model:      str
    tokens_in:  int
    tokens_out: int
    cost_usd:   float
    success:    bool


class SmartCaller:
    PRICING = {
        "gpt-4o":                 (5.0,  15.0),
        "gpt-4o-mini":            (0.15,  0.60),
        "claude-3-5-sonnet":      (3.0,  15.0),
        "claude-3-haiku":         (0.25,  1.25),
        "deepseek-chat":          (0.14,  0.28),
        "minimax/MiniMax-M2.7":   (0.0,   0.0),   # 内部定价未知
    }

    def __init__(
        self,
        max_calls_per_minute: int   = 10,
        max_calls_per_hour:   int   = 100,
        budget_usd_per_day:   float = 5.0,
        max_retries:          int   = 3,
        base_retry_delay:     float = 2.0,
    ):
        self.max_rpm       = max_calls_per_minute
        self.max_rph       = max_calls_per_hour
        self.budget        = budget_usd_per_day
        self.max_retries   = max_retries
        self.base_delay    = base_retry_delay

        self._minute_window: deque  = deque()
        self._hour_window:   deque  = deque()
        self._records:      list[CallRecord] = []
        self._lock           = threading.Lock()

    def _check_rate(self) -> tuple[bool, str]:
        now = time.time()
        with self._lock:
            while self._minute_window and self._minute_window[0] < now - 60:
                self._minute_window.popleft()
            while self._hour_window and self._hour_window[0] < now - 3600:
                self._hour_window.popleft()

            if len(self._minute_window) >= self.max_rpm:
                wait = 60 - (now - self._minute_window[0])
                return False, f"每分钟限制 {self.max_rpm} 次，需等待 {wait:.1f}s"
            if len(self._hour_window) >= self.max_rph:
                wait = 3600 - (now - self._hour_window[0])
                return False, f"每小时限制 {self.max_rph} 次，需等待 {wait:.0f}s"
            return True, "ok"

    def _check_budget(self, model: str, estimated_tokens: int) -> tuple[bool, str]:
        today_start = datetime.now().replace(hour=0, minute=0, second=0).timestamp()
        today_cost  = sum(r.cost_usd for r in self._records if r.timestamp >= today_start)
        price_in, price_out = self.PRICING.get(model, (1.0, 3.0))
        estimated_cost = (estimated_tokens / 1_000_000) * (price_in + price_out)

        if today_cost + estimated_cost > self.budget:
            return False, (
                f"预算告警: 今日已花费 ${today_cost:.4f}，"
                f"本次预估 ${estimated_cost:.4f}，"
                f"超过每日上限 ${self.budget}"
            )
        return True, "ok"

    def call(
        self,
        func: Callable,
        model:             str  = "gpt-4o-mini",
        estimated_tokens:   int  = 1000,
        need_web:           bool = False,
        local_knowledge_check: Optional[Callable] = None,
        **kwargs
    ) -> Any:
        # 1. 本地知识优先
        if local_knowledge_check:
            local_result = local_knowledge_check()
            if local_result is not None:
                audit_log.info("SMART_CALL: 命中本地缓存，跳过API调用")
                return local_result

        # 2. 网页访问需明确授权
        if need_web:
            audit_log.info("SMART_CALL: 需要联网访问，已标记")

        # 3. 速率检查
        ok, reason = self._check_rate()
        if not ok:
            error_log.warning(f"RATE_LIMIT: {reason}")
            raise RuntimeError(f"[速率限制] {reason}")

        # 4. 预算检查
        ok, reason = self._check_budget(model, estimated_tokens)
        if not ok:
            error_log.warning(f"BUDGET_EXCEEDED: {reason}")
            raise RuntimeError(f"[预算超限] {reason}")

        # 5. 指数退避重试
        last_exc = None
        for attempt in range(1, self.max_retries + 1):
            try:
                t0 = time.perf_counter()
                result = func(**kwargs)
                elapsed = (time.perf_counter() - t0) * 1000

                price_in, price_out = self.PRICING.get(model, (1.0, 3.0))
                cost = (estimated_tokens / 1_000_000) * (price_in + price_out)

                with self._lock:
                    now = time.time()
                    self._minute_window.append(now)
                    self._hour_window.append(now)
                    self._records.append(CallRecord(
                        timestamp=now, model=model,
                        tokens_in=estimated_tokens, tokens_out=0,
                        cost_usd=cost, success=True
                    ))

                audit_log.info(
                    f"LLM_CALL OK | model={model} | attempt={attempt} | "
                    f"{elapsed:.0f}ms | cost=${cost:.5f}"
                )
                return result

            except Exception as e:
                last_exc = e
                delay = self.base_delay * (2 ** (attempt - 1))
                error_log.warning(
                    f"LLM_CALL FAILED | attempt={attempt}/{self.max_retries} | "
                    f"{type(e).__name__}: {e} | 退避 {delay:.1f}s"
                )
                if attempt < self.max_retries:
                    print(f"  ⚠️ API调用失败（第{attempt}次），{delay:.1f}s 后重试…")
                    time.sleep(delay)

        raise RuntimeError(
            f"API调用连续失败 {self.max_retries} 次，最后错误: {last_exc}"
        )

    def stats(self) -> str:
        today_start = datetime.now().replace(hour=0, minute=0, second=0).timestamp()
        today = [r for r in self._records if r.timestamp >= today_start]
        total_cost = sum(r.cost_usd for r in today)
        total_calls = len(today)
        ok_calls = sum(1 for r in today if r.success)
        return (
            f"今日调用: {total_calls} 次 (成功 {ok_calls}) | "
            f"花费: ${total_cost:.4f} / ${self.budget} | "
            f"最近1分钟: {len(self._minute_window)} 次"
        )


# ══════════════════════════════════════════════
# 5. IntegrityWatchdog — 完整性看门狗
# ══════════════════════════════════════════════
class IntegrityWatchdog:
    """
    启动时：对核心文件做SHA-256快照
    运行时：定期检查，发现篡改立即告警
    """

    def __init__(self, watch_paths: list[str]):
        self.watch_paths  = [Path(p) for p in watch_paths]
        self._baseline: dict[str, str] = {}
        self._running   = False
        self._thread:   Optional[threading.Thread] = None

    @staticmethod
    def _hash_file(path: Path) -> str:
        h = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            return "UNREADABLE"

    def snapshot(self):
        self._baseline = {}
        for p in self.watch_paths:
            if p.exists():
                self._baseline[str(p)] = self._hash_file(p)
        BASELINE_FILE.write_text(json.dumps(self._baseline, indent=2, ensure_ascii=False))
        audit_log.info(f"INTEGRITY_SNAPSHOT: {len(self._baseline)} 文件已记录")

    def load_baseline(self):
        if BASELINE_FILE.exists():
            self._baseline = json.loads(BASELINE_FILE.read_text())

    def check_now(self) -> list[str]:
        tampered = []
        for path_str, expected_hash in self._baseline.items():
            p = Path(path_str)
            if not p.exists():
                msg = f"核心文件被删除: {path_str}"
                tampered.append(msg)
                audit_log.critical(f"INTEGRITY_VIOLATION — FILE_DELETED: {path_str}")
                error_log.critical(msg)
            else:
                current = self._hash_file(p)
                if current != expected_hash:
                    msg = f"核心文件被篡改: {path_str}"
                    tampered.append(msg)
                    audit_log.critical(
                        f"INTEGRITY_VIOLATION — HASH_MISMATCH: {path_str} "
                        f"expected={expected_hash[:8]}… got={current[:8]}…"
                    )
                    error_log.critical(msg)
        return tampered

    def start_monitoring(self, interval: float = 30.0):
        self._running = True
        def _loop():
            while self._running:
                violations = self.check_now()
                if violations:
                    print("\n" + "⛔" * 30)
                    print("  [完整性告警] 检测到以下核心文件异常:")
                    for v in violations:
                        print(f"  • {v}")
                    print("  建议立即停止运行并检查系统")
                    print("⛔" * 30 + "\n")
                time.sleep(interval)
        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()
        audit_log.info(f"INTEGRITY_MONITOR_STARTED: 每 {interval}s 检查一次")

    def stop(self):
        self._running = False


# ══════════════════════════════════════════════
# 6. Migrator — 一键打包 / 一键恢复
# ══════════════════════════════════════════════
class Migrator:
    INCLUDE_PATTERNS = [
        "CAPABILITY_REGISTRY.json",
        "baseline.sha256",
        "skills/**/*",
        "memory/**/*",
        "*.skill",
    ]

    def export(self, output_path: Optional[str] = None) -> str:
        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = Path(output_path) if output_path else \
              EXPORT_DIR / f"xiaolongxia_backup_{ts}.tar.gz"

        tracer = StepTracer("能力导出")

        def _collect():
            files_to_pack = []
            for pattern in self.INCLUDE_PATTERNS:
                for p in (BASE_DIR / "workspace").glob(pattern):
                    if p.is_file():
                        files_to_pack.append(p)
            return files_to_pack

        def _write_archive(files):
            with tarfile.open(out, "w:gz") as tar:
                for f in files:
                    arcname = f.relative_to(BASE_DIR / "workspace")
                    tar.add(f, arcname=str(arcname))
            return out

        def _write_manifest(files):
            manifest = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "version":    "1.0",
                "file_count": len(files),
                "files":      [str(f.relative_to(BASE_DIR / "workspace")) for f in files],
                "checksums": {
                    str(f.relative_to(BASE_DIR / "workspace")): IntegrityWatchdog._hash_file(f)
                    for f in files
                }
            }
            manifest_path = EXPORT_DIR / f"manifest_{ts}.json"
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
            return manifest_path

        files = _collect()
        steps = [
            ("收集能力文件",    lambda: files,            {}),
            ("写入压缩包",      _write_archive,            {"files": files}),
            ("生成校验清单",    _write_manifest,           {"files": files}),
        ]
        ok = tracer.run(steps)

        if ok:
            size_mb = out.stat().st_size / 1024 / 1024
            print(f"  📦 导出成功: {out}")
            print(f"  📋 文件数量: {len(files)}  大小: {size_mb:.2f} MB")
            audit_log.info(f"EXPORT_SUCCESS: {out} ({len(files)} files, {size_mb:.2f}MB)")
            return str(out)
        else:
            raise RuntimeError("导出失败，请查看上方错误详情")

    def restore(self, archive_path: str, target_dir: Optional[str] = None) -> bool:
        src  = Path(archive_path)
        dest = Path(target_dir) if target_dir else BASE_DIR / "workspace"

        if not src.exists():
            raise FileNotFoundError(f"备份文件不存在: {src}")

        tracer = StepTracer("能力恢复")

        def _verify_archive():
            if not tarfile.is_tarfile(src):
                raise ValueError("不是有效的 tar 压缩包")
            return True

        def _extract():
            dest.mkdir(parents=True, exist_ok=True)
            with tarfile.open(src, "r:gz") as tar:
                members = tar.getmembers()
                for m in members:
                    if m.name.startswith("/") or ".." in m.name:
                        raise ValueError(f"非法路径: {m.name}")
                tar.extractall(dest)
            return len(members)

        def _verify_restored():
            manifests = sorted(EXPORT_DIR.glob("manifest_*.json"))
            if not manifests:
                return "（无 manifest，跳过校验）"
            manifest = json.loads(manifests[-1].read_text())
            failed = []
            for rel, expected_hash in manifest.get("checksums", {}).items():
                restored = dest / rel
                if restored.exists():
                    actual = IntegrityWatchdog._hash_file(restored)
                    if actual != expected_hash:
                        failed.append(rel)
            if failed:
                raise ValueError(f"校验失败的文件: {failed}")
            return f"校验通过 ({len(manifest['checksums'])} 个文件)"

        steps = [
            ("验证压缩包完整性", _verify_archive,  {}),
            ("解压到目标目录",   _extract,         {}),
            ("校验恢复结果",     _verify_restored, {}),
        ]
        ok = tracer.run(steps)

        if ok:
            print(f"  ✅ 恢复成功，所有能力已还原到: {dest}")
            audit_log.info(f"RESTORE_SUCCESS: from={src} to={dest}")
        return ok


# ══════════════════════════════════════════════
# 7. Guardian — 统一入口
# ══════════════════════════════════════════════
class Guardian:
    """
    用法:
    g = Guardian()
    g.security.check_path_access("~/.ssh/id_rsa")
    g.capabilities.register("web_search", "1.1.0", 0.92)
    with g.trace("部署任务") as tracer:
        tracer.run(steps)
    g.caller.call(my_llm_func, model="gpt-4o-mini")
    g.migrator.export()
    """

    def __init__(self):
        self.security    = SecurityGuard()
        self.capabilities = CapabilityRegistry()
        self.caller      = SmartCaller()
        self.migrator    = Migrator()
        self.watchdog    = IntegrityWatchdog([
            str(BASE_DIR / "workspace" / "CAPABILITY_REGISTRY.json"),
            str(BASE_DIR / "workspace" / "baseline.sha256"),
            str(__file__),
        ])
        self.watchdog.load_baseline()
        violations = self.watchdog.check_now()
        if violations:
            for v in violations:
                print(f"  ⛔ 启动告警: {v}")
        self.watchdog.start_monitoring(interval=60.0)
        audit_log.info("GUARDIAN_STARTED")

    def trace(self, task_name: str) -> StepTracer:
        return StepTracer(task_name)

    def status(self):
        print("\n" + "═" * 60)
        print("  🦞 小龙虾 Guardian 系统状态")
        print("═" * 60)
        print(f"\n  📊 LLM 调用统计:\n  {self.caller.stats()}")
        print(f"\n  🧠 已注册能力 ({len(self.capabilities._data)} 个):")
        print(self.capabilities.summary())
        print("\n" + "═" * 60 + "\n")


# ─────────────────────────────────────────────
# 快速测试
# ─────────────────────────────────────────────
if __name__ == "__main__":
    g = Guardian()

    print("\n── 安全测试 ──")
    ok, reason = g.security.check_path_access("~/.ssh/id_rsa", "read")
    print(f"访问 ~/.ssh/id_rsa: {'✅' if ok else '⛔'} {reason}")

    ok, reason = g.security.check_intent("rm -rf ~/.qclaw/core")
    print(f"危险指令扫描: {'✅' if ok else '⛔'} {reason}")

    sanitized = g.security.sanitize_output(
        "Token: sk-abcdefghijklmnopqrstuvwxyz1234567890abcdef1234"
    )
    print("Output sanitized:", sanitized)

    print("\n-- Capability Test --")
    g.capabilities.register("code_generation", "1.0.0", 0.85, "code generation")
    g.capabilities.register("code_generation", "1.1.0", 0.91, "code generation upgraded")
    ok, msg = g.capabilities.register("code_generation", "0.9.0", 0.70, "attempt downgrade")
    print("Downgrade attempt:", msg)

    print("\n-- StepTracer Test --")
    tracer = g.trace("example task")
    def step_ok():   return "done"
    def step_fail(): raise ValueError("simulated error")
    tracer.run([
        ("read config",    step_ok,   {}),
        ("failing step",   step_fail, {}),
    ])

    g.status()
