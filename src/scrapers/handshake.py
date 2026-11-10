import logging
from typing import List
from urllib.parse import quote_plus
from playwright.async_api import async_playwright, BrowserContext
from src.config import settings
from src.models import JobListingSchema
from src.database import DatabaseManager
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class HandshakeScraper(BaseScraper):
    def __init__(self, db: DatabaseManager) -> None:
        self.db = db
        self.base_url = settings.HANDSHAKE_BASE_URL.rstrip("/")
        self.state_path = settings.HANDSHAKE_STATE_PATH

    async def _ensure_authenticated(self, p) -> BrowserContext:
        """
        Verifies if saved Handshake session cookies are valid.
        If missing or expired, launches a headed browser window for manual SSO + Duo MFA login.
        """
        if self.state_path.exists():
            logger.info("Found saved Handshake session state. Verifying session validity...")
            browser = await p.chromium.launch(headless=True)
            context = await self.create_stealth_context(browser, self.state_path)
            page = await context.new_page()
            await self.apply_page_stealth(page)

            try:
                await page.goto(
                    f"{self.base_url}/stu/postings",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
                await self.human_delay(2.5, 4.0)
                if "login" not in page.url.lower() and "sso" not in page.url.lower():
                    logger.info("Handshake session is valid!")
                    await page.close()
                    return context
                logger.warning("Saved Handshake session expired. Re-authentication required.")
            except Exception as e:
                logger.warning(f"Error checking Handshake session: {e}")
            await browser.close()

        # Launch visible browser for manual University SSO + Duo authentication
        logger.info(
            "Launching headed Chromium window for Handshake login. "
            "Please complete your University SSO and Duo 2FA in the browser window..."
        )
        browser = await p.chromium.launch(headless=False)
        context = await self.create_stealth_context(browser)
        page = await context.new_page()
        await page.goto(f"{self.base_url}/login")

        logger.info("Waiting up to 3 minutes for you to reach the Handshake student dashboard...")
        # Wait until redirected to student postings/dashboard or feed
        await page.wait_for_url(
            lambda url: ("/stu/" in url or "/explore" in url or "/postings" in url)
            and "login" not in url.lower(),
            timeout=180_000,
        )
        await self.human_delay(2.0, 3.0)
        await context.storage_state(path=str(self.state_path))
        logger.info(f"Saved authenticated Handshake cookies to {self.state_path}")
        await page.close()
        return context

    async def scrape(self, keywords: List[str], max_jobs: int = 15) -> List[JobListingSchema]:
        results: List[JobListingSchema] = []
        seen_urls = set()

        async with async_playwright() as p:
            try:
                context = await self._ensure_authenticated(p)
            except Exception as e:
                logger.error(f"Handshake authentication failed or timed out: {e}")
                return results

            page = await context.new_page()
            await self.apply_page_stealth(page)

            for keyword in keywords:
                if len(results) >= max_jobs:
                    break

                encoded_kw = quote_plus(keyword)
                # jobType=3 filters for Internships in Handshake
                search_url = (
                    f"{self.base_url}/stu/postings?page=1&per_page=25"
                    f"&sort_direction=desc&sort_column=default"
                    f"&job.job_types%5B%5D=3&query={encoded_kw}"
                )
                logger.info(f"[Handshake] Searching '{keyword}' -> {search_url}")

                try:
                    await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                    await self.human_delay(3.5, 6.0)

                    # Extract posting links matching /stu/postings/{id} or /postings/{id}
                    links = await page.eval_on_selector_all(
                        "a[href*='/postings/']",
                        "elements => elements.map(el => el.href)",
                    )
                    unique_links = list(dict.fromkeys(links))
                    logger.info(
                        f"[Handshake] Found {len(unique_links)} candidate links for '{keyword}'"
                    )

                    for raw_url in unique_links:
                        if len(results) >= max_jobs:
                            break
                        clean_url = raw_url.split("?")[0]
                        if clean_url in seen_urls or self.db.is_url_processed(clean_url):
                            continue
                        seen_urls.add(clean_url)

                        try:
                            await page.goto(
                                clean_url, wait_until="domcontentloaded", timeout=25000
                            )
                            await self.human_delay(2.5, 4.5)

                            title_el = await page.query_selector("h1")
                            title = (
                                (await title_el.inner_text()).strip()
                                if title_el
                                else keyword
                            )

                            company_el = await page.query_selector(
                                "a[href*='/employers/'], [data-hook='employer-name']"
                            )
                            company = (
                                (await company_el.inner_text()).strip()
                                if company_el
                                else "Handshake Employer"
                            )

                            main_el = await page.query_selector("main, [role='main'], body")
                            description = (
                                (await main_el.inner_text()).strip() if main_el else ""
                            )

                            if len(description) < 40:
                                continue

                            listing = JobListingSchema(
                                title=title,
                                company=company,
                                location="United States / See Posting",
                                description=description,
                                apply_url=clean_url,
                                source_platform="Handshake",
                            )
                            results.append(listing)
                            logger.info(
                                f"[Handshake] Extracted: {listing.title} @ {listing.company}"
                            )
                        except Exception as item_err:
                            logger.debug(
                                f"[Handshake] Failed parsing listing {clean_url}: {item_err}"
                            )
                except Exception as search_err:
                    logger.error(
                        f"[Handshake] Search failed for keyword '{keyword}': {search_err}"
                    )

            if context.browser:
                await context.browser.close()

        return results