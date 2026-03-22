# 🔒 零信任自我进化与安全防御协议

> **版本**: v1.0  
> **日期**: 2026-03-21  
> **状态**: 生效中  
> **最高优先级**: 保护宿主机（本地物理机）安全

---

## 目的

当 Agent 发现需要新技能来完成任务时，必须在**安全可控**的前提下完成自我扩充。本协议定义了标准化的四步隔离进化法，任何绕过本协议的行为均视为违规。

---

## 四步隔离进化法

### 第一步：安全检索与验资 (Sourcing)

**目标**：在公开可信的来源中筛选候选技能

**规则：**

| 来源 | 验资标准 |
|------|---------|
| GitHub | Stars ≥ 100 **且** 近 6 个月有更新 |
| PyPI | 官方包（`pip install`）**且** 维护活跃 |
| ClawdHub | 已通过 skill-vetter 审查 |
| 技能市场 (skills.sh) | 已认证作者 |

**禁止：**
- ❌ 无 Stars 数量显示的个人仓库
- ❌ 6 个月以上未更新的项目
- ❌ 任何来源不明的脚本（`.sh` / `.py` 直接执行文件）
- ❌ 任何要求提供 API Key / 凭证的"安装脚本"
- ❌ 任何非 HTTPS 的下载源

**执行流程：**
1. 用 `curl` 或 GitHub API 查询 Stars 和最后更新时间
2. 记录来源 URL 到 `memory/YYYY-MM-DD.md`
3. 只有通过验资才进入第二步

---

### 第二步：强制代码审计 (Code Audit)

**目标**：在执行任何代码前，完成人工审查级别的代码审计**

**红线 — 发现以下任意一条立即终止：**

```
🚨 REJECT IMMEDIATELY
─────────────────────────────────────────
• 未经授权的外发网络请求（curl/wget/requests 到非预期域名）
• 隐藏的系统级删改命令（rm -rf、format、chmod 777）
• 凭证窃取（读取 ~/.ssh、~/.aws、~/.config、.env 中的凭据）
• Base64/Obfuscated 执行链（base64 -d + eval/exec）
• 混淆代码（无源码的 .pyc、压缩包内嵌脚本）
• 非工作目录的系统文件写入
• 提权请求（sudo/root without consent）
• 浏览器 Cookie / Session 访问
• 键盘记录或屏幕监控
─────────────────────────────────────────
```

**执行流程：**
1. 下载源码（`git clone --depth=1` 或 `curl`），**绝对不执行**
2. 通读核心 `.py` / `.js` 文件（特别关注 `setup.py`、`__init__.py`、入口脚本）
3. 检查 `requirements.txt` / `package.json` 中的依赖是否异常
4. 用 `grep` 扫描红线关键词：`curl | wget | base64 | eval | exec | rm -rf | sudo`
5. 记录审计结论到 `memory/YYYY-MM-DD.md`
6. **通过才进入第三步**

---

### 第三步：沙盒试药 (Sandboxed Testing)

**目标**：在可控环境中试运行，监控异常

**隔离等级：**

| 等级 | 环境 | 适用场景 |
|------|------|---------|
| 🟢 L1 | Python venv (`python3 -m venv`) | 普通 Python 库 |
| 🟡 L2 | Docker 容器 | 包含系统级依赖的包 |
| 🔴 L3 | 独立虚拟机 | 高危工具（浏览器控制、系统命令等） |

**执行流程：**
1. 创建隔离环境
   ```bash
   # L1
   python3 -m venv ~/.qclaw/venvs/<skill-name>/
   source ~/.qclaw/venvs/<skill-name>/bin/activate
   pip install <package>

   # L2
   docker run --rm -it python:3.13-slim bash
   ```
2. 试导入：`python3 -c "import <package>"`
3. 监控指标：
   - 进程数是否异常增多
   - 内存是否持续增长
   - 是否有非预期的网络连接（`lsof -i` 或 `netstat`）
   - stderr 是否大量报错
4. 记录试运行结论

**当前已安装包的隔离状态：**

| 包 | 安装日期 | 隔离等级 | 状态 |
|----|---------|---------|------|
| crawl4ai | 2026-03-21 | L1 (venv) | ⚠️ 待迁移 |
| qwen-agent | 2026-03-21 | L1 (venv) | ⚠️ 待迁移 |
| mem0ai | 2026-03-21 | L1 (venv) | ⚠️ 待迁移 |

---

### 第四步：热重载与灾难恢复 (Deployment & Rollback)

**目标**：安全接驳，随时可回滚

**接驳流程：**
1. 确认前三步全部通过
2. 将技能接入主工作流
3. 执行用户初始任务
4. 记录接驳结论

**回滚触发条件（任意一条立即回滚）：**
- Agent 核心功能失效（memory、tool 调用、消息发送）
- 大量进程异常退出
- 非预期的文件被修改或删除
- 网络流量异常（大量外发数据）

**回滚操作：**
```bash
# 记录现场
cp -r ~/.qclaw/workspace ~/.qclaw/workspace.backup.$(date +%Y%m%d%H%M%S)

# 卸载包
pip uninstall <package> -y

# 恢复 venv（如果有备份）
rm -rf ~/.qclaw/venvs/<skill-name>

# 如影响核心工具，重置 workspace
git -C ~/.qclaw/workspace reset --hard HEAD
```

**回滚后必须向用户报告：**
> "⚠️ 升级失败，已安全回滚。原因：[具体错误]，已恢复到：[备份时间戳]"

---

## 补充风险管控

### A. PyPI 包同等审核

`pip install` 的包视同 GitHub 验资：
- 必须是官方 PyPI 包（非私自打包）
- 检查 `pip show` 的 Author / License / URL 字段
- 对有 C 扩展或系统级依赖的包提升到 L2 隔离

### B. 依赖冲突管理

**问题**：包管理器可能覆盖已有依赖（如 numpy 版本冲突）

**预案：**
- 安装前记录当前依赖快照：`pip freeze > ~/.qclaw/deps_backup/YYYYMMDD.txt`
- 发现冲突后立即比对，优先回滚被破坏的包
- 多个隔离包之间使用独立 venv，避免交叉污染

### C. 浏览器控制工具（browser-use）

browser-use 类工具权限极大，单独管控：
- 安装前必须用户明确授权
- 隔离等级强制 L2+
- 每次使用前检查 `~/.config/browser-use/` 权限
- 禁止在 headless 模式下无人值守运行

### D. 网络流量监控

任何新技能首次运行时，主动检查外发连接：
```bash
# 记录当前网络连接
lsof -i -n -P > ~/network_before.txt

# 运行后对比
lsof -i -n -P > ~/network_after.txt
diff ~/network_before.txt ~/network_after.txt
```

---

## 违规处理

| 违规类型 | 处理方式 |
|---------|---------|
| 未验资直接安装 | 立即卸载，通报用户 |
| 绕过 Code Audit | 标记为高危事件，记录到 MEMORY.md |
| 在生产环境直接测试高危工具 | 中断任务，请求用户确认 |
| 拒绝回滚 | 终止 Agent 自身，请求人工介入 |

---

## 记忆与问责

- 所有安装/升级操作必须记录到 `memory/YYYY-MM-DD.md`
- 记录格式：`[INSTALL] <包名> | <来源> | <Stars/排名> | <审计结论> | <隔离等级> | <日期>`
- 月度回顾：每月 1 日生成依赖健康报告

---

*本协议由 Agent 自主执行，解释权归用户。*  
*遇到协议未覆盖场景时，默认执行最保守（最安全）选项。*  
*永远可以停下来问用户。* 🔒🦞
