"""
agent_probe_hook.py — Agent 集成钩子
每次 Agent 完成任务后自动记录 + 自动检测采纳信号

在 agent_loop.py 或 main session 结束时调用：

  from agent_probe_hook import AgentProbe

  probe = AgentProbe()
  probe.on_task_start("分析新闻", organ="大脑")
  probe.on_task_complete(success=True)
  
  # 或者一次性记录
  probe.record("网页浏览", "眼睛", success=True, interrupted=False)

  # 检测用户回复中的采纳信号
  user_reply = "好，就这样做"
  if probe.is_accepted(user_reply):
      probe.on_reasoning_accepted("上次分析合理")
  elif probe.is_rejected(user_reply):
      probe.on_reasoning_rejected("方案不对")
"""

import re
from datetime import datetime
from typing import Optional, List, Dict, Any

# 采纳/否定信号
ACCEPT_PATTERNS = [
    r"^好", r"^对", r"^执行", r"^继续", r"^就这样", r"^可以", r"^行", r"^是",
    r"没错", r"有道理", r"说得对", r"按照你说的", r"开始吧",
    r"收到", r"明白", r"好嘞", r"好的", r"👍", r"✅"
]

REJECT_PATTERNS = [
    r"不对", r"重来", r"不是我", r"你理解错", r"^错", r"^不是",
    r"重新", r"换个", r"不行", r"不好", r"算了", r"不要",
    r"❌", r"👎", r"不对的"
]


class AgentProbe:
    """轻量级 Agent 探针，每次任务调用一次"""

    def __init__(self):
        self._task_start: Optional[datetime] = None
        self._task_type: str = ""
        self._organ: str = ""
        self._interrupted: bool = False

    # ─── 任务级记录 ─────────────────────────────────────

    def on_task_start(self, task_type: str, organ: str = "工具"):
        """任务开始"""
        from task_recorder import record_task
        self._task_start = datetime.now()
        self._task_type = task_type
        self._organ = organ
        self._interrupted = False

    def on_task_complete(
        self,
        success: bool,
        error: Optional[str] = None,
        interrupted: bool = False,
        result_preview: str = ""
    ):
        """任务完成，自动计算耗时并记录"""
        from task_recorder import record_task

        duration_ms = None
        if self._task_start:
            duration_ms = int((datetime.now() - self._task_start).total_seconds() * 1000)

        record_task(
            task_type=self._task_type or "unknown",
            organ=self._organ or "工具",
            success=success,
            error=error,
            interrupted=interrupted or self._interrupted,
            duration_ms=duration_ms
        )

        self._reset()

    def record(self, task_type: str, organ: str, success: bool, **kwargs):
        """一次性记录任务"""
        from task_recorder import record_task
        record_task(task_type=task_type, organ=organ, success=success, **kwargs)

    # ─── 推理采纳检测 ───────────────────────────────────

    def is_accepted(self, user_text: str) -> bool:
        """检测是否采纳"""
        if not user_text:
            return False
        text = user_text.strip()
        for p in ACCEPT_PATTERNS:
            if re.search(p, text):
                return True
        return False

    def is_rejected(self, user_text: str) -> bool:
        """检测是否否定"""
        if not user_text:
            return False
        text = user_text.strip()
        for p in REJECT_PATTERNS:
            if re.search(p, text):
                return True
        return False

    def on_reasoning_accepted(self, output_summary: str, reasoning_type: str = "general"):
        """记录推理被采纳"""
        from reasoning_probe import log_reasoning
        log_reasoning(
            input_summary=f"[采纳反馈] {self._task_type}",
            output_summary=output_summary,
            user_accepted=True,
            reasoning_type=reasoning_type
        )

    def on_reasoning_rejected(self, output_summary: str, reasoning_type: str = "general"):
        """记录推理被否定"""
        from reasoning_probe import log_reasoning
        log_reasoning(
            input_summary=f"[否定反馈] {self._task_type}",
            output_summary=output_summary,
            user_accepted=False,
            reasoning_type=reasoning_type
        )

    # ─── 能力缺口记录 ──────────────────────────────────

    def on_gap_found(
        self,
        missing_capability: str,
        resolution: str = "adapted",
        resolved: bool = True,
        priority: str = "medium"
    ):
        """记录发现的能力缺口"""
        from gap_recorder import record_gap
        record_gap(
            task=self._task_type,
            missing_capability=missing_capability,
            resolution=resolution,
            resolved=resolved,
            priority=priority
        )

    # ─── 私有 ──────────────────────────────────────────

    def _reset(self):
        self._task_start = None
        self._task_type = ""
        self._organ = ""
        self._interrupted = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._reset()


# ─── 快捷函数 ────────────────────────────────────────────

_agent_probe = AgentProbe()


def quick_record(task_type: str, organ: str, success: bool, **kwargs):
    """全局快捷记录"""
    _agent_probe.record(task_type, organ, success, **kwargs)


def quick_reasoning_check(user_text: str, output_summary: str = ""):
    """快捷推理采纳检测，返回是否处理了信号"""
    if _agent_probe.is_accepted(user_text):
        _agent_probe.on_reasoning_accepted(output_summary or "采纳")
        return True
    elif _agent_probe.is_rejected(user_text):
        _agent_probe.on_reasoning_rejected(output_summary or "否定")
        return True
    return False


# ─── 用于注入 SOUL.md 的自动采纳检测 ──────────────────────

AUTO_ACCEPT_PATTERNS = ACCEPT_PATTERNS
AUTO_REJECT_PATTERNS = REJECT_PATTERNS


def detect_and_log(user_text: str, input_summary: str, output_summary: str) -> Optional[bool]:
    """
    供外部调用的检测函数
    导入到 SOUL.md 执行层，自动检测用户回复
    返回 True(采纳)/False(否定)/None(无信号)
    """
    if not user_text:
        return None
    
    text = user_text.strip()
    
    # 先检查否定
    for p in REJECT_PATTERNS:
        if re.search(p, text):
            from reasoning_probe import log_reasoning
            log_reasoning(input_summary, output_summary, user_accepted=False)
            return False
    
    # 再检查采纳
    for p in ACCEPT_PATTERNS:
        if re.search(p, text):
            from reasoning_probe import log_reasoning
            log_reasoning(input_summary, output_summary, user_accepted=True)
            return True
    
    return None


if __name__ == "__main__":
    # 测试
    probe = AgentProbe()
    
    test_texts = [
        "好，就这样做",
        "不对，这不是我想要的",
        "继续执行",
        "等等，有点问题",
        "可以",
        "重新来一次",
        "就这样吧",
        "你说的有道理"
    ]
    
    print("信号检测测试：")
    for t in test_texts:
        accepted = probe.is_accepted(t)
        rejected = probe.is_rejected(t)
        result = "✅采纳" if accepted else "❌否定" if rejected else "⬜无信号"
        print(f"  「{t}」→ {result}")
