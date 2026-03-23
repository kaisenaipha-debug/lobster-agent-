"""
browser_control.py — 浏览器自动化 v5.0 人类级

核心能力：
  ✅ CDP连接真实Chrome（kaisenaipha@gmail.com 已登录）
  ✅ Google搜索用账号状态（搜索结果更精准）
  ✅ 多步骤流：search→click→extract→screenshot
  ✅ LLM引导提取（告诉AI你想找什么）
  ✅ 真实颜色截图
  ✅ 自动保持登录状态（_google_logged_in全局标志）
  ✅ Chrome自愈管理（ChromeSupervisor，进程死亡自动重启）

用法：
  from browser_control import BrowserSession
  b = BrowserSession().ensure_google()  # 确保Google已登录
  b.google_search("河源市教育局局长")     # 用账号搜索
  b.click_link("杨利华")                  # 点相关链接
  r = b.extract("局长简历")              # LLM提取
  ss = b.screenshot()                   # 截图
  b.close()
"""

import os, sys, time, base64, json, re, subprocess
from pathlib import Path
from typing import Optional

# ─── 配置 ──────────────────────────────────────────────

CDP_URL = "http://localhost:9222"
GOOGLE_ACCOUNT = {
    "email": "kaisenaipha@gmail.com",
    "password": "Zihua161020",
}
_GOOGLE_COOKIE_FILE = Path.home() / ".qclaw" / "workspace" / ".google_session"
_google_logged_in = _GOOGLE_COOKIE_FILE.exists()  # 持久化标志：文件存在=已登录
_playwright = None

# ─── Chrome管理（由 ChromeSupervisor 守护进程提供自愈能力）──

def _ensure_chrome():
    """
    确保 pha Chrome 在运行。
    现在委托给 chrome_supervisor_bridge.py 的 ChromeBridge：
      - 进程死亡自动重启 Chrome
      - 指数退避重连（最多 30s 间隔）
      - 双层健康检查（端口探针 + DevTools HTTP probe）
    """
    try:
        from chrome_supervisor_bridge import ChromeBridge
        bridge = ChromeBridge()
        if not bridge.is_healthy():
            bridge.start()
    except Exception as e:
        # 降级：保持原有逻辑（直接启动 Chrome）
        import httpx
        try:
            r = httpx.get(f"{CDP_URL}/json/version", timeout=3)
            if r.status_code == 200:
                return
        except:
            pass
        chrome_bin = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        subprocess.Popen(
            [chrome_bin,
             "--remote-debugging-port=9222",
             f"--user-data-dir={Path.home()}/.qclaw/browser/pha-debug",
             "--profile-directory=Profile 34",
             "--no-first-run", "--no-default-browser-check",
             "--disable-sync", "--disable-background-networking"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(3)

def _get_pw():
    global _playwright
    if _playwright is None:
        from playwright.sync_api import sync_playwright
        _playwright = sync_playwright().start()
    return _playwright

# ─── Google登录 ──────────────────────────────────────

def _google_login(b) -> bool:
    """登录Google账号（内部用）"""
    global _google_logged_in
    if _google_logged_in:
        return True

    try:
        b.goto("https://accounts.google.com/v3/signin/identifier", wait="load")
        time.sleep(1.5)

        b.page.wait_for_selector('input[type="email"]', timeout=8000)
        b.page.fill('input[type="email"]', GOOGLE_ACCOUNT["email"])
        b.page.keyboard.press("Enter")
        time.sleep(3)

        b.page.wait_for_selector('input[type="password"]', timeout=8000)
        b.page.fill('input[type="password"]', GOOGLE_ACCOUNT["password"])
        b.page.keyboard.press("Enter")
        time.sleep(5)

        b.goto("https://www.google.com", wait="networkidle")
        if "google" in b.page.title().lower():
            _google_logged_in = True
            _GOOGLE_COOKIE_FILE.touch()  # 持久化登录标志
            print(f"✅ Google已登录: {GOOGLE_ACCOUNT['email']}")
            return True
    except Exception as e:
        print(f"Google登录失败: {e}")
    return False

# ─── 浏览器会话 ───────────────────────────────────────

class BrowserSession:
    """人类级浏览器会话"""

    def __init__(self, headless: bool = False):
        self.browser = None
        self.context = None
        self.page = None
        self.headless = headless
        self.last_screenshot = None
        self.history = []

    def connect(self):
        _ensure_chrome()
        p = _get_pw()
        try:
            self.browser = p.chromium.connect_over_cdp(CDP_URL)
            ctxs = self.browser.contexts
            self.context = ctxs[0] if ctxs else None
            pages = self.context.pages if self.context else []
            self.page = pages[0] if pages else self.context.new_page() if self.context else None
        except Exception:
            self.browser = p.chromium.launch(headless=self.headless)
            self.context = self.browser.new_context(viewport={"width": 1280, "height": 900})
            self.page = self.context.new_page()
        self.page.set_default_timeout(15000)
        return self

    def ensure_google(self):
        """确保Google账号已登录"""
        _google_login(self)
        return self

    def google_search(self, query: str):
        """使用Google账号搜索"""
        self.ensure_google()
        return self.search(query)

    def goto(self, url: str, wait: str = "load") -> "BrowserSession":
        if not self.page:
            self.connect()
        self.page.goto(url, wait_until=wait, timeout=20000)
        self.history.append(url)
        return self

    def search(self, query: str) -> "BrowserSession":
        q = query.replace(" ", "+")
        return self.goto(f"https://www.google.com/search?q={q}", wait="networkidle")

    def click_link(self, text: str) -> "BrowserSession":
        """点击包含文字的链接"""
        self.page.wait_for_load_state("networkidle")
        try:
            self.page.click(f"a:has-text('{text}')")
            self.page.wait_for_load_state("networkidle")
        except:
            # 模糊匹配
            links = self.page.query_selector_all("a")
            for link in links:
                try:
                    t = (link.inner_text() or "") + (link.get_attribute("href") or "")
                    if text.lower() in t.lower():
                        href = link.get_attribute("href") or ""
                        if href.startswith("/url?q="):
                            m = re.search(r"/url\?q=(.*?)&", href)
                            href = m.group(1) if m else href
                        if href:
                            self.goto(href)
                            return self
                except:
                    continue
        return self

    def click_nth_link(self, n: int = 0) -> "BrowserSession":
        """点击第N个搜索结果（0=第1个）"""
        self.page.wait_for_load_state("networkidle")
        results = self.page.query_selector_all("div.g a[href]")
        results = [r for r in results if r.get_attribute("href")
                   and not r.get_attribute("href").startswith("/search")]
        if n < len(results):
            href = results[n].get_attribute("href")
            self.goto(href)
        return self

    def extract(self, goal: str = None) -> dict:
        if not self.page:
            return {"error": "No page loaded"}
        html = self.page.content()
        title = self.page.title()
        url = self.page.url
        if goal:
            return self._llm_extract(html, goal, title, url)
        return {"title": title, "url": url, "content": html[:3000]}

    def _llm_extract(self, html: str, goal: str, title: str, url: str) -> dict:
        prompt = (
            f"页面标题: {title}\nURL: {url}\n"
            f"用户想找: {goal}\n"
            f"请从以下页面HTML中提取所有与「{goal}」相关的内容，"
            f"返回结构化信息。如果没找到，请说「未找到」。\n\n---HTML---\n{html[:5000]}"
        )
        try:
            from http_pool import groq
            result = groq(prompt, max_tokens=400)
            return {"goal": goal, "title": title, "url": url, "extracted": result}
        except Exception as e:
            return {"goal": goal, "error": str(e), "title": title, "url": url}

    def smart_extract(self, goal: str) -> dict:
        """智能提取（当前页面）"""
        if not self.page:
            return {"error": "No page loaded"}
        return self.extract(goal)

    def screenshot(self, path: str = None, full: bool = True) -> str:
        if not self.page:
            return ""
        if not path:
            path = f"/tmp/browser_{int(time.time())}.png"
        self.page.screenshot(path=path, full_page=full)
        self.last_screenshot = path
        return path

    def smart_screenshot(self) -> str:
        """等页面完全加载再截"""
        if self.page:
            self.page.wait_for_load_state("networkidle")
            time.sleep(1.5)
        return self.screenshot()

    def scroll(self, px: int = 500) -> "BrowserSession":
        if self.page:
            self.page.evaluate(f"window.scrollBy(0, {px})")
            time.sleep(0.5)
        return self

    def scroll_to_bottom(self) -> "BrowserSession":
        if self.page:
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
        return self

    def extract_all_links(self) -> list:
        if not self.page:
            return []
        links = self.page.query_selector_all("a[href]")
        result = []
        skip_patterns = {
            "google.com/search", "support.google", "accounts.google",
            "policies.google", "maps.google", "youtube.com/results",
            "无障碍", "登录", "AI", "新闻", "图片", "视频", "购物",
            "短视频", "网页", "图书", "航班", "不限语言", "中文网页",
            "简体中文", "时间不限", "设置", "工具", "更多", "hide",
            "过去 1", "过去 24", "过去 1 周", "过去 1 个月", "过去 1 年",
            "更多设置", "所有时间", "sort", "lr=", "cr=", "精确匹配", "不换行",
        }
        for l in links:
            href = l.get_attribute("href") or ""
            text = l.inner_text().strip()
            if not href or len(text) < 4:
                continue
            # 排除Google导航/筛选器
            if any(p in text or p in href[:60] for p in skip_patterns):
                continue
            # 排除 href 是 # 或 javascript:
            if href in ("#", "javascript:void(0)"):
                continue
            result.append({"text": text[:80], "href": href[:200]})
        return result

    def click_search_result(self, n: int = 0) -> "BrowserSession":
        """点击第N个Google搜索结果"""
        self.page.wait_for_load_state("networkidle")
        results = self.page.query_selector_all("div.g a[href]")
        real_results = []
        for r in results:
            href = r.get_attribute("href") or ""
            text = r.inner_text().strip()
            if href and len(text) > 10 and "google.com/search" not in href:
                real_results.append((r, href, text))

        if n < len(real_results):
            elem, href, text = real_results[n]
            print(f"  → 直接跳转: {text[:50]}")
            try:
                self.goto(href)
            except Exception as e:
                print(f"  跳转失败: {e}")
        return self

    def close(self):
        try:
            if self.page:
                self.page.close()
        except:
            pass

    def __enter__(self):
        return self.connect()

    def __exit__(self, *args):
        self.close()


# ─── 快捷入口 ─────────────────────────────────────────

def google_search(query: str, click: str = None, extract: str = None) -> dict:
    """
    一句话完成：Google登录 → 搜索 → 点击 → 提取 → 截图
    用法：google_search("河源市教育局局长", click="杨利华", extract="简历")
    """
    with BrowserSession() as b:
        b.google_search(query)
        if click:
            b.click_link(click)
        elif extract:
            pass
        ss = b.screenshot()
        r = b.extract(extract)
        r["screenshot"] = ss
        return r


# ─── CLI ──────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    sub = p.add_subparsers()

    s = sub.add_parser("search", help="Google搜索")
    s.add_argument("query")
    s.add_argument("--click", "-c")
    s.add_argument("--extract", "-e")

    g = sub.add_parser("goto", help="访问URL")
    g.add_argument("url")

    sub.add_parser("screenshot", help="截图")

    args = p.parse_args()

    with BrowserSession() as b:
        if hasattr(args, "query"):
            b.google_search(args.query)
            if args.click:
                b.click_link(args.click)
            time.sleep(2)
            if args.extract:
                print(b.extract(args.extract).get("extracted", ""))
            else:
                print(f"标题: {b.page.title()}")
        elif hasattr(args, "url"):
            b.goto(args.url)
            print(f"标题: {b.page.title()}")
        else:
            ss = b.screenshot()
            print(f"截图: {ss}")
