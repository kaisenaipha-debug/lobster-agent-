"""
browser_control.py — 浏览器自动化控制 v1.0

功能：
  - 打开网页、截图、点击元素、填表、提取内容
  - 可串入 agent_loop 作为 browser tool

用法：
  python3 browser_control.py open "https://example.com"
  python3 browser_control.py screenshot "https://example.com" --out example.png
  python3 browser_control.py click "https://example.com" --selector "#login-btn"
  python3 browser_control.py extract "https://example.com" --selector "article"
  python3 browser_control.py interact "https://example.com" --actions "click:#btn|wait:2s"
"""

import os
import sys
import json
import time
import base64
import argparse
from pathlib import Path
from typing import Optional

CHROME_PATH = "/Users/tz/Library/Caches/ms-playwright/chromium-1200/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"

def get_browser():
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    browser = p.chromium.launch(
        executable_path=CHROME_PATH,
        headless=True,
        args=["--disable-blink-features=AutomationControlled"]
    )
    return p, browser

def close(p, browser):
    try:
        browser.close()
    except Exception: pass
    try:
        p.stop()
    except Exception: pass

# ─── 核心命令 ──────────────────────────────────────────

def open_url(url: str, screenshot: bool = False) -> dict:
    p, browser = get_browser()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    try:
        resp = page.goto(url, timeout=15000, wait_until="domcontentloaded")
        time.sleep(1)
        result = {"url": page.url, "title": page.title(), "status": resp.status if resp else 200}
        if screenshot:
            result["screenshot"] = base64.b64encode(page.screenshot()).decode()
        return result
    except Exception as e:
        return {"error": str(e)}
    finally:
        close(p, browser)

def screenshot(url: str, out_path: str) -> dict:
    p, browser = get_browser()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    try:
        page.goto(url, timeout=15000, wait_until="domcontentloaded")
        time.sleep(1)
        page.screenshot(path=out_path, full_page=True)
        return {"success": True, "saved": out_path, "title": page.title()}
    except Exception as e:
        return {"error": str(e)}
    finally:
        close(p, browser)

def click(url: str, selector: str, wait: float = 1) -> dict:
    p, browser = get_browser()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    try:
        page.goto(url, timeout=15000, wait_until="domcontentloaded")
        page.wait_for_selector(selector, timeout=5000)
        page.click(selector)
        time.sleep(wait)
        return {"success": True, "clicked": selector, "new_url": page.url, "title": page.title()}
    except Exception as e:
        return {"error": str(e)}
    finally:
        close(p, browser)

def fill(url: str, selector: str, value: str, submit: bool = False) -> dict:
    p, browser = get_browser()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    try:
        page.goto(url, timeout=15000, wait_until="domcontentloaded")
        page.wait_for_selector(selector, timeout=5000)
        page.fill(selector, value)
        if submit:
            page.press(selector, "Enter")
            time.sleep(2)
        return {"success": True, "filled": selector, "value": value[:20], "new_url": page.url}
    except Exception as e:
        return {"error": str(e)}
    finally:
        close(p, browser)

def extract(url: str, selector: str = None) -> dict:
    p, browser = get_browser()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    try:
        page.goto(url, timeout=15000, wait_until="domcontentloaded")
        time.sleep(1)
        if selector:
            elements = page.query_selector_all(selector)
            texts = [el.inner_text() for el in elements if el]
            return {"success": True, "selector": selector, "count": len(texts), "items": texts[:10]}
        else:
            content = page.content()
            return {"success": True, "title": page.title(), "length": len(content), "preview": content[:500]}
    except Exception as e:
        return {"error": str(e)}
    finally:
        close(p, browser)

def interact(url: str, actions: str) -> dict:
    """actions: click:#btn|fill:#inp:value|wait:2s|type:#inp:text"""
    p, browser = get_browser()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    try:
        page.goto(url, timeout=15000, wait_until="domcontentloaded")
        time.sleep(0.5)
        for action in actions.split("|"):
            action = action.strip()
            try:
                if action.startswith("click:"):
                    sel = action[6:]
                    page.wait_for_selector(sel, timeout=3000)
                    page.click(sel)
                    time.sleep(0.5)
                elif action.startswith("fill:"):
                    _, rest = action.split(":", 1)
                    parts = rest.split(":", 1)
                    sel, val = parts[0], parts[1] if len(parts) > 1 else ""
                    page.fill(sel, val)
                elif action.startswith("type:"):
                    _, rest = action.split(":", 1)
                    parts = rest.split(":", 1)
                    sel, val = parts[0], parts[1] if len(parts) > 1 else ""
                    page.wait_for_selector(sel, timeout=3000)
                    page.type(sel, val, delay=50)
                elif action.startswith("wait:"):
                    t = float(action[6:-1])
                    time.sleep(t)
            except Exception as ae:
                return {"success": False, "step": action, "error": str(ae)}
        time.sleep(1)
        return {"success": True, "final_url": page.url, "title": page.title()}
    except Exception as e:
        return {"error": str(e)}
    finally:
        close(p, browser)

# ─── 主入口 ───────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="🌐 浏览器自动化控制 v1.0")
    sub = parser.add_subparsers(dest="cmd")

    p_open = sub.add_parser("open", help="打开网页")
    p_open.add_argument("url")
    p_open.add_argument("--screenshot", "-s", action="store_true")

    p_ss = sub.add_parser("screenshot", help="截图")
    p_ss.add_argument("url")
    p_ss.add_argument("--out", "-o", required=True)

    p_click = sub.add_parser("click", help="点击元素")
    p_click.add_argument("url")
    p_click.add_argument("--selector", "-s", required=True)
    p_click.add_argument("--wait", "-w", type=float, default=1)

    p_fill = sub.add_parser("fill", help="填写表单")
    p_fill.add_argument("url")
    p_fill.add_argument("--selector", "-s", required=True)
    p_fill.add_argument("--value", "-v", required=True)
    p_fill.add_argument("--submit", action="store_true")

    p_extract = sub.add_parser("extract", help="提取内容")
    p_extract.add_argument("url")
    p_extract.add_argument("--selector", "-s")

    p_interact = sub.add_parser("interact", help="交互序列")
    p_interact.add_argument("url")
    p_interact.add_argument("--actions", "-a", required=True)

    args = parser.parse_args()
    if args.cmd is None:
        parser.print_help()
        return

    if args.cmd == "open":
        result = open_url(args.url, getattr(args, "screenshot", False))
    elif args.cmd == "screenshot":
        result = screenshot(args.url, args.out)
    elif args.cmd == "click":
        result = click(args.url, args.selector, args.wait)
    elif args.cmd == "fill":
        result = fill(args.url, args.selector, args.value, getattr(args, "submit", False))
    elif args.cmd == "extract":
        result = extract(args.url, getattr(args, "selector", None))
    elif args.cmd == "interact":
        result = interact(args.url, args.actions)
    else:
        parser.print_help()
        return

    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
