#!/usr/bin/env python3
"""
ChatGPT 图像生成 — Python 封装
通过 Playwright CDP 连接已登录 Chrome，完成 DALL-E 图片生成

用法：
    python3 chatgpt_image_gen.py "a cute lobster wearing a tiny hat"
"""

import sys
import os
import time
import random
import urllib.request
from datetime import datetime

def get_chrome_page():
    """连接已运行的 Chrome 并返回 ChatGPT 标签页"""
    from playwright.sync_api import sync_playwright
    
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    
    # 找到 ChatGPT 标签页
    for page in browser.contexts[0].pages:
        if 'chatgpt' in page.url.lower():
            return p, browser, page
    
    # 没有则打开新标签
    page = browser.contexts[0].pages[0]
    page.goto('https://chatgpt.com')
    page.wait_for_load_state('networkidle')
    return p, browser, page

def human_delay(min_ms=1000, max_ms=3000):
    """拟人化随机延迟"""
    delay = random.randint(min_ms, max_ms) / 1000
    time.sleep(delay)

def create_image(prompt: str, output_dir: str = None) -> str:
    """
    在 ChatGPT 中生成图片
    
    Args:
        prompt: 英文提示词
        output_dir: 保存目录，默认 ~/.qclaw/workspace/downloads/
    
    Returns:
        保存后的文件路径
    """
    if output_dir is None:
        output_dir = os.path.expanduser('~/.qclaw/workspace/downloads/')
    os.makedirs(output_dir, exist_ok=True)
    
    p, browser, page = get_chrome_page()
    
    try:
        # Step 1: 点击➕按钮
        plus_button = page.locator('button[aria-label*="Create"]').first
        if not plus_button.is_visible():
            plus_button = page.locator('button[aria-label*="Plus"]').first
        plus_button.click()
        human_delay(500, 1500)
        
        # Step 2: 选择"创建图片"
        create_image_option = page.locator('text=Create image').first
        create_image_option.click()
        human_delay(500, 1500)
        
        # Step 3: 输入提示词
        textarea = page.locator('textarea').last
        textarea.fill(prompt)
        human_delay(300, 800)
        
        # Step 4: 按 Enter 提交
        textarea.press('Enter')
        
        # Step 5: 等待图片生成（轮询，最长60秒）
        start = time.time()
        img_url = None
        while time.time() - start < 60:
            try:
                img_el = page.locator('img[src*="dalle"]').first
                if img_el.is_visible():
                    img_url = img_el.get_attribute('src')
                    break
            except:
                pass
            time.sleep(2)
        
        if not img_url:
            raise TimeoutError("图片生成超时")
        
        # Step 6: 下载
        filename = f'dalle_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
        output_path = os.path.join(output_dir, filename)
        urllib.request.urlretrieve(img_url, output_path)
        
        return output_path
    
    finally:
        p.stop()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python3 chatgpt_image_gen.py <prompt>")
        sys.exit(1)
    
    prompt = sys.argv[1]
    print(f"🎨 生成中: {prompt}")
    path = create_image(prompt)
    print(f"✅ 已保存: {path}")
