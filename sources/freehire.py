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
    BASE_URL = "https://freehire.me/api/v1/agent/jobs/search"
    USER_AGENT = "job-hunter/1.0 (+https://github.com/supto-khan/job-hunt)"

    def __init__(
        self,
        queries: Optional[List[str]] = None,
        work_mode: Optional[str] = None,
        limit_per_query: int = 100,
        posted_within_days: Optional[int] = 30,
        pages_per_query: int = 2,
    ):
        self.queries = queries
        self.work_mode = work_mode or FREEHIRE_WORK_MODE
        self.limit_per_query = min(max(1, limit_per_query), 100)
        self.posted_within_days = posted_within_days
        self.pages_per_query = max(1, pages_per_query)
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

        applied_sigs = {"ids": set(), "urls": set(), "pairs": set()}
        try:
            from core.database import get_applied_job_signatures
            applied_sigs = get_applied_job_signatures()
        except Exception:
            pass

        async with httpx.AsyncClient(timeout=30) as client:
            for term in terms:
                for page in range(self.pages_per_query):
                    offset = page * self.limit_per_query
                    params = {
                        "q": term,
                        "limit": self.limit_per_query,
                        "offset": offset,
                        "is_tech": "tech",
                        "source_type_exclude": "aggregator",
                    }
                    if self.posted_within_days and self.posted_within_days > 0:
                        params["posted_within_days"] = self.posted_within_days
                    if self.work_mode:
                        params["work_mode"] = self.work_mode

                    try:
                        resp = await client.get(self.BASE_URL, headers=headers, params=params)
                        if resp.status_code != 200:
                            break

                        data = resp.json()
                        items = data.get("data", [])
                        if not items:
                            break

                        for item in items:
                            url = item.get("url", "")
                            if not url or url in seen_urls:
                                continue
                            clean_url = url.strip().lower()
                            # Exclude spam aggregator whatjobs.com
                            if "whatjobs.com" in clean_url or "whatjobs" in clean_url:
                                continue

                            comp = (item.get("company") or "").strip().lower()
                            if "whatjobs" in comp:
                                continue

                            base_u = clean_url.split("?")[0].rstrip("/")
                            if clean_url in applied_sigs["urls"] or (base_u and base_u in applied_sigs["urls"]):
                                continue

                            tit = (item.get("title") or "").strip().lower()
                            if (comp, tit) in applied_sigs["pairs"]:
                                continue

                            seen_urls.add(url)

                            job = self._map_job(item)
                            if job:
                                jobs.append(job)

                        # If fewer items returned than the limit, we've reached the last page
                        if len(items) < self.limit_per_query:
                            break
                    except Exception:
                        break

        return jobs

    def _resolve_search_terms(self) -> List[str]:
        """Derive high-yield search queries from active profile (core tech + key role titles)."""
        if self.queries:
            return self.queries

        try:
            profile = get_active_profile()
            scoring = profile.get("scoring") or {}
            search = profile.get("search") or {}

            raw_core = scoring.get("core_tech") or []
            default_terms = search.get("default_terms") or []

            # Prioritize clean, high-signal single/double-word core technologies
            # (e.g. 'angular', 'react', 'typescript', 'laravel', 'vue')
            skip_generic = {"git", "rest", "api", "html", "css", "sql", "json", "npm", "yarn"}
            high_signal_tech = [
                t.strip().lower()
                for t in raw_core
                if len(t.strip()) >= 3 and t.strip().lower() not in skip_generic
            ]

            terms = []
            seen = set()

            # 1. Add top primary tech keywords (most powerful on FreeHire)
            for t in high_signal_tech[:3]:
                if t not in seen:
                    seen.add(t)
                    terms.append(t)

            # 2. Add top profile default terms (e.g. 'senior angular developer', 'frontend engineer')
            for dt in default_terms:
                c = dt.strip().lower()
                if c and c not in seen:
                    seen.add(c)
                    terms.append(dt)
                if len(terms) >= 6:
                    break

            if terms:
                return terms
        except Exception:
            pass

        return ["angular", "frontend", "full stack", "react", "typescript"]

    def _map_job(self, item: dict) -> Optional[Job]:
        title = (item.get("title") or "").strip()
        company = (item.get("company") or "").strip()
        url = (item.get("url") or "").strip()
        if not title or not company:
            return None

        # Exclude whatjobs.com
        if "whatjobs.com" in url.lower() or "whatjobs" in url.lower() or "whatjobs" in company.lower():
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
