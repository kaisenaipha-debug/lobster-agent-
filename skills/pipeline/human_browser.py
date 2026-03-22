#!/usr/bin/env python3
"""
human_browser.py — 像人一样操作浏览器
零 API key，纯 playwright 异步操作
"""

import asyncio
import random
import re
import time
from pathlib import Path
from typing import Optional, List, Dict

from playwright.async_api import async_playwright
from playwright.async_api import Page

CHROME_PATH = "/Users/tz/Library/Caches/ms-playwright/chromium-1200/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


class HumanBrowser:
    """像人一样操作浏览器 — 异步版本"""

    def __init__(self, headless: bool = True):
        self.browser = None
        self.context = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.headless = headless
        self.screenshot_dir = Path.home() / ".qclaw" / "screenshots"
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self._trace_enabled = False

    async def start(self) -> "HumanBrowser":
        """启动浏览器"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            executable_path=CHROME_PATH,
            headless=self.headless,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
            ]
        )
        self.context = await self.browser.new_context(
            user_agent=UA,
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        # 随机化一些特性，伪装更像人
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        self.page = await self.context.new_page()
        return self

    async def go(self, url: str, wait: str = "networkidle", timeout: int = 30000) -> "HumanBrowser":
        """打开网页，随机停顿"""
        await self.page.goto(url, wait_until=wait, timeout=timeout)
        await asyncio.sleep(random.uniform(1.0, 2.5))  # 人的停顿
        return self

    async def screenshot(self, name: str = None) -> str:
        """截图保存到本地"""
        ts = int(time.time())
        filename = name or f"screenshot_{ts}.png"
        path = self.screenshot_dir / filename
        await self.page.screenshot(path=str(path), full_page=True)
        return str(path)

    async def get_text(self, selector: str = "body") -> str:
        """提取页面文字内容"""
        try:
            el = await self.page.query_selector(selector)
            return await el.inner_text() if el else ""
        except Exception:
            return ""

    async def get_html(self) -> str:
        """获取页面 HTML"""
        return await self.page.content()

    # ── 搜索类动作 ───────────────────────────────────────

    async def search_baidu(self, query: str, n: int = 10) -> List[Dict]:
        """百度搜索"""
        encoded = query.replace(" ", "+")
        await self.go(f"https://www.baidu.com/s?wd={encoded}&rn=20")
        await self.screenshot(f"baidu_{query[:8]}_{int(time.time())}.png")

        results = []
        try:
            items = await self.page.query_selector_all(".result, .c-container")
            for item in items[:n]:
                try:
                    h3 = await item.query_selector("h3")
                    a = await h3.query_selector("a") if h3 else None
                    if a:
                        title = await h3.inner_text()
                        url = await a.get_attribute("href")
                        snippet_el = await item.query_selector(".c-abstract, .content-right_8Zs40")
                        snippet = await snippet_el.inner_text() if snippet_el else ""
                        if title and url:
                            results.append({
                                "title": title.strip(),
                                "url": url,
                                "snippet": snippet.strip()[:150],
                                "source": "百度"
                            })
                except Exception:
                    continue
        except Exception:
            pass

        # 如果 CSS 选择器失败，降级到文本提取
        if not results:
            text = await self.get_text()
            titles = re.findall(r'<h3[^>]*>(.*?)</h3>', await self.get_html(), re.DOTALL)
            for t in titles[:n]:
                clean = re.sub("<[^>]+>", "", t).strip()
                if clean and len(clean) > 5:
                    results.append({
                        "title": clean,
                        "url": "",
                        "snippet": "",
                        "source": "百度"
                    })

        return results

    async def search_sogou_web(self, query: str, n: int = 10) -> List[Dict]:
        """搜狗网页搜索"""
        encoded = query.replace(" ", "+")
        await self.go(f"https://www.sogou.com/web?query={encoded}&ie=utf8")
        await self.screenshot(f"sogou_web_{query[:8]}_{int(time.time())}.png")

        results = []
        try:
            items = await self.page.query_selector_all("h3")
            for h3 in items[:n]:
                try:
                    a = await h3.query_selector("a")
                    if a:
                        title = await h3.inner_text()
                        url = await a.get_attribute("href")
                        if title and url:
                            results.append({
                                "title": title.strip(),
                                "url": url if url.startswith("http") else "",
                                "source": "搜狗网页"
                            })
                except Exception:
                    continue
        except Exception:
            pass
        return results

    async def search_wechat(self, query: str, n: int = 8) -> List[Dict]:
        """搜狗微信搜索（真实提取文章链接）"""
        encoded = query.replace(" ", "+")
        await self.go(f"https://weixin.sogou.com/weixin?type=2&query={encoded}&ie=utf8")
        await self.screenshot(f"wechat_{query[:8]}_{int(time.time())}.png")

        results = []
        try:
            # 等 JS 渲染
            await asyncio.sleep(2)
            # 用 Playwright 的 evaluate 直接从页面提取 JS 数据
            data = await self.page.evaluate("""
                () => {
                    const results = [];
                    // 尝试找所有文章链接
                    document.querySelectorAll('a').forEach(a => {
                        const href = a.href;
                        if (href && (href.includes('mp.weixin') || href.includes('url='))) {
                            results.push({
                                title: a.innerText.trim(),
                                url: href
                            });
                        }
                    });
                    return results.slice(0, 10);
                }
            """)
            for item in data[:n]:
                if item.get("title") and len(item["title"]) > 3:
                    results.append({
                        "title": item["title"],
                        "url": item.get("url", ""),
                        "source": "搜狗微信",
                        "star": 4
                    })
        except Exception:
            pass

        # 降级：直接从 HTML 提取
        if not results:
            html = await self.get_html()
            h3s = re.findall(r'<h3[^>]*>(.*?)</h3>', html, re.DOTALL)
            for h in h3s[:n]:
                title = re.sub("<[^>]+>", "", h).strip()
                if title and len(title) > 3:
                    results.append({
                        "title": title,
                        "url": "",
                        "source": "搜狗微信",
                        "star": 4
                    })

        return results

    async def search_ccgp(self, query: str, n: int = 8) -> List[Dict]:
        """中国政府采购网搜索"""
        encoded = query.replace(" ", "+")
        url = f"https://search.ccgp.gov.cn/bxsh?query={encoded}&start=0&rows={n}"
        await self.go(url, timeout=20000)
        await self.screenshot(f"ccgp_{query[:8]}_{int(time.time())}.png")

        await asyncio.sleep(1)
        results = []
        try:
            items = await self.page.query_selector_all("li, .item, tr")
            for item in items[:n]:
                try:
                    title_el = await item.query_selector("a")
                    date_el = await item.query_selector("span, .date")
                    if title_el:
                        title = await title_el.inner_text()
                        url = await title_el.get_attribute("href")
                        date = await date_el.inner_text() if date_el else ""
                        if title and len(title) > 5:
                            results.append({
                                "title": title.strip(),
                                "url": url if url.startswith("http") else f"https://search.ccgp.gov.cn{url}",
                                "date": date.strip(),
                                "source": "政府采购网",
                                "star": 5
                            })
                except Exception:
                    continue
        except Exception:
            pass

        # 降级
        if not results:
            html = await self.get_html()
            titles = re.findall(r'<a[^>]+title=["\']([^"\']+)["\']', html)
            dates = re.findall(r"(\d{4}-\d{2}-\d{2})", html)
            for i, t in enumerate(titles[:n]):
                clean = re.sub("<[^>]+>", "", t).strip()
                if clean and len(clean) > 5:
                    results.append({
                        "title": clean,
                        "url": url,
                        "date": dates[i] if i < len(dates) else "",
                        "source": "政府采购网",
                        "star": 5
                    })
        return results

    async def search_zhipin(self, query: str) -> List[Dict]:
        """Boss直聘搜索"""
        encoded = query.replace(" ", "%20")
        await self.go(f"https://www.zhipin.com/web/geek/job?query={encoded}")
        await asyncio.sleep(3)
        await self.screenshot(f"zhipin_{query[:8]}_{int(time.time())}.png")

        results = []
        try:
            items = await self.page.query_selector_all(".job-card-box, .job-primary")
            for item in items[:8]:
                try:
                    title_el = await item.query_selector(".job-title, h3")
                    company_el = await item.query_selector(".company-name, .name")
                    salary_el = await item.query_selector(".salary")
                    title = await title_el.inner_text() if title_el else ""
                    company = await company_el.inner_text() if company_el else ""
                    salary = await salary_el.inner_text() if salary_el else ""
                    if title:
                        results.append({
                            "title": title.strip(),
                            "company": company.strip(),
                            "salary": salary.strip(),
                            "source": "Boss直聘"
                        })
                except Exception:
                    continue
        except Exception:
            pass
        return results

    async def search_gov_report(self, city: str, dept: str) -> List[Dict]:
        """政府工作报告"""
        query = f"{city} {dept} 2026 政府工作报告"
        return await self.search_baidu(query, n=10)

    async def search_leader_speech(self, city: str, dept: str) -> List[Dict]:
        """领导讲话"""
        query = f"{city} {dept} 局长 主任 发言 讲话 2025 2026"
        # 优先微信搜索
        wechat_results = await self.search_wechat(query)
        baidu_results = await self.search_baidu(query, n=5)
        return wechat_results + baidu_results

    # ── 通用搜索入口 ────────────────────────────────────

    async def search(self, query: str, search_type: str = "all") -> Dict:
        """
        统一搜索入口
        search_type: all | baidu | wechat | sogou | ccgp | jobs | gov | speech
        """
        results = {"query": query, "channels": [], "items": []}

        channels = {
            "baidu": lambda: self.search_baidu(query),
            "sogou": lambda: self.search_sogou_web(query),
            "wechat": lambda: self.search_wechat(query),
            "ccgp": lambda: self.search_ccgp(query),
            "jobs": lambda: self.search_zhipin(query),
        }

        if search_type == "all":
            active = channels.keys()
        elif "," in search_type:
            active = search_type.split(",")
        else:
            active = [search_type]

        for ch in active:
            if ch in channels:
                t0 = time.time()
                try:
                    items = await channels[ch]()
                    elapsed = round((time.time() - t0) * 1000)
                    results["channels"].append({
                        "channel": ch,
                        "count": len(items),
                        "ms": elapsed
                    })
                    results["items"].extend(items)
                except Exception as e:
                    results["channels"].append({
                        "channel": ch,
                        "count": 0,
                        "error": str(e)
                    })

        # 按 star 排序
        results["items"].sort(key=lambda x: x.get("star", 3), reverse=True)
        return results

    async def click_and_wait(self, selector: str, timeout: int = 5000) -> "HumanBrowser":
        """点击元素并等待"""
        await self.page.click(selector, timeout=timeout)
        await asyncio.sleep(random.uniform(1.0, 2.0))
        return self

    async def type_and_submit(self, selector: str, text: str, submit: str = None) -> "HumanBrowser":
        """输入文字并提交"""
        await self.page.fill(selector, text)
        await asyncio.sleep(random.uniform(0.5, 1.0))
        if submit:
            await self.page.click(submit, timeout=5000)
            await asyncio.sleep(random.uniform(1.5, 3.0))
        return self

    async def scroll_down(self, times: int = 3) -> "HumanBrowser":
        """向下滚动页面"""
        for _ in range(times):
            await self.page.keyboard.press("End")
            await asyncio.sleep(random.uniform(0.5, 1.5))
        return self

    async def close(self) -> None:
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


# ════════════════════════════════════════════════════════════════
# 便捷入口（非异步，直接用）
# ════════════════════════════════════════════════════════════════

def sync_search(query: str, search_type: str = "all", headless: bool = True) -> Dict:
    """
    同步封装：调用一次异步搜索
    用法：results = sync_search("深圳市教育局", "baidu,wechat")
    """
    async def _run():
        browser = HumanBrowser(headless=headless)
        await browser.start()
        try:
            return await browser.search(query, search_type)
        finally:
            await browser.close()

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 已经在某个 loop 里了，创建新 task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _run())
                return future.result(timeout=60)
        else:
            return asyncio.run(_run())
    except RuntimeError:
        # 嵌套 loop，创建新 loop
        return asyncio.run(_run())


def sync_screenshot(url: str, name: str = None) -> str:
    """同步截图"""
    async def _run():
        browser = HumanBrowser(headless=True)
        await browser.start()
        try:
            await browser.go(url)
            return await browser.screenshot(name)
        finally:
            await browser.close()

    return asyncio.run(_run())


# ════════════════════════════════════════════════════════════════
# CLI 入口
# ════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys, json

    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 human_browser.py search <关键词> [baidu,wechat,sogou,ccgp,jobs]")
        print("  python3 human_browser.py screenshot <URL> [名称]")
        print("  python3 human_browser.py wechat <关键词>")
        print("  python3 human_browser.py baidu <关键词>")
        sys.exit(1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    async def main():
        browser = HumanBrowser(headless=True)
        await browser.start()

        try:
            if cmd == "search" and len(args) >= 1:
                query = args[0]
                stype = args[1] if len(args) > 1 else "baidu,wechat"
                print(f"🔍 搜索: {query} [{stype}]")
                results = await browser.search(query, stype)
                print(f"\n📊 渠道: {', '.join(c['channel'] + ':' + str(c.get('count', c.get('error',0))) for c in results['channels'])}")
                print(f"\n📋 结果 ({len(results['items'])} 条):")
                for r in results["items"][:15]:
                    star = "⭐" * r.get("star", 3)
                    print(f"  {star} [{r.get('source','')}] {r['title']}")
                    if r.get("url"):
                        print(f"     → {r['url'][:80]}")
                print(f"\n💾 截图已保存至: ~/.qclaw/screenshots/")

            elif cmd == "screenshot" and len(args) >= 1:
                url = args[0]
                name = args[1] if len(args) > 1 else None
                print(f"📸 打开: {url}")
                await browser.go(url)
                path = await browser.screenshot(name)
                print(f"✅ 截图已保存: {path}")

            elif cmd == "wechat" and len(args) >= 1:
                query = args[0]
                print(f"🔍 微信搜索: {query}")
                results = await browser.search_wechat(query)
                for r in results[:10]:
                    print(f"  📄 {r['title']}")
                    if r.get("url"):
                        print(f"     → {r['url'][:80]}")

            elif cmd == "baidu" and len(args) >= 1:
                query = args[0]
                print(f"🔍 百度搜索: {query}")
                results = await browser.search_baidu(query)
                for r in results[:10]:
                    print(f"  📄 {r['title']}")
                    print(f"     → {r.get('snippet','')[:80]}")

            else:
                print(f"未知命令: {cmd}")

        finally:
            await browser.close()

    asyncio.run(main())
