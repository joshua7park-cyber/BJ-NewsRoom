"""Browser regression for BJ newsroom. Execute after Playwright Chromium installation."""
import asyncio
import os
import subprocess
import time
from playwright.async_api import async_playwright

async def verify():
    base=os.environ.get("BJ_TEST_URL","http://127.0.0.1:8765/")
    server = None if os.environ.get("BJ_TEST_URL") else subprocess.Popen(["python", "-m", "http.server", "8765", "--bind", "127.0.0.1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        await asyncio.sleep(1.5)
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, args=["--no-sandbox"])
            page = await browser.new_page(viewport={"width": 1300, "height": 900}, locale="ko-KR")
            errors=[]
            page.on("pageerror", lambda error: errors.append(str(error)))
            await page.goto(base, wait_until="networkidle", timeout=40000)
            await page.wait_for_selector(".story", timeout=20000)
            count=await page.locator(".story").count()
            assert 1 <= count <= 5, f"home page renders {count} articles, expected max 5"
            assert await page.locator("#stories").inner_text() != ""
            assert await page.locator("text=51건").count() == 0
            await page.locator(".story").first.locator("summary").click()
            assert await page.locator(".story").first.evaluate("(e)=>e.open"), "accordion did not open"
            await page.locator("#plus").click()
            assert float(await page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--scale')")) > 1
            await page.locator("#font").select_option("serif")
            assert await page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--font')") != ""
            await page.locator("#search").fill("검색 결과가 없어야 하는 임의의 단어 998877")
            assert await page.locator(".story").count() == 0
            await page.locator("#search").fill("")
            await page.locator("#tabs button").nth(1).click()
            assert await page.locator(".story").count() <= 5
            await page.locator("#tabs button").first.click()
            await page.set_viewport_size({"width":390,"height":844})
            await page.wait_for_timeout(250)
            dims=await page.evaluate("({scroll:document.documentElement.scrollWidth,view:innerWidth})")
            assert dims["scroll"] <= dims["view"]+2, f"mobile horizontal overflow: {dims}"
            assert not errors, f"browser JS errors: {errors}"
            print("BROWSER PASS: 5 story limit, accordion, search, font, A+, tabs, mobile, console errors")
            await browser.close()
    finally:
        if server:
            server.terminate()
            try: server.wait(timeout=4)
            except subprocess.TimeoutExpired: server.kill()

if __name__ == "__main__":
    asyncio.run(verify())
