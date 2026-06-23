"""
Playwright automation for Google ImageFX (labs.google/fx/tools/image-fx).
Runs in non-headless mode by default — Google blocks headless browsers.
Set BROWSER_HEADLESS=true only in environments with a virtual display.
"""
import asyncio
import base64
import os
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext, TimeoutError as PWTimeout
from app.logging_config import get_logger

logger = get_logger(__name__)

FLOW_URL        = os.getenv("GOOGLE_FLOW_URL", "https://labs.google/fx/tools/image-fx")
GOOGLE_EMAIL    = os.getenv("GOOGLE_EMAIL", "")
GOOGLE_PASSWORD = os.getenv("GOOGLE_PASSWORD", "")
DOWNLOAD_DIR    = Path(os.getenv("IMAGE_DOWNLOAD_DIR", "/tmp/persona_images"))
HEADLESS        = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"
AUTH_STATE_FILE = Path("/tmp/persona_auth_state.json")  # saved cookies — no lock conflicts
LOGIN_TIMEOUT      = 120_000
GENERATION_TIMEOUT = 180_000

CHROME_EXECUTABLE = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CHROME_USER_DATA  = str(Path.home() / "Library/Application Support/Google/Chrome")
CHROME_PROFILE    = os.getenv("CHROME_PROFILE", "Default")

DEBUG_DIR = DOWNLOAD_DIR / "debug"

BROWSER_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--disable-infobars",
    "--disable-notifications",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _screenshot(page: Page, name: str) -> None:
    """Save a debug screenshot (never raises)."""
    try:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(DEBUG_DIR / f"{name}.png"), full_page=False)
    except Exception:
        pass


async def _dismiss_overlays(page: Page) -> None:
    # Press Escape first — closes most modals/changelogs
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(600)

    # Dismiss any iframe changelog overlay (What's New popup on ImageFX)
    try:
        # Remove the overlay iframe via JS if it's blocking pointer events
        await page.evaluate("""
            document.querySelectorAll('iframe').forEach(f => {
                if (f.src && f.src.includes('changelog')) f.remove();
            });
            // Also remove any overlay containers that intercept events
            document.querySelectorAll('[class*="eoilMe"], [class*="overlay" i], [class*="modal" i]').forEach(el => {
                if (el.querySelector('iframe')) el.style.pointerEvents = 'none';
            });
        """)
        await page.wait_for_timeout(400)
    except Exception:
        pass

    # Click dismiss/close buttons
    for text in ["Accept all", "Accept", "I agree", "Got it", "Dismiss", "No thanks", "Close"]:
        try:
            btn = page.locator(f'button:has-text("{text}")').first
            if await btn.count() > 0:
                await btn.click()
                await page.wait_for_timeout(800)
                break
        except Exception:
            pass


async def _handle_login(page: Page) -> None:
    """Try automated login; fall back to waiting for manual completion."""
    logger.info("google_login_start", email=GOOGLE_EMAIL)

    try:
        email_input = page.locator('input[type="email"]')
        await email_input.wait_for(timeout=10_000)
        await email_input.fill(GOOGLE_EMAIL)
        await page.locator("#identifierNext, button:has-text('Next')").first.click()
        await page.wait_for_timeout(2500)
    except Exception as e:
        logger.warning("login_email_step_failed", error=str(e))
        await _wait_for_manual_login(page)
        return

    try:
        pwd_input = page.locator('input[type="password"]')
        await pwd_input.wait_for(timeout=12_000)
        await pwd_input.fill(GOOGLE_PASSWORD)
        await page.locator("#passwordNext, button:has-text('Next')").first.click()
        await page.wait_for_timeout(3000)
    except Exception as e:
        logger.warning("login_password_step_failed", error=str(e))
        await _wait_for_manual_login(page)
        return

    # If still on Google accounts (2FA, CAPTCHA, etc.) — wait for human
    if "accounts.google.com" in page.url:
        logger.info("login_needs_manual_completion")
        await _wait_for_manual_login(page)


async def _wait_for_manual_login(page: Page) -> None:
    logger.info("waiting_for_manual_login", timeout_s=LOGIN_TIMEOUT // 1000)
    try:
        await page.wait_for_function(
            "!window.location.href.includes('accounts.google.com')",
            timeout=LOGIN_TIMEOUT,
        )
        logger.info("manual_login_completed")
    except PWTimeout:
        raise RuntimeError("Login timed out. Complete Google sign-in within 2 minutes.")


async def _find_first_visible(page: Page, selectors: list[str], timeout: int = 8_000):
    """Return first locator that is visible within timeout, or None."""
    for sel in selectors:
        locator = page.locator(sel).first
        try:
            await locator.wait_for(state="visible", timeout=timeout)
            return locator
        except (PWTimeout, Exception):
            continue
    return None


async def _download_blob(page: Page, img_src: str, output_path: Path) -> bool:
    """Fetch an image (blob: or https:) via JS and save to disk."""
    try:
        data_url = await page.evaluate("""
            async (src) => {
                const res = await fetch(src);
                const blob = await res.blob();
                return new Promise(resolve => {
                    const reader = new FileReader();
                    reader.onloadend = () => resolve(reader.result);
                    reader.readAsDataURL(blob);
                });
            }
        """, img_src)
        if data_url and "," in data_url:
            output_path.write_bytes(base64.b64decode(data_url.split(",", 1)[1]))
            return True
    except Exception as e:
        logger.warning("blob_download_failed", error=str(e))
    return False


# ── Main entry point ──────────────────────────────────────────────────────────

async def generate_image(prompt: str, output_filename: str) -> str:
    """
    Open Google ImageFX, submit the prompt, download the first generated image.
    Returns the local file path of the saved image.
    """
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DOWNLOAD_DIR / output_filename

    async with async_playwright() as pw:
        # Use the user's Chrome with their profile (already logged in to Google)
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=CHROME_USER_DATA,
            executable_path=CHROME_EXECUTABLE,
            channel="chrome",
            headless=HEADLESS,
            args=BROWSER_ARGS + [f"--profile-directory={CHROME_PROFILE}"],
            viewport={"width": 1280, "height": 900},
            accept_downloads=True,
            ignore_https_errors=True,
        )
        browser = None

        page = await context.new_page()

        # Remove automation fingerprint
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        try:
            # ── 1. Navigate ───────────────────────────────────────────────
            logger.info("navigating_to_imagefx", url=FLOW_URL)
            await page.goto(FLOW_URL, wait_until="domcontentloaded", timeout=40_000)
            await page.wait_for_timeout(3000)
            await _screenshot(page, "01_initial")

            # ── 2. Login if needed ────────────────────────────────────────
            if "accounts.google.com" in page.url or "signin" in page.url.lower():
                await _handle_login(page)
                await page.goto(FLOW_URL, wait_until="domcontentloaded", timeout=40_000)
                await page.wait_for_timeout(3000)
                await _screenshot(page, "02_after_login")

            # ── 3. Dismiss overlays ───────────────────────────────────────
            await _dismiss_overlays(page)
            await _screenshot(page, "03_page_ready")

            # ── 4. Find prompt input ──────────────────────────────────────
            prompt_input = await _find_first_visible(page, [
                'textarea[placeholder*="escribe" i]',
                'textarea[placeholder*="prompt" i]',
                'textarea[placeholder*="image" i]',
                'textarea[aria-label*="prompt" i]',
                'div[contenteditable="true"][aria-label*="prompt" i]',
                'div[contenteditable="true"]',
                'textarea',
            ], timeout=15_000)

            if prompt_input is None:
                await _screenshot(page, "04_no_input")
                raise RuntimeError(
                    f"Could not find prompt input on ImageFX. "
                    f"Current URL: {page.url}. Check debug screenshots in {DEBUG_DIR}"
                )

            # Use JS focus to bypass any remaining overlay interception
            await page.evaluate("(el) => { el.focus(); el.click(); }", await prompt_input.element_handle())
            await page.wait_for_timeout(300)
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.wait_for_timeout(300)
            # Truncate to 480 chars — ImageFX has a prompt length limit
            await prompt_input.type(prompt[:480], delay=15)
            await page.wait_for_timeout(800)
            await _screenshot(page, "05_prompt_typed")

            # ── 5. Click Create / Generate ────────────────────────────────
            create_btn = await _find_first_visible(page, [
                'button:has-text("Create")',
                'button:has-text("Generate")',
                'button[aria-label*="create" i]',
                'button[aria-label*="generate" i]',
                '[data-testid*="create" i]',
                '[data-testid*="generate" i]',
            ], timeout=10_000)

            if create_btn is None:
                await _screenshot(page, "06_no_button")
                raise RuntimeError(
                    f"Could not find Create/Generate button. "
                    f"Check debug screenshots in {DEBUG_DIR}"
                )

            await create_btn.click()
            await page.wait_for_timeout(2000)
            await _screenshot(page, "07_generating")

            # ── 6. Wait for generated images ──────────────────────────────
            img_el = await _find_first_visible(page, [
                'img[src*="aisandbox"]',
                'img[src*="generativelanguage"]',
                'img[src*="imagegeneration"]',
                'img[src*="blob:"]',
                '[data-testid*="generated"] img',
                '[data-testid*="result"] img',
                'div[class*="result" i] img',
                'div[class*="output" i] img',
                'div[class*="generated" i] img',
                'div[class*="imageGrid" i] img',
                'div[class*="image-grid" i] img',
                'div[class*="image_grid" i] img',
            ], timeout=GENERATION_TIMEOUT)

            await page.wait_for_timeout(1500)
            await _screenshot(page, "08_result")

            # ── 7. Save image ─────────────────────────────────────────────
            if img_el:
                img_src = await img_el.get_attribute("src") or ""

                # Try JS fetch first (works for blob: and https:)
                if img_src and await _download_blob(page, img_src, output_path):
                    logger.info("image_saved_via_fetch", path=str(output_path))
                    return str(output_path)

                # Try Playwright download via click on download icon
                try:
                    dl_btn = await _find_first_visible(page, [
                        'button[aria-label*="download" i]',
                        'button:has-text("Download")',
                        '[data-testid*="download" i]',
                    ], timeout=3_000)
                    if dl_btn:
                        async with page.expect_download(timeout=15_000) as dl_info:
                            await dl_btn.click()
                        download = await dl_info.value
                        await download.save_as(str(output_path))
                        logger.info("image_saved_via_download", path=str(output_path))
                        return str(output_path)
                except Exception:
                    pass

                # Screenshot the element as last resort
                await img_el.screenshot(path=str(output_path))
                logger.info("image_saved_via_screenshot", path=str(output_path))
                return str(output_path)

            # No image element found — screenshot the page right portion
            await _screenshot(page, "09_no_image_found")
            await page.screenshot(
                path=str(output_path),
                clip={"x": 600, "y": 0, "width": 680, "height": 900},
            )
            logger.warning("image_captured_as_page_clip", path=str(output_path))
            return str(output_path)

        except Exception as e:
            await _screenshot(page, "error_state")
            logger.error("flow_automation_failed", error=str(e))
            raise
        finally:
            await context.close()
