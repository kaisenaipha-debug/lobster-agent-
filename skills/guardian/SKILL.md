# Guardian System — 安全护盾 + 能力进化框架

## 模块总览

| 模块 | 用途 |
|------|------|
| `SecurityGuard` | 路径ACL + 意图扫描 + 输出脱敏 |
| `CapabilityRegistry` | 能力版本管理（只进不退） |
| `StepTracer` | 多步骤任务追踪 + 错误精确定位 |
| `SmartCaller` | LLM调用防滥用（限速/退避/预算） |
| `IntegrityWatchdog` | 完整性看门狗（SHA-256基线监控） |
| `Migrator` | 一键打包/恢复全部能力 |

## 快速使用

```python
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from guardian import Guardian

g = Guardian()

# ── 安全检查 ──
ok, reason = g.security.check_path_access("~/.ssh/id_rsa", "read")
ok, reason = g.security.check_intent("rm -rf ~/.qclaw/core")

# ── 能力注册（只进不退）──
g.capabilities.register("web_search", "1.0.0", 0.90, "网页搜索")
g.capabilities.register("web_search", "1.1.0", 0.95, "网页搜索升级")
# 降版本/降分会自动拒绝并记录

# ── 步骤追踪 ──
tracer = g.trace("部署任务")
tracer.run([
    ("git pull",     lambda: "updated",  {}),
    ("安装依赖",     lambda: None,         {}),
    ("运行测试",     lambda: (_ for _ in ()).throw(ValueError("测试失败")), {}),
])
# 出错时精确告诉你：第几步、叫什么、什么错、怎么修

# ── 智能LLM调用 ──
def my_api_call():
    return "result"
g.caller.call(my_api_call, model="gpt-4o-mini", estimated_tokens=500)

# ── 导出/恢复 ──
g.migrator.export()           # 打包到 ~/.qclaw/exports/
g.migrator.restore("xxx.tar.gz")

# ── 系统状态 ──
g.status()
```

## 与现有系统集成

### 已有能力注册（来自 MEMORY.md）

现有能力以文本描述存在 MEMORY.md 中，接入 Guardian 时需手动注册：

| 现有能力 | 注册命令 |
|---------|---------|
| gov-sales-pipeline | `capabilities.register("gov-sales-pipeline", "1.0.0", 0.95, "政府B2G销售全流程编排器")` |
| smart-search | `capabilities.register("smart-search", "2.1.0", 0.93, "9通道并行搜索+S+级爬虫")` |
| gov-intel | `capabilities.register("gov-intel", "1.0.0", 0.90, "政府冷情报五步搜索")` |

### 路径说明

Guardian 文件存放于 `~/.qclaw/workspace/skills/guardian/`，数据存储：

- 能力注册表 → `~/.qclaw/workspace/CAPABILITY_REGISTRY.json`
- 完整性基线 → `~/.qclaw/workspace/baseline.sha256`
- 操作日志 → `~/.qclaw/logs/audit.log`, `errors.log`, `steps.log`
- 导出备份 → `~/.qclaw/exports/`

### 兼容性说明

✅ `CapabilityRegistry` 和现有 `skills/` 系统**互不冲突**
- 现有 skill 在 `~/.agents/skills/` 和 `~/.qclaw/workspace/skills/`
- Guardian 能力注册在 `CAPABILITY_REGISTRY.json`，独立管理
- IntegrityWatchdog 只监控核心文件，不监控 skill 目录

### 安全规则

Guardian 已内置以下防护（不可绕过）：

1. **路径ACL** — SSH/密钥/环境变量等敏感路径拒绝读写
2. **意图扫描** — 泄露/破坏/绕过类指令立即阻断
3. **输出脱敏** — API Key、Token、绝对路径自动遮盖
4. **能力只进** — 版本和评分不允许降低
5. **完整性基线** — 核心文件被篡改立即告警

## 完整性看门狗说明

IntegrityWatchdog 监控以下文件（启动时自动检查）：

- `CAPABILITY_REGISTRY.json`
- `baseline.sha256`
- `guardian.py`

启动时会比较 SHA-256 快照，发现变化立刻打印告警并在日志中记录。

如需重新建立基线：
```python
g.watchdog.snapshot()   # 立即更新基线快照
```
