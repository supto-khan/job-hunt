"""Lever ATS Multi-Company Adapter.
Fetches jobs from Lever postings: GET https://api.lever.co/v0/postings/{slug}?mode=json
Loops through target companies with delay, error handling, and tech keyword filtering.
"""

import asyncio
import logging
from datetime import datetime
import httpx
from sources.base import BaseSource
from core.models import Job
from config.ats_companies import LEVER_COMPANIES

logger = logging.getLogger(__name__)

# Keywords for title filtering as per application stack
TITLE_KEYWORDS = ["angular", "laravel", "php", "full-stack", "fullstack", "frontend", "front-end", "backend", "back-end", "developer", "engineer", "software"]


class LeverSource(BaseSource):
    name = "lever"

    def __init__(self, company_list: list[dict] = None):
        if company_list is None:
            try:
                from core.database import get_companies
                db_comps = get_companies(ats_platform="lever", limit=500)
                company_list = [
                    {"name": c["name"], "slug": c["ats_slug"], "domain": c.get("domain", "")}
                    for c in db_comps if c.get("ats_slug")
                ]
            except Exception:
                company_list = []
        self.company_list = company_list or LEVER_COMPANIES

    async def fetch(self) -> list[Job]:
        all_jobs = []
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            for comp in self.company_list:
                slug = comp.get("slug") or comp.get("ats_slug")
                name = comp.get("name", slug)
                domain = comp.get("domain", "")

                if not slug:
                    continue

                url = f"https://api.lever.co/v0/postings/{slug}"
                try:
                    resp = await client.get(url, params={"mode": "json"})
                    if resp.status_code != 200:
                        await asyncio.sleep(0.15)
                        continue

                    data = resp.json()
                    if not isinstance(data, list):
                        await asyncio.sleep(0.15)
                        continue

                    for item in data:
                        title = item.get("text", "").strip()
                        if not title:
                            continue

                        # Parse epoch timestamp
                        posted = ""
                        created_at = item.get("createdAt")
                        if created_at and isinstance(created_at, (int, float)):
                            posted = datetime.utcfromtimestamp(created_at / 1000).isoformat()

                        categories = item.get("categories", {})
                        location = ""
                        if isinstance(categories, dict):
                            location = categories.get("location", "")

                        job = Job(
                            title=title,
                            company=name,
                            location=location or "Remote",
                            description=item.get("descriptionPlain", "") or item.get("description", ""),
                            url=item.get("hostedUrl", ""),
                            source=f"lever:{slug}",
                            posted_date=posted,
                            company_domain=domain,
                        )
                        all_jobs.append(job)

                except Exception as e:
                    logger.warning(f"[Lever] Error fetching {name} ({slug}): {e}")

                # Polite delay between requests (300ms)
                await asyncio.sleep(0.3)

        return all_jobs
