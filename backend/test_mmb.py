import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--start-maximized",
                "--disable-http2",
            ],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        try:
            await page.goto("https://www.makemytrip.com", timeout=30000, wait_until="domcontentloaded")
        except Exception as e:
            print("Goto Error:", e)
        
        await asyncio.sleep(5)
        await page.screenshot(path="mmb_test.png")
        print("Screenshot saved to mmb_test.png")
        await browser.close()

asyncio.run(main())
