"""
http_pool.py — HTTP 工具池（Groq + 多路径搜索）
"""

import os, httpx, random, urllib.parse, re
from pathlib import Path

from _secrets import GROQ_KEY
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/json",
}

# ─── Groq ───────────────────────────────

def groq(prompt: str, max_tokens: int = 300) -> str:
    try:
        r = httpx.post(GROQ_URL, json={
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens
        }, headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}, timeout=15)
        data = r.json()
        if "error" not in data:
            return data["choices"][0]["message"]["content"]
    except Exception:
        pass
    return ""

def groq_fast(prompt: str, max_tokens: int = 200) -> str:
    return groq(prompt, max_tokens)

# ─── 多路径搜索 ────────────────────────────────

class MultiSearch:
    """
    自动尝试多个搜索路径，直到成功。
    路径优先级：搜狗微信 → 搜狗网页 → 直接URL
    """

    def __init__(self):
        self.ua = HEADERS["User-Agent"]

    def _sogou_weixin(self, query: str, count: int = 8) -> list[dict]:
        """路径1：搜狗微信搜索（最稳）"""
        url = f"https://weixin.sogou.com/weixin?type=2&query={urllib.parse.quote(query)}&ie=utf8"
        try:
            r = httpx.get(url, headers={"User-Agent": self.ua}, timeout=12)
            html = r.text
            titles = re.findall(r'<h3[^>]*>(.*?)</h3>', html, re.DOTALL)
            # 提取真实链接
            links = []
            raw_links = re.findall(r'href="(https?://[^"]+)"', html)
            for l in raw_links:
                if "mp.weixin" in l or "url=" in l:
                    if "url=" in l:
                        # Sogou 重定向 URL
                        decoded = urllib.parse.unquote(re.search(r'url=([^&"]+)', l).group(1)) if re.search(r'url=([^&"]+)', l) else l
                        links.append(decoded)
                    else:
                        links.append(l)
            results = []
            for i, t in enumerate(titles[:count]):
                clean = re.sub("<[^>]+>", "", t).strip()
                if clean:
                    results.append({
                        "title": clean,
                        "url": links[i] if i < len(links) else "",
                        "source": "搜狗微信"
                    })
            return results
        except Exception as e:
            return []

    def _sogou_web(self, query: str, count: int = 8) -> list[dict]:
        """路径2：搜狗网页搜索"""
        url = f"https://www.sogou.com/web?query={urllib.parse.quote(query)}&ie=utf8"
        try:
            r = httpx.get(url, headers={"User-Agent": self.ua}, timeout=12)
            html = r.text
            titles = re.findall(r'<h3[^>]*class="[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
            results = []
            for url, title_raw in titles[:count]:
                clean = re.sub("<[^>]+>", "", title_raw).strip()
                if clean:
                    results.append({"title": clean, "url": url, "source": "搜狗网页"})
            return results
        except Exception:
            return []

    def _baidu_search(self, query: str, count: int = 5) -> list[dict]:
        """路径3：百度网页（可能需验证码）"""
        url = f"https://www.baidu.com/s?wd={urllib.parse.quote(query)}"
        try:
            r = httpx.get(url, headers={"User-Agent": self.ua}, timeout=10)
            html = r.text
            titles = re.findall(r'<h3[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
            results = []
            for url, title_raw in titles[:count]:
                clean = re.sub("<[^>]+>", "", title_raw).strip()
                if clean and len(clean) > 5:
                    results.append({"title": clean, "url": url, "source": "百度"})
            return results
        except Exception:
            return []

    def _direct_url(self, query: str, known_domains: list[str]) -> list[dict]:
        """路径4：直接尝试已知域名（无需搜索）"""
        results = []
        for domain in known_domains:
            try:
                r = httpx.get(domain, headers={"User-Agent": self.ua}, timeout=8, follow_redirects=True)
                if r.status_code == 200:
                    title_match = re.search(r'<title>(.*?)</title>', r.text, re.DOTALL)
                    title = title_match.group(1)[:60] if title_match else domain
                    results.append({"title": title.strip(), "url": str(r.url), "source": "直接访问"})
            except Exception:
                pass
        return results

    def search(self, query: str, count: int = 8, domains: list[str] = None) -> list[dict]:
        """
        自动探测可用路径，返回结构化结果。
        domains: 已知域名列表（如 ["https://heyuan.gov.cn/..."]）
        """
        # 优先微信搜索（最干净）
        results = self._sogou_weixin(query, count)
        if results:
            return results

        # 其次搜狗网页
        results = self._sogou_web(query, count)
        if results:
            return results

        # 百度（可能失败）
        results = self._baidu_search(query, count)
        if results:
            return results

        # 直接域名
        if domains:
            return self._direct_url(query, domains)

        return []

    def search_all(self, query: str, count: int = 5) -> list[dict]:
        """多路径并行搜索，合并去重"""
        all_results = []

        for fn in [self._sogou_weixin, self._sogou_web, self._baidu_search]:
            try:
                r = fn(query, count)
                if r:
                    all_results.extend(r)
            except Exception:
                pass

        # 去重
        seen = set()
        unique = []
        for item in all_results:
            key = item["title"][:30]
            if key not in seen:
                seen.add(key)
                unique.append(item)
        return unique[:count]


# 全局实例
_search = None

def get_search():
    global _search
    if _search is None:
        _search = MultiSearch()
    return _search

def search(query: str, count: int = 8) -> list[dict]:
    """快捷入口：search("关键词") → [{"title","url","source"}, ...]"""
    return get_search().search(query, count)

def search_all(query: str, count: int = 5) -> list[dict]:
    return get_search().search_all(query, count)
