"""Workable ATS scraper — 100% free, public JSON endpoint per company.
Endpoint: https://apply.workable.com/api/v3/accounts/{slug}/jobs
"""

import httpx
from sources.base import BaseSource
from core.models import Job


class WorkableSource(BaseSource):
    name = "workable"

    def __init__(self, company: dict):
        self.company_info = company
        self.slug = company.get("ats_slug", "") or company.get("domain", "").split(".")[0]
        self.company_name = company.get("name", self.slug.capitalize())
        self.domain = company.get("domain", "")

    async def fetch(self) -> list[Job]:
        if not self.slug:
            return []

        url = f"https://apply.workable.com/api/v3/accounts/{self.slug}/jobs"
        jobs = []

        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.post(url, json={})
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = data.get("results") or []

            for item in results:
                title = item.get("title", "")
                code = item.get("shortcode") or item.get("code") or ""
                job_url = f"https://apply.workable.com/{self.slug}/j/{code}/" if code else f"https://apply.workable.com/{self.slug}/"

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
                    company=self.company_name,
                    company_domain=self.domain,
                    location=loc_str,
                    description=item.get("description", "") or title,
                    url=job_url,
                    source=f"workable:{self.slug}",
                    posted_date=item.get("published", ""),
                    job_type=item.get("type", "Full-time"),
                )
                jobs.append(job)

        return jobs
