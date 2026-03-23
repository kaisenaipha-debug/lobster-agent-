"""
一键打开Agent常用站点（新标签页）
用法: python quick_sites.py
"""
from playwright.sync_api import sync_playwright
import time

SITES = [
    ("https://chatgpt.com", "ChatGPT"),
    ("https://gemini.google.com", "Gemini"),
    ("https://github.com", "GitHub"),
    ("https://clawhub.ai", "ClawHub"),
    ("https://console.anthropic.com", "Anthropic"),
]

def open_all():
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    context = browser.contexts[0]
    
    for i, (url, name) in enumerate(SITES):
        if i == 0:
            context.pages[0].goto(url, timeout=20000)
        else:
            page = context.new_page()
            page.goto(url, timeout=20000)
        print(f"✅ {name}: {url}")
        time.sleep(1)
    
    # 回到第1个标签
    context.pages[0].bring_to_front()
    print(f"\n共打开 {len(SITES)} 个站点")
    browser.close()
    p.stop()

if __name__ == "__main__":
    open_all()
