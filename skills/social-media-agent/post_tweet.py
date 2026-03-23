#!/usr/bin/env python3
"""
X/Twitter 发帖工具
用法: python3 post_tweet.py "推文内容" [图片路径]
"""

import sys
import os
from datetime import datetime


def post_tweet(content, image_path=None):
    """发推文"""
    from playwright.sync_api import sync_playwright
    
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    
    # 找到X页面或新建
    x_page = None
    for page in browser.contexts[0].pages:
        if 'x.com' in page.url or 'twitter.com' in page.url:
            x_page = page
            break
    
    if not x_page:
        x_page = browser.contexts[0].new_page()
        x_page.goto('https://x.com/home', timeout=30000)
        x_page.wait_for_load_state('load', timeout=15000)
    
    x_page.bring_to_front()
    
    # 点击发帖按钮
    try:
        # X的新帖按钮通常在左侧边栏
        compose_button = x_page.locator('[data-testid="FloatingActionButton"]')
        if compose_button.count() > 0:
            compose_button.click()
            x_page.wait_for_timeout(1000)
            print("已点击发帖按钮")
        else:
            # 尝试找 "Post" 按钮
            post_btn = x_page.locator('a[href="/compose/post"]')
            if post_btn.count() > 0:
                post_btn.click()
                x_page.wait_for_timeout(1000)
                print("已点击发帖入口")
    except Exception as e:
        print(f"点击发帖按钮出错: {e}")
        x_page.screenshot(path='/tmp/x_compose_error.png')
        browser.close()
        p.stop()
        return False
    
    # 填入内容
    try:
        textbox = x_page.locator('[data-testid="tweetTextarea_0"]')
        if textbox.count() > 0:
            textbox.click()
            textbox.fill(content)
            print(f"已填入内容: {content[:50]}...")
        else:
            print("未找到文本框，请手动操作")
            x_page.screenshot(path='/tmp/x_compose_step1.png')
            browser.close()
            p.stop()
            return False
    except Exception as e:
        print(f"填入内容出错: {e}")
        browser.close()
        p.stop()
        return False
    
    # 上传图片（如果有）
    if image_path and os.path.exists(image_path):
        try:
            attach_btn = x_page.locator('[data-testid="addImage"]')
            if attach_btn.count() > 0:
                attach_btn.click()
                x_page.wait_for_timeout(500)
                # 使用文件输入
                file_input = x_page.locator('input[type="file"]')
                if file_input.count() > 0:
                    file_input.set_input_files(image_path)
                    x_page.wait_for_timeout(1000)
                    print(f"已添加图片: {image_path}")
        except Exception as e:
            print(f"添加图片出错: {e}")
    
    # 截图确认
    x_page.screenshot(path='/tmp/x_compose_preview.png')
    print(f"\n✅ 预览截图已保存: /tmp/x_compose_preview.png")
    print("请在浏览器中确认并点击发送")
    
    browser.close()
    p.stop()
    return True


def interact_with_tweet(action, tweet_url_or_selector):
    """
    与推文互动
    action: like | retweet | reply | bookmark
    """
    from playwright.sync_api import sync_playwright
    
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    x_page = browser.contexts[0].pages[0]
    x_page.bring_to_front()
    
    print(f"执行操作: {action}")
    browser.close()
    p.stop()
    return True


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法:")
        print("  发推文: python3 post_tweet.py \"推文内容\" [图片路径]")
        print("  互动:   python3 post_tweet.py like|retweet|reply|bookmark <selector>")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd in ['like', 'retweet', 'reply', 'bookmark']:
        interact_with_tweet(cmd, sys.argv[2] if len(sys.argv) > 2 else '')
    elif cmd == 'post':
        content = sys.argv[2] if len(sys.argv) > 2 else "测试推文"
        image = sys.argv[3] if len(sys.argv) > 3 else None
        post_tweet(content, image)
    else:
        # 直接发推
        post_tweet(cmd, sys.argv[2] if len(sys.argv) > 2 else None)
