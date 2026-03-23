#!/usr/bin/env python3
"""
Gemini 协作代理 - 用大模型帮小龙虾定位问题
用法: python3 agent.py <问题描述>
"""

import sys
import os
import time

SYSTEM_PROMPT = """你是小龙虾（一个AI助手）的技术顾问和debug伙伴。

当小龙虾向你描述一个问题时，你要：
1. 分析问题的本质（是什么、不是什么）
2. 把问题拆解成具体的子问题
3. 指出可能的原因和解决方向
4. 如果需要工具或代码，给出具体的建议

回答要简洁、直接、技术性强。不要废话。
"""


def get_browser():
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    return p, browser


def find_gemini_page(browser):
    """找Gemini页面"""
    for page in browser.contexts[0].pages:
        if 'gemini.google.com/app' in page.url:
            return page
    return None


def send_to_gemini(question, system_prompt=None, use_new_chat=True):
    """发送问题到Gemini"""
    p, browser = get_browser()
    
    try:
        page = find_gemini_page(browser)
        if not page:
            page = browser.contexts[0].new_page()
            page.goto('https://gemini.google.com/app', timeout=30000)
            page.wait_for_load_state('load', timeout=15000)
            page.wait_for_timeout(3000)
        
        page.bring_to_front()
        
        # 新建对话
        if use_new_chat:
            new_chat = page.get_by_text('发起新对话')
            if new_chat.count() > 0:
                new_chat.first.click()
                page.wait_for_timeout(2000)
        
        # 找输入框
        input_area = page.locator('[contenteditable="true"]').first
        
        # 发送系统提示词（如果需要）
        if system_prompt:
            input_area.click()
            page.wait_for_timeout(500)
            input_area.fill(system_prompt)
            page.wait_for_timeout(300)
            page.keyboard.press('Enter')
            page.wait_for_timeout(3000)
        
        # 发送实际问题
        input_area.fill(question)
        page.wait_for_timeout(300)
        page.keyboard.press('Enter')
        print('已发送，等待回复...')
        
        # 等待回复
        for i in range(20):
            page.wait_for_timeout(2000)
            response = page.evaluate("""
            () => {
                const body = document.body.innerText;
                // Gemini回复的特征：包含 "Gemini 说" 或 "Gemini:"
                const match = body.match(/Gemini[:：][\s\n]([\s\S]{100,})/);
                if (match) {
                    return match[0].substring(0, 2000);
                }
                return null;
            }
            """)
            if response and len(response) > 50:
                return response
            print(f'等待回复 {i+1}...')
        
        return '未收到回复'
    
    finally:
        browser.close()
        p.stop()


def analyze_problem(problem):
    """分析问题的完整流程"""
    print(f'分析问题: {problem[:50]}...')
    response = send_to_gemini(
        f"""我的问题是：{problem}

请分析：
1. 问题的本质
2. 可能的原因  
3. 解决方向
""",
        system_prompt=SYSTEM_PROMPT,
        use_new_chat=True
    )
    return response


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("""
Gemini 协作代理

用法:
  python3 agent.py "我的问题是什么"
  
流程:
1. 新建对话
2. 发送系统提示词（设定角色）
3. 发送问题
4. 获取分析
        """)
        sys.exit(1)
    
    problem = ' '.join(sys.argv[1:])
    print(f'\n{"="*50}')
    print('问题分析')
    print(f'{"="*50}\n')
    
    result = analyze_problem(problem)
    
    print(f'\n{"="*50}')
    print('Gemini 分析结果')
    print(f'{"="*50}\n')
    print(result)
