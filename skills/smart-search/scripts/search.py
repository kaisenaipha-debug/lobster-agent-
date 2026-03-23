#!/usr/bin/env python3
"""
smart-search v2.1 S+级 — 融合统一爬虫引擎
8通道搜索 + unified_crawler（HTTP/Playwright/crawl4ai三层级联）
"""
import sys
import re
import ssl
import json
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── SSL ───────────────────────────────────────────────────
_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

UA_PC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
UA_MOBILE = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"

# ─── Layer 1: HTTP池 ───────────────────────────────────────
def fetch(url: str, timeout: int = 12, mobile: bool = False, retries: int = 2) -> str:
    ua = UA_MOBILE if mobile else UA_PC
    last_err = "unknown"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=timeout, context=_ctx) as r:
                return r.read().decode("utf-8", errors="ignore")
        except Exception as exc:
            last_err = str(exc)
            if attempt < retries - 1:
                time.sleep(1)
    return f"ERROR:{last_err}"

# ─── Layer 2: Playwright 真浏览器 ─────────────────────────
CHROME_PATH = "/Users/tz/Library/Caches/ms-playwright/chromium-1200/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"

def crawl_full_text(url: str, timeout: int = 20) -> str:
    """用 Playwright 提取页面全文（gov.cn/需JS的网站自动切换）"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return fetch(url, timeout=timeout)
    p = None
    try:
        p = sync_playwright().start()
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(url, timeout=timeout * 1000, wait_until="domcontentloaded")
        time.sleep(2)
        content = page.inner_text("body")
        browser.close()
        p.stop()
        return content
    except Exception:
        try:
            if browser: browser.close()
        except Exception: pass
        try:
            if p: p.stop()
        except Exception: pass
        return fetch(url, timeout=timeout)

def smart_fetch(url: str) -> str:
    """智能选择：普通HTTP → 失败/JS网站则切换Playwright"""
    html = fetch(url, timeout=8)
    if html.startswith("ERROR") or len(html) < 200:
        return crawl_full_text(url)
    # 自动识别需JS渲染的域名
    if any(d in url for d in ["gov.cn", "zhipin.com", "liepin.com", "ccgp.gov.cn"]):
        return crawl_full_text(url)
    return html

# ─── Serper API ───────────────────────────────────────────
SERPER_KEY = "e60b55e1eac362203615c503b9d17d544e28e22e"
SERPER_BASE = "https://google.serper.dev/search"
import ssl
import json
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── SSL ───────────────────────────────────────────────────
_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

UA_PC = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
UA_MOBILE = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"

# ─── Serper API ───────────────────────────────────────────
SERPER_KEY = "e60b55e1eac362203615c503b9d17d544e28e22e"
SERPER_BASE = "https://google.serper.dev/search"

def serper_search(query: str, gl: str = "cn", hl: str = "zh-cn", num: int = 10) -> List[Dict]:
    """Serper.dev Google 搜索 API（国内直连）"""
    if not SERPER_KEY:
        return []
    payload = json.dumps({"q": query, "gl": gl, "hl": hl, "num": num}).encode()
    req = urllib.request.Request(
        SERPER_BASE,
        data=payload,
        headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_ctx) as r:
            data = json.load(r)
        results = []
        for item in data.get("organic", [])[:num]:
            snippet = item.get("snippet", "")
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": snippet[:200],
                "source": "Google(Serper)" if gl == "us" else "百度(Serper)",
                "star": 5 if "gov.cn" in item.get("link", "") or "weixin" in item.get("link", "") else 4,
            })
        return results
    except Exception as exc:
        return []

def serper_baidu_mode(query: str) -> List[Dict]:
    """用 Serper 的 gl=cn 模式搜百度风格结果"""
    return serper_search(query, gl="cn", hl="zh-cn", num=10)

def serper_google_mode(query: str) -> List[Dict]:
    """用 Serper 的 gl=us 模式搜英文/国际内容"""
    return serper_search(query, gl="us", hl="en", num=10)


# ─── HTTP 通用 ─────────────────────────────────────────────
def fetch(url: str, timeout: int = 12, mobile: bool = False, retries: int = 2) -> str:
    ua = UA_MOBILE if mobile else UA_PC
    last_err = "unknown"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=timeout, context=_ctx) as r:
                return r.read().decode("utf-8", errors="ignore")
        except Exception as exc:
            last_err = str(exc)
            if attempt < retries - 1:
                time.sleep(2)
    return f"ERROR:{last_err}"


def decode_sogou_url(url: str) -> str:
    """解析搜狗重定向获取真实微信文章 URL"""
    if url.startswith("/"):
        url = "https://www.sogou.com" + url
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA_PC})
        with urllib.request.urlopen(req, timeout=8, context=_ctx) as r:
            return str(r.url)
    except:
        return url


# ─── 搜狗微信搜索（v2：账号+文章双模式）────────────────────
def sogou_weixin_article(query: str, count: int = 8) -> List[Dict]:
    """搜公众号文章 type=2"""
    url = f"https://weixin.sogou.com/weixin?type=2&query={urllib.parse.quote(query)}&ie=utf8"
    html = fetch(url, mobile=False)
    if html.startswith("ERROR"):
        return []
    return _parse_weixin_results(html, count, "搜狗微信文章")

def sogou_weixin_account(query: str, count: int = 5) -> List[Dict]:
    """搜公众号账号 type=1"""
    url = f"https://weixin.sogou.com/weixin?type=1&query={urllib.parse.quote(query)}&ie=utf8"
    html = fetch(url, mobile=False)
    if html.startswith("ERROR"):
        return []
    return _parse_weixin_results(html, count, "搜狗微信公众号")

def _parse_weixin_results(html: str, count: int, source: str) -> List[Dict]:
    """解析搜狗微信 HTML，提取标题+URL"""
    h3s = re.findall(r"<h3[^>]*>(.*?)</h3>", html, re.DOTALL)
    titles = [re.sub("<[^>]+>", "", h).strip() for h in h3s if re.sub("<[^>]+>", "", h).strip()]

    raw_urls = re.findall(r'href=["\']([^"\']+)["\']', html)
    mp_urls = []
    for u in raw_urls:
        u_decoded = urllib.parse.unquote(u)
        if "mp.weixin.qq.com" in u_decoded:
            mp_urls.append(u_decoded)
        elif "url=" in u_decoded:
            m = re.search(r"url=([^&\"']+)", u_decoded)
            decoded = m.group(1) if m else u_decoded
            if "mp.weixin" in decoded:
                mp_urls.append(decoded)

    # 提取公众号名称
    mp_names = re.findall(r'nickname[^>]*>([^<]+)<', html)
    dates = re.findall(r'(\d{4}-\d{2}-\d{2})', html)

    results = []
    for i, title in enumerate(titles[:count]):
        if not title or len(title) < 4:
            continue
        results.append({
            "title": title,
            "url": mp_urls[i] if i < len(mp_urls) else "",
            "mp_name": mp_names[i] if i < len(mp_names) else "",
            "date": dates[i] if i < len(dates) else "",
            "source": source,
            "star": 5 if "官方" in title or "局" in title else 4,
        })
    return results


# ─── 搜狗网页搜索 ─────────────────────────────────────────
def sogou_web(query: str, count: int = 8) -> List[Dict]:
    url = f"https://www.sogou.com/web?query={urllib.parse.quote(query)}&ie=utf8"
    html = fetch(url)
    if html.startswith("ERROR"):
        return []
    items = re.findall(r"<h3[^>]*>.*?<a[^>]+href=['\"]([^'\"]+)['\"][^>]*>(.*?)</a>.*?</h3>", html, re.DOTALL)
    results = []
    for raw_url, title_raw in items[:count]:
        title = re.sub("<[^>]+>", "", title_raw).strip()
        if not title or len(title) < 4:
            continue
        resolved = decode_sogou_url(raw_url) if raw_url.startswith("/link") else raw_url
        if resolved.startswith("http"):
            results.append({
                "title": title,
                "url": resolved,
                "source": "搜狗网页",
                "star": 4 if any(x in resolved for x in ["gov.cn", "org.cn"]) else 3,
            })
    return results


# ─── 政府采购网 CCGP ──────────────────────────────────────
def ccgp_search(query: str, count: int = 10) -> List[Dict]:
    # CCGP 有严格反爬，间隔请求
    time.sleep(3)
    url = f"https://search.ccgp.gov.cn/bxsearch?query={urllib.parse.quote(query)}&start=0&rows={count}"
    html = fetch(url, timeout=15)
    if html.startswith("ERROR"):
        return []
    # CCGP 限流时返回提示页
    if "频繁访问" in html or len(html) < 200:
        return [{"title": "[限流] 政府采购网暂时无法访问，请在1小时后重试，或通过Serper查询", "url": "", "source": "中国政府采购网(限流)", "star": 3}]
    titles = re.findall(r'<a[^>]+title=["\']([^"\']+)["\']', html)
    dates = re.findall(r"<span[^>]*>(\d{4}-\d{2}-\d{2})</span>", html)
    results = []
    for i, title in enumerate(titles[:count]):
        clean = re.sub("<[^>]+>", "", title).strip()
        if not clean or len(clean) < 5:
            continue
        results.append({
            "title": clean,
            "url": url,
            "date": dates[i] if i < len(dates) else "",
            "source": "中国政府采购网",
            "star": 5,
        })
    return results


# ─── Boss直聘 ─────────────────────────────────────────────
def bosszhipin(query: str, count: int = 8) -> List[Dict]:
    """Boss直聘搜索（直连，无 API Key）"""
    url = f"https://www.zhipin.com/web/boss/browse/jobs.json?query={urllib.parse.quote(query)}&pageSize={count}"
    html = fetch(url, mobile=True)
    if html.startswith("ERROR") or len(html) < 100:
        return []
    try:
        data = json.loads(html)
        jobs = data.get("zpData", {}).get("jobList", []) if isinstance(data, dict) else []
        results = []
        for job in jobs[:count]:
            results.append({
                "title": job.get("jobName", ""),
                "company": job.get("companyName", ""),
                "salary": job.get("salary", ""),
                "url": f"https://www.zhipin.com{job.get('jobHref','')}",
                "source": "Boss直聘",
                "star": 4,
            })
        return results
    except Exception:
        return []


# ─── 城市 gov.cn 政策爬取 ─────────────────────────────────
def gov_cn_search(city: str, dept: str, query: str = "", count: int = 5) -> List[Dict]:
    """直接爬取城市政府官网政策文件"""
    base_domains = [
        f"https://www.{city}.gov.cn",
        f"https://fgw.{city}.gov.cn",
    ]
    results = []
    for domain in base_domains:
        search_url = f"{domain}/search.html?searchWord={urllib.parse.quote(dept + ' ' + query)}"
        html = fetch(search_url, timeout=8)
        if html.startswith("ERROR") or len(html) < 200:
            continue
        titles = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html)
        for raw_url, title_raw in titles:
            title = re.sub("<[^>]+>", "", title_raw).strip()
            if title and len(title) > 8 and any(kw in title for kw in [dept, "教育", "政策", "通知", "公告"]):
                full_url = raw_url if raw_url.startswith("http") else domain + raw_url
                results.append({
                    "title": title,
                    "url": full_url,
                    "source": f"{city}政府网",
                    "star": 5,
                })
        if results:
            break
    return results[:count]


# ─── 招聘情报（猎聘）───────────────────────────────────────
def liepin_search(query: str, count: int = 5) -> List[Dict]:
    """猎聘网搜索"""
    url = f"https://www.liepin.com/zhaopin/?compLayer=1&deptNode=00&industryType=0&jobKind=1&key={urllib.parse.quote(query)}&ckid=0&degradeFlag=0&dqs=0&industries=&linkOp=0&pageSize={count}&salary=0%2C0&searchVersion=1&siTag=Td-0wv4WMhM1n4~1Kx7c_wfA~R7rNqhps3Xy3cR7rNqh&headckid=0&d_headId=0&d_ckId=0&d_curPage=0&d_pageSize={count}&d_headId=0"
    html = fetch(url, mobile=True)
    if html.startswith("ERROR"):
        return []
    titles = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>\s*([^<]{5,50})\s*</a>', html)
    results = []
    for raw_url, title in [(u, t.strip()) for u, t in titles if "zhaopin" in u or "job" in u][:count]:
        full_url = raw_url if raw_url.startswith("http") else "https://www.liepin.com" + raw_url
        if full_url.startswith("http"):
            results.append({
                "title": title,
                "url": full_url,
                "source": "猎聘网",
                "star": 3,
            })
    return results[:count]


# ─── 路由引擎 ─────────────────────────────────────────────
def route_channels(query: str, intent: str = "auto") -> List[str]:
    """根据查询意图自动选择最佳通道组合（最多3个并行）"""
    q_lower = query.lower()

    if any(kw in q_lower for kw in ["采购", "招标", "中标", "供应商"]):
        return ["ccgp", "serper_baidu"]
    if any(kw in q_lower for kw in ["政府报告", "工作报告", "政策", "规划", "文件"]):
        return ["serper_baidu", "weixin_article", "gov_cn"]
    if any(kw in q_lower for kw in ["局长", "领导", "发言", "讲话", "文章"]):
        return ["weixin_article", "weixin_account", "gov_cn"]
    if any(kw in q_lower for kw in ["招聘", "职位", "人才", "团队"]):
        return ["bosszhipin", "liepin"]
    if any(kw in q_lower for kw in ["英文", "international", "global", "案例"]):
        return ["serper_google"]
    # 默认：并行最强通道
    return ["weixin_article", "serper_baidu", "sogou_web"]


# ─── 并行聚合搜索 v2 ──────────────────────────────────────
def search_all(query: str, channels: str = "auto", intent: str = "auto") -> Dict:
    # 解析通道
    if channels == "auto":
        selected = route_channels(query, intent)
    elif channels == "all":
        selected = ["weixin_article", "weixin_account", "sogou_web", "ccgp", "serper_baidu", "bosszhipin"]
    else:
        selected = channels.split(",")

    func_map = {
        "weixin_article": (sogou_weixin_article, "搜狗微信文章"),
        "weixin_account": (sogou_weixin_account, "搜狗微信公众号"),
        "sogou_web":      (sogou_web, "搜狗网页"),
        "ccgp":           (ccgp_search, "政府采购网"),
        "serper_baidu":   (serper_baidu_mode, "Serper(百度模式)"),
        "serper_google":  (serper_google_mode, "Serper(Google模式)"),
        "bosszhipin":     (bosszhipin, "Boss直聘"),
        "gov_cn":         (gov_cn_search, "政府官网"),
        "liepin":         (liepin_search, "猎聘网"),
    }

    results = {"query": query, "channels": [], "total": 0, "items": [], "intent": intent}
    seen_urls = set()

    def run_channel(ch):
        if ch not in func_map:
            return []
        fn, name = func_map[ch]
        t0 = time.time()
        try:
            items = fn(query) if ch != "gov_cn" else fn(query.split()[0] if query else "", query)
            elapsed = round((time.time() - t0) * 1000)
            results["channels"].append({"channel": ch, "name": name, "count": len(items), "ms": elapsed})
            return items
        except Exception as ex:
            results["channels"].append({"channel": ch, "name": name, "count": 0, "ms": 0, "error": str(ex)})
            return []

    # 并行执行
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(run_channel, ch): ch for ch in selected if ch in func_map}
        for future in as_completed(futures):
            items = future.result()
            for item in items:
                url_key = item.get("url", "")
                if url_key and url_key not in seen_urls:
                    seen_urls.add(url_key)
                    results["items"].append(item)
                    results["total"] += 1

    # 全通道补充（all 模式）
    if channels == "all":
        for ch, (fn, name) in func_map.items():
            if ch not in selected:
                t0 = time.time()
                try:
                    items = fn(query) if ch != "gov_cn" else fn(query.split()[0] if query else "", query)
                    elapsed = round((time.time() - t0) * 1000)
                    results["channels"].append({"channel": ch, "name": name, "count": len(items), "ms": elapsed})
                    for item in items:
                        url_key = item.get("url", "")
                        if url_key and url_key not in seen_urls:
                            seen_urls.add(url_key)
                            results["items"].append(item)
                            results["total"] += 1
                except Exception:
                    pass

    # 按可信度 + 时效性 排序
    results["items"].sort(key=lambda x: (x.get("star", 3), bool(x.get("date"))), reverse=True)
    return results


# ─── 冷情报七步搜索（S级完整版）────────────────────────────
def cold_intel(city: str, dept: str, year: int = 2025) -> Dict:
    """gov-intel 触发时：七通道并行搜索"""
    queries = [
        (f"{city} {dept} {year} 工作报告 重点任务", ["serper_baidu", "weixin_article"]),
        (f"{dept} {year} 考核指标 绩效", ["serper_baidu", "sogou_web"]),
        (f"{city} {dept} 局长 {year}", ["weixin_article", "weixin_account"]),
        (f"{city} {dept} 采购 中标 {year}", ["ccgp", "serper_baidu"]),
        (f"{dept} 招聘信息 {city} {year}", ["bosszhipin", "liepin"]),
        (f"{city}.gov.cn {dept} 工作 {year}", ["gov_cn", "serper_baidu"]),
        (f"{city} {dept} 重点工作 {year}", ["serper_baidu", "weixin_article"]),
    ]
    all_items = []
    all_channels = []
    seen = set()

    for query_str, ch_list in queries:
        result = search_all(query_str, channels=",".join(ch_list))
        for item in result["items"]:
            key = item.get("url", "") + item.get("title", "")
            if key not in seen:
                seen.add(key)
                all_items.append(item)
        all_channels.extend(result["channels"])

    all_items.sort(key=lambda x: (x.get("star", 3), bool(x.get("date", ""))), reverse=True)
    return {"query": f"{city} {dept}", "cold_intel": True, "channels": all_channels, "total": len(all_items), "items": all_items}


# ─── CLI ──────────────────────────────────────────────────
if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "深圳市教育局 2025"
    mode = sys.argv[2] if len(sys.argv) > 2 else "auto"
    intent = sys.argv[3] if len(sys.argv) > 3 else "auto"

    if mode == "cold_intel":
        parts = query.split()
        city = parts[0] if len(parts) > 0 else ""
        dept = parts[1] if len(parts) > 1 else query
        results = cold_intel(city, dept)
    else:
        results = search_all(query, channels=mode, intent=intent)

    print(f"\n🔍 [{results.get('intent', mode)}] {results['query']}")
    print(f"📊 总计: {results['total']} 条结果 | 通道: {len(results['channels'])}\n")
    for ch in results.get("channels", []):
        err = f" ❌{ch.get('error','')}" if ch.get("error") else ""
        print(f"  [{ch['name']}] {ch['count']}条 ({ch['ms']}ms){err}")

    print("\n" + "=" * 65)
    for item in results["items"][:20]:
        star = "⭐" * item.get("star", 3)
        date = f"[{item.get('date','')}] " if item.get("date") else ""
        mp = f" 📣{item.get('mp_name','')}" if item.get("mp_name") else ""
        print(f"\n{star} {date}{item['title']}{mp}")
        if item.get("snippet"):
            print(f"   💬 {item['snippet'][:120]}")
        if item.get("url"):
            print(f"   → {item['url'][:90]}")
        if item.get("company"):
            print(f"   🏢 {item['company']} | 💰 {item.get('salary','')}")

    # 保存
    path = f"/tmp/smart_search_v2_{hash(query)}.json"
    with open(path, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n💾 结果已保存: {path}")
