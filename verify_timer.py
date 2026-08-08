from playwright.sync_api import sync_playwright

def run_cuj(page):
    page.goto("file:///app/timer.html?pid=999&proj=Test%20Project")
    page.wait_for_timeout(500)

    # Setup a dialog handler to always accept prompts with "Test Location"
    page.on("dialog", lambda dialog: dialog.accept("Test Location"))

    page.get_by_text("➕ НОВАЯ СМЕНА (ВРУЧНУЮ)").click()
    page.wait_for_timeout(500)

    page.get_by_role("button", name="НАЧАТЬ СМЕНУ").click()
    page.wait_for_timeout(500)

    for _ in range(4):
        page.get_by_role("button", name="ПОДТВЕРДИТЬ").click()
        page.wait_for_timeout(500)

    # Click a timer button to start a timer
    page.locator("#btn_travel").click()
    page.wait_for_timeout(2000)

    page.screenshot(path="/home/jules/verification/screenshots/verification.png")
    page.wait_for_timeout(1000)

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir="/home/jules/verification/videos"
        )
        page = context.new_page()
        try:
            run_cuj(page)
        finally:
            context.close()
            browser.close()
