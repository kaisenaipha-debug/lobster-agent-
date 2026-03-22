"""
crawl_pipeline.py — 爬取 → 结构化提取 → Groq 分析

优先级:
  1. Groq (免费) — llama-3.1-8b-instant
  2. Gemini  (需配置)
  3. 本地规则分析（无需 API）

用法:
  ~/.qclaw/venvs/crawl4ai/bin/python crawl_pipeline.py <url> [--task "分析任务"]
  ~/.qclaw/venvs/crawl4ai/bin/python crawl_pipeline.py <url> --local   # 纯本地分析
"""

import asyncio
import re
import json
import os
import sys
import argparse
from html import escape
from pathlib import Path
from datetime import datetime
from typing import Optional

from _secrets import GROQ_KEY
GROQ_URL = 'https://api.groq.com/openai/v1/chat/completions'

# ─── 内容提取器（纯本地） ─────────────────────────────────

STOPWORDS_ZH = {'的','了','是','在','和','与','为','对','有','我','你','他','这','那',
                '上','下','中','个','一','不','也','就','都','要','会','能','可','但','或','而','以','及','被'}
STOPWORDS_EN = {'the','and','is','in','of','a','for','on','with','it','by','as','at',
                'an','be','or','from','that','this','you','are','was','were','has','have','had'}

def extract(content: str) -> dict:
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    pure_lines = [l for l in lines if len(l) > 10]
    md_text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', content)
    md_text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', md_text)
    md_text = re.sub(r'[*_`#>-]+', '', md_text)

    words = re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{4,}', md_text.lower())
    freq = {}
    for w in words:
        if w not in STOPWORDS_ZH and w not in STOPWORDS_EN and len(w) > 1:
            freq[w] = freq.get(w, 0) + 1
    keywords = sorted(freq.items(), key=lambda x: -x[1])[:20]

    links = list(dict.fromkeys(re.findall(r'https?://[^\s\)"\'<>]{10,}', content)))[:20]

    title_match = re.search(r'<title[^>]*>([^<]+)</title>', content, re.I)
    title = title_match.group(1).strip() if title_match else None
    if not title:
        for l in pure_lines[:10]:
            if 3 < len(l) < 80:
                title = l; break

    desc_match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', content, re.I)
    description = desc_match.group(1).strip() if desc_match else None

    zh_chars = len(re.findall(r'[\u4e00-\u9fff]', content))
    en_words = len(re.findall(r'[a-zA-Z]{4,}', content))
    lang = "zh" if zh_chars > en_words * 0.3 else "en"

    paragraphs = [l for l in pure_lines if 20 < len(l) < 500][:15]

    return {
        "title": title,
        "description": description,
        "language": lang,
        "keywords": [{"word": w, "count": c} for w, c in keywords],
        "links": links,
        "paragraphs": paragraphs,
        "stats": {
            "total_chars": len(content),
            "total_lines": len(pure_lines),
            "link_count": len(links),
            "crawl_time": datetime.now().isoformat(),
        }
    }

# ─── Groq 分析（免费） ──────────────────────────────────────

def groq_analyze(content: str, task: str) -> str:
    """用 Groq 免费模型分析"""
    import httpx
    max_chars = 10000
    if len(content) > max_chars:
        content = content[:max_chars] + "\n\n[内容已截断...]"

    r = httpx.post(GROQ_URL, json={
        'model': 'llama-3.1-8b-instant',
        'messages': [
            {'role': 'system', 'content': '你是一个专业、高效的内容分析助手。用中文输出简洁有力的分析报告。格式：\n1. 一句话总结\n2. 核心要点（3条）\n3. 关键数据或事实\n4. 简要评价'},
            {'role': 'user', 'content': f'任务：{task}\n\n内容：\n{content}'}
        ],
        'max_tokens': 400
    }, headers={
        'Authorization': f'Bearer {GROQ_KEY}',
        'Content-Type': 'application/json'
    }, timeout=20)

    data = r.json()
    if 'error' in data:
        return f"Groq 分析失败: {data['error']['message']}"
    return data['choices'][0]['message']['content']

# ─── 本地分析兜底 ──────────────────────────────────────────

def local_analyze(content: str, task: str, data: dict) -> str:
    kw_table = '\n'.join(f"| `{k['word']}` | {k['count']} |" for k in data['keywords'][:12])
    links = '\n'.join(f"- {l}" for l in data['links'][:8])
    paras = '\n'.join(f"{i}. {escape(p[:150])}" for i, p in enumerate(data['paragraphs'][:5], 1))

    return f"""## 🔍 本地分析结果

**任务**: {task}

### 📊 关键词
| 关键词 | 频次 |
|--------|------|
{kw_table}

### 🔗 链接
{links or '无'}

### 📄 内容预览
{paras}

**统计**: {data['stats']['total_chars']:,} 字符 | {data['stats']['total_lines']} 行 | {data['stats']['link_count']} 个链接"""

# ─── 主流程 ────────────────────────────────────────────────

async def crawl(url: str, task: str, use_groq: bool = True, use_local: bool = False):
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

    print(f"🕷️  正在爬取: {url}", file=sys.stderr)
    browser_cfg = BrowserConfig(headless=True)
    run_cfg = CrawlerRunConfig(word_count_threshold=5, only_text=True)

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        result = await crawler.arun(url=url, config=run_cfg)

    if not result.success:
        return {"error": result.error_message}

    content = result.markdown or result.cleaned_html or ""
    print(f"✅ 爬取完成 ({len(content):,} 字符)", file=sys.stderr)

    data = extract(content)
    data["url"] = url
    data["task"] = task
    return data

def main():
    parser = argparse.ArgumentParser(description="爬取 → 分析 Pipeline")
    parser.add_argument("url", help="目标 URL")
    parser.add_argument("--task", default="总结这个网页的核心内容和关键信息", help="分析任务")
    parser.add_argument("--local", action="store_true", help="纯本地分析（无 API）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--out", help="保存到文件")
    args = parser.parse_args()

    data = asyncio.run(crawl(args.url, args.task))

    if "error" in data:
        print(json.dumps({"error": data["error"]}, ensure_ascii=False, indent=2))
        sys.exit(1)

    # 分析
    if args.local:
        analysis = local_analyze(data.get('paragraphs', [])[:10] and '\n'.join(data['paragraphs'][:10]) or "", args.task, data)
        mode = "🔍 本地规则"
    else:
        print("🤖 正在用 Groq 分析...", file=sys.stderr)
        raw_content = '\n\n'.join(data.get('paragraphs', []))
        if not raw_content:
            raw_content = data.get('title', '') + ' ' + data.get('description', '')
        if not raw_content:
            raw_content = data.get('keywords', [{}])[:3] and ' '.join(k.get('word','') for k in data['keywords'][:3])
        analysis = groq_analyze(raw_content, args.task)
        mode = "🤖 Groq AI"

    # 输出
    output = f"""# 🌐 爬取分析报告
- **URL**: {data['url']}
- **任务**: {args.task}
- **时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
- **模式**: {mode}
- **提取**: {data['stats']['total_chars']:,} 字符 | {data['stats']['link_count']} 链接

---

## 📋 基础信息
- **标题**: {data.get('title', 'N/A')}
- **语言**: {data.get('language', 'N/A')}
- **描述**: {data.get('description', 'N/A')}

---

{analysis}
"""
    print(output)

    if args.out:
        Path(args.out).write_text(output, encoding='utf-8')
        print(f"\n📄 已保存到: {args.out}", file=sys.stderr)

if __name__ == "__main__":
    main()
