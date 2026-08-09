"""SmartRecruiters ATS Multi-Company Adapter.
Endpoint: GET https://api.smartrecruiters.com/v1/companies/{slug}/postings
Loops through target companies with delay and error handling.
"""

import asyncio
import logging
from datetime import datetime
import httpx
from sources.base import BaseSource
from core.models import Job
from config.ats_companies import SMARTRECRUITERS_COMPANIES

logger = logging.getLogger(__name__)


class SmartRecruitersSource(BaseSource):
    name = "smartrecruiters"

    def __init__(self, company_list: list[dict] = None):
        if company_list is None:
            try:
                from core.database import get_companies
                db_comps = get_companies(ats_platform="smartrecruiters", limit=500)
                company_list = [
                    {"name": c["name"], "slug": c["ats_slug"], "domain": c.get("domain", "")}
                    for c in db_comps if c.get("ats_slug")
                ]
            except Exception:
                company_list = []
        self.company_list = company_list or SMARTRECRUITERS_COMPANIES

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

                url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        await asyncio.sleep(0.15)
                        continue

                    data = resp.json()
                    content = data.get("content", []) if isinstance(data, dict) else []

                    for item in content:
                        title = item.get("name", "").strip()
                        if not title:
                            continue

                        location = item.get("location", {})
                        city = location.get("city", "")
                        country = location.get("country", "")
                        remote = location.get("remote", False)
                        
                        loc_parts = []
                        if city: loc_parts.append(city)
                        if country: loc_parts.append(country)
                        
                        loc_str = ", ".join(loc_parts)
                        if remote:
                            loc_str = "Remote" if not loc_str else f"{loc_str} (Remote)"

                        # SmartRecruiters URL fallback if missing
                        job_id = item.get("id", "")
                        job_url = f"https://jobs.smartrecruiters.com/{slug}/{job_id}"

                        job = Job(
                            title=title,
                            company=name,
                            location=loc_str or "Remote",
                            description=title, # Full desc requires a separate GET request in SR, so we use title
                            url=job_url,
                            source=f"smartrecruiters:{slug}",
                            posted_date=item.get("releasedDate", ""),
                            company_domain=domain,
                        )
                        all_jobs.append(job)

                except Exception as e:
                    logger.warning(f"[SmartRecruiters] Error fetching {name} ({slug}): {e}")

                await asyncio.sleep(0.2)

        return all_jobs
