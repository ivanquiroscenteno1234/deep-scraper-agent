"""
Test script to debug Playwright + LangChain integration issues.
Run this directly: python test_playwright.py
"""
import os
import sys
import asyncio
import traceback

# Fix for Windows asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from dotenv import load_dotenv
load_dotenv()

print("=" * 50)
print("Testing Playwright + LangChain Integration")
print("=" * 50)

# Test 1: Check if Playwright works standalone
print("\n[Test 1] Testing Playwright standalone...")
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://example.com")
        print(f"  ✅ Playwright works! Page title: {page.title()}")
        browser.close()
except Exception as e:
    print(f"  ❌ Playwright failed: {e}")
    traceback.print_exc()

# Test 2: Check if LangChain's sync browser works
print("\n[Test 2] Testing LangChain's create_sync_playwright_browser...")
try:
    from langchain_community.tools.playwright.utils import create_sync_playwright_browser
    browser = create_sync_playwright_browser(headless=True)
    print(f"  ✅ LangChain sync browser created: {browser}")
    browser.close()
except Exception as e:
    print(f"  ❌ LangChain sync browser failed: {e}")
    traceback.print_exc()

# Test 3: Check if PlayWrightBrowserToolkit works
print("\n[Test 3] Testing PlayWrightBrowserToolkit...")
try:
    from langchain_community.agent_toolkits import PlayWrightBrowserToolkit
    from langchain_community.tools.playwright.utils import create_sync_playwright_browser
    
    browser = create_sync_playwright_browser(headless=True)
    toolkit = PlayWrightBrowserToolkit.from_browser(sync_browser=browser)
    tools = toolkit.get_tools()
    print(f"  ✅ Toolkit created with {len(tools)} tools: {[t.name for t in tools]}")
    browser.close()
except Exception as e:
    print(f"  ❌ Toolkit failed: {e}")
    traceback.print_exc()

# Test 4: Check Gemini API
print("\n[Test 4] Testing Gemini API connection...")
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    
    api_key = os.getenv("GOOGLE_API_KEY")
    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro-latest")
    
    if not api_key:
        print("  ⚠️ GOOGLE_API_KEY not set!")
    else:
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=0,
            google_api_key=api_key
        )
        response = llm.invoke("Say hello in one word")
        print(f"  ✅ Gemini API works! Response: {response.content}")
except Exception as e:
    print(f"  ❌ Gemini API failed: {e}")
    traceback.print_exc()

print("\n" + "=" * 50)
print("Testing complete!")
print("=" * 50)
