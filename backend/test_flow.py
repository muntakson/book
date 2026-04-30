#!/usr/bin/env python3
"""
Playwright test to debug the BookMaker flow.
"""

import asyncio
from playwright.async_api import async_playwright

BASE_URL = "https://book.iotok.org"

async def test_bookmaker_flow():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        # Enable console logging
        page.on("console", lambda msg: print(f"[BROWSER] {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"[BROWSER ERROR] {err}"))

        print("=" * 60)
        print("Step 1: Navigate to BookMaker")
        print("=" * 60)
        await page.goto(BASE_URL)
        await page.wait_for_load_state("networkidle")
        print(f"Page title: {await page.title()}")

        # Take screenshot
        await page.screenshot(path="/tmp/bookmaker_step1.png")
        print("Screenshot saved: /tmp/bookmaker_step1.png")

        # Check if we're on the path input page
        path_input = await page.query_selector('input[type="text"]')
        if path_input:
            print("\nFound path input field")

            print("\n" + "=" * 60)
            print("Step 2: Enter codebase path")
            print("=" * 60)
            await path_input.fill("/var/www/aibook/nanochat")
            await page.screenshot(path="/tmp/bookmaker_step2.png")

            # First click Validate button
            validate_btn = await page.query_selector('button:has-text("Validate")')
            if validate_btn:
                print("Clicking Validate button...")
                await validate_btn.click()

                # Wait for validation to complete
                print("Waiting for validation...")
                await asyncio.sleep(3)
                await page.screenshot(path="/tmp/bookmaker_step2b.png")

            # Find and click the submit button
            submit_btn = await page.query_selector('button[type="submit"]')
            if not submit_btn:
                submit_btn = await page.query_selector('button:has-text("Start")')
            if not submit_btn:
                submit_btn = await page.query_selector('button:has-text("Analyze")')

            if submit_btn:
                # Check if button is enabled
                is_disabled = await submit_btn.get_attribute('disabled')
                print(f"Submit button disabled: {is_disabled}")

                if is_disabled:
                    print("Waiting for button to become enabled...")
                    await page.wait_for_selector('button[type="submit"]:not([disabled])', timeout=10000)

                print("Clicking submit button...")
                await submit_btn.click()
                print("Submitted!")

                # Wait for analysis
                print("\n" + "=" * 60)
                print("Step 3: Waiting for analysis...")
                print("=" * 60)

                # Wait for the prompt editor
                print("Waiting for prompt editor...")
                try:
                    # Wait for either textarea or "Approve & Start" button
                    await page.wait_for_selector('textarea, button:has-text("Approve")', timeout=60000)
                    print("Prompt editor found!")
                except Exception as e:
                    print(f"Timeout waiting for prompt editor: {e}")
                    await page.screenshot(path="/tmp/bookmaker_timeout.png")

                await page.screenshot(path="/tmp/bookmaker_step3_final.png")

                # Check if we have a textarea or approve button (prompt editor)
                textarea = await page.query_selector('textarea')
                approve_btn = await page.query_selector('button:has-text("Approve")')

                if textarea or approve_btn:
                    print("\n" + "=" * 60)
                    print("Step 4: Found prompt editor, approving...")
                    print("=" * 60)

                    # Find approve button (has "Approve & Start" text)
                    approve_btn = await page.query_selector('button:has-text("Approve & Start")')
                    if not approve_btn:
                        approve_btn = await page.query_selector('button:has-text("Approve")')
                    if not approve_btn:
                        approve_btn = await page.query_selector('button:has-text("Start")')

                    if approve_btn:
                        print("Clicking approve button...")
                        await approve_btn.click()
                        print("Approved!")

                        # Wait for execution
                        print("\n" + "=" * 60)
                        print("Step 5: Waiting for execution...")
                        print("=" * 60)

                        for i in range(30):
                            await asyncio.sleep(2)
                            await page.screenshot(path=f"/tmp/bookmaker_step5_{i}.png")

                            content = await page.content()
                            print(f"  Waiting... ({i*2}s) - Page length: {len(content)}")

                            # Check for progress or output
                            if "phase" in content.lower():
                                print("Phase indicator found!")

                            if "error" in content.lower():
                                error_el = await page.query_selector('.error, [class*="error"]')
                                if error_el:
                                    error_text = await error_el.inner_text()
                                    print(f"Error: {error_text}")
                                break

                        await page.screenshot(path="/tmp/bookmaker_step5_final.png")
                    else:
                        print("Could not find approve button")
                        buttons = await page.query_selector_all('button')
                        for btn in buttons:
                            text = await btn.inner_text()
                            print(f"  Button: {text}")
                else:
                    print("No textarea found - may still be analyzing or error occurred")
                    await page.screenshot(path="/tmp/bookmaker_no_textarea.png")
            else:
                print("Could not find submit button")
        else:
            print("Not on path input page")
            await page.screenshot(path="/tmp/bookmaker_unknown.png")

        print("\n" + "=" * 60)
        print("Test completed. Check screenshots in /tmp/")
        print("=" * 60)

        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_bookmaker_flow())
