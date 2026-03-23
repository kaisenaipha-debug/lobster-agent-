#!/usr/bin/env python3
"""
MiniMax API 调用模块
API: https://api.minimaxi.com
Key: ***REDACTED***
"""

import os
import base64
import requests

API_KEY = "***REDACTED***"
API_HOST = "https://api.minimaxi.com"


def understand_image(image_path_or_url, prompt="请描述这张图片的内容，用中文回复"):
    """
    图片理解 - 使用 MiniMax V-01 模型
    支持本地路径或URL
    """
    url = f"{API_HOST}/v1/text/chatcompletion_v2"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 处理图片
    if os.path.exists(image_path_or_url):
        with open(image_path_or_url, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        image_data = f"data:image/jpeg;base64,{img_b64}"
    else:
        image_data = image_path_or_url  # 直接是URL
    
    payload = {
        "model": "MiniMax-Text-01",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_data}},
                {"type": "text", "text": prompt}
            ]
        }],
        "max_tokens": 1000
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content
    except Exception as e:
        return f"错误: {e}"


def web_search(query, max_tokens=1000):
    """
    网络搜索 - 使用 plugins=web_search
    """
    url = f"{API_HOST}/v1/text/chatcompletion_v2"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "MiniMax-Text-01",
        "messages": [{"role": "user", "content": query}],
        "plugins": [{"name": "web_search"}],
        "max_tokens": max_tokens
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content
    except Exception as e:
        return f"错误: {e}"


def chat(prompt, system_prompt=None, max_tokens=500):
    """
    文字对话
    """
    url = f"{API_HOST}/v1/text/chatcompletion_v2"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": "MiniMax-Text-01",
        "messages": messages,
        "max_tokens": max_tokens
    }
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        return result.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        return f"错误: {e}"


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("用法:")
        print("  python3 minimax_api.py image <图片路径> [提示词]")
        print("  python3 minimax_api.py search <关键词>")
        print("  python3 minimax_api.py chat <对话内容>")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "image":
        img_path = sys.argv[2]
        prompt = sys.argv[3] if len(sys.argv) > 3 else "请描述这张图片的内容，用中文回复"
        print("分析图片...")
        result = understand_image(img_path, prompt)
        print(result)
        
    elif cmd == "search":
        query = sys.argv[2]
        print("搜索中...")
        result = web_search(query)
        print(result)
        
    elif cmd == "chat":
        content = sys.argv[2]
        print("对话中...")
        result = chat(content)
        print(result)
    
    else:
        print(f"未知命令: {cmd}")
