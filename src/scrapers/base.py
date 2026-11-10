import asyncio
import logging
import random
from pathlib import Path
from typing import Optional
from playwright.async_api import Browser, BrowserContext, Page

logger = logging.getLogger(__name__)

# Modern User-Agent for Chromium stealth contexts
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = { runtime: {} };
"""


class BaseScraper:
    """Base scraper class handling human-like jitter and stealth browser contexts."""

    @staticmethod
    async def human_delay(min_sec: float = 2.0, max_sec: float = 5.0) -> None:
        """Randomized non-uniform delay to prevent behavioral rate-limit detection."""
        delay = random.uniform(min_sec, max_sec)
        await asyncio.sleep(delay)

    @staticmethod
    async def create_stealth_context(
        browser: Browser, storage_state: Optional[Path] = None
    ) -> BrowserContext:
        """Creates an isolated BrowserContext with anti-bot patches applied."""
        context_kwargs = {
            "user_agent": DEFAULT_USER_AGENT,
            "viewport": {"width": 1920, "height": 1080},
            "locale": "en-US",
            "timezone_id": "America/New_York",
        }
        if storage_state and storage_state.exists():
            context_kwargs["storage_state"] = str(storage_state)

        context = await browser.new_context(**context_kwargs)
        await context.add_init_script(STEALTH_INIT_SCRIPT)
        return context

    @staticmethod
    async def apply_page_stealth(page: Page) -> None:
        """Applies playwright-stealth patches to an active page (supports v2.x and v1.x)."""
        try:
            from playwright_stealth import Stealth
            stealth = Stealth()
            if hasattr(stealth, "apply_stealth_async"):
                await stealth.apply_stealth_async(page)
        except ImportError:
            try:
                from playwright_stealth import stealth_async
                await stealth_async(page)
            except Exception as e:
                logger.debug(f"Fallback init script used instead of playwright_stealth: {e}")