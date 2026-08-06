"""BambooHR ATS scraper — 100% free, public JSON endpoint per company.
Endpoint: https://{slug}.bamboohr.com/careers/list
"""

import httpx
from sources.base import BaseSource
from core.models import Job


class BambooHRSource(BaseSource):
    name = "bamboohr"

    def __init__(self, company: dict):
        self.company_info = company
        self.slug = company.get("ats_slug", "") or company.get("domain", "").split(".")[0]
        self.company_name = company.get("name", self.slug.capitalize())
        self.domain = company.get("domain", "")

    async def fetch(self) -> list[Job]:
        if not self.slug:
            return []

        url = f"https://{self.slug}.bamboohr.com/careers/list"
        jobs = []

        headers = {"Accept": "application/json"}

        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return []

            try:
                data = resp.json()
            except Exception:
                return []

            result_list = data.get("result") or data.get("jobs") or []

            for item in result_list:
                title = item.get("jobTitle") or item.get("title") or ""
                job_id = item.get("id") or ""
                if not title:
                    continue

                job_url = f"https://{self.slug}.bamboohr.com/careers/{job_id}" if job_id else f"https://{self.slug}.bamboohr.com/careers"

                location_info = item.get("location") or {}
                if isinstance(location_info, dict):
                    city = location_info.get("city", "")
                    state = location_info.get("state", "")
                    loc_str = f"{city}, {state}".strip(", ") or "Remote / Flexible"
                else:
                    loc_str = str(location_info) or "Remote / Flexible"

                job = Job(
                    title=title,
                    company=self.company_name,
                    company_domain=self.domain,
                    location=loc_str,
                    description=item.get("department", "") or title,
                    url=job_url,
                    source=f"bamboohr:{self.slug}",
                    posted_date="",
                    job_type=item.get("type", "Full-time"),
                )
                jobs.append(job)

        return jobs
