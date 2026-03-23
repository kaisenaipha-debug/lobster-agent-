#!/usr/bin/env python3
"""
ChatGPT/Gemini 操控代理 - 核心动作模块
用法: python3 agent.py <action> [params]
"""

import sys
import os
import time
import base64

# ==================== Chrome 连接 ====================

def get_browser():
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    return p, browser


def find_page(browser, url_pattern):
    """在已打开的页面中找匹配的标签页"""
    for page in browser.contexts[0].pages:
        if url_pattern in page.url:
            return page
    return None


def open_ai_page(browser, name='chatgpt'):
    """打开 ChatGPT 或 Gemini 页面"""
    url = 'https://chatgpt.com/' if name == 'chatgpt' else 'https://gemini.google.com/app'
    
    # 先查找已打开的页面
    page = find_page(browser, 'chatgpt.com' if name == 'chatgpt' else 'gemini')
    if page:
        page.bring_to_front()
        page.wait_for_timeout(1000)
        return page
    
    # 新建标签页
    page = browser.contexts[0].new_page()
    page.goto(url, timeout=30000)
    page.wait_for_load_state('load', timeout=15000)
    page.wait_for_timeout(3000)
    return page


# ==================== 截图 ====================

def take_screenshot(browser, url=None, path='/tmp/screenshot.png', full_page=False):
    """截取页面截图"""
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
    print(f'📸 截图已保存: {path}')
    return path


# ==================== 图片上传 ====================

def upload_image(page, image_path):
    """上传图片到ChatGPT（带防封检查）"""
    if not os.path.exists(image_path):
        print(f'❌ 文件不存在: {image_path}')
        return False
    
    # 先检查是否已上传过相同图片（防封措施）
    existing_files = page.locator('[aria-label="移除文件"]')
    if existing_files.count() > 0:
        # 已有图片，先移除
        remove_btn = page.locator('button[aria-label="移除文件"]')
        if remove_btn.count() > 0:
            remove_btn.click()
            page.wait_for_timeout(500)
            print('已移除旧图片')
    
    file_inputs = page.locator('input[type="file"]')
    uploaded = False
    
    for i in range(file_inputs.count()):
        accept = file_inputs.nth(i).get_attribute('accept') or ''
        # 优先使用接受图片的input
        if 'image' in accept or accept == '':
            try:
                file_inputs.nth(i).set_input_files(image_path)
                uploaded = True
                print(f'✅ 图片已上传')
                break
            except Exception as e:
                print(f'尝试第{i}个input失败: {e}')
    
    page.wait_for_timeout(1500)
    return uploaded


# ==================== 发送消息 ====================

def send_message(page, message):
    """发送消息到ChatGPT"""
    # 使用JS方式填充textarea（避免点击问题）
    script = f"""
() => {{
    const ta = document.querySelector('textarea[name="prompt-textarea"]');
    if (ta) {{
        ta.value = {repr(message)};
        ta.dispatchEvent(new Event('input', {{bubbles: true}}));
        return 'success';
    }}
    return 'not_found';
}}
"""
    result = page.evaluate(script)
    if result == 'not_found':
        print('⚠️ 未找到输入框')
        return False
    
    page.wait_for_timeout(500)
    
    # 点击右下角的「发送提示」按钮（不是话筒！）
    # ❌ 禁止点击 button[aria-label="听写按钮"] 或 button[aria-label="启动语音功能"]
    try:
        send_btn = page.locator('button[aria-label="发送提示"]')
        if send_btn.count() > 0:
            send_btn.click()
            print('✅ 点击「发送提示」按钮')
        else:
            # 备选：回车发送（但不要在有图片时用回车）
            page.keyboard.press('Enter')
            print('✅ 回车发送（备选）')
    except:
        page.keyboard.press('Enter')
        print('✅ 回车发送（异常备选）')
    
    return True


def wait_for_response(page, timeout=15):
    """等待ChatGPT回复"""
    print('⏳ 等待ChatGPT回复...')
    time.sleep(timeout)
    
    response = page.evaluate("""
    () => {
        const msgs = document.querySelectorAll('[data-message-author-role="assistant"]');
        const last = msgs[msgs.length - 1];
        return last ? last.innerText : null;
    }
    """)
    
    if response:
        print(f'✅ 获取到回复 ({len(response)} 字符)')
    return response


# ==================== 核心操作 ====================

def analyze_image(image_path, prompt=None):
    """分析图片 - 截图 + 上传 + 分析"""
    if prompt is None:
        prompt = '请描述这张图片的内容，用中文回复'
    
    p, browser = get_browser()
    try:
        # 打开ChatGPT
        page = open_ai_page(browser, 'chatgpt')
        page.wait_for_timeout(2000)
        
        # 上传图片
        if not upload_image(page, image_path):
            return None
        
        # 发送分析请求
        if not send_message(page, prompt):
            return None
        
        # 等待回复
        response = wait_for_response(page, timeout=12)
        
        return response
        
    finally:
        browser.close()
        p.stop()


def generate_image(prompt, style=None, save_path='/tmp/generated_image.png'):
    """生成图片 - 使用ChatGPT的创建功能"""
    if style:
        full_prompt = f"{prompt}, {style} style"
    else:
        full_prompt = prompt
    
    p, browser = get_browser()
    try:
        page = open_ai_page(browser, 'chatgpt')
        page.wait_for_timeout(2000)
        
        # 点➕号
        plus_btn = page.locator('button[aria-label="添加文件等"]')
        plus_btn.click()
        page.wait_for_timeout(1000)
        
        # 点击"创建图片"
        create_btn = page.get_by_text('创建图片')
        create_btn.click()
        page.wait_for_timeout(2000)
        
        # 让textarea可见
        page.evaluate("""
        () => {
            document.querySelectorAll('textarea').forEach(ta => {
                ta.style.cssText = 'display:block !important; visibility:visible !important; opacity:1 !important;';
            });
        }
        """)
        page.wait_for_timeout(500)
        
        # 输入提示词（模拟人打字速度）
        import time
        textarea = page.locator('textarea').first
        for char in full_prompt:
            textarea.type(char, delay=80 + (hash(char) % 40))
            time.sleep(0.05)
        page.wait_for_timeout(500)
        
        # 按Enter发送（创建图片模式不需要点发送按钮）
        page.keyboard.press('Enter')
        print(f'已发送提示词: {full_prompt[:50]}...')
        
        # 等待图片生成（轮询）
        for i in range(15):
            page.wait_for_timeout(2000)
            img_found = page.evaluate("""
            () => {
                const imgs = Array.from(document.querySelectorAll('img'));
                return imgs.some(img => img.src && img.src.startsWith('http') && !img.src.includes('data:'));
            }
            """)
            if img_found:
                print(f'图片已生成！')
                break
        
        # 下载图片
        import subprocess, os
        img_url = page.evaluate("""
        () => {
            const imgs = Array.from(document.querySelectorAll('img'));
            const found = imgs.find(img => img.src && img.src.startsWith('http') && !img.src.includes('data:'));
            return found ? found.src : null;
        }
        """)
        
        if img_url:
            result = subprocess.run(['curl', '-L', '-o', save_path, img_url], capture_output=True, timeout=30)
            if result.returncode == 0 and os.path.exists(save_path):
                size = os.path.getsize(save_path)
                print(f'✅ 图片已保存: {save_path} ({size//1024}KB)')
                return save_path
        
        return None
        
    finally:
        browser.close()
        p.stop()


def deep_research(topic):
    """深度研究"""
    p, browser = get_browser()
    try:
        page = open_ai_page(browser, 'chatgpt')
        page.wait_for_timeout(2000)
        
        prompt = f"""请对「{topic}」进行深度研究，包括：
1. 背景和现状
2. 主要参与者和立场
3. 最新进展
4. 未来趋势

请给出详细的研究报告。"""
        
        send_message(page, prompt)
        response = wait_for_response(page, timeout=20)
        
        return response
        
    finally:
        browser.close()
        p.stop()


def web_search(query):
    """网页搜索 - 通过ChatGPT"""
    p, browser = get_browser()
    try:
        page = open_ai_page(browser, 'chatgpt')
        page.wait_for_timeout(2000)
        
        prompt = f"请搜索「{query}」的最新信息，给我总结关键内容"
        
        send_message(page, prompt)
        response = wait_for_response(page, timeout=12)
        
        return response
        
    finally:
        browser.close()
        p.stop()


# ==================== 主入口 ====================

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("""
ChatGPT/Gemini 操控代理

用法:
  python3 agent.py analyze <图片路径> [提示词]
  python3 agent.py generate <描述> [风格]
  python3 agent.py research <主题>
  python3 agent.py search <关键词>
  python3 agent.py screenshot [URL] [保存路径]
  python3 agent.py open [chatgpt|gemini]
        """)
        sys.exit(1)
    
    cmd = sys.argv[1]
    result = None
    
    if cmd == 'analyze':
        image_path = sys.argv[2] if len(sys.argv) > 2 else '/tmp/screenshot.png'
        prompt = sys.argv[3] if len(sys.argv) > 3 else None
        result = analyze_image(image_path, prompt)
        
    elif cmd == 'generate':
        prompt_text = sys.argv[2] if len(sys.argv) > 2 else '一只赛博朋克风格的猫'
        style = sys.argv[3] if len(sys.argv) > 3 else None
        result = generate_image(prompt_text, style)
        
    elif cmd == 'research':
        topic = sys.argv[2] if len(sys.argv) > 2 else '人工智能最新进展'
        result = deep_research(topic)
        
    elif cmd == 'search':
        keyword = sys.argv[2] if len(sys.argv) > 2 else '今日科技新闻'
        result = web_search(keyword)
        
    elif cmd == 'screenshot':
        url = sys.argv[2] if len(sys.argv) > 2 else None
        path = sys.argv[3] if len(sys.argv) > 3 else '/tmp/screenshot.png'
        p, browser = get_browser()
        try:
            result = take_screenshot(browser, url, path)
        finally:
            browser.close()
            p.stop()
        sys.exit(0)
        
    elif cmd == 'open':
        name = sys.argv[2] if len(sys.argv) > 2 else 'chatgpt'
        p, browser = get_browser()
        try:
            page = open_ai_page(browser, name)
            print(f'✅ 已打开/切换到 {name}')
        finally:
            browser.close()
            p.stop()
        sys.exit(0)
    
    if result:
        print('\n' + '='*50)
        print('分析结果:')
        print('='*50)
        print(result)
    else:
        print('❌ 操作失败')
