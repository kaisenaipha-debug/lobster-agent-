#!/usr/bin/env python3
"""
社交媒体浏览器控制 + 内容总结
用法: python3 social_browser.py <url> [关键词]
"""

import sys
import os
import base64
import json

def get_chrome_page(url=None):
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    if url:
        # 尝试在已有页面中找
        target_page = None
        for page in browser.contexts[0].pages:
            if url in page.url:
                target_page = page
                break
        if not target_page:
            target_page = browser.contexts[0].new_page()
            target_page.goto(url, timeout=30000)
            target_page.wait_for_load_state('load', timeout=15000)
        target_page.bring_to_front()
        return p, browser, target_page
    return p, browser, browser.contexts[0].pages[0]


def take_screenshot(page, path, full_page=True):
    page.wait_for_timeout(2000)
    page.screenshot(path=path, full_page=full_page)
    print(f"📸 截图已保存: {path}")


def scroll_and_load(page, scrolls=3):
    """滚动加载更多内容"""
    for i in range(scrolls):
        page.evaluate('window.scrollBy(0, 800)')
        page.wait_for_timeout(1500)
        print(f"滚动第 {i+1} 次...")


def extract_page_content(page, max_length=8000):
    """提取页面文字内容"""
    content = page.evaluate("""
        () => {
            // 移除script和style
            const clone = document.body.cloneNode(true);
            clone.querySelectorAll('script,style,nav,footer,header,[role="navigation"],[role="banner"],[role="contentinfo"]').forEach(el => el.remove());
            
            // 获取主要文本内容
            const text = clone.innerText || clone.textContent || '';
            return text.replace(/\\s+/g, ' ').trim().substring(0, 8000);
        }
    """)
    return content


def search_and_screenshot(query, platform='x'):
    """搜索并截图"""
    p, browser, page = get_chrome_page()
    
    if platform == 'x':
        search_url = f"https://x.com/search?q={query}&src=typed_query&f=top"
        page.goto(search_url, timeout=30000)
        page.wait_for_load_state('load', timeout=15000)
        scroll_and_load(page, scrolls=2)
        screenshot_path = f'/tmp/search_{platform}_{hash(query)}.png'
        take_screenshot(page, screenshot_path)
    
    browser.close()
    p.stop()
    return screenshot_path


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python3 social_browser.py <url> [action]")
        print("action: screenshot | scroll | content | all")
        sys.exit(1)
    
    url = sys.argv[1]
    action = sys.argv[2] if len(sys.argv) > 2 else 'screenshot'
    
    p, browser, page = get_chrome_page(url)
    
    if action == 'screenshot':
        path = '/tmp/page_screenshot.png'
        take_screenshot(page, path)
        print(path)
    elif action == 'scroll':
        scroll_and_load(page)
        path = '/tmp/page_scrolled.png'
        take_screenshot(page, path)
        print(path)
    elif action == 'content':
        content = extract_page_content(page)
        print(content[:3000])
    elif action == 'all':
        scroll_and_load(page, scrolls=3)
        path = '/tmp/page_full.png'
        take_screenshot(page, path)
        content = extract_page_content(page)
        print(f"\n=== 页面内容摘要 ===\n{content[:5000]}")
        print(f"\n截图: {path}")
    
    browser.close()
    p.stop()
