"""Workable ATS Multi-Company Adapter.
Endpoint: POST https://apply.workable.com/api/v3/accounts/{slug}/jobs
Loops through target companies with delay and error handling.
"""

import asyncio
import logging
import httpx
from sources.base import BaseSource
from core.models import Job
from config.ats_companies import WORKABLE_COMPANIES

logger = logging.getLogger(__name__)


class WorkableSource(BaseSource):
    name = "workable"

    def __init__(self, company_list: list[dict] = None):
        if company_list is None:
            try:
                from core.database import get_companies
                db_comps = get_companies(ats_platform="workable", limit=500)
                company_list = [
                    {"name": c["name"], "slug": c["ats_slug"], "domain": c.get("domain", "")}
                    for c in db_comps if c.get("ats_slug")
                ]
            except Exception:
                company_list = []
        self.company_list = company_list or WORKABLE_COMPANIES

    async def fetch(self) -> list[Job]:
        all_jobs = []
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=headers) as client:
            for comp in self.company_list:
                slug = comp.get("slug") or comp.get("ats_slug")
                name = comp.get("name", slug)
                domain = comp.get("domain", "")

                if not slug:
                    continue

                url = f"https://apply.workable.com/api/v1/widget/accounts/{slug}"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        await asyncio.sleep(0.15)
                        continue

                    data = resp.json()
                    results = data.get("jobs", []) if isinstance(data, dict) else []

                    for item in results:
                        title = item.get("title", "").strip()
                        if not title:
                            continue

                        job_url = item.get("url", "")

                        location_parts = []
                        if item.get("location"):
                            loc = item["location"]
                            city = loc.get("city", "")
                            country = loc.get("country", "")
                            if city:
                                location_parts.append(city)
                            if country:
                                location_parts.append(country)

                        is_remote = item.get("workplace", "") == "remote" or item.get("telecommute", False)
                        loc_str = ", ".join(location_parts) if location_parts else ("Remote" if is_remote else "Office")

                        job = Job(
                            title=title,
                            company=name,
                            location=loc_str,
                            description=item.get("description", "") or title,
                            url=job_url,
                            source=f"workable:{slug}",
                            posted_date=item.get("published", ""),
                            company_domain=domain,
                        )
                        all_jobs.append(job)

                except Exception as e:
                    logger.warning(f"[Workable] Error fetching {name} ({slug}): {e}")

                await asyncio.sleep(0.2)

        return all_jobs
