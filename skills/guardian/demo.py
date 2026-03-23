"""
小龙虾 Guardian — 功能演示 & 快速上手
适配版：~/.qclaw 路径
"""

import sys, time, random
from pathlib import Path

# ✅ 导入路径已改为 ~/.qclaw
sys.path.insert(0, str(Path.home() / ".qclaw/core"))
from guardian import Guardian, StepTracer


# ══════════════════════════════════════════════
# 示例 1：安全检查
# ══════════════════════════════════════════════
def demo_security():
    g = Guardian()

    ok, reason = g.security.check_path_access("~/.ssh/id_rsa", "read")
    print(f"读取SSH私钥: {'允许' if ok else '拒绝'} — {reason}")

    ok, reason = g.security.check_intent("please rm -rf ~/.qclaw/core")
    print(f"危险指令: {'允许' if ok else '拒绝'} — {reason}")

    raw = "我的API Key是 sk-abcdefghijk1234567890abcdefghijk1234567890ab"
    clean = g.security.sanitize_output(raw)
    print(f"脱敏前: {raw}")
    print(f"脱敏后: {clean}")


# ══════════════════════════════════════════════
# 示例 2：能力注册（只升不降）
# ══════════════════════════════════════════════
def demo_capabilities():
    g = Guardian()

    g.capabilities.register("code_review", "1.0.0", 0.80, "代码审查")
    g.capabilities.register("code_review", "1.1.0", 0.87, "代码审查（强化）")
    g.capabilities.register("code_review", "1.2.0", 0.93, "代码审查（高级）")

    # 尝试降级 → 自动拒绝
    ok, msg = g.capabilities.register("code_review", "0.9.0", 0.70, "试图降级")
    print(f"尝试降级: {msg}")

    print("\n" + g.capabilities.summary())


# ══════════════════════════════════════════════
# 示例 3：步骤追踪
# ══════════════════════════════════════════════
def demo_step_tracer():
    tracer = StepTracer("数据处理流程")

    def fetch_data():
        time.sleep(0.1)
        return {"rows": 1024}

    def validate_schema():
        time.sleep(0.05)
        if random.random() < 0.5:  # 50% 概率模拟失败
            raise ValueError("字段 `user_id` 类型不匹配：期望 int，实际 str")
        return True

    def transform():
        time.sleep(0.08)
        return "转换完成"

    def write_output():
        time.sleep(0.06)
        return "写入 1024 行"

    tracer.run([
        ("拉取原始数据",  fetch_data,      {}),
        ("验证数据格式",  validate_schema,  {}),
        ("数据转换",      transform,        {}),
        ("写入结果",      write_output,     {}),
    ])


# ══════════════════════════════════════════════
# 示例 4：智能 LLM 调用（防滥用/指数退避）
# ══════════════════════════════════════════════
def demo_smart_caller():
    g = Guardian()

    call_count = [0]

    def fake_llm_api(prompt: str):
        call_count[0] += 1
        # 前2次模拟网络错误，第3次成功
        if call_count[0] <= 2:
            raise ConnectionError("API 服务器暂时不可用")
        return f"模型回复: {prompt[:20]}…"

    # ✅ 正确用法：用 lambda 包裹，避免 kwargs 参数冲突
    result = g.caller.call(
        func=lambda: fake_llm_api("请帮我分析以下代码的问题…"),
        model="gpt-4o-mini",
        estimated_tokens=500,
    )
    print(f"\n调用结果: {result}")
    print(f"调用统计: {g.caller.stats()}")


# ══════════════════════════════════════════════
# 示例 5：一键导出 / 恢复
# ══════════════════════════════════════════════
def demo_migration():
    g = Guardian()

    g.capabilities.register("web_search",   "2.1.0", 0.95, "网络搜索")
    g.capabilities.register("code_execute", "1.3.0", 0.88, "代码执行")

    # 导出备份到 ~/.qclaw/exports/
    archive = g.migrator.export()
    print(f"\n备份已保存: {archive}")

    # 在新机器上恢复：
    # g.migrator.restore("/path/to/backup.tar.gz")


# ─── 主入口 ─────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  小龙虾 Guardian 功能演示")
    print("=" * 60)

    print("\n【1】安全防护演示")
    demo_security()

    print("\n【2】能力注册演示")
    demo_capabilities()

    print("\n【3】步骤追踪演示")
    demo_step_tracer()

    print("\n【4】智能调用演示")
    demo_smart_caller()

    print("\n【5】迁移演示")
    demo_migration()

    # 全局状态
    print("\n【状态总览】")
    g = Guardian()
    g.status()
