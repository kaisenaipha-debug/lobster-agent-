#!/usr/bin/env python3
"""
视频下载助手 - 帮你找到视频并提供下载方法
用法: python3 download_video.py <url>
"""

import sys
import os


def analyze_video_page(url):
    """分析视频页面，返回视频信息"""
    from playwright.sync_api import sync_playwright
    
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp('http://localhost:9222')
    page = browser.contexts[0].new_page()
    
    page.goto(url, timeout=30000)
    page.wait_for_load_state('load', timeout=15000)
    page.wait_for_timeout(3000)
    
    # 截图保存
    screenshot_path = f'/tmp/video_page_{os.getpid()}.png'
    page.screenshot(path=screenshot_path)
    print(f"📸 页面截图: {screenshot_path}")
    
    # 提取视频信息
    video_info = page.evaluate("""
        () => {
            const videos = document.querySelectorAll('video');
            const iframes = document.querySelectorAll('iframe');
            
            return {
                videoCount: videos.length,
                videos: Array.from(videos).map(v => ({
                    src: v.src ? (v.src.length > 100 ? v.src.substring(0,100) + '...' : v.src) : '无src',
                    currentSrc: v.currentSrc ? (v.currentSrc.length > 100 ? v.currentSrc.substring(0,100) + '...' : v.currentSrc) : '无currentSrc',
                    duration: v.duration,
                    poster: v.poster
                })),
                iframeCount: iframes.length,
                iframes: Array.from(iframes).map(f => f.src || f.getAttribute('data-src') || '无src').slice(0, 3)
            };
        }
    """)
    
    browser.close()
    p.stop()
    
    return video_info, screenshot_path


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python3 download_video.py <视频页面URL>")
        sys.exit(1)
    
    url = sys.argv[1]
    print(f"分析视频: {url}")
    
    info, screenshot = analyze_video_page(url)
    
    print(f"\n=== 视频分析结果 ===")
    print(f"视频元素数量: {info['videoCount']}")
    print(f"iframe数量: {info['iframeCount']}")
    
    if info['videos']:
        print("\n视频列表:")
        for i, v in enumerate(info['videos']):
            print(f"  [{i+1}] src: {v['src']}")
            print(f"      duration: {v['duration']}秒")
    
    if info['iframes']:
        print("\nIframe列表:")
        for i, src in enumerate(info['iframes']):
            print(f"  [{i+1}] {src}")
    
    print(f"\n✅ 截图已保存，请查看后决定如何下载")
    print(f"📁 {screenshot}")
