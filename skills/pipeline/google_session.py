#!/usr/bin/env python3
"""
google_session.py - Google 账号一次登录永久复用
"""

import asyncio
import json
import sys
from pathlib import Path

SESSION_FILE = Path.home() / ".qclaw" / "google_session.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/122.0.0.0 Safari/537.36")


async def login_and_save():
    from playwright.async_api import async_playwright
    print("\n" + "=" * 50)
    print("Globe open browser, please complete Google login")
    print("=" * 50)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--no-sandbox"])
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
            user_agent=UA,
        )
        page = await context.new_page()
        await page.goto("https://accounts.google.com")
        print("Browser opened Google login page")
        print("After login, type 'done' and press Enter")
        print("-" * 40)

        while True:
            user_input = input(">>> ").strip()
            if user_input in ("done", "ok", "OK", "complete"):
                break
            print("Type 'done' after completing login")

        storage = await context.storage_state()
        SESSION_FILE.parent.mkdir(exist_ok=True)
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(storage, f, ensure_ascii=False, indent=2)

        await browser.close()

    size = SESSION_FILE.stat().st_size
    print(f"\nDone! Session saved to {SESSION_FILE} ({size} bytes)\n")


async def google_search(query, num=10):
    from playwright.async_api import async_playwright

    if not SESSION_FILE.exists():
        print("No session file found. Run: python3 google_session.py login")
        return []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            storage_state=str(SESSION_FILE),
            viewport={"width": 1280, "height": 800},
            locale="zh-CN",
            user_agent=UA,
        )
        page = await context.new_page()

        url = "https://www.google.com/search?q=" + query + "&hl=zh-CN&num=" + str(num)
        try:
            await page.goto(url, wait_until="load", timeout=25000)
            await asyncio.sleep(3)
        except Exception as e:
            print("Page load warning: " + str(e))

        results = []
        seen_urls = set()
        links = await page.query_selector_all("a[href]")

        for link in links:
            href = await link.get_attribute("href") or ""
            text = (await link.inner_text()).strip()

            skip_patterns = ["/search?", "maps.google", "accounts.google",
                              "support.google", "policies.google", "youtube.com/results"]
            if (href and len(text) > 15
                    and "google.com" not in href
                    and href not in seen_urls
                    and not any(s in href for s in skip_patterns)):
                seen_urls.add(href)
                results.append({"title": text[:120], "url": href[:200], "summary": ""})
                if len(results) >= num:
                    break

        await browser.close()
        return results


async def check_session():
    if not SESSION_FILE.exists():
        return False
    results = await google_search("test", num=1)
    return len(results) > 0


async def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "login":
        await login_and_save()

    elif cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: python3 google_session.py search KEYWORDS")
            return
        query = " ".join(sys.argv[2:])
        print("Search: " + query)
        results = await google_search(query)
        if not results:
            print("No results or session expired. Run: python3 google_session.py login")
            return
        print("\nResults: " + str(len(results)) + "\n")
        for i, r in enumerate(results, 1):
            print("[" + str(i) + "] " + r["title"])
            print("    " + r["url"][:80])
            print()
        out_path = "/tmp/google_search_results.json"
        with open(out_path, "w") as f:
            json.dump({"query": query, "results": results}, f, ensure_ascii=False, indent=2)
        print("Saved to " + out_path)

    elif cmd == "check":
        valid = await check_session()
        if valid:
            print("Session valid")
        else:
            print("Session expired. Run: python3 google_session.py login")

    elif cmd == "help":
        print("Commands:")
        print("  python3 google_session.py login             - login first time")
        print("  python3 google_session.py search KEYWORDS   - search")
        print("  python3 google_session.py check             - check session")

    else:
        print("Unknown command: " + cmd)


if __name__ == "__main__":
    asyncio.run(main())
