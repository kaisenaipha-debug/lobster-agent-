---
name: "smart-search"
description: "Government B2G 顶级情报搜索 S级 v2.0。8通道并行：搜狗微信(文章+账号)、搜狗网页、Serper API(Google+百度)、政府采购网CCGP、Boss直聘、猎聘、gov.cn官方政策。路由引擎自动选择最佳通道组合，触发 gov-intel 冷情报时执行7×并行搜索+合并去重+可信度排序。"
metadata:
  openclaw:
    emoji: "🔍"
    version: "2.0.0"
    author: "custom"
    serper_key_needed: true
---

# smart-search v2.0 S级情报搜索

## 核心能力（8通道）

| 通道 | 方法 | 适用场景 |
|------|------|---------|
| **搜狗微信文章** | urllib → weixin.sogou.com type=2 | 局长文章、政策解读、行业情报 |
| **搜狗微信公众号** | urllib → weixin.sogou.com type=1 | 找官方账号、长期监控 |
| **Serper API(百度)** | POST → google.serper.dev gl=cn | 国内搜索结果、政务索引 |
| **Serper API(Google)** | POST → google.serper.dev gl=us | 英文资料、国际案例 |
| **搜狗网页** | urllib → sogou.com | 政府新闻、通知公告 |
| **政府采购网** | urllib → search.ccgp.gov.cn | 招标记录、竞争态势 |
| **Boss直聘+猎聘** | urllib → zhipin/liepin | 招聘情报、战略信号 |
| **gov.cn** | urllib → 城市政府官网 | 政策文件、工作报告 |

## 路由规则

```
查询意图 → 自动选择通道（最多3个并行）

[采购/招标] → ccgp + serper_baidu
[政府报告/政策] → serper_baidu + weixin_article + gov_cn
[局长/领导发言] → weixin_article + weixin_account + gov_cn
[招聘信息] → bosszhipin + liepin
[英文/国际] → serper_google
[默认] → weixin_article + serper_baidu + sogou_web
```

## 冷情报七步搜索

触发：「冷情报：[城市] [部门]」

**自动并行7个搜索**：
1. Serper(百度)：「{城市} {部门} {年份} 工作报告 重点任务」
2. 搜狗微信文章：「{部门} 局长 {年份}」
3. 搜狗微信账号：「{城市} {部门}」（找官方公众号）
4. CCGP采购网：「{城市} {部门} 采购 中标」
5. Boss直聘：「{部门} 招聘 {城市}」
6. gov.cn：「{city}.gov.cn {部门} 工作」
7. Serper+搜狗：「{城市} {部门} 重点工作」

→ 合并去重 → 按可信度+时效性排序 → 输出报告

## API Key 配置

Serper API Key（Google 搜索，国内直连，2500次/月免费）：
→ 访问 https://serper.dev 注册
→ 获取 key 后设置环境变量：
```bash
export SERPER_API_KEY="your_key_here"
```

## 测试命令

```bash
# 搜狗微信文章搜索
~/.qclaw/venvs/crawl4ai/bin/python ~/.agents/skills/smart-search/scripts/search.py "深圳市教育局 2025" auto

# 公众号账号搜索
~/.qclaw/venvs/crawl4ai/bin/python ~/.agents/skills/smart-search/scripts/search.py "深圳市教育局" weixin_account

# 政府采购搜索
~/.qclaw/venvs/crawl4ai/bin/python ~/.agents/skills/smart-search/scripts/search.py "深圳市教育局" ccgp

# 全通道搜索
~/.qclaw/venvs/crawl4ai/bin/python ~/.agents/skills/smart-search/scripts/search.py "深圳市教育局 2025" all

# 冷情报七步
~/.qclaw/venvs/crawl4ai/bin/python ~/.agents/skills/smart-search/scripts/search.py "深圳 教育局" cold_intel
```

## 可信度评级

- ⭐⭐⭐⭐⭐ 政府官网、官方公众号、政府采购网
- ⭐⭐⭐⭐ 搜狗微信权威媒体文章
- ⭐⭐⭐ 搜狗网页新闻
- ⭐⭐ Boss/猎聘招聘信息
