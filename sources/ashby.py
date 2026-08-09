"""Ashby ATS Multi-Company Adapter.
Fetches jobs from Ashby boards: GET https://api.ashbyhq.com/posting-api/job-board/{slug}
Loops through target companies with delay and error handling.
"""

import asyncio
import logging
import httpx
from sources.base import BaseSource
from core.models import Job
from config.ats_companies import ASHBY_COMPANIES

logger = logging.getLogger(__name__)


class AshbySource(BaseSource):
    name = "ashby"

    def __init__(self, company_list: list[dict] = None):
        if company_list is None:
            try:
                from core.database import get_companies
                db_comps = get_companies(ats_platform="ashby", limit=500)
                company_list = [
                    {"name": c["name"], "slug": c["ats_slug"], "domain": c.get("domain", "")}
                    for c in db_comps if c.get("ats_slug")
                ]
            except Exception:
                company_list = []
        self.company_list = company_list or ASHBY_COMPANIES

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

                url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
                try:
                    resp = await client.get(url, params={"includeCompensation": "true"})
                    if resp.status_code != 200:
                        await asyncio.sleep(0.15)
                        continue

                    data = resp.json()
                    raw_jobs = data.get("jobs", []) if isinstance(data, dict) else []

                    for item in raw_jobs:
                        title = item.get("title", "").strip()
                        if not title:
                            continue

                        location = item.get("location", "")
                        if isinstance(location, dict):
                            location = location.get("name", "")

                        salary = ""
                        comp_info = item.get("compensation")
                        if comp_info and isinstance(comp_info, dict):
                            parts = comp_info.get("summaryComponents", [])
                            if parts:
                                salary = " ".join(str(p) for p in parts)

                        job = Job(
                            title=title,
                            company=name,
                            location=location or "Remote",
                            description=item.get("descriptionHtml", "") or item.get("descriptionPlain", ""),
                            url=item.get("externalLink", "") or item.get("jobUrl", ""),
                            source=f"ashby:{slug}",
                            posted_date=item.get("publishedDate", ""),
                            salary=salary,
                            company_domain=domain,
                        )
                        all_jobs.append(job)

                except Exception as e:
                    logger.warning(f"[Ashby] Error fetching {name} ({slug}): {e}")

                await asyncio.sleep(0.2)

        return all_jobs
