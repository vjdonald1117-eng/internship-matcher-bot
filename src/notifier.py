import logging
import asyncio
import httpx
from src.models import JobListingSchema

logger = logging.getLogger(__name__)

PLATFORM_COLORS = {
    "Handshake": 0xE6005C,  # Handshake Red/Pink
    "LinkedIn": 0x0A66C2,   # LinkedIn Blue
    "Indeed": 0x2164F3,     # Indeed Blue
}


class DiscordNotifier:
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url.strip()

    async def send_job_alert(self, job: JobListingSchema, score: float) -> bool:
        """Dispatches a formatted Discord Embed for high-similarity job matches."""
        if not self.webhook_url or "YOUR_WEBHOOK" in self.webhook_url:
            logger.warning(
                f"[DRY-RUN ALERT] {job.title} @ {job.company} ({score:.1%}) -> {job.apply_url}"
            )
            return False

        snippet = (
            job.description[:350].strip() + "..."
            if len(job.description) > 350
            else job.description
        )

        payload = {
            "username": "Internship Matcher Bot",
            "embeds": [
                {
                    "title": f"🎯 {job.title} — {job.company}",
                    "url": job.apply_url,
                    "description": f"**Description Snippet:**\n{snippet}",
                    "color": PLATFORM_COLORS.get(job.source_platform, 0x2ECC71),
                    "fields": [
                        {
                            "name": "📍 Location",
                            "value": job.location,
                            "inline": True,
                        },
                        {
                            "name": "🌐 Platform",
                            "value": job.source_platform,
                            "inline": True,
                        },
                        {
                            "name": "🧠 Match Score",
                            "value": f"**{score:.1%}** (`{score:.4f}`)",
                            "inline": True,
                        },
                        {
                            "name": "🔗 Direct Application Link",
                            "value": f"[Click Here to Apply]({job.apply_url})",
                            "inline": False,
                        },
                    ],
                    "footer": {
                        "text": "Semantic Match via sentence-transformers/all-MiniLM-L6-v2"
                    },
                }
            ],
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            for attempt in range(3):
                try:
                    response = await client.post(self.webhook_url, json=payload)
                    if response.status_code in (200, 204):
                        logger.info(
                            f"Discord alert sent for {job.title} @ {job.company} ({score:.1%})"
                        )
                        return True
                    elif response.status_code == 429:
                        retry_after = float(response.json().get("retry_after", 2.0))
                        logger.warning(f"Discord rate limited. Sleeping {retry_after}s...")
                        await asyncio.sleep(retry_after)
                    else:
                        logger.error(
                            f"Discord webhook failed ({response.status_code}): {response.text}"
                        )
                        return False
                except Exception as e:
                    logger.error(f"Error sending Discord alert (attempt {attempt + 1}): {e}")
                    await asyncio.sleep(2.0)
        return False