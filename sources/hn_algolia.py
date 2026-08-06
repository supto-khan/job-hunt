"""Hacker News 'Who is Hiring' source via Algolia HN Search API.
100% free, no API key needed.
API Docs: https://hn.algolia.com/api
"""

import re
import httpx
from sources.base import BaseSource
from core.models import Job


class HackerNewsSource(BaseSource):
    name = "hacker_news"
    HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
    HN_ITEMS_URL = "https://hn.algolia.com/api/v1/search_by_date"

    async def fetch(self) -> list[Job]:
        jobs = []
        async with httpx.AsyncClient(timeout=25) as client:
            # 1. Find the latest "Ask HN: Who is hiring?" thread
            params = {
                "tags": "story,author_whoishiring",
                "query": "Ask HN: Who is hiring?",
                "hitsPerPage": 3,
            }
            resp = await client.get(self.HN_SEARCH_URL, params=params)
            resp.raise_for_status()
            stories = resp.json().get("hits", [])

            if not stories:
                return jobs

            # Get the top latest story ID
            latest_story_id = stories[0].get("objectID")
            if not latest_story_id:
                return jobs

            # 2. Fetch top comment hits for this story
            comment_params = {
                "tags": f"comment,story_{latest_story_id}",
                "hitsPerPage": 150,
            }
            resp_comments = await client.get(self.HN_ITEMS_URL, params=comment_params)
            resp_comments.raise_for_status()
            comments = resp_comments.json().get("hits", [])

        # 3. Parse comments into Job objects
        for item in comments:
            comment_text = item.get("comment_text") or ""
            if not comment_text or len(comment_text) < 50:
                continue

            # Strip HTML tags
            clean_text = re.sub(r"<[^>]+>", " ", comment_text).strip()
            lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
            if not lines:
                continue

            first_line = lines[0]
            # HN first line typically formatted as: "Company | Title | Location | Remote | ..."
            parts = [p.strip() for p in first_line.split("|")]
            company = parts[0] if len(parts) > 0 else "Hacker News Startup"
            title = parts[1] if len(parts) > 1 else first_line[:60]
            location = parts[2] if len(parts) > 2 else "Remote / Flexible"

            if len(company) > 60:
                company = company[:57] + "..."

            # Find URL inside comment if present
            url_match = re.search(r"https?://[^\s<>\"']+", comment_text)
            job_url = url_match.group(0) if url_match else f"https://news.ycombinator.com/item?id={item.get('objectID')}"

            job = Job(
                title=title,
                company=company,
                location=location,
                description=clean_text,
                url=job_url,
                source=self.name,
                posted_date=item.get("created_at", ""),
                job_type="Full-time",
            )
            jobs.append(job)

        return jobs
