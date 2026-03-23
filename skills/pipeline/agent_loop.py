"""
agent_loop.py — 自主执行闭环 v2.0

升级要点：
  1. 搜索改用 http_pool（真实搜索，非 Groq 幻觉）
  2. 政府客户任务 → 自动走 scenario_engine（S++七模型）
  3. 执行结果自动写入记忆
  4. 主循环可被 heartbeat/cron 调用

用法（模块内）：
  from agent_loop import run
  run("收集河源市教育局情报")  # → 自动分配到对应 pipeline 模块
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

WORKSPACE = Path.home() / ".qclaw" / "workspace"
STATE_FILE = WORKSPACE / "memory" / "agent_loop_state.json"

# ─── 路由表：任务类型 → 处理模块 ──────────────────────────

from http_pool import search, groq_fast
from google_session import google_search
from scenario_engine import process_plus, format_plus

# ─── BRAIN 大脑集成 ──────────────────────────────────────
_BRAIN = None
try:
    import sys as _sys
    _brain_path = Path.home() / ".qclaw" / "BRAIN.py"
    if _brain_path.exists():
        _sys.path.insert(0, str(Path.home() / ".qclaw"))
        from BRAIN import boot as _brain_boot, get_brain, get_search, register
        _brain = _brain_boot()
        _brain_loaded = True
    else:
        _brain_loaded = False
except Exception as _e:
    _brain_loaded = False
    _brain = None
# ─────────────────────────────────────────────────────────

GOVERNMENT_KEYWORDS = [
    "教育局","政府","局长","书记","单位","采购","招标",
    "领导","干部","厅","局","委","办"
]

SEARCH_KEYWORDS = ["搜索","收集","查一下","调研","情报","背景"]

CLIENT_KEYWORDS = ["客户","跟进","阶段","推进","签约","合同","方案"]

GOVERNMENT_STAGE_KEYWORDS = {
    "S1": ["调研","了解","情报","背景","了解一下"],
    "S2": ["见面","拜访","第一次","破冰","初次"],
    "S3": ["需求","诉求","他要什么"],
    "S4": ["方案","立项","预算","报价","走流程"],
    "S5": ["签约","签合同","付款","还没签","障碍"],
}


class Router:
    """智能路由：根据输入内容判断走哪个处理路径"""

    def __init__(self, user_input: str):
        self.input = user_input
        self.lower = user_input.lower()

    def is_government(self) -> bool:
        return any(kw in self.input for kw in GOVERNMENT_KEYWORDS)

    def is_search(self) -> bool:
        return any(kw in self.input for kw in SEARCH_KEYWORDS)

    def is_client_update(self) -> bool:
        return any(kw in self.input for kw in CLIENT_KEYWORDS)

    def guess_client_name(self) -> Optional[str]:
        """从输入中提取客户名称"""
        # 去掉前缀干扰词后再匹配
        clean = re.sub(r'^(收集|了解|查一下|调研|分析|跟进)', '', self.input)
        m = re.search(r'([\u4e00-\u9fa5]{2,6}(?:局|厅|委|办|公司|单位|学校|医院))', clean)
        return m.group(1) if m else None

    def guess_gov_stage(self) -> Optional[str]:
        for stage, kws in GOVERNMENT_STAGE_KEYWORDS.items():
            if any(kw in self.input for kw in kws):
                return stage
        return None

    def route(self) -> dict:
        """返回路由决策和上下文"""
        # 显式搜索命令优先
        if self.is_search() and any(kw in self.input for kw in ["搜索", "搜一下", "查一下", "收集"]):
            return {
                "path": "search",
                "query": self.input,
                "intent": self.input,
            }
        elif self.is_government():
            client_name = self.guess_client_name() or "default"
            stage = self.guess_gov_stage()
            return {
                "path": "government",
                "client": client_name,
                "stage": stage,
                "intent": self.input,
            }
        elif self.is_client_update():
            client_name = self.guess_client_name()
            return {
                "path": "client",
                "client": client_name,
                "intent": self.input,
            }
        else:
            return {
                "path": "general",
                "intent": self.input,
            }


# ─── 各路径处理器 ────────────────────────────────────────

def handle_government(ctx: dict) -> str:
    """政府客户路径：BRAIN 搜索 + S++ 分析 + 记忆写入"""
    client = ctx["client"]
    stage = ctx.get("stage")
    intent = ctx["intent"]

    # 阶段关键字注入
    if stage:
        stage_signals = {
            "S1": "调研情报收集",
            "S2": "初次见面破冰",
            "S3": "需求挖掘",
            "S4": "方案推进",
            "S5": "成交障碍排除",
        }
        full_input = f"{intent} [{stage_signals.get(stage, '')}]"
    else:
        full_input = intent

    # ── BRAIN 集成：情报搜索 ────────────────────────────
    search_results = []
    if _brain_loaded and _brain is not None:
        try:
            s = get_search()
            # 四个方向并行搜索
            q_dept = client.replace("市", "") + "教育局"
            all_results = s.search(q_dept, search_type="all")
            search_results = all_results[:12]  # 取前12条
        except Exception as e:
            pass  # 降级到 http_pool

    if not search_results:
        # 降级：原有 http_pool
        query = f"{client} 局长"
        raw = search(query, count=5)
        search_results = [{"title": r["title"], "source": r["source"]} for r in raw]

    # ── S++ 分析 ────────────────────────────────────────
    result = process_plus(full_input, client)
    result["_search"] = search_results

    # ── BRAIN 集成：写入客户记忆 ─────────────────────────
    if _brain_loaded and _brain is not None:
        try:
            from BRAIN import get_brain
            brain = get_brain()
            today = datetime.now().strftime("%Y-%m-%d")
            client_key = client
            # 更新客户档案
            if client_key not in brain.clients:
                brain.clients[client_key] = {
                    "file": str(WORKSPACE / "memory" / f"{today}-client-{client}.md"),
                    "stage": stage or "S0",
                    "updated": today,
                }
                # 写新档案
                mem_file = Path(brain.clients[client_key]["file"])
                mem_file.parent.mkdir(parents=True, exist_ok=True)
                header = f"# {client} · 阶段追踪 | {today}\n\n"
                header += f"## 当前阶段：S{stage or '0'} · government\n\n"
                header += "## 情报搜索结果\n"
                for r in search_results[:8]:
                    header += f"- [{r.get('source','')}] {r['title']}\n"
                header += "\n## 互动记录\n"
                mem_file.write_text(header)
        except Exception as e:
            pass

    return format_plus(result)


def handle_search(ctx: dict) -> str:
    """Search path: google_session priority -> http_pool fallback"""
    import asyncio
    query = ctx['query']

    # google_session (logged in, no captcha)
    results = []
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        raw = loop.run_until_complete(google_search(query, num=10))
        loop.close()
        if raw:
            results = [{'title': r['title'], 'url': r['url'], 'source': 'Google'} for r in raw]
    except Exception:
        pass

    # http_pool fallback
    if not results:
        try:
            raw = search(query, count=8)
            results = [{'title': r['title'], 'url': r.get('url',''), 'source': r.get('source','')} for r in raw]
        except Exception:
            pass

    if not results:
        fallback = groq_fast(f'About: {query}, summarize in 50 chars', max_tokens=100)
        return f'Search failed. Reference: {fallback}'

    lines = [f'Search query, found {len(results)} results:']
    for r in results:
        lines.append(f"[{r['source']}] {r['title']}")
        if r.get('url'):
            lines.append(f"   -> {r['url'][:80]}")
        lines.append('')
    return chr(10).join(lines)

def handle_client(ctx: dict) -> str:
    """客户更新路径：读取档案 + 分析"""
    client = ctx.get("client")
    if not client:
        return "❓ 未识别到客户名称，请明确说是哪个客户"

    client_file = WORKSPACE / "memory" / "clients" / f"{client}.json"
    if not client_file.exists():
        # 走新建流程
        return handle_government({**ctx, "path": "government"})

    import json
    data = json.loads(client_file.read_text())
    stage = data.get("stage", "未知")
    log = data.get("log", [])

    lines = [
        f"📋 客户：{client}",
        f"   当前阶段：{stage}",
        f"   互动记录：{len(log)} 条",
    ]
    if log:
        last = log[-1]
        lines.append(f"   最新动态：{last.get('time','')[:19]} — {last.get('stage','')}")

    # 触发七模型分析
    result = process_plus(ctx["intent"], client)
    lines.append("")
    lines.append("🧠 S++ 分析：")
    lines.append(format_plus(result))

    return "\n".join(lines)


def handle_general(ctx: dict) -> str:
    """通用路径：用 Groq 理解意图 + 引导到具体功能"""
    intent = ctx["intent"]
    hint = groq_fast(
        f"判断用户想要什么，用一句话回复：\n用户说：「{intent}」\n你应该建议他怎么做？（简短）",
        max_tokens=100
    )
    return f"🤔 我理解的是：{hint}\n\n如果你要：\n• 收集情报 → 说「收集XX情报」\n• 分析客户 → 说「XX局/XX公司」\n• 执行任务 → 说具体要做什么"


# ─── 主入口 ──────────────────────────────────────────────

def run(user_input: str, dry: bool = False) -> str:
    """
    唯一入口函数。
    输入自然语言 → BRAIN 路由判断 → 执行 → 返回结果
    """
    # BRAIN 状态提示（只在第一次调用时）
    if _brain_loaded and _brain is not None:
        brain_note = ""
    else:
        brain_note = " [BRAIN: 未加载]"

    router = Router(user_input)
    ctx = router.route()
    path = ctx.pop("path")

    if dry:
        return f"[Dry Run] 路由: {path} | 上下文: {ctx}{brain_note}"

    handlers = {
        "government": handle_government,
        "search":     handle_search,
        "client":     handle_client,
        "general":    handle_general,
    }

    handler = handlers.get(path, handle_general)

    try:
        result = handler(ctx)
        _log_run(user_input, path, ctx, result)
        return result
    except Exception as e:
        error_msg = f"❌ 执行出错：{e}"
        _log_run(user_input, path, ctx, error_msg)
        return error_msg


def _log_run(user_input: str, path: str, ctx: dict, result: str):
    """记录执行历史"""
    state_file = WORKSPACE / "memory" / "agent_loop_state.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        state = json.loads(state_file.read_text()) if state_file.exists() else {"runs": []}
    except Exception:
        state = {"runs": []}

    state["runs"].append({
        "time": datetime.now().isoformat(),
        "input": user_input,
        "path": path,
        "ctx": ctx,
        "result_preview": result[:100],
    })
    state["runs"] = state["runs"][-50:]  # 保留最近50条
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2))


# ─── CLI ─────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if not args:
        print("用法: python3 agent_loop.py \"任务描述\" [--dry]")
        sys.exit(1)

    dry = "--dry" in args
    task = [a for a in args if not a.startswith("--")][0]

    print(run(task, dry=dry))
