"""Adzuna Job API Adapter.
Docs: https://developer.adzuna.com/docs/search
Requires ADZUNA_APP_ID and ADZUNA_APP_KEY in .env.
"""

import httpx
import logging
from sources.base import BaseSource
from core.models import Job
from config.settings import ADZUNA_APP_ID, ADZUNA_APP_KEY

logger = logging.getLogger(__name__)


class AdzunaSource(BaseSource):
    name = "adzuna"
    # Adzuna API endpoint for US/Remote software jobs
    BASE_URL = "https://api.adzuna.com/v1/api/jobs/us/search/1"

    async def fetch(self) -> list[Job]:
        if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
            logger.info("AdzunaSource: ADZUNA_APP_ID or ADZUNA_APP_KEY not set, skipping.")
            return []

        jobs = []
        params = {
            "app_id": ADZUNA_APP_ID,
            "app_key": ADZUNA_APP_KEY,
            "results_per_page": 50,
            "what": "developer remote",
            "content-type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(self.BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            for item in data.get("results", []):
                company_obj = item.get("company") or {}
                company_name = company_obj.get("display_name", "") if isinstance(company_obj, dict) else str(company_obj)

                location_obj = item.get("location") or {}
                location_name = location_obj.get("display_name", "Remote") if isinstance(location_obj, dict) else "Remote"

                # Parse salary if available
                sal_min = item.get("salary_min")
                sal_max = item.get("salary_max")
                salary_str = ""
                if sal_min and sal_max:
                    salary_str = f"${int(sal_min):,} - ${int(sal_max):,}"
                elif sal_min:
                    salary_str = f"${int(sal_min):,}+"

                created = item.get("created", "")

                job = Job(
                    title=item.get("title", ""),
                    company=company_name,
                    location=location_name,
                    description=item.get("description", ""),
                    url=item.get("redirect_url") or item.get("url", ""),
                    source=self.name,
                    posted_date=str(created),
                    salary=salary_str,
                    job_type="full-time",
                )
                jobs.append(job)

        except Exception as e:
            logger.error(f"AdzunaSource fetch failed: {e}")

        return jobs
