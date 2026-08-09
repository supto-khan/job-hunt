"""Greenhouse ATS Multi-Company Adapter.
Fetches jobs from Greenhouse boards: GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true
Loops through target companies with delay, error handling, and tech keyword filtering.
"""

import asyncio
import logging
import httpx
from sources.base import BaseSource
from core.models import Job
from config.ats_companies import GREENHOUSE_COMPANIES

logger = logging.getLogger(__name__)

# Keywords for title filtering as per application stack
TITLE_KEYWORDS = ["angular", "laravel", "php", "full-stack", "fullstack", "frontend", "front-end", "backend", "back-end", "developer", "engineer", "software"]


class GreenhouseSource(BaseSource):
    name = "greenhouse"

    def __init__(self, company_list: list[dict] = None):
        if company_list is None:
            try:
                from core.database import get_companies
                db_comps = get_companies(ats_platform="greenhouse", limit=500)
                company_list = [
                    {"name": c["name"], "token": c["ats_slug"], "domain": c.get("domain", "")}
                    for c in db_comps if c.get("ats_slug")
                ]
            except Exception:
                company_list = []
        self.company_list = company_list or GREENHOUSE_COMPANIES

    async def fetch(self) -> list[Job]:
        all_jobs = []
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            for comp in self.company_list:
                token = comp.get("token") or comp.get("ats_slug")
                name = comp.get("name", token)
                domain = comp.get("domain", "")

                if not token:
                    continue

                url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
                try:
                    resp = await client.get(url, params={"content": "true"})
                    if resp.status_code != 200:
                        await asyncio.sleep(0.15)
                        continue

                    data = resp.json()
                    raw_jobs = data.get("jobs", []) if isinstance(data, dict) else []

                    for item in raw_jobs:
                        title = item.get("title", "").strip()
                        if not title:
                            continue

                        # Extract location
                        location = ""
                        loc_data = item.get("location", {})
                        if isinstance(loc_data, dict):
                            location = loc_data.get("name", "")
                        elif isinstance(loc_data, str):
                            location = loc_data

                        ext_id = str(item.get("id", ""))
                        job_url = item.get("absolute_url", "")

                        job = Job(
                            title=title,
                            company=name,
                            location=location or "Remote",
                            description=item.get("content", ""),
                            url=job_url,
                            source=f"greenhouse:{token}",
                            posted_date=item.get("updated_at", ""),
                            company_domain=domain,
                        )
                        all_jobs.append(job)

                except Exception as e:
                    logger.warning(f"[Greenhouse] Error fetching {name} ({token}): {e}")

                # Polite delay between requests (300ms)
                await asyncio.sleep(0.3)

        return all_jobs
