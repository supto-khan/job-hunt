"""FreeHire Source — public search engine indexing 3.3M+ direct ATS jobs.
API Docs: https://freehire.me/docs/api / https://freehire.me/openapi.yaml
Keyless public API, no credit card or account required.
"""

from typing import List, Optional
import httpx
from sources.base import BaseSource
from core.models import Job
from core.profile import get_active_profile
from config.settings import FREEHIRE_API_KEY, FREEHIRE_ENABLED, FREEHIRE_WORK_MODE


class FreeHireSource(BaseSource):
    name = "freehire"
    BASE_URL = "https://freehire.me/api/v1/jobs/search"
    USER_AGENT = "job-hunter/1.0 (+https://github.com/supto-khan/job-hunt)"

    def __init__(
        self,
        queries: Optional[List[str]] = None,
        work_mode: Optional[str] = None,
        limit_per_query: int = 50,
        posted_within_days: int = 14,
    ):
        self.queries = queries
        self.work_mode = work_mode or FREEHIRE_WORK_MODE
        self.limit_per_query = limit_per_query
        self.posted_within_days = posted_within_days
        self.api_key = FREEHIRE_API_KEY

    async def fetch(self) -> List[Job]:
        if not FREEHIRE_ENABLED:
            return []

        # Determine search queries: either explicit or derived from active candidate profile
        terms = self._resolve_search_terms()
        if not terms:
            return []

        headers = {
            "User-Agent": self.USER_AGENT,
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        seen_urls = set()
        jobs: List[Job] = []

        async with httpx.AsyncClient(timeout=30) as client:
            for term in terms:
                params = {
                    "q": term,
                    "limit": self.limit_per_query,
                    "is_tech": "tech",
                    "posted_within_days": self.posted_within_days,
                }
                if self.work_mode:
                    params["work_mode"] = self.work_mode

                try:
                    resp = await client.get(self.BASE_URL, headers=headers, params=params)
                    if resp.status_code != 200:
                        continue

                    data = resp.json()
                    items = data.get("data", [])
                    for item in items:
                        url = item.get("url", "")
                        if not url or url in seen_urls:
                            continue
                        seen_urls.add(url)

                        job = self._map_job(item)
                        if job:
                            jobs.append(job)
                except Exception:
                    continue

        return jobs

    def _resolve_search_terms(self) -> List[str]:
        """Derive search queries from active profile's default terms."""
        if self.queries:
            return self.queries

        try:
            profile = get_active_profile()
            profile_search = profile.get("search") or {}
            terms = profile_search.get("default_terms") or []
            if terms:
                # Top 4 terms provide high diversity without overwhelming rate limits
                return terms[:4]
        except Exception:
            pass

        return ["software engineer", "backend developer", "python developer"]

    def _map_job(self, item: dict) -> Optional[Job]:
        title = (item.get("title") or "").strip()
        company = (item.get("company") or "").strip()
        if not title or not company:
            return None

        # Location & work mode normalization
        loc = (item.get("location") or "").strip()
        work_mode = item.get("work_mode") or ""
        if work_mode == "remote":
            if loc and "remote" not in loc.lower():
                location = f"Remote ({loc})"
            else:
                location = loc or "Remote"
        else:
            location = loc or "Remote"

        # Skills & Tech stack
        skills = item.get("skills") or []
        tech_stack = ", ".join(skills) if isinstance(skills, list) else ""

        # Enrichment (Salary, Seniority, Description summary)
        enrichment = item.get("enrichment") or {}
        salary = self._format_salary(enrichment)
        experience_level = enrichment.get("seniority") or ""
        job_type = enrichment.get("employment_type") or ("remote" if work_mode == "remote" else "")

        # Description: combine summary if present with truncated excerpt
        desc = item.get("description") or ""
        summary = enrichment.get("summary") or ""
        if summary and summary not in desc:
            desc = f"{summary}\n\n{desc}" if desc else summary

        return Job(
            title=title,
            company=company,
            location=location,
            description=desc,
            url=item.get("url", ""),
            source=self.name,
            posted_date=item.get("posted_at") or "",
            tech_stack=tech_stack,
            experience_level=experience_level,
            salary=salary,
            job_type=job_type,
        )

    @staticmethod
    def _format_salary(enrichment: dict) -> str:
        s_min = enrichment.get("salary_min")
        s_max = enrichment.get("salary_max")
        curr = enrichment.get("salary_currency", "")
        period = enrichment.get("salary_period", "")

        if s_min and s_max:
            return f"{curr} {s_min:,} - {s_max:,} / {period}".strip()
        elif s_min:
            return f"{curr} {s_min:,}+ / {period}".strip()
        return ""
