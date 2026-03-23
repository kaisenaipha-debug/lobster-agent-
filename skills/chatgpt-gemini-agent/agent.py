#!/usr/bin/env python3
"""
ChatGPT/Gemini 操控代理 - 拟人化打字版
"""

import sys
import os
import time
import random
import numpy as np

# ==================== 拟人化打字 ====================

# 相邻键盘映射（模拟按错临键）
ADJACENT_KEYS = {
    'a': 'sq', 'b': 'vn', 'c': 'xv', 'd': 'sf', 'e': 'wr',
    'f': 'dg', 'g': 'fh', 'h': 'gj', 'i': 'uo', 'j': 'hk',
    'k': 'jl', 'l': 'ko', 'm': 'n', 'n': 'bm', 'o': 'ik',
    'p': 'ol', 'q': 'wa', 'r': 'et', 's': 'ad', 't': 'ry',
    'u': 'yi', 'v': 'cb', 'w': 'qe', 'x': 'zc', 'y': 'tu', 'z': 'x',
    '1': '2', '2': '13', '3': '24', '4': '35', '5': '46',
    '6': '57', '7': '68', '8': '79', '9': '80', '0': '9-',
}

# 常用词组（打更快）
COMMON_BIGRAMS = ['th', 'he', 'in', 'er', 'an', 're', 'on', 'ti', 'te', 'es', 'the', 'and', 'you', 'for', 'ing', 'ion']


def get_adjacent_key(char):
    """获取相邻键"""
    return random.choice(ADJACENT_KEYS.get(char.lower(), char))


def human_delay(base_ms=120, variance=50):
    """高斯分布随机延迟"""
    delay = np.random.normal(base_ms, variance)
    return max(40, min(350, delay))


def type_like_human(page, text, textarea):
    """
    拟人化打字：包含随机延迟、按错键、长停顿
    """
    for i, char in enumerate(text):
        # 1.5%概率按错临键
        if char.isalpha() and random.random() < 0.015:
            wrong = get_adjacent_key(char)
            textarea.type(wrong, delay=human_delay())
            time.sleep(0.05)
            textarea.press('Backspace')
            time.sleep(random.uniform(0.1, 0.2))
        
        # 判断是否常用词组
        is_common = text[max(0, i-1):i+1].lower() in COMMON_BIGRAMS
        
        # 计算延迟
        if is_common:
            delay = random.uniform(30, 70)  # 常用词更快
        else:
            delay = human_delay()
        
        textarea.type(char, delay=delay)
        
        # 标点后额外停顿
        if char in '.,!?;:':
            time.sleep(random.uniform(0.3, 0.8))
        
        # 段落/换行后长停顿
        if char == '\n':
            time.sleep(random.uniform(1.0, 2.5))
        
        # 每句话结束稍微停顿
        if char == '.' or char == '!' or char == '?':
            time.sleep(random.uniform(0.2, 0.5))


# ==================== Chrome 连接 ====================

def get_browser():
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    return p, browser


def find_page(browser, url_pattern):
    for page in browser.contexts[0].pages:
        if url_pattern in page.url:
            return page
    return None


def open_ai_page(browser, name='chatgpt'):
    url = 'https://chatgpt.com/' if name == 'chatgpt' else 'https://gemini.google.com/app'
    
    page = find_page(browser, 'chatgpt.com' if name == 'chatgpt' else 'gemini')
    if page:
        page.bring_to_front()
        page.wait_for_timeout(1000)
        return page
    
    page = browser.contexts[0].new_page()
    page.goto(url, timeout=30000)
    page.wait_for_load_state('load', timeout=15000)
    page.wait_for_timeout(3000)
    return page


# ==================== 截图 ====================

def take_screenshot(browser, url=None, path='/tmp/screenshot.png', full_page=False):
    if url:
        page = find_page(browser, url) or browser.contexts[0].new_page()
        if url not in page.url:
            page.goto(url, timeout=30000)
            page.wait_for_load_state('load', timeout=15000)
    else:
        page = browser.contexts[0].pages[0]
    
    page.bring_to_front()
    page.wait_for_timeout(2000)
    page.screenshot(path=path, full_page=full_page)
    return path


# ==================== 图片上传 ====================

def upload_image(page, image_path):
    if not os.path.exists(image_path):
        print(f'文件不存在: {image_path}')
        return False
    
    # 先移除旧图片
    existing = page.locator('button[aria-label="移除文件"]')
    if existing.count() > 0:
        existing.click()
        page.wait_for_timeout(500)
    
    # 上传新图片
    file_inputs = page.locator('input[type="file"]')
    for i in range(file_inputs.count()):
        accept = file_inputs.nth(i).get_attribute('accept') or ''
        if 'image' in accept or accept == '':
            file_inputs.nth(i).set_input_files(image_path)
            page.wait_for_timeout(1500)
            return True
    
    return False


# ==================== 发送消息 ====================

def send_message(page, message, use_human_type=True):
    """发送消息（可选拟人化打字）"""
    textarea = page.locator('textarea[name="prompt-textarea"]')
    
    # 让textarea可见
    page.evaluate("""
    () => {
        const tas = document.querySelectorAll('textarea');
        tas.forEach(ta => {
            ta.style.cssText = 'display:block !important; visibility:visible !important; opacity:1 !important';
        });
    }
    """)
    page.wait_for_timeout(500)
    
    textarea.first.click()
    page.wait_for_timeout(500)
    
    if use_human_type:
        type_like_human(page, message, textarea.first)
    else:
        textarea.first.fill(message)
    
    page.wait_for_timeout(500)
    
    # 点击发送按钮
    send_btn = page.locator('button[aria-label="发送提示"]')
    if send_btn.count() > 0:
        send_btn.click()
        print('已点击发送')
    else:
        page.keyboard.press('Enter')
    
    return True


def wait_for_response(page, timeout=20):
    """等待ChatGPT回复"""
    print('等待回复...')
    page.wait_for_timeout(timeout)
    
    response = page.evaluate("""
    () => {
        const msgs = document.querySelectorAll('[data-message-author-role="assistant"]');
        const last = msgs[msgs.length - 1];
        return last ? last.innerText : null;
    }
    """)
    
    return response if response else '未收到回复'


# ==================== 核心操作 ====================

def analyze_image(image_path, prompt=None):
    """分析图片"""
    if prompt is None:
        prompt = '请描述这张图片的内容，用中文回复'
    
    p, browser = get_browser()
    try:
        page = open_ai_page(browser, 'chatgpt')
        page.wait_for_timeout(2000)
        
        if not upload_image(page, image_path):
            return None
        
        send_message(page, prompt)
        return wait_for_response(page)
        
    finally:
        browser.close()
        p.stop()


def generate_image(prompt, save_path='/tmp/generated.png'):
    """生成图片"""
    p, browser = get_browser()
    try:
        page = open_ai_page(browser, 'chatgpt')
        page.wait_for_timeout(2000)
        
        # 点➕ → 创建图片
        page.locator('button[aria-label="添加文件等"]').click()
        page.wait_for_timeout(1000)
        
        page.get_by_text('创建图片').click()
        page.wait_for_timeout(2000)
        
        # 拟人化输入
        page.evaluate("""
        () => {
            document.querySelectorAll('textarea').forEach(ta => {
                ta.style.cssText = 'display:block !important; visibility:visible !important; opacity:1 !important';
            });
        }
        """)
        page.wait_for_timeout(500)
        
        type_like_human(page, prompt, page.locator('textarea').first)
        page.wait_for_timeout(1000)
        
        # 等发送按钮出现
        for _ in range(20):
            page.wait_for_timeout(1000)
            if page.locator('button[aria-label="发送提示"]').count() > 0:
                page.locator('button[aria-label="发送提示"]').click()
                break
        
        # 等待生成
        for _ in range(15):
            page.wait_for_timeout(2000)
            img_found = page.evaluate("""
            () => {
                return Array.from(document.querySelectorAll('img'))
                    .some(img => img.src && img.src.startsWith('http') && !img.src.includes('data:'));
            }
            """)
            if img_found:
                break
        
        return '图片生成完成'
        
    finally:
        browser.close()
        p.stop()


if __name__ == '__main__':
    print("""
ChatGPT/Gemini 操控代理

用法:
  python3 agent.py analyze <图片路径> [提示词]
  python3 agent.py generate <描述>
  python3 agent.py screenshot [URL] [保存路径]
    """)
