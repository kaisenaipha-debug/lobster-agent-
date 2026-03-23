#!/usr/bin/env python3
"""快速打开新闻标签页"""
from browser_control import BrowserSession
import time

SITES = [
    ('https://techcrunch.com', 'TechCrunch'),
    ('https://www.theverge.com', 'TheVerge'),
    ('https://www.wired.com', 'Wired'),
    ('https://www.bbc.com/news', 'BBC'),
    ('https://apnews.com', 'APNews'),
    ('https://arstechnica.com', 'Ars'),
]

def open_news_tabs():
    b = BrowserSession()
    b.connect()
    print(f'当前标签: {len(b.context.pages)}个')
    
    for url, name in SITES:
        try:
            page = b.context.new_page()
            page.goto(url, wait_until='commit', timeout=12000)
            time.sleep(0.5)
            print(f'✅ {name}')
        except Exception as e:
            print(f'❌ {name}')
    
    print(f'\n最终标签: {len(b.context.pages)}个')
    b.close()

if __name__ == '__main__':
    open_news_tabs()
