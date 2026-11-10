import logging
from typing import List
from urllib.parse import quote_plus
import httpx
from bs4 import BeautifulSoup
from src.models import JobListingSchema
from src.database import DatabaseManager
from src.scrapers.base import BaseScraper, DEFAULT_USER_AGENT

logger = logging.getLogger(__name__)


class LinkedInScraper(BaseScraper):
    """
    Scrapes LinkedIn public internship feeds via LinkedIn's unauthenticated Guest API
    with randomized delays to avoid IP blocks and auth walls.
    """

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db
        self.headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    async def scrape(
        self, keywords: List[str], locations: List[str], max_jobs: int = 15
    ) -> List[JobListingSchema]:
        results: List[JobListingSchema] = []
        seen_urls = set()

        async with httpx.AsyncClient(
            headers=self.headers, follow_redirects=True, timeout=20.0
        ) as client:
            for keyword in keywords:
                for location in locations:
                    if len(results) >= max_jobs:
                        break

                    # f_E=1 filters for Internship experience level; f_TPR=r86400 filters past 24h (or r604800 for past week)
                    search_url = (
                        "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                        f"?keywords={quote_plus(keyword)}"
                        f"&location={quote_plus(location)}"
                        "&f_E=1&f_TPR=r604800&start=0"
                    )
                    logger.info(
                        f"[LinkedIn] Querying Guest API for '{keyword}' in '{location}'..."
                    )

                    try:
                        resp = await client.get(search_url)
                        if resp.status_code != 200:
                            logger.warning(
                                f"[LinkedIn] Search returned HTTP {resp.status_code}"
                            )
                            await self.human_delay(4.0, 7.0)
                            continue

                        soup = BeautifulSoup(resp.text, "html.parser")
                        cards = soup.find_all("li")
                        logger.info(
                            f"[LinkedIn] Retrieved {len(cards)} job cards for '{keyword}'"
                        )

                        for card in cards:
                            if len(results) >= max_jobs:
                                break

                            link_tag = card.find("a", class_="base-card__full-link")
                            if not link_tag or not link_tag.get("href"):
                                continue

                            apply_url = link_tag["href"].split("?")[0].strip()
                            if (
                                apply_url in seen_urls
                                or self.db.is_url_processed(apply_url)
                            ):
                                continue
                            seen_urls.add(apply_url)

                            title_tag = card.find(
                                "h3", class_="base-search-card__title"
                            )
                            company_tag = card.find(
                                "h4", class_="base-search-card__subtitle"
                            )
                            loc_tag = card.find(
                                "span", class_="job-search-card__location"
                            )

                            title = (
                                title_tag.get_text(strip=True)
                                if title_tag
                                else keyword
                            )
                            company = (
                                company_tag.get_text(strip=True)
                                if company_tag
                                else "Unknown Company"
                            )
                            job_loc = (
                                loc_tag.get_text(strip=True) if loc_tag else location
                            )

                            # Extract numeric job ID from the card data-entity-urn or URL
                            urn_div = card.find("div", attrs={"data-entity-urn": True})
                            job_id = None
                            if urn_div:
                                urn = urn_div["data-entity-urn"]
                                job_id = urn.split(":")[-1]
                            elif "-" in apply_url:
                                job_id = apply_url.split("-")[-1].rstrip("/")

                            if not job_id or not job_id.isdigit():
                                continue

                            await self.human_delay(2.0, 4.5)
                            detail_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
                            detail_resp = await client.get(detail_url)
                            if detail_resp.status_code != 200:
                                continue

                            detail_soup = BeautifulSoup(
                                detail_resp.text, "html.parser"
                            )
                            desc_div = detail_soup.find(
                                "div", class_="show-more-less-html__markup"
                            ) or detail_soup.find("div", class_="description__text")

                            if not desc_div:
                                continue

                            description = desc_div.get_text(separator="\n", strip=True)
                            if len(description) < 40:
                                continue

                            listing = JobListingSchema(
                                title=title,
                                company=company,
                                location=job_loc,
                                description=description,
                                apply_url=apply_url,
                                source_platform="LinkedIn",
                            )
                            results.append(listing)
                            logger.info(
                                f"[LinkedIn] Extracted: {listing.title} @ {listing.company}"
                            )
                    except Exception as e:
                        logger.error(f"[LinkedIn] Error during guest scrape: {e}")

                    await self.human_delay(3.0, 6.0)

        return results