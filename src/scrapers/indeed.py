import logging
from typing import List
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from src.models import JobListingSchema
from src.database import DatabaseManager
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class IndeedScraper(BaseScraper):
    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    async def scrape(
        self, keywords: List[str], locations: List[str], max_jobs: int = 15
    ) -> List[JobListingSchema]:
        results: List[JobListingSchema] = []
        seen_urls = set()

        # Use playwright-stealth v2.x context manager
        async with Stealth().use_async(async_playwright()) as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = await self.create_stealth_context(browser)
            page = await context.new_page()

            for keyword in keywords:
                for location in locations:
                    if len(results) >= max_jobs:
                        break

                    # sc=0kf:jt(internship); filters for Internship job type; fromage=7 filters past 7 days
                    search_url = (
                        f"https://www.indeed.com/jobs?q={quote_plus(keyword)}"
                        f"&l={quote_plus(location)}&sc=0kf%3Ajt(internship)%3B&fromage=7"
                    )
                    logger.info(
                        f"[Indeed] Navigating to search: '{keyword}' in '{location}'"
                    )

                    try:
                        await page.goto(
                            search_url, wait_until="domcontentloaded", timeout=30000
                        )
                        await self.human_delay(3.5, 6.0)

                        html = await page.content()
                        soup = BeautifulSoup(html, "html.parser")
                        job_cards = soup.select("div.job_seen_beacon")

                        if not job_cards:
                            logger.warning(
                                "[Indeed] No job cards found (possible anti-bot challenge or empty query)."
                            )
                            continue

                        logger.info(
                            f"[Indeed] Found {len(job_cards)} cards for '{keyword}'"
                        )

                        for card in job_cards:
                            if len(results) >= max_jobs:
                                break

                            link_el = card.select_one("h2.jobTitle a[data-jk], a.jcs-JobTitle")
                            if not link_el:
                                continue

                            job_key = link_el.get("data-jk")
                            if job_key:
                                apply_url = f"https://www.indeed.com/viewjob?jk={job_key}"
                            else:
                                href = link_el.get("href", "")
                                apply_url = (
                                    f"https://www.indeed.com{href}"
                                    if href.startswith("/")
                                    else href
                                )

                            if (
                                not apply_url
                                or apply_url in seen_urls
                                or self.db.is_url_processed(apply_url)
                            ):
                                continue
                            seen_urls.add(apply_url)

                            title_el = card.select_one("h2.jobTitle span[title], h2.jobTitle")
                            company_el = card.select_one(
                                "[data-testid='company-name'], span.companyName"
                            )
                            loc_el = card.select_one(
                                "[data-testid='text-location'], div.companyLocation"
                            )

                            title = (
                                title_el.get_text(strip=True) if title_el else keyword
                            )
                            company = (
                                company_el.get_text(strip=True)
                                if company_el
                                else "Unknown Company"
                            )
                            job_loc = (
                                loc_el.get_text(strip=True) if loc_el else location
                            )

                            # Navigate to the job detail view to get the full description
                            try:
                                await page.goto(
                                    apply_url,
                                    wait_until="domcontentloaded",
                                    timeout=25000,
                                )
                                await self.human_delay(2.5, 5.0)
                                desc_el = await page.query_selector(
                                    "#jobDescriptionText"
                                )
                                if not desc_el:
                                    continue
                                description = (await desc_el.inner_text()).strip()
                                if len(description) < 40:
                                    continue

                                listing = JobListingSchema(
                                    title=title,
                                    company=company,
                                    location=job_loc,
                                    description=description,
                                    apply_url=apply_url,
                                    source_platform="Indeed",
                                )
                                results.append(listing)
                                logger.info(
                                    f"[Indeed] Extracted: {listing.title} @ {listing.company}"
                                )
                            except Exception as detail_err:
                                logger.debug(
                                    f"[Indeed] Could not load job detail {apply_url}: {detail_err}"
                                )

                    except Exception as e:
                        logger.error(f"[Indeed] Error scraping '{keyword}': {e}")

            await browser.close()

        return results