"""Recruitee ATS scraper — 100% free, public API endpoint per company.
Endpoint: https://{slug}.recruitee.com/api/offers/
"""

import httpx
from sources.base import BaseSource
from core.models import Job


class RecruiteeSource(BaseSource):
    name = "recruitee"

    def __init__(self, company: dict):
        self.company_info = company
        self.slug = company.get("ats_slug", "") or company.get("domain", "").split(".")[0]
        self.company_name = company.get("name", self.slug.capitalize())
        self.domain = company.get("domain", "")

    async def fetch(self) -> list[Job]:
        if not self.slug:
            return []

        url = f"https://{self.slug}.recruitee.com/api/offers/"
        jobs = []

        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []

            data = resp.json()
            offers = data.get("offers") or []

            for item in offers:
                title = item.get("title", "")
                job_url = item.get("careers_url") or f"https://{self.slug}.recruitee.com/o/{item.get('slug', '')}"

                city = item.get("city", "")
                country = item.get("country", "")
                is_remote = item.get("remote", False) or item.get("hybrid", False)

                loc_parts = [p for p in [city, country] if p]
                loc_str = ", ".join(loc_parts) if loc_parts else ("Remote" if is_remote else "Office")

                desc = item.get("description", "") or item.get("requirements", "") or title

                job = Job(
                    title=title,
                    company=self.company_name,
                    company_domain=self.domain,
                    location=loc_str,
                    description=desc,
                    url=job_url,
                    source=f"recruitee:{self.slug}",
                    posted_date=item.get("created_at", ""),
                    job_type=item.get("employment_type_code", "Full-time"),
                )
                jobs.append(job)

        return jobs
