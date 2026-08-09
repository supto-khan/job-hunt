"""Jobicy API source — 100% free JSON API, no API key required.
Fetches high-quality remote jobs directly via Jobicy v2 REST API.
"""

import httpx
from bs4 import BeautifulSoup
from sources.base import BaseSource
from core.models import Job


class JobicySource(BaseSource):
    name = "jobicy"
    API_URL = "https://jobicy.com/api/v2/remote-jobs?count=50"

    async def fetch(self) -> list[Job]:
        jobs = []
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=headers) as client:
                resp = await client.get(self.API_URL)
                if resp.status_code != 200:
                    return []
                
                data = resp.json()
                items = data.get("jobs", [])
                
                for item in items:
                    title = item.get("jobTitle", "").strip()
                    company = item.get("companyName", "").strip()
                    url = item.get("url", "").strip()
                    raw_desc = item.get("jobDescription", "")
                    location = item.get("jobGeo", "") or "Remote"
                    pub_date = item.get("pubDate", "")
                    job_type = item.get("jobType", ["Full-Time"])
                    if isinstance(job_type, list):
                        job_type = job_type[0] if job_type else "Full-Time"

                    if not title or not url:
                        continue

                    # Clean HTML description
                    clean_desc = ""
                    if raw_desc:
                        if "<" in raw_desc and ">" in raw_desc:
                            clean_desc = BeautifulSoup(raw_desc, "html.parser").get_text(separator=" ").strip()
                        else:
                            clean_desc = raw_desc.strip()

                    job = Job(
                        title=title,
                        company=company or "Remote Company",
                        location=location,
                        description=clean_desc,
                        url=url,
                        source="jobicy",
                        posted_date=pub_date,
                        job_type=str(job_type),
                    )
                    jobs.append(job)
        except Exception:
            pass

        return jobs
