import asyncio
import logging
import sys
from typing import List
from src.config import settings
from src.database import DatabaseManager
from src.matcher import SemanticMatcher
from src.notifier import DiscordNotifier
from src.models import JobListingSchema
from src.scrapers.linkedin import LinkedInScraper
from src.scrapers.indeed import IndeedScraper
from src.scrapers.handshake import HandshakeScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("InternshipBot")


async def run_pipeline() -> None:
    logger.info("=== Starting Multi-Platform Internship Scraping & Matching Bot ===")
    logger.info(f"Target Keyphrases: {settings.SEARCH_KEYWORDS}")
    logger.info(f"Target Location: {settings.SEARCH_LOCATIONS}")

    # 1. Initialize core services (No resume.pdf needed!)
    db = DatabaseManager()
    matcher = SemanticMatcher(keywords=settings.SEARCH_KEYWORDS)
    notifier = DiscordNotifier(webhook_url=settings.DISCORD_WEBHOOK_URL)

    # 2. Instantiate platform scrapers
    linkedin_scraper = LinkedInScraper(db=db)
    indeed_scraper = IndeedScraper(db=db)
    handshake_scraper = HandshakeScraper(db=db)

    # 3. Collect new listings across platforms
    all_listings: List[JobListingSchema] = []

    logger.info("--- Phase 1: Scraping LinkedIn Public Feed ---")
    linkedin_jobs = await linkedin_scraper.scrape(
        keywords=settings.SEARCH_KEYWORDS,
        locations=settings.SEARCH_LOCATIONS,
        max_jobs=settings.MAX_JOBS_PER_PLATFORM,
    )
    all_listings.extend(linkedin_jobs)

    logger.info("--- Phase 2: Scraping Indeed Public Feed ---")
    indeed_jobs = await indeed_scraper.scrape(
        keywords=settings.SEARCH_KEYWORDS,
        locations=settings.SEARCH_LOCATIONS,
        max_jobs=settings.MAX_JOBS_PER_PLATFORM,
    )
    all_listings.extend(indeed_jobs)

    logger.info("--- Phase 3: Scraping Authenticated Handshake Feed ---")
    handshake_jobs = await handshake_scraper.scrape(
        keywords=settings.SEARCH_KEYWORDS,
        max_jobs=settings.MAX_JOBS_PER_PLATFORM,
    )
    all_listings.extend(handshake_jobs)

    logger.info(f"Total new, unprocessed jobs discovered: {len(all_listings)}")

    # 4. Evaluate keyword similarity, store in SQLite, and dispatch Discord alerts
    high_matches = 0
    for job in all_listings:
        if db.is_url_processed(job.apply_url):
            continue

        score = matcher.compute_similarity(job.title, job.description)
        job.similarity_score = score

        is_high_match = score >= settings.SIMILARITY_THRESHOLD
        alert_sent = False

        if is_high_match:
            high_matches += 1
            logger.info(
                f"🔥 HIGH MATCH ({score:.1%}): {job.title} @ {job.company} [{job.source_platform}]"
            )
            alert_sent = await notifier.send_job_alert(job, score)
        else:
            logger.info(
                f"Below threshold ({score:.1%}): {job.title} @ {job.company} [{job.source_platform}]"
            )

        db.save_job(job=job, score=score, alerted=alert_sent)

    logger.info(
        f"=== Run Complete: {len(all_listings)} processed, {high_matches} high-match alerts sent to Discord ==="
    )


if __name__ == "__main__":
    try:
        asyncio.run(run_pipeline())
    except KeyboardInterrupt:
        logger.info("Bot execution interrupted by user.")