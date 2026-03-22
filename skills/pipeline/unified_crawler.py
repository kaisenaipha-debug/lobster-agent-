#!/usr/bin/env python3
"""
unified_crawler.py — 统一爬虫引擎 v1.0
═══════════════════════════════════════════════════════
三层能力融合：

  Layer 1 · HTTP池（httpx）
    → 高速并发，无JS的静态页面
    → 适用：搜狗微信/网页、CCGP、gov.cn、Boss直聘

  Layer 2 · 浏览器（Playwright Real Chrome）
    → JS渲染、点击交互、验证码处理、截图
    → 适用：需要JS加载的政务平台、需要登录的内容

  Layer 3 · 爬虫管道（crawl4ai + LLM分析）
    → 任意URL深度提取 + 结构化情报
    → 适用：文章正文提取、内容分类、情报分析

级联策略：
  HTTP → (失败/需JS) → Browser → (内容分析) → LLM

═══════════════════════════════════════════════════════
"""
import os
import sys
import re
import json
import time
import ssl
import asyncio
import urllib.request
import urllib.parse
import urllib.error
import argparse
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── Layer 1: HTTP ────────────────────────────────────────
class HTTPFetcher:
    """高速HTTP池，支持重试+UA轮换+连接复用"""

    UA_POOL = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/121.0 Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/15.0 Safari/605.1.15",
    ]

    def __init__(self):
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

    def fetch(self, url: str, timeout: int = 12, mobile: bool = False, retries: int = 2) -> str:
        ua = self.UA_POOL[1] if mobile else self.UA_POOL[0]
        last_err = "unknown"
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": ua})
                with urllib.request.urlopen(req, timeout=timeout, context=self.ctx) as r:
                    return r.read().decode("utf-8", errors="ignore")
            except Exception as exc:
                last_err = str(exc)
                if attempt < retries - 1:
                    time.sleep(1)
        return f"ERROR:{last_err}"

    def fetch_all(self, urls: List[str], timeout: int = 10) -> Dict[str, str]:
        """并发抓取多个URL"""
        results = {}
        with ThreadPoolExecutor(max_workers=5) as ex:
            futs = {ex.submit(self.fetch, u, timeout): u for u in urls}
            for fut in as_completed(futs):
                url = futs[fut]
                results[url] = fut.result()
        return results


# ─── Layer 2: Browser ─────────────────────────────────────
class BrowserFetcher:
    """Playwright 真浏览器，支持截图/点击/JS等待"""

    def __init__(self):
        self.chrome_path = "/Users/tz/Library/Caches/ms-playwright/chromium-1200/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"

    def _get_browser(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return None, None
        try:
            p = sync_playwright().start()
            browser = p.chromium.launch(
                executable_path=self.chrome_path,
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            return p, browser
        except Exception:
            return None, None

    def screenshot(self, url: str, out_path: str = "/tmp/crawl_screenshot.png") -> dict:
        p, browser = self._get_browser()
        if not browser:
            return {"error": "Playwright not available"}
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            page.goto(url, timeout=20000, wait_until="networkidle")
            time.sleep(1.5)
            page.screenshot(path=out_path, full_page=True)
            return {"success": True, "saved": out_path, "title": page.title(), "url": page.url}
        except Exception as e:
            return {"error": str(e)}
        finally:
            try:
                browser.close()
            except Exception: pass
            try:
                p.stop()
            except Exception: pass

    def extract(self, url: str, selector: str = "article", wait: float = 2) -> dict:
        p, browser = self._get_browser()
        if not browser:
            return {"error": "Playwright not available"}
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            page.goto(url, timeout=20000, wait_until="domcontentloaded")
            time.sleep(wait)
            # 先试 selector，失败则取 body 全文
            try:
                if selector:
                    page.wait_for_selector(selector, timeout=5000)
                    content = page.inner_text(selector)
                else:
                    content = page.inner_text("body")
            except Exception:
                # selector 超时，取全页文字
                content = page.inner_text("body")
            return {"success": True, "content": content[:5000], "title": page.title(), "url": page.url}
        except Exception as e:
            return {"error": str(e)}
        finally:
            try: browser.close()
            except Exception: pass
            try: p.stop()
            except Exception: pass

    def interact(self, url: str, actions: str, wait: float = 2) -> dict:
        """
        actions: "click:#btn|wait:2s|fill:#input|hello|press:Enter"
        """
        p, browser = self._get_browser()
        if not browser:
            return {"error": "Playwright not available"}
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            page.goto(url, timeout=20000, wait_until="domcontentloaded")
            time.sleep(wait)
            for action in actions.split("|"):
                if action.startswith("click:"):
                    sel = action.split(":", 1)[1]
                    page.click(sel, timeout=5000)
                elif action.startswith("fill:"):
                    _, sel, val = action.split(":", 2)
                    page.fill(sel, val)
                elif action.startswith("wait:"):
                    t = float(action.split(":")[1].rstrip("s"))
                    time.sleep(t)
                elif action.startswith("press:"):
                    page.keyboard.press(action.split(":")[1])
                time.sleep(1)
            return {"success": True, "title": page.title(), "url": page.url, "content": page.inner_text("body")[:3000]}
        except Exception as e:
            return {"error": str(e)}
        finally:
            try: browser.close()
            except Exception: pass
            try: p.stop()
            except Exception: pass


# ─── Layer 3: Crawl4AI + LLM ──────────────────────────────
class CrawlPipeline:
    """crawl4ai 深度爬取 + LLM 结构化分析"""

    def __init__(self):
        self.groq_key = os.environ.get("GROQ_KEY", "")
        self.groq_url = "https://api.groq.com/openai/v1/chat/completions"

    def _groq(self, prompt: str, max_tokens: int = 300) -> str:
        if not self.groq_key:
            return ""
        try:
            import httpx
            r = httpx.post(self.groq_url, json={
                "model": "llama-3.1-8b-instant",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens
            }, headers={"Authorization": f"Bearer {self.groq_key}"}, timeout=15)
            data = r.json()
            return data["choices"][0]["message"]["content"]
        except Exception:
            return ""

    def extract_content(self, html: str) -> dict:
        """本地正文提取 + 关键词抽取"""
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        # 关键词
        words = re.findall(r'[\u4e00-\u9fff]{2,}', text)
        freq = {}
        for w in words:
            if len(w) > 1:
                freq[w] = freq.get(w, 0) + 1
        keywords = sorted(freq.items(), key=lambda x: -x[1])[:15]

        return {"text": text[:3000], "keywords": keywords}

    def analyze(self, url: str, task: str = "情报分析", local: bool = False) -> dict:
        """
        抓取URL → 提取正文 → LLM分析 → 结构化输出
        """
        try:
            from crawl4ai import AsyncWebCrawler
            async def _crawl():
                async with AsyncWebCrawler() as crawler:
                    result = await crawler.arun(url=url)
                    return result.html if hasattr(result, 'html') else str(result)
            html = asyncio.run(_crawl())
        except Exception:
            # fallback: HTTP
            http = HTTPFetcher()
            html = http.fetch(url)

        extracted = self.extract_content(html)

        if local or not self.groq_key:
            return {"url": url, **extracted, "llm_analysis": ""}

        prompt = f"""分析以下网页内容，{task}。

标题相关度：判断是否与{url}匹配
关键词：{','.join([k for k,v in extracted['keywords']])}
正文摘要：{extracted['text'][:1000]}

输出JSON格式：{{"summary":"摘要","entities":["关键实体"],"sentiment":"情感","relevant":true/false}}
"""
        llm = self._groq(prompt, max_tokens=250)
        return {"url": url, **extracted, "llm_analysis": llm}


# ─── 统一爬虫 API ─────────────────────────────────────────
class UnifiedCrawler:
    """
    统一爬虫入口，按需自动选择最优层
    """

    def __init__(self):
        self.http = HTTPFetcher()
        self.browser = BrowserFetcher()
        self.pipeline = CrawlPipeline()

    def fetch(self, url: str, mode: str = "auto", **kwargs) -> dict:
        """
        mode:
          http      → 纯HTTP，最快
          browser   → Playwright真浏览器
          crawl     → HTTP + LLM分析
          screenshot→ 截图保存
          auto      → 智能选择
        """
        if mode == "http" or mode == "auto" and not self._needs_browser(url):
            t0 = time.time()
            html = self.http.fetch(url, timeout=kwargs.get("timeout", 12))
            elapsed = round((time.time() - t0) * 1000)
            if html.startswith("ERROR"):
                # 降级到浏览器
                return self.fetch(url, mode="browser", **kwargs)
            extracted = self.pipeline.extract_content(html)
            return {
                "mode": "http",
                "url": url,
                "elapsed_ms": elapsed,
                **extracted
            }

        if mode == "browser" or mode == "auto":
            result = self.browser.extract(url, selector=kwargs.get("selector", "article"))
            return {"mode": "browser", "url": url, **result}

        if mode == "screenshot":
            out = kwargs.get("out", f"/tmp/screenshot_{hash(url)}.png")
            return self.browser.screenshot(url, out_path=out)

        if mode == "crawl":
            return self.pipeline.analyze(url, task=kwargs.get("task", "情报分析"), local=kwargs.get("local", False))

        return {"error": f"Unknown mode: {mode}"}

    def _needs_browser(self, url: str) -> bool:
        """判断是否需要浏览器（JS渲染/交互/登录）"""
        js_domains = ["gov.cn", "zhipin.com", "liepin.com", "ccgp.gov.cn", "weixin.qq.com"]
        return any(d in url for d in js_domains)

    def fetch_all(self, urls: List[str], mode: str = "http") -> Dict[str, dict]:
        results = {}
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = {ex.submit(self.fetch, u, mode): u for u in urls}
            for fut in as_completed(futs):
                url = futs[fut]
                try:
                    results[url] = fut.result()
                except Exception as e:
                    results[url] = {"error": str(e)}
        return results


# ─── CLI ──────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="统一爬虫引擎")
    parser.add_argument("url", help="目标URL")
    parser.add_argument("--mode", default="auto", choices=["http", "browser", "crawl", "screenshot", "auto"])
    parser.add_argument("--out", default="/tmp/screenshot.png", help="截图保存路径")
    parser.add_argument("--selector", default="article", help="CSS选择器（browser模式）")
    parser.add_argument("--actions", help="交互动作（browser模式）")
    parser.add_argument("--task", default="情报分析", help="LLM分析任务（crawl模式）")
    parser.add_argument("--local", action="store_true", help="纯本地分析无LLM")
    args = parser.parse_args()

    crawler = UnifiedCrawler()

    if args.mode == "screenshot":
        result = crawler.fetch(args.url, mode="screenshot", out=args.out)
    elif args.mode == "browser":
        if args.actions:
            result = crawler.browser.interact(args.url, args.actions)
        else:
            result = crawler.fetch(args.url, mode="browser", selector=args.selector)
    elif args.mode == "crawl":
        result = crawler.fetch(args.url, mode="crawl", task=args.task, local=args.local)
    else:
        result = crawler.fetch(args.url, mode=args.mode)

    print(json.dumps(result, ensure_ascii=False, indent=2))
